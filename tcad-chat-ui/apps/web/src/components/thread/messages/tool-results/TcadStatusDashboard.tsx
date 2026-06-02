import { ToolMessage } from "@langchain/langgraph-sdk";
import { Activity, CheckCircle2, XCircle, Clock, Play, AlertTriangle } from "lucide-react";

interface NodeStatusInfo {
  id: number;
  status: string;
  tool?: string;
}

interface StatusCounts {
  [status: string]: number;
}

function StatusIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === "done") return <CheckCircle2 className="size-3.5 text-green-500" />;
  if (s === "running" || s === "queued") return <Play className="size-3.5 text-blue-500" />;
  if (s === "failed" || s === "aborted") return <XCircle className="size-3.5 text-red-500" />;
  if (s === "pending") return <Clock className="size-3.5 text-yellow-500" />;
  return <AlertTriangle className="size-3.5 text-gray-400" />;
}

function StatusBadge({ status, size = "sm" }: { status: string; size?: "sm" | "md" }) {
  const colorMap: Record<string, string> = {
    done: "bg-green-50 text-green-700 border-green-200",
    running: "bg-blue-50 text-blue-700 border-blue-200",
    failed: "bg-red-50 text-red-700 border-red-200",
    queued: "bg-yellow-50 text-yellow-700 border-yellow-200",
    pending: "bg-yellow-50 text-yellow-700 border-yellow-200",
    ready: "bg-gray-50 text-gray-600 border-gray-200",
    none: "bg-gray-50 text-gray-400 border-gray-200",
    aborted: "bg-red-50 text-red-500 border-red-200",
  };
  const s = status?.toLowerCase() || "";
  const base = colorMap[s] || "bg-gray-50 text-gray-600 border-gray-200";
  const sizeClass = size === "md" ? "px-2.5 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md font-medium border ${base} ${sizeClass}`}>
      <StatusIcon status={status} />
      {status}
    </span>
  );
}

function parseStatusCounts(text: string): StatusCounts {
  const counts: StatusCounts = {};
  const lines = text.split("\n");
  let inStats = false;

  for (const line of lines) {
    if (line.includes("叶子节点状态统计") || line.includes("Status:")) {
      inStats = true;
      continue;
    }
    if (inStats) {
      const trimmed = line.trim();
      const match = trimmed.match(/^(\w+):\s*(\d+)/);
      if (match) {
        counts[match[1]] = parseInt(match[2]);
      } else if (!trimmed.startsWith("(") && trimmed.length > 0 && !trimmed.includes(":")) {
        inStats = false;
      }
    }
  }
  return counts;
}

function parseNodeStatusList(text: string): NodeStatusInfo[] {
  const nodes: NodeStatusInfo[] = [];
  const lines = text.split("\n");

  for (const line of lines) {
    const trimmed = line.trim();
    // "节点 2 状态: done"
    const match = trimmed.match(/节点\s*(\d+)\s*状态:\s*(\w+)/);
    if (match) {
      nodes.push({ id: parseInt(match[1]), status: match[2] });
      continue;
    }
    // "2      sdevice           done         leaf"
    const tableMatch = trimmed.match(/^\s*(\d+)\s{2,}(\w+)\s{2,}(\w+)/);
    if (tableMatch) {
      nodes.push({ id: parseInt(tableMatch[1]), tool: tableMatch[2], status: tableMatch[3] });
    }
  }
  return nodes;
}

function parseFilteredNodes(text: string): number[] {
  const match = text.match(/状态\s*'[^']+'\s*的节点:\s*(\[.*?\])/);
  if (match) {
    try {
      return JSON.parse(match[1]);
    } catch { /* ignore */ }
  }
  const simpleMatch = text.match(/状态\s*'([^']+)'\s*的节点:\s*\[(.*?)\]/);
  if (simpleMatch) {
    return simpleMatch[2].split(",").map((s) => parseInt(s.trim())).filter((n) => !isNaN(n));
  }
  return [];
}

function parseOverallStatus(text: string): string {
  const match = text.match(/项目状态:\s*(\w+)/);
  return match ? match[1] : "";
}

export function TcadStatusDashboard({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const counts = parseStatusCounts(contentStr);
  const nodes = parseNodeStatusList(contentStr);
  const filteredNodes = parseFilteredNodes(contentStr);
  const overallStatus = parseOverallStatus(contentStr);

  const hasStructuredData = Object.keys(counts).length > 0 || nodes.length > 0 || filteredNodes.length > 0 || overallStatus;

  if (!hasStructuredData) {
    return (
      <div className="border border-gray-200 rounded-lg p-3 bg-white">
        <div className="font-mono text-xs whitespace-pre-wrap text-gray-700">{contentStr}</div>
      </div>
    );
  }

  // Sort status order for display
  const statusOrder = ["done", "running", "queued", "pending", "ready", "none", "failed", "aborted"];
  const sortedStatuses = Object.keys(counts).sort(
    (a, b) => statusOrder.indexOf(a.toLowerCase()) - statusOrder.indexOf(b.toLowerCase())
  );

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center gap-2">
        <Activity className="size-4 text-gray-600" />
        <span className="font-medium text-gray-800 text-sm">节点状态概览</span>
        {overallStatus && (
          <span className="ml-auto text-xs text-gray-500">
            项目状态: {overallStatus}
          </span>
        )}
      </div>

      {/* Status count cards */}
      {sortedStatuses.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-gray-100">
          {sortedStatuses.map((status) => {
            const count = counts[status];
            const bgMap: Record<string, string> = {
              done: "bg-green-50",
              running: "bg-blue-50",
              failed: "bg-red-50",
              queued: "bg-yellow-50",
              pending: "bg-yellow-50",
              ready: "bg-gray-50",
              none: "bg-gray-50",
              aborted: "bg-red-50",
            };
            return (
              <div key={status} className={`${bgMap[status.toLowerCase()] || "bg-white"} px-3 py-2.5 flex flex-col items-center`}>
                <span className="text-xl font-bold text-gray-800">{count}</span>
                <StatusBadge status={status} />
              </div>
            );
          })}
        </div>
      )}

      {/* Filtered nodes */}
      {filteredNodes.length > 0 && (
        <div className="px-4 py-2.5 border-b border-gray-100">
          <div className="text-xs text-gray-500 mb-1.5 font-medium">🔍 搜索结果</div>
          <div className="flex flex-wrap gap-1.5">
            {filteredNodes.map((nid) => (
              <span key={nid} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                节点 {nid}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Node list */}
      {nodes.length > 0 && (
        <div className="px-4 py-2.5">
          <div className="text-xs text-gray-500 mb-2 font-medium">📋 节点明细</div>
          <div className="space-y-1 max-h-[240px] overflow-y-auto">
            {nodes.map((nd) => (
              <div key={nd.id} className="flex items-center gap-2 text-xs py-0.5">
                <span className="font-mono text-gray-400 w-12 shrink-0">#{nd.id}</span>
                <StatusBadge status={nd.status} />
                {nd.tool && <span className="text-gray-500 ml-1">({nd.tool})</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw status info fallback for unparsed data */}
      {sortedStatuses.length === 0 && nodes.length === 0 && filteredNodes.length === 0 && (
        <div className="px-4 py-3">
          <div className="font-mono text-xs whitespace-pre-wrap text-gray-600">{contentStr}</div>
        </div>
      )}
    </div>
  );
}
