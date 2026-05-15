import React from 'react';
import { MessageSquare, FileCode, Settings, Terminal, BarChart3 } from 'lucide-react';
import { useAppStore } from '../store';

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  panel: 'chat' | 'script' | 'parameters' | 'console' | 'report';
}

const SidebarItem: React.FC<SidebarItemProps> = ({ icon, label, panel }) => {
  const activePanel = useAppStore((state) => state.activePanel);
  const setActivePanel = useAppStore((state) => state.setActivePanel);
  const isActive = activePanel === panel;

  return (
    <button
      onClick={() => setActivePanel(panel)}
      className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg transition-all duration-200 ${
        isActive
          ? 'bg-primary text-white shadow-lg shadow-primary/20'
          : 'text-gray-400 hover:bg-dark-800 hover:text-white'
      }`}
    >
      {icon}
      <span className="font-medium">{label}</span>
    </button>
  );
};

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-dark-800 border-r border-dark-700 p-4 flex flex-col">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-primary flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <span className="text-white font-bold">T</span>
          </div>
          TCAD Agent
        </h1>
        <p className="text-xs text-gray-500 mt-1">智能仿真助手</p>
      </div>

      <nav className="flex-1 space-y-2">
        <SidebarItem
          icon={<MessageSquare size={20} />}
          label="智能对话"
          panel="chat"
        />
        <SidebarItem
          icon={<FileCode size={20} />}
          label="脚本编辑器"
          panel="script"
        />
        <SidebarItem
          icon={<Settings size={20} />}
          label="参数设置"
          panel="parameters"
        />
        <SidebarItem
          icon={<Terminal size={20} />}
          label="仿真控制台"
          panel="console"
        />
        <SidebarItem
          icon={<BarChart3 size={20} />}
          label="分析报告"
          panel="report"
        />
      </nav>

      <div className="mt-auto pt-4 border-t border-dark-700">
        <div className="bg-dark-700/50 rounded-lg p-3">
          <p className="text-xs text-gray-400 mb-2">快捷操作</p>
          <div className="flex gap-2">
            <QuickAction label="加载示例" action="load" />
            <QuickAction label="运行仿真" action="run" />
          </div>
        </div>
      </div>
    </aside>
  );
};

interface QuickActionProps {
  label: string;
  action: string;
}

const QuickAction: React.FC<QuickActionProps> = ({ label }) => (
  <button className="flex-1 bg-primary/10 hover:bg-primary/20 text-primary text-xs py-2 px-3 rounded-md transition-colors">
    {label}
  </button>
);
