import type { TCADAction, TCADScript } from '../../shared/types.js';
import dotenv from 'dotenv';
import { writeScript, parseScript } from './scriptService.js';

dotenv.config();

const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY;
const DEEPSEEK_API_URL = process.env.DEEPSEEK_API_URL || 'https://api.deepseek.com/v1/chat/completions';
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL || 'deepseek-chat';

interface DeepSeekMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

const systemPrompt = `你是一个专业的Sentaurus TCAD仿真助手。你的职责是：
1. 帮助用户读取、创建、编写和修改TCAD脚本
2. 解释仿真参数并提供建议
3. 分析仿真结果并给出专业意见
4. 当用户说"读取"、"打开"时，返回action: read_script
5. 当用户说"创建"、"写入"、"新建"、"生成"时，返回action: create_script
6. 当用户说"修改"、"编辑"时，返回action: modify_script
7. 当用户说"运行"、"仿真"、"执行"时，返回action: run_simulation
8. 当用户说"报告"、"分析"、"结果"时，返回action: generate_report

请用中文回复用户，并在需要时返回相应的action。`;

async function callDeepSeekAPI(messages: DeepSeekMessage[]): Promise<string> {
  if (!DEEPSEEK_API_KEY) {
    throw new Error('DeepSeek API key not configured');
  }

  const response = await fetch(DEEPSEEK_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${DEEPSEEK_API_KEY}`
    },
    body: JSON.stringify({
      model: DEEPSEEK_MODEL,
      messages: messages,
      temperature: 0.7,
      max_tokens: 2000
    })
  });

  if (!response.ok) {
    const errorData = await response.text();
    throw new Error(`DeepSeek API error: ${response.status} - ${errorData}`);
  }

  const data = await response.json();
  return data.choices[0]?.message?.content || '';
}

function extractAction(content: string): TCADAction | undefined {
  const lowerContent = content.toLowerCase();

  if (lowerContent.includes('读取') || lowerContent.includes('打开') || lowerContent.includes('read')) {
    return { type: 'read_script', payload: { path: './examples/mosfet.cmd' } };
  }
  if (lowerContent.includes('创建') || lowerContent.includes('写入') || lowerContent.includes('新建') || lowerContent.includes('生成') || lowerContent.includes('write') || lowerContent.includes('create')) {
    return { type: 'create_script', payload: {} };
  }
  if (lowerContent.includes('修改') || lowerContent.includes('编辑') || lowerContent.includes('edit') || lowerContent.includes('change')) {
    return { type: 'modify_script', payload: {} };
  }
  if (lowerContent.includes('运行') || lowerContent.includes('仿真') || lowerContent.includes('执行') || lowerContent.includes('run') || lowerContent.includes('simulate')) {
    return { type: 'run_simulation', payload: {} };
  }
  if (lowerContent.includes('报告') || lowerContent.includes('分析') || lowerContent.includes('result') || lowerContent.includes('report') || lowerContent.includes('analyze')) {
    return { type: 'generate_report', payload: {} };
  }

  return undefined;
}

function cleanGeneratedScript(content: string): string {
  let cleaned = content;

  cleaned = cleaned.replace(/```(?:\w*)?[\r\n]?([\s\S]*?)```/g, '$1');
  cleaned = cleaned.replace(/^\s*#+.*$/gm, '');
  cleaned = cleaned.replace(/^\s*[-*]\s+.*$/gm, '');
  cleaned = cleaned.replace(/^\s*>.*$/gm, '');

  return cleaned.trim();
}

function validateTCADScript(content: string): void {
  const trimmed = content.trim();
  if (!trimmed) {
    throw new Error('生成的 TCAD 脚本为空，请检查描述内容。');
  }

  const validStartPattern = /^(File|Physics|Math|Solve|Structure|Mesh|Contact|Material|Boundary|Doping|Function)\b/m;
  if (!validStartPattern.test(trimmed)) {
    throw new Error('生成脚本必须以有效的 Sentaurus 命令块开始，例如 File { ... }、Physics { ... }、Math { ... }、Solve { ... }。');
  }

  if (/```/.test(trimmed)) {
    throw new Error('生成脚本包含 Markdown 代码块标记，请只输出纯 TCAD 文本。');
  }
  if (/^\s*=/.test(trimmed)) {
    throw new Error('生成脚本包含非法行开头 “=”，请不要在脚本中插入空行或无效赋值。');
  }
  if (/^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\s*$/m.test(trimmed)) {
    throw new Error('生成脚本包含非法独立数值行，例如 1e-9，请只输出有效的 Sentaurus 命令和属性定义。');
  }

  const invalidSingleWordLine = /^\s*(Voltage|Current|Resistance|Capacitance|Inductance|Power|Frequency|Temperature)\s*$/m;
  if (invalidSingleWordLine.test(trimmed)) {
    throw new Error('生成脚本包含非法独立关键字，例如 Voltage 或 Current。请只使用 Sentaurus 命令块和属性语法。');
  }

  if (/^\s*(anode|cathode|electrode)\s*$/im.test(trimmed)) {
    throw new Error('生成脚本包含未定义的接触名称，例如 anode 或 cathode。请只使用标准接触名称，并确保先定义后使用。');
  }

  if (/\bInitialStep\b/i.test(trimmed) && !/Quasistationary\s*\([^)]*\bInitialStep\b/i.test(trimmed)) {
    throw new Error('生成脚本包含非法命令 InitialStep，请使用 Sentaurus 标准命令块和参数。');
  }

  if (/^\s*Poisson\s*$/m.test(trimmed) && !/\bSolve\s*\{[\s\S]*?^\s*Poisson\s*$/m.test(trimmed)) {
    throw new Error('生成脚本包含非法独立行 Poisson。请使用标准 Solve { Coupled(...) { Poisson Electron Hole } } 语法。');
  }

  if (/^\s*Electron\s+Hole\s*$/m.test(trimmed) && !/\bSolve\s*\{[\s\S]*?^\s*Electron\s+Hole\s*$/m.test(trimmed)) {
    throw new Error('生成脚本包含非法独立行 Electron Hole。请使用标准 Solve { Coupled(...) { Poisson Electron Hole } } 语法。');
  }

  if (/Solve\s*\{[\s\S]*?\bPoisson\b[\s\S]*?\bElectron\s+Hole\b[\s\S]*?\}/m.test(trimmed) === false && /\bSolve\b/.test(trimmed)) {
    throw new Error('Solve 块必须使用标准 Coupled 语法，例如 Solve { Coupled(Iterations=100) { Poisson Electron Hole } }。');
  }

  if (/^\s*\)+\s*$/m.test(trimmed)) {
    throw new Error('生成脚本包含非法独立闭括号行 “)”。请不要单独输出闭括号。');
  }

  const gridMatch = trimmed.match(/Grid\s*=\s*(?:"([^\"]+)"|'([^']+)'|([^\s\}\n]+))/m);
  if (!gridMatch) {
    throw new Error('生成脚本缺少有效的 Grid= 几何文件定义，请提供一个有效的几何文件路径。');
  }
  const gridValue = (gridMatch[1] || gridMatch[2] || gridMatch[3] || '').trim();
  if (!gridValue || /^(?:<.+?>|TODO|path|filename|dummy|none)$/i.test(gridValue) || /n1220_msh\.tdr|X-2025\.06|GarandAppVar|GettingStarted/i.test(gridValue)) {
    throw new Error('生成脚本中的 Grid= 几何文件名无效。请使用真实可访问的网格文件路径，例如 Grid= "YOUR_MESH_FILE.tdr"，不要使用默认示例或占位符路径。');
  }

  if (/<\s*\w+\s*>/.test(trimmed)) {
    throw new Error('生成脚本包含尖括号占位符，例如 <0>、out<1>，这不是有效的 Sentaurus 语法。');
  }
}

async function generateTCADScriptFromDescription(description: string, scriptType?: 'sdevice' | 'sprocess'): Promise<TCADScript> {
  const messages: DeepSeekMessage[] = [
    {
      role: 'system',
      content: `你是一个专业的 Sentaurus TCAD 脚本生成器。根据用户要求生成完整的 Sentaurus TCAD 脚本（sdevice 或 sprocess），必须满足以下要求：\n1. 只输出纯 TCAD 脚本内容，不要解释、不要注释、不要前导或尾随文本。\n2. 不要输出任何 JSON、Markdown、对话、标题或说明性文字。\n3. 脚本必须以有效的 Sentaurus 命令块开始，例如 File { ... }、Physics { ... }、Math { ... }、Solve { ... } 等。\n4. 绝对禁止使用占位符或尖括号表达式，例如 <0>、<1>、out<0>、out<1>。\n5. 不要创建自定义器件名或复杂器件结构，例如 Counter8bit、MyDevice、CustomDevice。只输出简单、标准的可执行器件脚本。\n6. 不要使用一般的电路术语作为独立命令，例如 Voltage、Current、Resistance、Capacitance。只使用 Sentaurus 属性和值语法。\n7. 不要输出独立数字或科学计数法行，例如 1e-9、1.0、0.5。
8. 不要输出独立的括号行，例如 ) 或 (。\n9. 不要使用无效或未知的 Sentaurus 命令关键字，例如 InitialStep。\n10. Solve 块必须使用标准 Sentaurus 语法，例如 Solve { Coupled(Iterations=100) { Poisson Electron Hole } }。不要输出独立的 Poisson 或 Electron Hole 行。
11. 必须提供有效的几何文件名，并使用当前可访问的真实网格文件路径。不要使用默认示例网格路径，如 /usr/synopsys/.../n1220_msh.tdr，也不要输出占位符或 TODO 路径。
12. 使用真实文件名，如 des.log、des.plt、des.tdr。\n13. 输出必须直接可写入命令文件并由 Sentaurus 解析.`
    },
    { role: 'user', content: description }
  ];

  let scriptContent = await callDeepSeekAPI(messages);
  scriptContent = cleanGeneratedScript(scriptContent);
  validateTCADScript(scriptContent);

  const finalScriptType = scriptType || (description.toLowerCase().includes('process') || description.includes('工艺') ? 'sprocess' : 'sdevice');

  const script: TCADScript = {
    id: 'script_' + Date.now(),
    name: 'Generated TCAD Script',
    type: finalScriptType,
    content: scriptContent,
    parameters: await parseScript(scriptContent, finalScriptType)
  };

  return writeScript(script);
}

export async function processChatMessage(message: string, context?: any): Promise<{ reply: string; action?: TCADAction }> {
  if (!DEEPSEEK_API_KEY) {
    return {
      reply: 'DeepSeek API未配置。请在.env文件中设置DEEPSEEK_API_KEY。',
      action: undefined
    };
  }

  try {
    const userMessage = context ? `${message}\n\nContext: ${JSON.stringify(context)}` : message;
    const messages: DeepSeekMessage[] = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userMessage }
    ];

    const reply = await callDeepSeekAPI(messages);
    const action = extractAction(reply);

    if (action?.type === 'create_script') {
      try {
        const script = await generateTCADScriptFromDescription(message);
        action.payload = { script };
      } catch (scriptError) {
        console.error('Script generation error:', scriptError);
        return {
          reply: `脚本生成失败：${scriptError instanceof Error ? scriptError.message : String(scriptError)}。请检查你的描述是否符合 Sentaurus TCAD 标准，并稍后重试。`, 
          action: undefined
        };
      }
    }

    return { reply, action };
  } catch (error) {
    console.error('DeepSeek API error:', error);
    return {
      reply: `抱歉，调用DeepSeek API时发生错误：${error instanceof Error ? error.message : String(error)}`,
      action: undefined
    };
  }
}

export { generateTCADScriptFromDescription };