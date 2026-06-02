import { ToolMessage } from "@langchain/langgraph-sdk";
import { useEffect, useState, useRef, useCallback } from "react";
import {
  Play, CheckCircle2, XCircle, AlertCircle, Clock,
  LoaderCircle, BarChart3, Activity,
} from "lucide-react";
import { TcadSimulationResult } from "./TcadSimulationResult";

const MONITOR_URL =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_MONITOR_URL) ||
  "http://localhost:2025";
const POLL_INTERVAL_MS = 2000;

/* ── Type definitions matching sim_progress.py ─────────────────── */

interface Iteration {
  n: number;
  error: number;
  t: number;
}

interface SimNode {
  id: number;
  tool: string;
  status: string;
  converged: boolean | null;
  progress_pct: number;
  iterations: Iteration[];
  phase: string | null;
}

interface SimProgressData {
  sim_id: string;
  project_path: string;
  elapsed_sec: number;
  running: boolean;
  nodes: SimNode[];
  overall_progress: number;
}

/* ── Helpers ───────────────────────────────────────────────────── */

function extractSimId(content: string): string | null {
  const m = content.match(/仿真ID:\s*([a-f0-9]{16})/);
  return m ? m[1] : null;
}

/* ── Sub-components ────────────────────────────────────────────── */

function ProgressBar({ pct, status }: { pct: number; status: string }) {
  const colorMap: Record<string, string> = {
    done: "bg-green-500",
    failed: "bg-red-500",
    running: "bg-blue-500",
    converging: "bg-indigo-500",
    meshing: "bg-amber-500",
    waiting: "bg-gray-300",
    aborted: "bg-red-400",
  };
  const barColor = colorMap[status] || "bg-blue-500";
  const displayPct = Math.min(Math.max(pct, 0), 100);

  return (
    <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ease-out ${barColor}`}
        style={{ width: `${displayPct}%` }}
      />
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  const s = status.toLowerCase();
  if (s === "done") return <CheckCircle2 className="size-4 text-green-500" />;
  if (s === "failed" || s === "aborted") return <XCircle className="size-4 text-red-500" />;
  if (s === "running" || s === "converging") return <LoaderCircle className="size-4 text-blue-500 animate-spin" />;
  if (s === "meshing") return <Activity className="size-4 text-amber-500" />;
  return <Clock className="size-4 text-gray-400" />;
}

const STATUS_LABEL: Record<string, string> = {
  waiting: "等待中",
  meshing: "网格划分",
  running: "运行中",
  converging: "收敛中",
  done: "完成",
  failed: "失败",
  aborted: "已中止",
};

function NodeCard({ node, index }: { node: SimNode; index: number }) {
  const lastIter = node.iterations.length > 0
    ? node.iterations[node.iterations.length - 1]
    : null;

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <StatusIcon status={node.status} />
          <span className="font-semibold text-sm text-gray-800">
            节点 #{node.id}
          </span>
          <span className="text-xs text-gray-400">({node.tool})</span>
        </div>
        <span className="text-xs font-medium text-gray-500">
          {STATUS_LABEL[node.status] || node.status}
        </span>
      </div>

      <div className="px-3 py-2 space-y-2">
        <ProgressBar pct={node.progress_pct} status={node.status} />

        <div className="flex justify-between text-xs text-gray-400">
          <span>{Math.round(node.progress_pct)}%</span>
          {lastIter && (
            <span>
              迭代 #{lastIter.n} error={lastIter.error.toExponential(2)}
            </span>
          )}
        </div>

        {node.converged !== null && (
          <div className={`flex items-center gap-1.5 text-xs font-medium ${
            node.converged ? "text-green-600" : "text-red-600"
          }`}>
            {node.converged ? (
              <><CheckCircle2 className="size-3.5" /> 收敛</>
            ) : (
              <><XCircle className="size-3.5" /> 未收敛</>
            )}
          </div>
        )}

        {node.iterations.length > 0 && (
          <details className="group">
            <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 select-none">
              收敛详情 ({node.iterations.length} 步)
            </summary>
            <div className="mt-1 max-h-[160px] overflow-y-auto border border-gray-100 rounded text-xs font-mono">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-50 text-gray-500">
                    <th className="px-2 py-1 text-left">#</th>
                    <th className="px-2 py-1 text-right">Error</th>
                    <th className="px-2 py-1 text-right">时间(秒)</th>
                  </tr>
                </thead>
                <tbody>
                  {node.iterations.map((it) => (
                    <tr key={it.n} className="border-t border-gray-50 hover:bg-gray-50">
                      <td className="px-2 py-0.5 text-gray-500">{it.n}</td>
                      <td className="px-2 py-0.5 text-right text-gray-700 font-medium">
                        {it.error.toExponential(3)}
                      </td>
                      <td className="px-2 py-0.5 text-right text-gray-400">
                        {it.t.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="border border-gray-200 rounded-lg p-6 bg-white text-center">
      <BarChart3 className="size-8 text-gray-300 mx-auto mb-2" />
      <p className="text-sm text-gray-500">等待仿真启动...</p>
    </div>
  );
}

/* ── Main component ────────────────────────────────────────────── */

export function TcadSimulationMonitor({ message }: { message: ToolMessage }) {
  const contentStr = typeof message.content === "string" ? message.content : "";
  const simId = extractSimId(contentStr);
  const [data, setData] = useState<SimProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchProgress = useCallback(async () => {
    if (!simId) return;
    try {
      const res = await fetch(`${MONITOR_URL}/sim_progress/${simId}`);
      if (!res.ok) {
        if (res.status === 404) return; // not yet available
        throw new Error(`HTTP ${res.status}`);
      }
      const json: SimProgressData = await res.json();
      setData(json);
      setError(null);
      if (!json.running) {
        // stop polling when simulation completes
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch (e: any) {
      setError(e.message || "poll error");
    }
  }, [simId]);

  useEffect(() => {
    if (!simId) return;
    // Initial fetch immediately
    fetchProgress();
    // Then poll
    intervalRef.current = setInterval(fetchProgress, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [simId, fetchProgress]);

  if (!simId) {
    return <TcadSimulationResult message={message} />;
  }

  const isDone = data && !data.running;
  const allOk = isDone && data.nodes.every((n) => n.status === "done");

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className={`px-4 py-2.5 flex items-center gap-2 border-b ${
        isDone
          ? allOk ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
          : "bg-blue-50 border-blue-200"
      }`}>
        {isDone ? (
          allOk
            ? <><CheckCircle2 className="size-4 text-green-600" /><span className="font-medium text-green-800 text-sm">仿真完成</span></>
            : <><XCircle className="size-4 text-red-600" /><span className="font-medium text-red-800 text-sm">仿真结束（有失败节点）</span></>
        ) : (
          <><LoaderCircle className="size-4 text-blue-600 animate-spin" /><span className="font-medium text-blue-800 text-sm">仿真运行中</span></>
        )}
        {data && (
          <span className="ml-auto text-xs text-gray-500">
            {data.elapsed_sec.toFixed(0)}秒
            {!isDone && ` | ${data.overall_progress}%`}
          </span>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-yellow-50 border-b border-yellow-100 flex items-center gap-2 text-xs text-yellow-700">
          <AlertCircle className="size-3.5 shrink-0" />
          <span>进度更新暂不可用: {error}</span>
        </div>
      )}

      {/* Overall progress bar */}
      {data && (
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-100">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>总体进度</span>
            <span>{data.overall_progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                isDone
                  ? allOk ? "bg-green-500" : "bg-red-400"
                  : "bg-blue-500"
              }`}
              style={{ width: `${Math.min(data.overall_progress, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Node cards */}
      <div className="p-3 space-y-2">
        {data ? (
          data.nodes.map((node, idx) => (
            <NodeCard key={node.id} node={node} index={idx} />
          ))
        ) : (
          <EmptyState />
        )}
      </div>

      {/* Footer with raw content toggle */}
      {contentStr && (
        <details className="group border-t border-gray-100">
          <summary className="px-4 py-2 text-xs text-gray-400 cursor-pointer hover:text-gray-600 select-none bg-gray-50/50">
            查看完整输出
          </summary>
          <div className="p-3 font-mono text-xs whitespace-pre-wrap text-gray-600 max-h-[200px] overflow-y-auto bg-gray-50/30">
            {contentStr}
          </div>
        </details>
      )}
    </div>
  );
}
