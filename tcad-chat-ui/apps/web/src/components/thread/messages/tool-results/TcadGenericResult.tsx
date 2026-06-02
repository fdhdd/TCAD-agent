import { ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";

/**
 * Generic fallback renderer for unrecognized tool results.
 * Shows the tool name + the raw content with expand/collapse.
 */
export function TcadGenericResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const contentStr = typeof message.content === "string" ? message.content : String(message.content);
  const lines = contentStr.split("\n");
  const shouldTruncate = lines.length > 6 || contentStr.length > 800;

  const displayedContent = shouldTruncate && !isExpanded
    ? contentStr.length > 800
      ? contentStr.slice(0, 800) + "..."
      : lines.slice(0, 6).join("\n") + "\n..."
    : contentStr;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <div className="bg-gray-50 px-4 py-2.5 border-b border-gray-200 flex items-center gap-2">
        <FileText className="size-4 text-gray-500" />
        <span className="font-medium text-gray-900 text-sm">{message.name}</span>
        {message.tool_call_id && (
          <code className="ml-auto text-xs bg-gray-200 px-1.5 py-0.5 rounded text-gray-600">
            {message.tool_call_id.slice(0, 8)}...
          </code>
        )}
      </div>
      <div className="bg-gray-50/50">
        <div className="p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-gray-700 max-h-[300px] overflow-y-auto">
          {displayedContent}
        </div>
        {shouldTruncate && (
          <motion.button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full py-1.5 flex items-center justify-center border-t border-gray-200 text-gray-400 hover:text-gray-600 hover:bg-gray-100 text-xs gap-1 transition-colors cursor-pointer"
          >
            {isExpanded ? (
              <><ChevronUp className="size-3" /> 收起</>
            ) : (
              <><ChevronDown className="size-3" /> 展开全部 ({lines.length} 行)</>
            )}
          </motion.button>
        )}
      </div>
    </div>
  );
}
