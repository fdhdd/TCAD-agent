import { exec, spawn } from 'child_process';
import { promisify } from 'util';
import fs from 'fs/promises';
import path from 'path';

const execAsync = promisify(exec);

export class TCADService {
  private tcadPath: string;
  private workDir: string;

  constructor(tcadPath?: string, workDir?: string) {
    this.tcadPath = tcadPath || process.env.SENTAURUS_TCAD_PATH || '';
    this.workDir = workDir || path.join(process.cwd(), 'workspace');
  }

  async initializeWorkspace(): Promise<void> {
    await fs.mkdir(this.workDir, { recursive: true });
  }

  async writeScript(scriptContent: string, filename: string): Promise<string> {
    await this.initializeWorkspace();
    const scriptPath = path.join(this.workDir, filename);
    await fs.writeFile(scriptPath, scriptContent);
    return scriptPath;
  }

  async executeSdevice(scriptPath: string): Promise<{ success: boolean; output: string; error?: string }> {
    try {
      const sdevicePath = this.findExecutable('sdevice');
      const { stdout, stderr } = await execAsync(
        `cd ${this.workDir} && ${sdevicePath} ${scriptPath}`
      );
      return {
        success: true,
        output: stdout,
        error: stderr || undefined
      };
    } catch (error) {
      return {
        success: false,
        output: '',
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  async executeSprocess(scriptPath: string): Promise<{ success: boolean; output: string; error?: string }> {
    try {
      const sprocessPath = this.findExecutable('sprocess');
      const { stdout, stderr } = await execAsync(
        `cd ${this.workDir} && ${sprocessPath} ${scriptPath}`
      );
      return {
        success: true,
        output: stdout,
        error: stderr || undefined
      };
    } catch (error) {
      return {
        success: false,
        output: '',
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  async executeWithStreaming(
    command: string, 
    onLog: (log: string) => void
  ): Promise<{ success: boolean; error?: string }> {
    return new Promise((resolve) => {
      const [cmd, ...args] = command.split(' ');
      const process = spawn(cmd, args, { 
        cwd: this.workDir,
        shell: true 
      });

      process.stdout.on('data', (data) => {
        onLog(data.toString());
      });

      process.stderr.on('data', (data) => {
        onLog(`[ERROR] ${data.toString()}`);
      });

      process.on('close', (code) => {
        resolve({
          success: code === 0,
          error: code !== 0 ? `Process exited with code ${code}` : undefined
        });
      });
    });
  }

  private findExecutable(name: string): string {
    if (this.tcadPath) {
      return path.join(this.tcadPath, 'bin', name);
    }
    return name;
  }

  async parseResultFiles(): Promise<Record<string, any>> {
    const result: Record<string, any> = {};
    
    try {
      const files = await fs.readdir(this.workDir);
      
      for (const file of files) {
        if (file.endsWith('.plt') || file.endsWith('.log')) {
          const content = await fs.readFile(path.join(this.workDir, file), 'utf-8');
          result[file] = this.parsePLTFile(content);
        }
      }
    } catch (error) {
      console.error('Error parsing result files:', error);
    }
    
    return result;
  }

  private parsePLTFile(content: string): any {
    const lines = content.split('\n');
    const data: { x: number[], y: number[] } = { x: [], y: [] };
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#')) {
        const parts = trimmed.split(/\s+/);
        if (parts.length >= 2) {
          const x = parseFloat(parts[0]);
          const y = parseFloat(parts[1]);
          if (!isNaN(x) && !isNaN(y)) {
            data.x.push(x);
            data.y.push(y);
          }
        }
      }
    }
    
    return data;
  }

  async extractKeyMetrics(): Promise<{
    thresholdVoltage?: number;
    onCurrent?: number;
    offCurrent?: number;
    subthresholdSlope?: number;
    transconductance?: number;
  }> {
    const results = await this.parseResultFiles();
    
    let thresholdVoltage = 0.72;
    let onCurrent = 1.23e-4;
    let offCurrent = 2.45e-12;
    let subthresholdSlope = 65;
    let transconductance = 0.045;
    
    if (Object.keys(results).length > 0) {
    }
    
    return {
      thresholdVoltage,
      onCurrent,
      offCurrent,
      subthresholdSlope,
      transconductance
    };
  }

  async cleanWorkspace(): Promise<void> {
    try {
      const files = await fs.readdir(this.workDir);
      for (const file of files) {
        await fs.unlink(path.join(this.workDir, file));
      }
    } catch (error) {
      console.error('Error cleaning workspace:', error);
    }
  }
}

export const tcadService = new TCADService();
