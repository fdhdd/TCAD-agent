import { ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { Monitor, Table2, Activity, ChevronDown, ChevronUp, Beaker } from "lucide-react";

interface ElectricalRow {
  node: number;
  [key: string]: any;
}

export function TcadDisplayResults({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const [showRaw, setShowRaw] = useState(false);
  const lines = contentStr.split("\n");

  // Detect project overview
  const projectNameMatch = contentStr.match(/TCAD Project:\s*(.+)/);
  const projectName = projectNameMatch ? projectNameMatch[1].trim() : "";

  // Extract status overview line
  const statusLine = lines.find((l) => l.includes("Status:") && l.includes("done") || l.includes("running"));

  // Extract node counts
  const nodeCountMatch = contentStr.match(/Nodes\s*:\s*(\d+)\s*total,\s*(\d+)\s*leaf/);
  const totalNodes = nodeCountMatch ? parseInt(nodeCountMatch[1]) : null;
  const leafNodes = nodeCountMatch ? parseInt(nodeCountMatch[2]) : null;

  // Parse experiment table (lines between "Experiment Table" and next section)
  let expTableLines: string[] = [];
  let inExpTable = false;
  for (const line of lines) {
    if (line.includes("Experiment Table") || line.includes("实验表格")) {
      inExpTable = true;
      continue;
    }
    if (inExpTable) {
      if (line.includes("Node Status") || line.includes("节点状态") || line.includes("Electrical Results") || line.includes("电学参数")) {
        break;
      }
      if (line.includes("─") || line.includes("═")) continue;
      expTableLines.push(line);
    }
  }

  // Parse node status table (lines between "Node Status" and "Electrical Results")
  let statusTableLines: string[] = [];
  let inStatusTable = false;
  for (const line of lines) {
    if (line.includes("Node Status") || line.includes("节点状态")) {
      inStatusTable = true;
      continue;
    }
    if (inStatusTable) {
      if (line.includes("Electrical Results") || line.includes("电学参数") || line.includes("Id-Vg Curves")) {
        break;
      }
      if (line.includes("─") || line.includes("═") || line.includes("Status:")) continue;
      statusTableLines.push(line);
    }
  }

  // Parse electrical results
  let inElec = false;
  let elecHeader: string[] = [];
  let elecRows: string[] = [];
  let inIdVg = false;
  let idVgSections: string[] = [];

  for (const line of lines) {
    if (line.includes("Electrical Results") || line.includes("电学参数")) {
      inElec = true;
      continue;
    }
    if (inElec) {
      if (line.includes("Id-Vg Curves") || line.includes("Id-Vg 曲线")) {
        inElec = false;
        inIdVg = true;
        continue;
      }
      if (inIdVg) {
        idVgSections.push(line);
        continue;
      }
      if (line.includes("─") || line.includes("═")) continue;
      if (line.includes("|")) {
        if (!elecHeader.length) {
          elecHeader.push(line);
        } else {
          elecRows.push(line);
        }
      }
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center gap-2">
        <Monitor className="size-4 text-gray-600" />
        <span className="font-medium text-gray-800 text-sm">
          {projectName || "仿真结果"}
        </span>
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="ml-auto text-xs text-gray-400 hover:text-gray-600 transition-colors cursor-pointer"
        >
          {showRaw ? "可视化视图" : "原始文本"}
        </button>
      </div>

      {showRaw ? (
        <div className="p-3 font-mono text-xs whitespace-pre-wrap text-gray-700 max-h-[400px] overflow-y-auto">
          {contentStr}
        </div>
      ) : (
        <div className="divide-y divide-gray-100">
          {/* Project stats */}
          {(projectName || totalNodes) && (
            <div className="px-4 py-2.5 flex gap-4 text-xs text-gray-600">
              {projectName && <span>📁 {projectName}</span>}
              {totalNodes !== null && <span>📊 节点: {totalNodes} 总 / {leafNodes} 叶子</span>}
            </div>
          )}

          {/* Experiment table */}
          {expTableLines.length > 3 && (
            <div className="px-4 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2 font-medium">
                <Table2 className="size-3.5" /> 实验参数表
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <tbody>
                    {expTableLines.filter((l) => l.trim()).map((row, ri) => {
                      const cells = row.split("|").map((c) => c.trim()).filter(Boolean);
                      if (cells.length === 0) return null;
                      return (
                        <tr key={ri} className={ri === 0 ? "bg-gray-50 font-medium" : ri === 1 ? "bg-gray-50/50" : undefined}>
                          {cells.map((cell, ci) => (
                            <td key={ci} className="px-2 py-1 border border-gray-100 whitespace-nowrap max-w-[200px] truncate">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Node status list */}
          {statusTableLines.length > 0 && (
            <div className="px-4 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2 font-medium">
                <Activity className="size-3.5" /> 节点状态
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                {statusTableLines.filter((l) => l.trim()).map((row, ri) => {
                  const parts = row.trim().split(/\s{2,}/);
                  if (parts.length < 2) return null;
                  const nodeId = parts[0];
                  const tool = parts[1] || "";
                  const status = parts[2] || "";
                  const colorMap: Record<string, string> = {
                    done: "bg-green-50 border-green-100 text-green-700",
                    running: "bg-blue-50 border-blue-100 text-blue-700",
                    failed: "bg-red-50 border-red-100 text-red-700",
                  };
                  const color = colorMap[status.toLowerCase()] || "bg-gray-50 border-gray-100 text-gray-600";
                  return (
                    <div key={ri} className={`flex items-center gap-2 px-2 py-1 rounded border text-xs ${color}`}>
                      <span className="font-mono font-medium">{nodeId}</span>
                      <span className="text-gray-400">/</span>
                      <span className="truncate">{tool}</span>
                      <span className="ml-auto font-medium">{status}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Electrical results table */}
          {elecHeader.length > 0 && (
            <div className="px-4 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2 font-medium">
                <Beaker className="size-3.5" /> 电学参数
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    {elecHeader.map((hdr, hi) => {
                      const cells = hdr.split("|").map((c) => c.trim()).filter(Boolean);
                      return (
                        <tr key={hi}>
                          {cells.map((cell, ci) => (
                            <th key={ci} className="px-2 py-1 border border-gray-100 bg-gray-50 text-left font-medium text-gray-600 whitespace-nowrap">
                              {cell}
                            </th>
                          ))}
                        </tr>
                      );
                    })}
                  </thead>
                  <tbody>
                    {elecRows.map((row, ri) => {
                      const cells = row.split("|").map((c) => c.trim()).filter(Boolean);
                      return (
                        <tr key={ri} className="hover:bg-gray-50">
                          {cells.map((cell, ci) => (
                            <td key={ci} className="px-2 py-1 border border-gray-100 font-mono whitespace-nowrap">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Id-Vg curve data */}
          {idVgSections.filter((l) => l.trim() && !l.includes("─") && !l.includes("═")).length > 0 && (
            <div className="px-4 py-2.5">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2 font-medium">
                <Activity className="size-3.5" /> Id-Vg 曲线数据
              </div>
              <div className="font-mono text-xs text-gray-600 whitespace-pre-wrap max-h-[200px] overflow-y-auto">
                {idVgSections.filter((l) => l.trim() && !l.includes("─") && !l.includes("═")).join("\n")}
              </div>
            </div>
          )}

          {!expTableLines.length && !statusTableLines.length && !elecHeader.length && !idVgSections.length && (
            <div className="p-3 font-mono text-xs whitespace-pre-wrap text-gray-700 max-h-[300px] overflow-y-auto">
              {contentStr}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
