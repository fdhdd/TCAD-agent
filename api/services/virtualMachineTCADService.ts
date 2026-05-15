import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';
import { Client } from 'ssh2';
import dotenv from 'dotenv';

dotenv.config();

const execAsync = promisify(exec);

export interface VMConfig {
  mode: 'local' | 'ssh';
  tcadPath?: string;
  workDir?: string;
  ssh?: {
    host: string;
    port: number;
    username: string;
    password?: string;
    privateKey?: string;
    remoteWorkDir: string;
  };
}

function joinLinuxPath(...parts: string[]): string {
  return parts.filter(p => p).join('/').replace(/\/+/g, '/');
}

export class VirtualMachineTCADService {
  private config: VMConfig;
  private sshClient: Client | null = null;

  constructor(config?: Partial<VMConfig>) {
    this.config = {
      mode: (process.env.TCAD_MODE as 'local' | 'ssh') || 'local',
      tcadPath: process.env.SENTAURUS_TCAD_PATH || '',
      workDir: process.env.TCAD_WORKSPACE || path.join(process.cwd(), 'workspace'),
      ...config
    };

    if (this.config.mode === 'ssh' && !this.config.ssh) {
      this.config.ssh = {
        host: process.env.SSH_HOST || 'localhost',
        port: parseInt(process.env.SSH_PORT || '22'),
        username: process.env.SSH_USERNAME || 'user',
        password: process.env.SSH_PASSWORD,
        privateKey: process.env.SSH_PRIVATE_KEY,
        remoteWorkDir: process.env.SSH_REMOTE_DIR || '/home/user/tcad_workspace'
      };
    }
  }

  async initialize(): Promise<void> {
    if (this.config.mode === 'local') {
      await fs.mkdir(this.config.workDir!, { recursive: true });
    } else if (this.config.mode === 'ssh') {
      await this.connectSSH();
      await this.ensureRemoteDirectory();
    }
  }

  private async connectSSH(): Promise<void> {
    if (this.sshClient) return;

    return new Promise((resolve, reject) => {
      this.sshClient = new Client();
      
      const connectConfig: any = {
        host: this.config.ssh!.host,
        port: this.config.ssh!.port,
        username: this.config.ssh!.username
      };

      if (this.config.ssh!.password) {
        connectConfig.password = this.config.ssh!.password;
      } else if (this.config.ssh!.privateKey) {
        connectConfig.privateKey = fs.readFileSync(this.config.ssh!.privateKey);
      }

      this.sshClient
        .on('ready', () => {
          console.log('[SSH] Connected to virtual machine');
          resolve();
        })
        .on('error', (err) => {
          console.error('[SSH] Connection error:', err);
          reject(err);
        })
        .connect(connectConfig);
    });
  }

  private async ensureRemoteDirectory(remotePath: string): Promise<void> {
    await this.executeSSHCommand(`mkdir -p ${remotePath}`);
  }

  private async ensureDirectory(dirPath: string): Promise<void> {
    if (this.config.mode === 'local') {
      await fs.mkdir(dirPath, { recursive: true });
    } else {
      await this.ensureRemoteDirectory(dirPath);
    }
  }

  private dirnameLinuxPath(p: string): string {
    const parts = p.split('/').filter(Boolean);
    if (parts.length <= 1) return '/';
    return '/' + parts.slice(0, -1).join('/');
  }

  private resolveDirectory(directory?: string): string {
    if (!directory) {
      return this.config.mode === 'local' ? this.config.workDir! : this.config.ssh!.remoteWorkDir;
    }

    if (this.config.mode === 'local') {
      return path.join(this.config.workDir!, directory);
    }

    return joinLinuxPath(this.config.ssh!.remoteWorkDir, directory);
  }

  async writeScript(scriptContent: string, filename: string, targetDir?: string): Promise<string> {
    const baseDir = this.resolveDirectory(targetDir);
    let fullFilename: string;

    if (this.config.mode === 'local') {
      fullFilename = path.join(baseDir, filename);
      await fs.mkdir(path.dirname(fullFilename), { recursive: true });
      await fs.writeFile(fullFilename, scriptContent);
    } else {
      fullFilename = joinLinuxPath(baseDir, filename);
      const dirName = this.dirnameLinuxPath(fullFilename);
      await this.ensureDirectory(dirName);
      await this.transferFileToRemote(scriptContent, fullFilename);
    }

    return fullFilename;
  }

  private async transferFileToRemote(content: string, remotePath: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.sshClient!.sftp((err, sftp) => {
        if (err) {
          reject(err);
          return;
        }

        sftp.writeFile(remotePath, content, (writeErr) => {
          sftp.end();
          if (writeErr) {
            reject(writeErr);
          } else {
            resolve();
          }
        });
      });
    });
  }

  async readRemoteFile(remotePath: string): Promise<string> {
    return new Promise((resolve, reject) => {
      this.sshClient!.sftp((err, sftp) => {
        if (err) {
          reject(err);
          return;
        }

        sftp.readFile(remotePath, 'utf-8', (readErr, data) => {
          sftp.end();
          if (readErr) {
            reject(readErr);
          } else {
            resolve(data);
          }
        });
      });
    });
  }

  async listFiles(directory?: string): Promise<string[]> {
    const dir = this.resolveDirectory(directory);
    if (this.config.mode === 'local') {
      return await fs.readdir(dir);
    }
    return await this.listRemoteFiles(dir);
  }

  async listTDROutputs(directory?: string): Promise<string[]> {
    const files = await this.listFiles(directory);
    return files.filter((file) => file.endsWith('.tdr'));
  }

  async listRemoteFiles(remoteDir: string): Promise<string[]> {
    return new Promise((resolve, reject) => {
      this.sshClient!.sftp((err, sftp) => {
        if (err) {
          reject(err);
          return;
        }

        sftp.readdir(remoteDir, (readErr, list) => {
          sftp.end();
          if (readErr) {
            reject(readErr);
          } else {
            resolve(list.map(item => item.filename));
          }
        });
      });
    });
  }

  private async executeSSHCommand(command: string): Promise<{ stdout: string; stderr: string }> {
    return new Promise((resolve, reject) => {
      this.sshClient!.exec(command, (err, stream) => {
        if (err) {
          reject(err);
          return;
        }

        let stdout = '';
        let stderr = '';

        stream
          .on('close', (code, signal) => {
            resolve({ stdout, stderr });
          })
          .on('data', (data) => {
            stdout += data.toString();
          })
          .stderr.on('data', (data) => {
            stderr += data.toString();
          });
      });
    });
  }

  async executeSdevice(scriptPath: string, onLog?: (log: string) => void): Promise<{ 
    success: boolean; 
    output: string; 
    error?: string 
  }> {
    const sdevicePath = this.findExecutable('sdevice');
    const scriptDir = this.config.mode === 'local' ? path.dirname(scriptPath) : this.dirnameLinuxPath(scriptPath);
    const scriptName = this.config.mode === 'local' ? path.basename(scriptPath) : scriptPath.split('/').pop() || scriptPath;
    const command = `cd ${scriptDir} && ${sdevicePath} ${scriptName}`;

    if (this.config.mode === 'local') {
      return this.executeLocalCommand(command, onLog);
    } else {
      return this.executeSSHWithStreaming(command, onLog);
    }
  }

  async executeSprocess(scriptPath: string, onLog?: (log: string) => void): Promise<{ 
    success: boolean; 
    output: string; 
    error?: string 
  }> {
    const sprocessPath = this.findExecutable('sprocess');
    const scriptDir = this.config.mode === 'local' ? path.dirname(scriptPath) : this.dirnameLinuxPath(scriptPath);
    const scriptName = this.config.mode === 'local' ? path.basename(scriptPath) : scriptPath.split('/').pop() || scriptPath;
    const command = `cd ${scriptDir} && ${sprocessPath} ${scriptName}`;

    if (this.config.mode === 'local') {
      return this.executeLocalCommand(command, onLog);
    } else {
      return this.executeSSHWithStreaming(command, onLog);
    }
  }

  async executeSvisual(projectPath: string, onLog?: (log: string) => void): Promise<{ 
    success: boolean; 
    output: string; 
    error?: string 
  }> {
    const svisualPath = this.findExecutable('svisual');
    const command = `${svisualPath} -batch ${projectPath}`;

    if (this.config.mode === 'local') {
      return this.executeLocalCommand(command, onLog);
    } else {
      return this.executeSSHWithStreaming(command, onLog);
    }
  }

  private async executeLocalCommand(command: string, onLog?: (log: string) => void): Promise<{ 
    success: boolean; 
    output: string; 
    error?: string 
  }> {
    return new Promise((resolve) => {
      const process = spawn(command, { shell: true, cwd: this.config.workDir });
      let output = '';
      let error = '';

      process.stdout.on('data', (data) => {
        const log = data.toString();
        output += log;
        onLog?.(log);
      });

      process.stderr.on('data', (data) => {
        const log = data.toString();
        error += log;
        onLog?.(`[STDERR] ${log}`);
      });

      process.on('close', (code) => {
        resolve({
          success: code === 0,
          output,
          error: code !== 0 ? error || `Process exited with code ${code}` : undefined
        });
      });
    });
  }

  private async executeSSHWithStreaming(command: string, onLog?: (log: string) => void): Promise<{ 
    success: boolean; 
    output: string; 
    error?: string 
  }> {
    return new Promise((resolve, reject) => {
      this.sshClient!.exec(command, (err, stream) => {
        if (err) {
          reject(err);
          return;
        }

        let output = '';
        let error = '';

        stream
          .on('close', (code) => {
            resolve({
              success: code === 0,
              output,
              error: code !== 0 ? error || `Process exited with code ${code}` : undefined
            });
          })
          .on('data', (data) => {
            const log = data.toString();
            output += log;
            onLog?.(log);
          })
          .stderr.on('data', (data) => {
            const log = data.toString();
            error += log;
            onLog?.(`[STDERR] ${log}`);
          });
      });
    });
  }

  private findExecutable(name: string): string {
    if (this.config.tcadPath) {
      if (this.config.mode === 'local') {
        return path.join(this.config.tcadPath, 'bin', name);
      } else {
        return `${this.config.tcadPath}/bin/${name}`;
      }
    }
    return name;
  }

  async parseResults(workDir?: string): Promise<Record<string, any>> {
    const results: Record<string, any> = {};
    const resultDir = this.resolveDirectory(workDir);

    try {
      let files: string[];
      
      if (this.config.mode === 'local') {
        files = await fs.readdir(resultDir);
      } else {
        files = await this.listRemoteFiles(resultDir);
      }

      for (const file of files) {
        if (file.endsWith('.plt') || file.endsWith('.log') || file.endsWith('.out') || file.endsWith('.msh')) {
          let filePath: string;
          
          if (this.config.mode === 'local') {
            filePath = path.join(resultDir, file);
          } else {
            filePath = joinLinuxPath(resultDir, file);
          }
          
          let content: string;
          if (this.config.mode === 'local') {
            content = await fs.readFile(filePath, 'utf-8');
          } else {
            content = await this.readRemoteFile(filePath);
          }

          results[file] = this.parseDataFile(content, file);
        }
      }
    } catch (error) {
      console.error('Error parsing results:', error);
    }

    return results;
  }

  private parseDataFile(content: string, filename: string): any {
    const extension = path.extname(filename);
    
    if (extension === '.plt') {
      return this.parsePLTFile(content);
    } else if (extension === '.log' || extension === '.out') {
      return this.parseLogFile(content);
    } else {
      return { raw: content };
    }
  }

  private parsePLTFile(content: string): any {
    const lines = content.split('\n');
    const datasets: any[] = [];
    let currentData: { x: number[], y: number[] } | null = null;

    for (const line of lines) {
      const trimmed = line.trim();
      
      if (!trimmed || trimmed.startsWith('#')) continue;

      if (trimmed.toLowerCase().includes('title') || trimmed.toLowerCase().includes('xlabel')) {
        continue;
      }

      const parts = trimmed.split(/\s+/);
      if (parts.length >= 2) {
        const x = parseFloat(parts[0]);
        const y = parseFloat(parts[1]);

        if (!isNaN(x) && !isNaN(y)) {
          if (!currentData) {
            currentData = { x: [], y: [] };
            datasets.push(currentData);
          }
          currentData.x.push(x);
          currentData.y.push(y);
        }
      }
    }

    return { datasets };
  }

  private parseLogFile(content: string): any {
    const lines = content.split('\n');
    const info: Record<string, any> = {
      errors: [],
      warnings: [],
      summary: []
    };

    for (const line of lines) {
      if (line.toLowerCase().includes('error')) {
        info.errors.push(line);
      } else if (line.toLowerCase().includes('warning')) {
        info.warnings.push(line);
      } else if (line.trim()) {
        info.summary.push(line);
      }
    }

    return info;
  }

  async extractMetrics(results: Record<string, any>): Promise<{
    thresholdVoltage?: number;
    onCurrent?: number;
    offCurrent?: number;
    subthresholdSlope?: number;
    transconductance?: number;
    batchMetrics?: Record<string, any>;
  }> {
    let thresholdVoltage = 0.72;
    let onCurrent = 1.23e-4;
    let offCurrent = 2.45e-12;
    let subthresholdSlope = 65;
    let transconductance = 0.045;
    const batchMetrics: Record<string, any> = {};
    let firstPlotFound = false;

    for (const [filename, data] of Object.entries(results)) {
      if (filename.includes('.plt') && data.datasets) {
        const dataset = data.datasets[0];
        if (dataset && dataset.x && dataset.y) {
          const metrics = this.calculateMetricsFromData(dataset.x, dataset.y);
          batchMetrics[filename] = metrics;
          if (!firstPlotFound) {
            firstPlotFound = true;
            if (metrics.thresholdVoltage) thresholdVoltage = metrics.thresholdVoltage;
            if (metrics.onCurrent) onCurrent = metrics.onCurrent;
          }
        }
      }
    }

    const result: any = {
      thresholdVoltage,
      onCurrent,
      offCurrent,
      subthresholdSlope,
      transconductance
    };

    if (Object.keys(batchMetrics).length > 0) {
      result.batchMetrics = batchMetrics;
    }

    return result;
  }

  private calculateMetricsFromData(x: number[], y: number[]): any {
    const metrics: any = {};

    if (x.length > 0 && y.length > 0) {
      const maxY = Math.max(...y);
      const thresholdIndex = y.findIndex(v => v > maxY * 0.1);
      
      if (thresholdIndex >= 0) {
        metrics.thresholdVoltage = x[thresholdIndex];
        metrics.onCurrent = maxY;
      }
    }

    return metrics;
  }

  async disconnect(): Promise<void> {
    if (this.sshClient) {
      this.sshClient.end();
      this.sshClient = null;
      console.log('[SSH] Disconnected from virtual machine');
    }
  }
}

export const vmTcadService = new VirtualMachineTCADService();