export interface TCADScript {
  id: string;
  name: string;
  type: 'sde' | 'sprocess' | 'sdevice';
  content: string;
  parameters: TCADParameter[];
}

export interface TCADParameter {
  id: string;
  name: string;
  value: number | string | boolean;
  type: 'number' | 'string' | 'boolean';
  range?: [number, number];
  description?: string;
}

export interface SimulationStatus {
  id: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  progress: number;
  logs: string[];
  result?: SimulationResult;
}

export interface SimulationResult {
  id: string;
  timestamp: number;
  data: Record<string, any>;
  charts: ChartData[];
  summary: string;
}

export interface ChartData {
  type: 'line' | 'bar' | 'scatter';
  title: string;
  xLabel: string;
  yLabel: string;
  data: { x: number; y: number }[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface TCADAction {
  type: 'read_script' | 'create_script' | 'write_script' | 'modify_script' | 'run_simulation' | 'generate_report';
  payload: any;
}
