import { ToolMessage } from "@langchain/langgraph-sdk";
import { TcadProjectInfo } from "./TcadProjectInfo";
import { TcadStatusDashboard } from "./TcadStatusDashboard";
import { TcadSimulationMonitor } from "./TcadSimulationMonitor";
import { TcadModifyResult } from "./TcadModifyResult";
import { TcadGetResults } from "./TcadGetResults";
import { TcadDisplayResults } from "./TcadDisplayResults";
import { TcadGenericResult } from "./TcadGenericResult";

const TOOL_RENDERERS: Record<string, React.FC<{ message: ToolMessage }>> = {
  tcad_open_project: TcadProjectInfo,
  tcad_check_status: TcadStatusDashboard,
  tcad_run_simulation: TcadSimulationMonitor,
  tcad_modify_project: TcadModifyResult,
  tcad_get_results: TcadGetResults,
  tcad_display_results: TcadDisplayResults,
  tcad_cleanup: TcadGenericResult,
  tcad_tail_output: TcadGenericResult,
};

export function renderToolResult(message: ToolMessage) {
  const name = message.name || "";
  const Renderer = TOOL_RENDERERS[name];
  if (Renderer) {
    return <Renderer message={message} />;
  }
  return <TcadGenericResult message={message} />;
}
