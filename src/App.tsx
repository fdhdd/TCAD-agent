import React from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
import { ScriptEditor } from './components/ScriptEditor';
import { ParameterPanel } from './components/ParameterPanel';
import { SimulationConsole } from './components/SimulationConsole';
import { ReportViewer } from './components/ReportViewer';
import { useAppStore } from './store';

function App() {
  const activePanel = useAppStore((state) => state.activePanel);

  return (
    <div className="flex h-screen bg-dark text-white">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        {activePanel === 'chat' && <ChatPanel />}
        {activePanel === 'script' && <ScriptEditor />}
        {activePanel === 'parameters' && <ParameterPanel />}
        {activePanel === 'console' && <SimulationConsole />}
        {activePanel === 'report' && <ReportViewer />}
      </main>
    </div>
  );
}

export default App;
