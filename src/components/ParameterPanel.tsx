import React from 'react';
import { Play, Settings2, Info } from 'lucide-react';
import { useAppStore } from '../store';

export const ParameterPanel: React.FC = () => {
  const currentScript = useAppStore((state) => state.currentScript);
  const updateParameterAndScript = useAppStore((state) => state.updateParameterAndScript);
  const setActivePanel = useAppStore((state) => state.setActivePanel);

  if (!currentScript) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-gray-400">
          <Settings2 size={48} className="mx-auto mb-4 opacity-50" />
          <p>请先加载脚本</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-dark-700 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">参数设置</h2>
          <p className="text-sm text-gray-400 mt-1">可视化调整仿真参数（参数修改会同步更新脚本内容）</p>
        </div>
        <button
          onClick={() => setActivePanel('console')}
          className="flex items-center gap-2 px-6 py-2 bg-primary hover:bg-primary/90 rounded-lg transition-colors font-medium"
        >
          <Play size={18} />
          <span>运行仿真</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-4 max-w-3xl mx-auto">
          {currentScript.parameters.map((param) => (
            <div key={param.id} className="bg-dark-800 border border-dark-700 rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-white">{param.name}</h3>
                  {param.description && (
                    <p className="text-sm text-gray-400 mt-1">{param.description}</p>
                  )}
                </div>
                <Info size={16} className="text-gray-500" />
              </div>

              {param.type === 'number' && param.range && (
                <div className="space-y-3">
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min={Math.log10(param.range[0])}
                      max={Math.log10(param.range[1])}
                      step={0.1}
                      value={Math.log10(Number(param.value))}
                      onChange={(e) => {
                        const newValue = Math.pow(10, parseFloat(e.target.value));
                        updateParameterAndScript(param.id, newValue);
                      }}
                      className="flex-1 h-2 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                    <div className="w-32">
                      <input
                        type="number"
                        value={Number(param.value)}
                        onChange={(e) => updateParameterAndScript(param.id, parseFloat(e.target.value))}
                        className="w-full bg-dark-700 border border-dark-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-primary"
                      />
                    </div>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>{formatNumber(param.range[0])}</span>
                    <span>{formatNumber(param.range[1])}</span>
                  </div>
                </div>
              )}

              {param.type === 'number' && !param.range && (
                <input
                  type="number"
                  value={Number(param.value)}
                  onChange={(e) => updateParameterAndScript(param.id, parseFloat(e.target.value))}
                  className="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
                />
              )}

              {param.type === 'boolean' && (
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={param.value === true}
                    onChange={(e) => updateParameterAndScript(param.id, e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-dark-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                </label>
              )}

              {param.type === 'string' && (
                <input
                  type="text"
                  value={String(param.value)}
                  onChange={(e) => updateParameterAndScript(param.id, e.target.value)}
                  className="w-full bg-dark-700 border border-dark-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary"
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

function formatNumber(num: number): string {
  if (num >= 1e9) return (num / 1e9).toFixed(1) + 'e9';
  if (num >= 1e6) return (num / 1e6).toFixed(1) + 'e6';
  if (num >= 1e3) return (num / 1e3).toFixed(1) + 'e3';
  if (num <= 1e-6 && num > 0) return (num * 1e9).toFixed(1) + 'e-9';
  if (num <= 1e-3 && num > 0) return (num * 1e6).toFixed(1) + 'e-6';
  return num.toPrecision(3);
}
