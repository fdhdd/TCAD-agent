import React, { useEffect, useRef } from 'react';
import { Play, Square, RotateCcw, BarChart3 } from 'lucide-react';
import { useAppStore } from '../store';

export const SimulationConsole: React.FC = () => {
  const currentScript = useAppStore((state) => state.currentScript);
  const simulationStatus = useAppStore((state) => state.simulationStatus);
  const setSimulationStatus = useAppStore((state) => state.setSimulationStatus);
  const setActivePanel = useAppStore((state) => state.setActivePanel);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [simulationStatus?.logs]);

  const handleRun = async () => {
    if (!currentScript) return;

    try {
      const response = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scriptId: currentScript.id,
          parameters: currentScript.parameters
        })
      });
      const data = await response.json();

      const pollStatus = async () => {
        const statusResponse = await fetch(`/api/simulation/status/${data.simulationId}`);
        const status = await statusResponse.json();
        setSimulationStatus(status);

        if (status.status === 'running') {
          setTimeout(pollStatus, 500);
        }
      };

      pollStatus();
    } catch (error) {
      console.error('Failed to run simulation:', error);
    }
  };

  const handleStop = async () => {
    if (!simulationStatus?.id) return;
    try {
      const response = await fetch('/api/simulation/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulationId: simulationStatus.id })
      });
      const data = await response.json();
      if (data.status) {
        setSimulationStatus(data.status);
      }
    } catch (error) {
      console.error('Failed to stop simulation:', error);
    }
  };

  const handleReset = async () => {
    if (!simulationStatus?.id) return;
    try {
      const response = await fetch('/api/simulation/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulationId: simulationStatus.id })
      });
      const data = await response.json();
      if (data.status) {
        setSimulationStatus(data.status);
      }
    } catch (error) {
      console.error('Failed to reset simulation:', error);
    }
  };

  const getStatusColor = () => {
    if (!simulationStatus) return 'text-gray-400';
    switch (simulationStatus.status) {
      case 'idle': return 'text-gray-400';
      case 'running': return 'text-yellow-400';
      case 'completed': return 'text-green-400';
      case 'failed': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getStatusText = () => {
    if (!simulationStatus) return '待运行';
    switch (simulationStatus.status) {
      case 'idle': return '待运行';
      case 'running': return '运行中...';
      case 'completed': return '已完成';
      case 'failed': return '失败';
      default: return '未知';
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-dark-700">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">仿真控制台</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className={`w-2 h-2 rounded-full ${getStatusColor().replace('text-', 'bg-')}`} />
              <span className={`text-sm ${getStatusColor()}`}>{getStatusText()}</span>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleRun}
              disabled={simulationStatus?.status === 'running'}
              className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 disabled:opacity-50 rounded-lg transition-colors"
            >
              <Play size={18} />
              <span>运行仿真</span>
            </button>
            <button
              onClick={handleStop}
              disabled={simulationStatus?.status !== 'running'}
              className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <Square size={18} />
              <span>停止</span>
            </button>
            <button
              onClick={handleReset}
              disabled={!simulationStatus || simulationStatus.status === 'running'}
              className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <RotateCcw size={18} />
              <span>重置</span>
            </button>
            {simulationStatus?.status === 'completed' && (
              <button
                onClick={() => setActivePanel('report')}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
              >
                <BarChart3 size={18} />
                <span>查看报告</span>
              </button>
            )}
          </div>
        </div>

        {simulationStatus && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-400">进度</span>
              <span>{simulationStatus.progress}%</span>
            </div>
            <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{ width: `${simulationStatus.progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 bg-black/30 p-4 overflow-y-auto font-mono text-sm">
        <div className="space-y-1">
          {(!simulationStatus || simulationStatus.logs.length === 0) ? (
            <div className="text-gray-500 text-center py-8">
              点击"运行仿真"开始
            </div>
          ) : (
            simulationStatus.logs.map((log, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-gray-500">[{new Date().toLocaleTimeString()}]</span>
                <span className={log.includes('[SUCCESS]') ? 'text-green-400' : log.includes('[ERROR]') ? 'text-red-400' : 'text-gray-300'}>
                  {log}
                </span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
};
