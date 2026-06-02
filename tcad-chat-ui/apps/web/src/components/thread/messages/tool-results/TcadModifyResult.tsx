import { ToolMessage } from "@langchain/langgraph-sdk";
import { Pencil, Plus, Trash2, Save, GitBranch } from "lucide-react";

type ModifyAction = "add_tool" | "add_param" | "add_experiment" | "change_node" | "change_param" | "delete_param" | "delete_tool" | "save" | "unknown";

function classifyModify(text: string): { action: ModifyAction; detail: string } {
  if (text.includes("已添加到") && text.includes("工具")) return { action: "add_tool", detail: text };
  if (text.includes("已添加到") && text.includes("参数")) return { action: "add_param", detail: text };
  if (text.includes("已添加到场景")) return { action: "add_experiment", detail: text };
  if (text.includes("的值已从") && text.includes("变更为")) return { action: "change_node", detail: text };
  if (text.includes("的值已从") && text.includes("变更为")) return { action: "change_param", detail: text };
  if (text.includes("已删除") && text.includes("参数")) return { action: "delete_param", detail: text };
  if (text.includes("已删除") && text.includes("工具")) return { action: "delete_tool", detail: text };
  if (text.includes("已保存")) return { action: "save", detail: text };
  return { action: "unknown", detail: text };
}

function ActionIcon({ action }: { action: ModifyAction }) {
  const className = "size-4 shrink-0";
  switch (action) {
    case "add_tool":
    case "add_param":
    case "add_experiment":
      return <Plus className={`${className} text-green-500`} />;
    case "change_node":
    case "change_param":
      return <Pencil className={`${className} text-blue-500`} />;
    case "delete_param":
    case "delete_tool":
      return <Trash2 className={`${className} text-red-500`} />;
    case "save":
      return <Save className={`${className} text-indigo-500`} />;
    default:
      return <GitBranch className={`${className} text-gray-500`} />;
  }
}

const actionLabels: Record<ModifyAction, string> = {
  add_tool: "添加工具",
  add_param: "添加参数",
  add_experiment: "添加实验",
  change_node: "修改节点",
  change_param: "修改参数",
  delete_param: "删除参数",
  delete_tool: "删除工具",
  save: "保存项目",
  unknown: "修改",
};

export function TcadModifyResult({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const { action, detail } = classifyModify(contentStr);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <div className="px-4 py-2.5 flex items-center gap-2">
        <ActionIcon action={action} />
        <span className="font-medium text-gray-800 text-sm">{actionLabels[action]}</span>
      </div>
      <div className="px-4 pb-3">
        <p className="text-sm text-gray-600">{detail}</p>
      </div>
    </div>
  );
}
