import { create } from 'zustand';
import type { TCADScript, TCADParameter, SimulationStatus, ChatMessage } from '../shared/types';

interface AppState {
  messages: ChatMessage[];
  currentScript: TCADScript | null;
  simulationStatus: SimulationStatus | null;
  activePanel: 'chat' | 'script' | 'parameters' | 'console' | 'report';
  addMessage: (message: ChatMessage) => void;
  setCurrentScript: (script: TCADScript | null) => void;
  updateScriptContent: (content: string) => void;
  updateParameter: (paramId: string, value: any) => void;
  updateParameterAndScript: (paramId: string, value: any) => void;
  setSimulationStatus: (status: SimulationStatus | null) => void;
  setActivePanel: (panel: AppState['activePanel']) => void;
}

function replaceParameterInScript(content: string, param: TCADParameter, newValue: any): string {
  const paramName = param.name.toLowerCase().replace(/\s+/g, '');
  
  const patterns = [
    new RegExp(`(${paramName}\\s*=\\s*)[\\d.eE+-]+`, 'gi'),
    new RegExp(`(=\\s*)${param.value}(\\s|$)`, 'gi'),
    new RegExp(`(${param.value})(\\s|,|\\)|$)`, 'gi')
  ];
  
  let newContent = content;
  const stringValue = typeof newValue === 'number' ? newValue.toString() : newValue;
  
  for (const pattern of patterns) {
    const match = newContent.match(pattern);
    if (match) {
      newContent = newContent.replace(pattern, (match, p1) => {
        if (p1) {
          return p1 + stringValue;
        }
        return stringValue;
      });
      break;
    }
  }
  
  return newContent;
}

export const useAppStore = create<AppState>((set) => ({
  messages: [],
  currentScript: null,
  simulationStatus: null,
  activePanel: 'chat',
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  
  setCurrentScript: (script) => set({ currentScript: script }),
  
  updateScriptContent: (content) => set((state) => ({
    currentScript: state.currentScript ? { ...state.currentScript, content } : null
  })),
  
  updateParameter: (paramId, value) => set((state) => {
    if (!state.currentScript) return {};
    return {
      currentScript: {
        ...state.currentScript,
        parameters: state.currentScript.parameters.map(p =>
          p.id === paramId ? { ...p, value } : p
        )
      }
    };
  }),
  
  updateParameterAndScript: (paramId, value) => set((state) => {
    if (!state.currentScript) return {};
    
    const param = state.currentScript.parameters.find(p => p.id === paramId);
    if (!param) return {};
    
    const updatedContent = replaceParameterInScript(state.currentScript.content, param, value);
    
    return {
      currentScript: {
        ...state.currentScript,
        content: updatedContent,
        parameters: state.currentScript.parameters.map(p =>
          p.id === paramId ? { ...p, value } : p
        )
      }
    };
  }),
  
  setSimulationStatus: (status) => set({ simulationStatus: status }),
  
  setActivePanel: (panel) => set({ activePanel: panel })
}));
