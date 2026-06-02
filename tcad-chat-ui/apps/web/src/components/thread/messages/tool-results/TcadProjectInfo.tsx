import { ToolMessage } from "@langchain/langgraph-sdk";
import { FolderOpen, Wrench, SlidersHorizontal, Layers, Database, Beaker } from "lucide-react";

interface ProjectSummary {
  path: string;
  tools: string[];
  params: string[];
  steps: number;
  scenarios: number;
  experiments: number;
}

interface ToolDetail {
  name: string;
  dbTool: string;
  params: string[];
}

interface ParamDetail {
  name: string;
  default: string;
  values: string[];
}

interface NodeDetail {
  id: number;
  tool: string;
  status: string;
  pvalues: string[];
  data?: string;
}

function parseProjectSummary(text: string): ProjectSummary | null {
  const lines = text.split("\n").map((l) => l.trim());
  let path = "";
  const tools: string[] = [];
  const params: string[] = [];
  let steps = 0;
  let scenarios = 0;
  let experiments = 0;

  for (const line of lines) {
    if (line.startsWith("项目:")) {
      path = line.replace("项目:", "").trim();
    } else if (line.startsWith("工具列表:")) {
      const match = line.match(/工具列表:\s*(\[.*?\])/);
      if (match) {
        try {
          const parsed = JSON.parse(match[1].replace(/'/g, '"'));
          tools.push(...parsed);
        } catch { /* ignore */ }
      }
    } else if (line.startsWith("参数列表:")) {
      const match = line.match(/参数列表:\s*(\[.*?\])/);
      if (match) {
        try {
          const parsed = JSON.parse(match[1].replace(/'/g, '"'));
          params.push(...parsed);
        } catch { /* ignore */ }
      }
    } else if (line.startsWith("步骤数:")) {
      steps = parseInt(line.replace("步骤数:", "").trim()) || 0;
    } else if (line.startsWith("场景数:")) {
      scenarios = parseInt(line.replace("场景数:", "").trim()) || 0;
    } else if (line.startsWith("实验数:")) {
      experiments = parseInt(line.replace("实验数:", "").trim()) || 0;
    }
  }

  if (!path && tools.length === 0) return null;
  return { path, tools, params, steps, scenarios, experiments };
}

function parseToolDetails(text: string): ToolDetail[] {
  const details: ToolDetail[] = [];
  const lines = text.split("\n");
  let inTools = false;

  for (const line of lines) {
    if (line.includes("工具详情:")) {
      inTools = true;
      continue;
    }
    if (inTools) {
      if (line.includes("详情:") || line.startsWith("场景:") || line.startsWith("全部节点")) {
        inTools = false;
        continue;
      }
      const trimmed = line.trim();
      const match = trimmed.match(/-\s*(\w+)\s*\(db:\s*(\w+),\s*params:\s*(.*?)\)/);
      if (match) {
        try {
          const p = JSON.parse(match[3].replace(/'/g, '"'));
          details.push({ name: match[1], dbTool: match[2], params: p });
        } catch {
          details.push({ name: match[1], dbTool: match[2], params: [] });
        }
      }
    }
  }
  return details;
}

function parseParamDetails(text: string): ParamDetail[] {
  const details: ParamDetail[] = [];
  const lines = text.split("\n");
  let inParams = false;

  for (const line of lines) {
    if (line.includes("参数详情:")) {
      inParams = true;
      continue;
    }
    if (inParams) {
      if (line.includes("详情:") || line.startsWith("场景:") || line.startsWith("全部节点")) {
        inParams = false;
        continue;
      }
      const trimmed = line.trim();
      const match = trimmed.match(/-\s*(\w+)\s*\(默认:\s*([^,]+),\s*值:\s*(.*?)\)/);
      if (match) {
        try {
          const v = JSON.parse(match[3].replace(/'/g, '"'));
          details.push({ name: match[1], default: match[2].trim(), values: v });
        } catch {
          details.push({ name: match[1], default: match[2].trim(), values: [] });
        }
      }
    }
  }
  return details;
}

function parseNodeDetails(text: string): NodeDetail[] {
  const nodes: NodeDetail[] = [];
  const lines = text.split("\n");
  let currentNode: Partial<NodeDetail> | null = null;

  for (const line of lines) {
    const trimmed = line.trim();
    const headerMatch = trimmed.match(/^节点\s*(\d+):/);
    if (headerMatch) {
      if (currentNode && currentNode.id !== undefined) {
        nodes.push(currentNode as NodeDetail);
      }
      currentNode = { id: parseInt(headerMatch[1]) };
      continue;
    }
    if (currentNode) {
      if (trimmed.startsWith("tool:")) {
        currentNode.tool = trimmed.replace("tool:", "").trim();
      } else if (trimmed.startsWith("status:")) {
        currentNode.status = trimmed.replace("status:", "").trim();
      } else if (trimmed.startsWith("pvalues:")) {
        const match = trimmed.match(/pvalues:\s*(.*)/);
        if (match) {
          try {
            const p = JSON.parse(match[1].replace(/'/g, '"'));
            currentNode.pvalues = p;
          } catch { /* ignore */ }
        }
      }
    }
  }
  if (currentNode && currentNode.id !== undefined) {
    nodes.push(currentNode as NodeDetail);
  }
  return nodes;
}

function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    done: "bg-green-100 text-green-700 border-green-200",
    running: "bg-blue-100 text-blue-700 border-blue-200",
    failed: "bg-red-100 text-red-700 border-red-200",
    queued: "bg-yellow-100 text-yellow-700 border-yellow-200",
    pending: "bg-yellow-100 text-yellow-700 border-yellow-200",
    ready: "bg-gray-100 text-gray-700 border-gray-200",
    none: "bg-gray-50 text-gray-400 border-gray-200",
    aborted: "bg-red-50 text-red-500 border-red-200",
  };
  const s = status?.toLowerCase() || "";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${colorMap[s] || "bg-gray-100 text-gray-600 border-gray-200"}`}>
      {status}
    </span>
  );
}

export function TcadProjectInfo({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const summary = parseProjectSummary(contentStr);
  const toolDetails = parseToolDetails(contentStr);
  const paramDetails = parseParamDetails(contentStr);
  const nodeDetails = parseNodeDetails(contentStr);

  if (!summary) {
    // Fallback: show raw text
    return (
      <div className="border border-gray-200 rounded-lg p-3 bg-white">
        <div className="font-mono text-xs whitespace-pre-wrap text-gray-700">{contentStr}</div>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="bg-blue-50 px-4 py-3 border-b border-blue-100 flex items-center gap-2">
        <FolderOpen className="size-4 text-blue-600" />
        <span className="font-medium text-blue-900 text-sm truncate">{summary.path}</span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-px bg-gray-100">
        {[
          { icon: Wrench, label: "工具", value: summary.tools.length },
          { icon: SlidersHorizontal, label: "参数", value: summary.params.length },
          { icon: Layers, label: "步骤", value: summary.steps },
          { icon: Database, label: "实验", value: summary.experiments },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="bg-white px-3 py-2.5 flex flex-col items-center gap-0.5">
            <Icon className="size-3.5 text-gray-400" />
            <span className="text-lg font-semibold text-gray-800">{value}</span>
            <span className="text-xs text-gray-500">{label}</span>
          </div>
        ))}
      </div>

      {/* Tool badges */}
      {summary.tools.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5 font-medium">🛠️ 工具</div>
          <div className="flex flex-wrap gap-1.5">
            {summary.tools.map((t) => (
              <span key={t} className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-100">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Param badges */}
      {summary.params.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5 font-medium">📐 参数</div>
          <div className="flex flex-wrap gap-1.5">
            {summary.params.map((p) => (
              <span key={p} className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-teal-50 text-teal-700 border border-teal-100">
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tool details */}
      {toolDetails.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5 font-medium">🔧 工具详情</div>
          <div className="space-y-1">
            {toolDetails.map((td) => (
              <div key={td.name} className="flex items-center gap-2 text-xs">
                <span className="font-medium text-gray-700">{td.name}</span>
                <span className="text-gray-400">→</span>
                <span className="text-gray-500">{td.dbTool}</span>
                {td.params.length > 0 && (
                  <span className="text-gray-400 ml-1">
                    (参数: {td.params.join(", ")})
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Param details */}
      {paramDetails.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5 font-medium">📊 参数详情</div>
          <div className="space-y-1">
            {paramDetails.map((pd) => (
              <div key={pd.name} className="flex items-center gap-2 text-xs">
                <span className="font-medium text-gray-700">{pd.name}</span>
                <span className="text-gray-400">默认={pd.default}</span>
                {pd.values.length > 0 && (
                  <span className="text-gray-500">值=[{pd.values.join(", ")}]</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Node details */}
      {nodeDetails.length > 0 && (
        <div className="px-4 py-2.5">
          <div className="text-xs text-gray-500 mb-1.5 font-medium">📋 节点信息</div>
          <div className="space-y-1">
            {nodeDetails.map((nd) => (
              <div key={nd.id} className="flex items-center gap-2 text-xs">
                <span className="font-medium text-gray-700">节点 {nd.id}</span>
                {nd.tool && <span className="text-gray-500">({nd.tool})</span>}
                {nd.status && <StatusBadge status={nd.status} />}
                {nd.pvalues && nd.pvalues.length > 0 && (
                  <span className="text-gray-400 text-xs">
                    pvalues=[{nd.pvalues.join(", ")}]
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scenario count footer */}
      {(summary.scenarios > 0 || summary.experiments > 0) && (
        <div className="bg-gray-50 px-4 py-2 border-t border-gray-100 flex gap-4 text-xs text-gray-500">
          <span>📁 场景: {summary.scenarios}</span>
          <span>🧪 实验: {summary.experiments}</span>
        </div>
      )}
    </div>
  );
}
