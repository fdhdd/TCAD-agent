import { useStreamContext } from "@/providers/Stream";
import { getContentString } from "../utils";

export default function PromptHistory() {
  const stream = useStreamContext();
  const messages = stream.messages;

  const userMessages = messages.filter((m) => m.type === "human");

  if (userMessages.length === 0) return null;

  const handleScrollTo = (messageId: string | undefined) => {
    if (!messageId) return;
    const el = document.getElementById(`human-msg-${messageId}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  return (
    <div className="flex flex-col items-end gap-3">
      {userMessages.map((msg, i) => (
        <div
          key={msg.id || i}
          className="group relative flex items-center justify-end"
        >
          <div className="absolute right-full mr-2.5 top-1/2 -translate-y-1/2 
                          opacity-0 group-hover:opacity-100 
                          whitespace-nowrap bg-white border border-gray-200 rounded-lg shadow-lg 
                          px-2.5 py-1.5 text-sm text-gray-700 max-w-[280px] truncate
                          transition-all duration-150 pointer-events-none">
            <span className="text-xs text-gray-400 mr-1 font-mono">{i + 1}.</span>
            <span>{getContentString(msg.content)}</span>
          </div>
          <div
            className="w-3 h-3 rounded-full bg-gray-300 hover:bg-gray-500 transition-colors cursor-pointer"
            onClick={() => handleScrollTo(msg.id)}
          />
        </div>
      ))}
    </div>
  );
}
