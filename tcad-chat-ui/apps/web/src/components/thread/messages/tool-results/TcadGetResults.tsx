import { ToolMessage } from "@langchain/langgraph-sdk";
import { Database, CheckCircle2, XCircle } from "lucide-react";

export function TcadGetResults({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const lines = contentStr.split("\n");

  // Parse basic info
  const headerMatch = contentStr.match(/节点\s*(\d+)\s*\((\w+)\)\s*结果:/);
  const statusMatch = contentStr.match(/状态:\s*(\w+)/);
  const pathMatch = contentStr.match(/路径:\s*(.+)/);

  const nodeId = headerMatch ? parseInt(headerMatch[1]) : null;
  const toolName = headerMatch ? headerMatch[2] : null;
  const status = statusMatch ? statusMatch[1] : null;
  const nodePath = pathMatch ? pathMatch[1].trim() : null;

  // Extract data JSON
  const dataMatch = contentStr.match(/数据:\s*(\{[\s\S]*)/);
  let dataObj: Record<string, any> | null = null;
  if (dataMatch) {
    try {
      dataObj = JSON.parse(dataMatch[1]);
    } catch {
      // Not valid JSON, leave as null
    }
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center gap-2">
        <Database className="size-4 text-gray-600" />
        <span className="font-medium text-gray-800 text-sm">
          {nodeId ? `节点 #${nodeId} 结果` : "结果提取"}
        </span>
        {toolName && <span className="text-xs text-gray-500">({toolName})</span>}
        {status && (
          <span className="ml-auto">
            {status.toLowerCase() === "done" ? (
              <span className="inline-flex items-center gap-1 text-xs text-green-600">
                <CheckCircle2 className="size-3" /> {status}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs text-red-600">
                <XCircle className="size-3" /> {status}
              </span>
            )}
          </span>
        )}
      </div>

      {/* Node path */}
      {nodePath && (
        <div className="px-4 py-2 border-b border-gray-100">
          <span className="text-xs text-gray-500">路径: </span>
          <code className="text-xs text-gray-700 bg-gray-50 px-1.5 py-0.5 rounded">{nodePath}</code>
        </div>
      )}

      {/* Data display */}
      {dataObj && Object.keys(dataObj).length > 0 ? (
        <div className="px-4 py-3">
          <div className="text-xs text-gray-500 mb-2 font-medium">📊 结果数据</div>
          <div className="space-y-1">
            {Object.entries(dataObj).slice(0, 20).map(([key, value]) => (
              <div key={key} className="flex items-start gap-2 text-xs">
                <span className="font-medium text-gray-700 shrink-0 min-w-[100px]">{key}</span>
                <span className="text-gray-600 break-all font-mono">
                  {typeof value === "object" ? JSON.stringify(value, null, 1) : String(value)}
                </span>
              </div>
            ))}
            {Object.keys(dataObj).length > 20 && (
              <div className="text-xs text-gray-400 mt-1">
                ... 还有 {Object.keys(dataObj).length - 20} 个字段
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="px-4 py-3">
          <div className="font-mono text-xs whitespace-pre-wrap text-gray-600 max-h-[200px] overflow-y-auto">
            {lines.slice(1).join("\n")}
          </div>
        </div>
      )}
    </div>
  );
}
