import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User } from 'lucide-react';
import { useAppStore } from '../store';
import type { ChatMessage, TCADAction } from '../../shared/types';

export const ChatPanel: React.FC = () => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [scriptType, setScriptType] = useState<'sdevice' | 'sprocess'>('sdevice');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messages = useAppStore((state) => state.messages);
  const addMessage = useAppStore((state) => state.addMessage);
  const setCurrentScript = useAppStore((state) => state.setCurrentScript);
  const setSimulationStatus = useAppStore((state) => state.setSimulationStatus);
  const setActivePanel = useAppStore((state) => state.setActivePanel);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const runSimulationFromChat = async (script?: any) => {
    if (!script) return;

    setCurrentScript(script);
    setActivePanel('console');
    setSimulationStatus({
      id: script.id || 'sim_' + Date.now(),
      status: 'running',
      progress: 0,
      logs: ['[INFO] 已从对话启动仿真...']
    });

    try {
      const response = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scriptId: script.id, parameters: script.parameters })
      });
      const data = await response.json();

      const pollStatus = async () => {
        const statusResponse = await fetch(`/api/simulation/status/${data.simulationId}`);
        const status = await statusResponse.json();
        setSimulationStatus(status);

        if (status.status === 'running') {
          setTimeout(pollStatus, 1000);
        }
      };

      pollStatus();
    } catch (error) {
      console.error('Failed to run simulation from chat:', error);
    }
  };

  const handleAction = async (action: TCADAction) => {
    if (action.type === 'read_script') {
      await loadSampleScript();
    } else if (action.type === 'create_script' || action.type === 'write_script') {
      const script = action.payload?.script;
      if (script) {
        setCurrentScript(script);
        setActivePanel('script');
      } else {
        await loadSampleScript();
      }
    } else if (action.type === 'run_simulation') {
      const script = action.payload?.script;
      if (script) {
        await runSimulationFromChat(script);
      } else {
        setActivePanel('console');
      }
    } else if (action.type === 'generate_report') {
      setActivePanel('report');
    }
  };

  const loadSampleScript = async () => {
    try {
      const response = await fetch('/api/script/sample');
      const data = await response.json();
      if (data.script) {
        setCurrentScript(data.script);
        setActivePanel('script');
      }
    } catch (error) {
      console.error('Failed to load sample script:', error);
    }
  };

  const generateScript = async (description: string, type: 'sdevice' | 'sprocess') => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/script/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description, type })
      });
      const data = await response.json();

      if (data.script) {
        setCurrentScript(data.script);
        setActivePanel('script');
      } else {
        throw new Error(data.error || 'Failed to generate script');
      }
    } catch (error) {
      console.error('Failed to generate script:', error);
      // Show error message to user
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `脚本生成失败：${error instanceof Error ? error.message : String(error)}`,
        timestamp: Date.now()
      };
      addMessage(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: Date.now()
    };

    addMessage(userMessage);
    const currentInput = input;
    setInput('');
    setIsLoading(true);

    try {
      // Check if this is a script generation request
      const lowerInput = currentInput.toLowerCase();
      if (lowerInput.includes('创建') || lowerInput.includes('生成') || lowerInput.includes('新建') || lowerInput.includes('create') || lowerInput.includes('generate')) {
        await generateScript(currentInput, scriptType);
        setIsLoading(false);
        return;
      }

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: currentInput, context: {} })
      });
      const data = await response.json();

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.reply,
        timestamp: Date.now()
      };

      addMessage(assistantMessage);

      if (data.action) {
        setTimeout(() => handleAction(data.action), 500);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickQuestions = [
    { text: '读取一个示例脚本', action: 'load' },
    { text: '创建一个MOSFET器件仿真', action: 'generate', type: 'sdevice' as const },
    { text: '创建一个工艺仿真', action: 'generate', type: 'sprocess' as const },
    { text: '运行仿真并分析结果', action: 'run' }
  ];

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b border-dark-700">
        <h2 className="text-2xl font-bold">智能对话</h2>
        <p className="text-gray-400 mt-1">用自然语言描述您的TCAD仿真需求</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-8">
            <div className="w-20 h-20 bg-primary/10 rounded-2xl flex items-center justify-center mb-6">
              <Bot size={40} className="text-primary" />
            </div>
            <h3 className="text-xl font-semibold mb-2">您好！我是TCAD智能助手</h3>
            <p className="text-gray-400 mb-8 text-center max-w-md">
              我可以帮您读取和编辑TCAD脚本、可视化调整参数、运行仿真并自动分析结果。试试以下问题：
            </p>
            <div className="grid grid-cols-1 gap-3 max-w-md mx-auto">
              {quickQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => {
                    if (q.action === 'load') {
                      loadSampleScript();
                    } else if (q.action === 'generate' && q.type) {
                      setScriptType(q.type);
                      setInput(q.text);
                      generateScript(q.text, q.type);
                    } else if (q.action === 'run') {
                      setActivePanel('console');
                    }
                  }}
                  className="p-4 bg-dark-800 hover:bg-dark-700 border border-dark-700 hover:border-primary rounded-xl text-left transition-all hover:shadow-lg"
                >
                  <span className="text-primary mr-2">→</span>
                  {q.text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="p-4 border-t border-dark-700">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-400 mb-2">
            脚本类型
          </label>
          <select
            value={scriptType}
            onChange={(e) => setScriptType(e.target.value as 'sdevice' | 'sprocess')}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-primary"
          >
            <option value="sdevice">sdevice - 器件仿真</option>
            <option value="sprocess">sprocess - 工艺仿真</option>
          </select>
        </div>
        <div className="flex gap-4">
          <div className="flex-1">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="描述您的仿真需求..."
              className="w-full bg-dark-800 border border-dark-700 rounded-xl py-4 px-6 text-white placeholder-gray-500 focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
            />
          </div>
          <button
            onClick={handleSend}
            disabled={isLoading}
            className="bg-primary hover:bg-primary/90 disabled:opacity-50 px-8 rounded-xl transition-all flex items-center gap-2 font-medium"
          >
            {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
            <span>{isLoading ? '思考中...' : '发送'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

interface ChatBubbleProps {
  message: ChatMessage;
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-primary' : 'bg-dark-700'
      }`}>
        {isUser ? <User size={20} /> : <Bot size={20} />}
      </div>
      <div className={`max-w-2xl p-4 rounded-2xl ${
        isUser
          ? 'bg-primary text-white rounded-tr-md'
          : 'bg-dark-800 border border-dark-700 rounded-tl-md'
      }`}>
        <div className="whitespace-pre-wrap">{message.content}</div>
        <div className="text-xs opacity-50 mt-2">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};
