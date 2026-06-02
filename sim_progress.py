"""
Simulation progress tracker for TCAD Agent.

In-memory store that tracks simulation progress (node statuses, Newton
convergence, iteration errors) and serves it over HTTP so the frontend
can poll for live updates.

Design:
  - Each simulation gets an ID derived from the project path.
  - A monitoring thread (started inside the tool) feeds parsed .out
    data into this store.
  - An embedded HTTP server on port 2025 serves GET /sim_progress/<id>.

Start the server via ``start_monitor_server()`` (called from run_server.sh).
"""

import os
import re
import json
import time
import threading
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Any

# ── In-memory store ───────────────────────────────────────────────

_sim_store: Dict[str, Dict[str, Any]] = {}
_store_lock = threading.Lock()

# ── Regex patterns for .out parsing ──────────────────────────────

RE_ITERATION = re.compile(
    r"Newton iteration:\s*(\d+),\s*error:\s*([\d.eE+\-]+)"
)
RE_CONVERGED = re.compile(r"Convergence\s+achieved", re.IGNORECASE)
RE_NOT_CONVERGED = re.compile(
    r"(?:Convergence\s+NOT\s+achieved|ERROR)", re.IGNORECASE
)
RE_STEP = re.compile(
    r"(?:Transient|Steady-state|DC)\s+(?:simulation|analysis).*?"
    r"(?:step|sweep)\s*:\s*(\d+)",
    re.IGNORECASE,
)
RE_MESH = re.compile(r"(?:Creating|generating)\s+(?:initial\s+)?mesh", re.IGNORECASE)


def make_sim_id(project_path: str) -> str:
    """Deterministic simulation ID from an absolute project path."""
    raw = os.path.abspath(project_path)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def parse_out_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single .out line into a structured event, or None."""
    stripped = line.strip()
    if not stripped:
        return None

    m = RE_ITERATION.search(stripped)
    if m:
        return {
            "type": "iteration",
            "iteration": int(m.group(1)),
            "error": float(m.group(2)),
        }

    if RE_CONVERGED.search(stripped):
        return {"type": "converged", "converged": True, "elapsed": None}
    if RE_NOT_CONVERGED.search(stripped):
        return {"type": "converged", "converged": False, "elapsed": None}

    m = RE_STEP.search(stripped)
    if m:
        return {"type": "step", "step": int(m.group(1))}

    if RE_MESH.search(stripped):
        return {"type": "phase", "phase": "mesh"}

    return None


# ── Progress data helpers ─────────────────────────────────────────

STATUS_WEIGHTS = {
    "waiting": 0,
    "meshing": 15,
    "running": 40,
    "converging": 65,
    "done": 100,
    "failed": 100,
    "aborted": 100,
}


def _estimate_progress(node: Dict) -> float:
    """Estimate completion % for one node based on status + iterations."""
    base = STATUS_WEIGHTS.get(node.get("status", "waiting"), 0)
    iters = node.get("iterations", [])
    if not iters:
        return float(base)
    if node.get("converged") is True:
        return 100.0
    # Each iteration adds incremental progress within "running" phase
    bonus = min(len(iters) * 8, 35)
    return min(float(base + bonus), 99.0)


# ── Public API ───────────────────────────────────────────────────

def create_progress(project_path: str, nodes_info: List[Dict]) -> str:
    """Register a new simulation and return its ID.

    Args:
        project_path: Absolute path to the SWB project.
        nodes_info: List of dicts with ``id`` and ``tool`` keys.

    Returns:
        Simulation ID (16-char hex string).
    """
    sim_id = make_sim_id(project_path)
    now = time.time()
    entry = {
        "sim_id": sim_id,
        "project_path": os.path.abspath(project_path),
        "start_time": now,
        "running": True,
        "nodes": {
            str(n["id"]): {
                "id": n["id"],
                "tool": n.get("tool", "?"),
                "status": "waiting",
                "iterations": [],
                "converged": None,
                "phase": None,
            }
            for n in nodes_info
        },
        "node_order": [str(n["id"]) for n in nodes_info],
    }
    with _store_lock:
        _sim_store[sim_id] = entry
    return sim_id


def update_node_status(sim_id: str, node_id: int, status: str):
    with _store_lock:
        entry = _sim_store.get(sim_id)
        if entry and str(node_id) in entry["nodes"]:
            entry["nodes"][str(node_id)]["status"] = status


def add_iteration(sim_id: str, node_id: int, iteration: int, error: float):
    with _store_lock:
        entry = _sim_store.get(sim_id)
        if entry and str(node_id) in entry["nodes"]:
            node = entry["nodes"][str(node_id)]
            node["iterations"].append({
                "n": iteration,
                "error": error,
                "t": round(time.time() - entry["start_time"], 1),
            })
            node["status"] = "converging"


def set_converged(sim_id: str, node_id: int, converged: bool):
    with _store_lock:
        entry = _sim_store.get(sim_id)
        if entry and str(node_id) in entry["nodes"]:
            node = entry["nodes"][str(node_id)]
            node["converged"] = converged
            node["status"] = "done" if converged else "failed"


def mark_done(sim_id: str):
    with _store_lock:
        if sim_id in _sim_store:
            _sim_store[sim_id]["running"] = False


def feed_line(sim_id: str, node_id: int, line: str):
    """Feed a .out line to the tracker; parsed events update state."""
    event = parse_out_line(line)
    if event is None:
        return
    if event["type"] == "iteration":
        add_iteration(sim_id, node_id, event["iteration"], event["error"])
    elif event["type"] == "converged":
        set_converged(sim_id, node_id, event["converged"])
    elif event["type"] == "phase":
        update_node_status(sim_id, node_id, "meshing")


def get_progress(sim_id: str) -> Optional[Dict]:
    """Get current snapshot of simulation progress (JSON-serialisable)."""
    with _store_lock:
        entry = _sim_store.get(sim_id)
        if not entry:
            return None
        return {
            "sim_id": entry["sim_id"],
            "project_path": entry["project_path"],
            "elapsed_sec": round(time.time() - entry["start_time"], 1),
            "running": entry["running"],
            "nodes": [
                _node_snapshot(n) for n in entry["node_order"]
                if n in entry["nodes"]
            ],
            "overall_progress": _overall_progress(entry),
        }


def _node_snapshot(node: Dict) -> Dict:
    return {
        "id": node["id"],
        "tool": node["tool"],
        "status": node["status"],
        "converged": node["converged"],
        "progress_pct": _estimate_progress(node),
        "iterations": node["iterations"][-20:],  # last 20 iters
        "phase": node["phase"],
    }


def _overall_progress(entry: Dict) -> float:
    nodes = entry.get("nodes", {})
    if not nodes:
        return 0.0
    total = sum(_estimate_progress(n) for n in nodes.values())
    return round(total / len(nodes), 1)


# ── Periodic cleanup ─────────────────────────────────────────────

def _cleanup_loop():
    while True:
        time.sleep(300)
        now = time.time()
        with _store_lock:
            stale = [
                sid for sid, e in _sim_store.items()
                if not e["running"] and (now - e["start_time"]) > 3600
            ]
            for sid in stale:
                del _sim_store[sid]


threading.Thread(target=_cleanup_loop, daemon=True).start()


# ── Embedded HTTP server ─────────────────────────────────────────

class _ProgressHandler(BaseHTTPRequestHandler):
    """Serves GET /sim_progress/<id> as JSON."""

    def do_GET(self):
        path = self.path
        if path.startswith("/sim_progress/"):
            sim_id = path.split("/")[-1]
            data = get_progress(sim_id)
            if data:
                self._json(data)
            else:
                self._json({"error": "not_found", "sim_id": sim_id}, 404)
        elif path == "/health":
            self._json({"ok": True})
        else:
            self._json({"error": "not_found"}, 404)

    def do_OPTIONS(self):
        self._cors()
        self.send_response(204)
        self.end_headers()

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        pass  # quiet


_server: Optional[HTTPServer] = None


def start_monitor_server(port: int = 2025):
    """Start the embedded HTTP server in a daemon thread."""
    global _server
    if _server is not None:
        return
    _server = HTTPServer(("0.0.0.0", port), _ProgressHandler)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
