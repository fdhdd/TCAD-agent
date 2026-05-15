import type { TCADScript, TCADParameter } from '../../shared/types.js';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs/promises';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const scriptsDir = join(__dirname, '..', 'scripts');

const scripts: Map<string, TCADScript> = new Map();

const sampleScriptContent = `# =================================================== 
# MOSFET I-V特性仿真命令文件 
# 请将 Grid 路径替换为实际可用的网格文件名 
# =================================================== 

File {
  Grid=   "YOUR_MESH_FILE.tdr"
  Plot=   "des.tdr"
  Current= "des.plt"
  Output= "des.log"
}

Physics {
  AreaFactor=1.0
  Fermi
  EffectiveIntrinsicDensity(BandGapNarrowing(OldSlotBoom))
  Mobility(Enormal HighFieldSaturation)
  Recombination(SRH(DopingDep) Auger)
}

Math {
  -CheckUndefinedModels
  Extrapolate
  Derivative
  Method=ILS
  Iterations=30
}

Solve {
  Coupled(Iterations=100) { Poisson Electron Hole }
}
`;

async function ensureScriptsDir(): Promise<void> {
  await fs.mkdir(scriptsDir, { recursive: true });
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await fs.access(path);
    return true;
  } catch {
    return false;
  }
}

function getScriptFilePath(id: string): string {
  return join(scriptsDir, `${id}.json`);
}

function getScriptCmdPath(id: string): string {
  return join(scriptsDir, `${id}.cmd`);
}

async function loadSavedScripts(): Promise<void> {
  await ensureScriptsDir();

  try {
    const entries = await fs.readdir(scriptsDir);
    for (const file of entries) {
      if (!file.endsWith('.json')) continue;
      const filePath = join(scriptsDir, file);
      try {
        const raw = await fs.readFile(filePath, 'utf-8');
        const script = JSON.parse(raw) as TCADScript;
        if (script?.id && script?.content) {
          scripts.set(script.id, script);
        }
      } catch (error) {
        console.warn(`Failed to load saved script file ${file}:`, error);
      }
    }
  } catch (error) {
    console.warn('Failed to read scripts directory:', error);
  }
}

const scriptsReady = loadSavedScripts();

export async function readScript(path: string): Promise<TCADScript> {
  await scriptsReady;

  if (path) {
    const isAbsolute = path.startsWith('/') || /^[A-Za-z]:\\/.test(path);
    const resolvedPath = isAbsolute ? path : join(process.cwd(), path);
    if (await fileExists(resolvedPath)) {
      const content = await fs.readFile(resolvedPath, 'utf-8');
      const id = 'script_' + Date.now();
      const script: TCADScript = {
        id,
        name: path.split('/').pop() || 'Loaded Script',
        type: 'sdevice',
        content,
        parameters: parseParametersFromContent(content)
      };
      scripts.set(id, script);
      return script;
    }
  }

  if (scripts.size > 0) {
    return scripts.values().next().value;
  }

  const id = 'script_' + Date.now();
  const script: TCADScript = {
    id,
    name: 'MOSFET IV Curve',
    type: 'sdevice',
    content: sampleScriptContent,
    parameters: parseParametersFromContent(sampleScriptContent)
  };
  scripts.set(id, script);
  return script;
}

export async function writeScript(script: TCADScript): Promise<TCADScript> {
  await scriptsReady;

  script.id = script.id || 'script_' + Date.now();
  scripts.set(script.id, script);

  await ensureScriptsDir();
  const filePath = getScriptFilePath(script.id);
  const cmdPath = getScriptCmdPath(script.id);
  await fs.writeFile(filePath, JSON.stringify(script, null, 2), 'utf-8');
  await fs.writeFile(cmdPath, script.content, 'utf-8');

  return script;
}

export async function parseScript(content: string, type: string): Promise<TCADParameter[]> {
  return parseParametersFromContent(content);
}

function parseParametersFromContent(content: string): TCADParameter[] {
  return [
    {
      id: 'p1',
      name: 'Drain Voltage',
      value: 1.0,
      type: 'number',
      range: [0.1, 2.0],
      description: '漏极扫描电压 (V)'
    }
  ];
}

export function getScriptById(id: string): TCADScript | undefined {
  return scripts.get(id);
}