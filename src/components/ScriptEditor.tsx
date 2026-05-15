import React, { useEffect, useState } from 'react';
import { Save, FolderOpen, Play, Settings, TestTube } from 'lucide-react';
import Editor from '@monaco-editor/react';
import { useAppStore } from '../store';

export const ScriptEditor: React.FC = () => {
  const currentScript = useAppStore((state) => state.currentScript);
  const updateScriptContent = useAppStore((state) => state.updateScriptContent);
  const setActivePanel = useAppStore((state) => state.setActivePanel);
  const [isLoading, setIsLoading] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const loadSampleScript = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/script/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: './examples/mosfet.cmd' })
      });
      const data = await response.json();
      const setCurrentScript = useAppStore.getState().setCurrentScript;
      setCurrentScript(data.script);
    } catch (error) {
      console.error('Failed to load script:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!currentScript) {
      loadSampleScript();
    }
  }, []);

  const handleSave = async () => {
    if (!currentScript) return;
    try {
      await fetch('/api/script/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: currentScript })
      });
    } catch (error) {
      console.error('Failed to save script:', error);
    }
  };

  const handleTest = async () => {
    if (!currentScript) return;
    
    setIsTesting(true);
    setTestResult(null);
    
    try {
      const response = await fetch('/api/simulation/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: currentScript })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setTestResult(`✅ 测试成功！\n\n${data.message}\n\n执行日志:\n${data.logs.join('\n')}`);
      } else {
        setTestResult(`❌ 测试失败：${data.error}\n\n执行日志:\n${data.logs?.join('\n') || '无日志'}`);
      }
    } catch (error) {
      setTestResult(`❌ 测试失败：网络错误 - ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsTesting(false);
    }
  };

  if (!currentScript) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-pulse mb-4">加载中...</div>
          <button
            onClick={loadSampleScript}
            className="bg-primary hover:bg-primary/90 px-6 py-2 rounded-lg"
          >
            加载示例脚本
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-dark-700 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">脚本编辑器</h2>
          <p className="text-sm text-gray-400 mt-1">
            {currentScript.name} · <span className="uppercase tracking-[0.12em]">{currentScript.type}</span>
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadSampleScript}
            className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <FolderOpen size={18} />
            <span>打开</span>
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors"
          >
            <Save size={18} />
            <span>保存</span>
          </button>
          <button
            onClick={handleTest}
            disabled={isTesting}
            className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:opacity-50 rounded-lg transition-colors"
          >
            <TestTube size={18} />
            <span>{isTesting ? '测试中...' : '测试连接'}</span>
          </button>
          <button
            onClick={() => setActivePanel('parameters')}
            className="flex items-center gap-2 px-4 py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg transition-colors"
          >
            <Settings size={18} />
            <span>参数设置</span>
          </button>
          <button
            onClick={() => setActivePanel('console')}
            className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 rounded-lg transition-colors"
          >
            <Play size={18} />
            <span>运行仿真</span>
          </button>
        </div>
      </div>

      <div className="flex-1 relative">
        <Editor
          height="100%"
          defaultLanguage="plaintext"
          value={currentScript.content}
          onChange={(value) => updateScriptContent(value || '')}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: 'on',
            roundedSelection: false,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            padding: { top: 16, bottom: 16 }
          }}
        />
      </div>

      {testResult && (
        <div className="p-4 border-t border-dark-700 bg-dark-900">
          <h3 className="text-lg font-semibold mb-2">测试结果</h3>
          <pre className="bg-dark-800 p-4 rounded-lg text-sm overflow-x-auto whitespace-pre-wrap">
            {testResult}
          </pre>
          <button
            onClick={() => setTestResult(null)}
            className="mt-2 px-3 py-1 bg-dark-700 hover:bg-dark-600 rounded text-sm"
          >
            关闭
          </button>
        </div>
      )}
    </div>
  );
};
