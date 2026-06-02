import { ToolMessage } from "@langchain/langgraph-sdk";
import { Play, CheckCircle2, LoaderCircle, FolderTree, AlertCircle } from "lucide-react";

interface SimNodeInfo {
  id: number;
  tool: string;
  status: string;
  path?: string;
}

function parseNodes(text: string): SimNodeInfo[] {
  const nodes: SimNodeInfo[] = [];
  const lines = text.split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    const match = trimmed.match(/节点\s*(\d+)\s*\((\w+)\):\s*(\w+)/);
    if (match) {
      nodes.push({ id: parseInt(match[1]), tool: match[2], status: match[3] });
      continue;
    }
    const pathMatch = trimmed.match(/节点\s*(\d+)\s*\((\w+)\)\s*路径:\s*(.+)/);
    if (pathMatch) {
      nodes.push({ id: parseInt(pathMatch[1]), tool: pathMatch[2], status: "", path: pathMatch[3].trim() });
    }
  }
  return nodes;
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
    submitted: "bg-blue-50 text-blue-700 border-blue-200",
  };
  const s = status?.toLowerCase() || "";
  const base = colorMap[s] || "bg-gray-50 text-gray-600 border-gray-200";
  const sizeClass = size === "md" ? "px-2.5 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1 rounded-md font-medium border ${base} ${sizeClass}`}>
      {status}
    </span>
  );
}

export function TcadSimulationResult({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const nodes = parseNodes(contentStr);

  const hasPreprocess = contentStr.includes("预处理") || contentStr.includes("spp");
  const preprocessDone = contentStr.includes("✅") && (contentStr.includes("预处理") || contentStr.includes("spp"));
  const hasSubmitted = contentStr.includes("已提交");
  const allDone = nodes.length > 0 && nodes.every((n) => n.status.toLowerCase() === "done");

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center gap-2">
        <Play className="size-4 text-gray-600" />
        <span className="font-medium text-gray-800 text-sm">仿真执行结果</span>
        {allDone && (
          <span className="ml-auto flex items-center gap-1 text-xs text-green-600 font-medium">
            <CheckCircle2 className="size-3.5" /> 全部完成
          </span>
        )}
      </div>

      {/* Steps */}
      <div className="px-4 py-3 space-y-2">
        {hasPreprocess && (
          <div className="flex items-center gap-2 text-sm">
            {preprocessDone ? (
              <CheckCircle2 className="size-4 text-green-500 shrink-0" />
            ) : (
              <LoaderCircle className="size-4 text-blue-500 shrink-0 animate-spin" />
            )}
            <span className={preprocessDone ? "text-green-700" : "text-gray-600"}>
              预处理 (spp)
            </span>
            {preprocessDone && <span className="text-xs text-green-500 ml-auto">完成</span>}
          </div>
        )}

        {hasSubmitted && (
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="size-4 text-blue-500 shrink-0" />
            <span className="text-gray-700">仿真已提交</span>
          </div>
        )}

        {nodes.length > 0 && (
          <div className="mt-3">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-2 font-medium">
              <FolderTree className="size-3.5" /> 仿真节点
            </div>
            <div className="space-y-1.5">
              {nodes.map((nd) => (
                <div key={nd.id} className="flex items-center gap-2 text-xs py-0.5">
                  <span className="font-mono text-gray-400 w-10 shrink-0">#{nd.id}</span>
                  {nd.status ? (
                    <StatusBadge status={nd.status} />
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                  <span className="text-gray-600">{nd.tool}</span>
                  {nd.path && <span className="text-gray-400 truncate max-w-[200px]">{nd.path}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {!hasPreprocess && !hasSubmitted && nodes.length === 0 && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <AlertCircle className="size-4 text-gray-400 shrink-0" />
            <span>仿真执行中，请查看详细输出</span>
          </div>
        )}
      </div>
    </div>
  );
}
