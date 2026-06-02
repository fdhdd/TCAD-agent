# TCAD Agent

> LangGraph-based AI agent for Synopsys Sentaurus TCAD — natural-language-driven semiconductor simulation, now with a modern web chat UI.

## Overview

TCAD Agent wraps SWB (Sentaurus WorkBench) operations into LangChain tools and exposes them through a streaming AI agent powered by DeepSeek (or any OpenAI-compatible LLM). You describe what you want in natural language — the agent opens projects, inspects structures, runs simulations, monitors progress, and displays results.

The agent is served through a **LangGraph API server** (`langgraph dev`) and comes with a **Next.js chat UI** for interactive use, real-time tool result visualization, and simulation progress monitoring.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Chat UI (Next.js 15)                      │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────────┐  │
│  │   Thread      │  │  Message/Stream   │  │  Tool Result     │  │
│  │   History     │  │  Rendering        │  │  Visualization   │  │
│  └──────────────┘  └────────┬──────────┘  └──────────────────┘  │
└─────────────────────────────┼────────────────────────────────────┘
                              │ SSE (text/event-stream)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                LangGraph API Server (port 2024)                   │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │              LangGraph Agent (graph.py)                       ││
│  │  ┌─────────────────────────────────────────────────────────┐ ││
│  │  │          create_react_agent + 8 Tools                   │ ││
│  │  │  ┌────────────┬───────────┬───────────┬──────────────┐ │ ││
│  │  │  │TCADProject │TCADSimul. │TCADStatus │TCADModify    │ │ ││
│  │  │  ├────────────┼───────────┼───────────┼──────────────┤ │ ││
│  │  │  │TCADResults │TCADTailOut│TCADCleanup│TCADDisplayRes│ │ ││
│  │  │  └────────────┴───────────┴───────────┴──────────────┘ │ ││
│  │  └─────────────────────────────────────────────────────────┘ ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────┐   ┌──────────────────┐
│   swbpy2 (SWB)   │   │  Monitor Sidecar  │
│   Sentaurus API  │   │  (port 2025)      │
└──────────────────┘   │  Real-time .out    │
                       │  progress polling  │
                       └──────────────────┘
```

## Project Structure

```
├── agent.py                  # LangGraph agent: build, stream, CLI
├── graph.py                  # LangGraph API server entry point
├── langgraph.json            # LangGraph server configuration
├── tool.py                   # All LangChain tools (8 tools, ~1230 lines)
├── sim_progress.py           # Simulation monitor HTTP sidecar (port 2025)
├── TCAD_SYSTEM_PROMPT.md     # System prompt with workflow rules & constraints
├── .env                      # API key & model config
│
├── tcad-chat-ui/             # Web chat UI (Next.js 15 Monorepo)
│   └── apps/web/
│       ├── src/
│       │   ├── app/               # Next.js app router (page, layout)
│       │   ├── components/
│       │   │   ├── thread/        # Main chat thread component
│       │   │   │   ├── index.tsx          # Thread layout, input, submit
│       │   │   │   ├── messages/          # AI/Human/Tool message renderers
│       │   │   │   │   └── tool-results/  # 8 TCAD tool visualization components
│       │   │   │   ├── history/           # Thread history sidebar
│       │   │   │   ├── prompt-history/    # Prompt navigation dots
│       │   │   │   └── agent-inbox/       # Human-in-the-loop interrupt UI
│       │   │   └── ui/            # shadcn/ui primitives
│       │   ├── providers/
│       │   │   ├── Stream.tsx     # StreamProvider, setup form
│       │   │   ├── Thread.tsx     # ThreadProvider, thread list
│       │   │   └── client.ts      # LangGraph SDK client factory
│       │   └── lib/               # Utilities
│       ├── .env.local             # NEXT_PUBLIC_API_URL, ASSISTANT_ID
│       └── package.json
│
├── run_agent.sh              # CLI launch script
├── run_server.sh             # Launch LangGraph server + monitor sidecar
└── README.md
```

## Tools

| Tool                   | Function                                    | Key Schema Fields                          |
|------------------------|---------------------------------------------|--------------------------------------------|
| `tcad_open_project`    | Open SWB project; query tools/params/nodes  | `project_path`, `detail`, `scenario`, `node`|
| `tcad_run_simulation`  | Run preprocess + simulation with monitor    | `mode`, `nodes`, `monitor`, `monitor_timeout`|
| `tcad_check_status`    | Query project/node status                   | `scenario`, `node`, `status_filter`        |
| `tcad_modify_project`  | Add/delete tools, params, experiments       | `action`, `params`                         |
| `tcad_get_results`     | Extract results from completed node         | `node`, `trials`, `delay`                  |
| `tcad_tail_output`     | Tail .out file during simulation            | `node`, `max_lines`, `offset`              |
| `tcad_display_results` | SWB Workbench-style result display          | `detail` (`all`/`overview`/`electrical`)   |
| `tcad_cleanup`         | Clean intermediate files                    | `level`, `nodes`                           |

## Features

### 1. Web Chat UI (New)

A full-featured Next.js 15 chat interface replaces the basic CLI:

- **Streaming messages** — Real-time SSE streaming via `@langchain/langgraph-sdk/react`
- **Thread management** — Left sidebar lists all conversation threads, click to switch; plus `New thread` button
- **Message actions** — Regenerate AI responses, branch switching for checkpoint history, Markdown + LaTeX rendering
- **Prompt navigation** — Right-side dot indicators showing user messages at a glance, click to scroll
- **Tool call visibility toggle** — Hide/show detailed tool call cards to keep the conversation clean
- **Auto-scroll** — New messages auto-scroll into view; `Scroll to bottom` button when scrolled up
- **Loading states** — Animated typing indicator during initial response
- **Cancel in-flight** — Cancel a running AI response mid-stream

### 2. TCAD Tool Result Visualizations (New)

Each tool result gets its own rich visual component instead of raw text:

| Tool | Frontend Component | Visualization |
|---|---|---|
| `tcad_open_project` | `TcadProjectInfo` | Project summary card with stats grid (tools, params, steps, experiments), tool/param badges, tool details, param details, node list with status badges |
| `tcad_check_status` | `TcadStatusDashboard` | Status count cards (done/running/failed/queued/pending), node detail list with colored status badges, filtered node search results |
| `tcad_run_simulation` | `TcadSimulationMonitor` | **Live progress dashboard**: real-time polling of monitor sidecar, overall progress bar, per-node cards with status icon + progress bar + convergence details + iteration table; auto-detects completion |
| `tcad_modify_project` | `TcadModifyResult` | Action card with context-aware icon (add/change/delete/save) and human-readable description |
| `tcad_get_results` | `TcadGetResults` | Structured data panel with node path, status, and key-value results (fields limited to 20 with overflow indicator) |
| `tcad_display_results` | `TcadDisplayResults` | Experiment parameter table, node status grid, electrical results table, Id-Vg curve data section; raw/visual toggle |
| `tcad_cleanup` | `TcadGenericResult` | Expandable/collapsible text panel with line count |
| `tcad_tail_output` | `TcadGenericResult` | Same expandable text panel |

### 3. Simulation Monitor Sidecar (New)

`sim_progress.py` runs as an independent HTTP server (port 2025) that:

- Tracks per-node simulation progress (status, Newton iteration errors, convergence state)
- Provides a polling endpoint `GET /sim_progress/{sim_id}` consumed by the frontend
- Updates in real-time as a background thread within the tool
- Auto-detects simulation completion

The frontend `TcadSimulationMonitor` component polls this endpoint every 2 seconds and renders:
- Overall progress bar
- Per-node status cards with animated progress
- Newton iteration convergence table
- Final pass/fail indicator

### 4. Human-in-the-Loop (Agent Inbox)

When the agent encounters an interrupt node (e.g., asking for user confirmation before running simulation), the chat UI renders a dedicated **Agent Inbox** panel with:

- Action request display (what the agent wants to do)
- Accept / Edit / Reject / Ignore controls
- State inspection panel
- Description panel

### 5. Streaming Output with Reasoning Visibility

Agent streams responses token-by-token. If the LLM provides `reasoning_content` (DeepSeek), it's printed as a collapsible thought block before the final answer.

```
💭 模型思考过程:
    用户要求打开 mosfet 项目，我需要先调用 tcad_open_project。
    项目路径需用户提供，先询问。
💭 思考结束

👤 请提供项目路径。
```

### 6. Simulation Monitoring (CLI)

When `tcad_run_simulation` is called with `monitor=True` (default), a background thread polls `.out` file content and prints it alongside status changes in real time.

```
⏳ 启动仿真，同时监控 .out 输出...

  [节点 2 des] Creating initial mesh...
  [节点 2 des] Newton iteration: 0, error: 1.0e+00
  [节点 2 des] Newton iteration: 1, error: 2.3e-03
  📊 节点 2: running, 节点 6: running
  [节点 2 des] Newton iteration: 2, error: 4.1e-06
  📊 节点 2: done, 节点 6: running
  ✅ 全部节点仿真完成！
```

### 7. SWB Workbench-Style Results Display

`tcad_display_results` goes beyond raw `tcad_get_results`: it parses `.plt` files (DF-ISE format) via TCAD's built-in `PltReader`, extracts Id-Vg sweeps for linear/saturation regions, computes Vt via the gm-max method, and formats everything in clean tables.

```
════════════════════════════════════════════════════════════════════════
  TCAD Project: SingleDevice
════════════════════════════════════════════════════════════════════════
  Tools : 3 | Params: 1 | Steps: 4
  Nodes : 10 total, 3 leaf, 3 experiments

────────────────────────────────────────────────────────────────────────
  ⚡ Electrical Results (from .plt files)
────────────────────────────────────────────────────────────────────────

| Node | Lg   | Id_lin@Vg=1V (A/µm)| ... | Vt_lin (V)| Vt_sat (V)|
+──────+──────+─────────────────────+     +───────────+───────────+
| 2    | 0.05 |      3.28e-05       |     | 0.432     | 0.398     |

  Id-Vg Curves (Detailed)

  Node 2:
    Linear region (Vd~0.1V):
          Vg (V)           Id (A/um)
         -0.5000        3.702280e-15
          0.0400        2.092418e-08
          2.2000        3.007258e-04
```

### 8. DeepSeek Compatibility

`agent.py` patches `langchain-openai`'s message converters to preserve `reasoning_content` across turns — required for DeepSeek API. The patch is transparent.

## Setup

### Prerequisites

- Synopsys Sentaurus TCAD (with swbpy2 wheel installed into TCAD's Python)
- Python 3.11+ (TCAD bundled)
- OpenAI-compatible API key (DeepSeek, etc.)
- Node.js 18+ (for chat UI)

### 1. Backend Installation

```bash
# Install swbpy2 into TCAD's Python (adjust path to your TCAD installation)
cd [TCAD-installation-directory]/lib
python3.11 -m pip install swbpy2-*.whl swbutils-*.whl

# Install langchain dependencies into TCAD's Python
python3.11 -m pip install langchain langchain-openai langgraph python-dotenv numpy pydantic

# Configure environment
cp .env.example .env   # edit with your API key and model settings
```

### 2. Chat UI Installation

```bash
cd tcad-chat-ui/apps/web
npm install

# Configure
echo "NEXT_PUBLIC_API_URL=http://localhost:2024" > .env.local
echo "NEXT_PUBLIC_ASSISTANT_ID=tcad_agent" >> .env.local
```

### Configuration (`.env`)

```bash
# Required
API_KEY_NAME=sk-your-api-key-here

# Optional (with defaults)
API_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat
```

## Usage

### Start the LangGraph API Server + Monitor Sidecar

```bash
./run_server.sh
```

This starts:
- LangGraph API server on **port 2024**
- Simulation monitor sidecar on **port 2025**

### Start the Chat UI (separate terminal)

```bash
cd tcad-chat-ui/apps/web
npm run dev
```

Open **http://localhost:5173** in your browser.

### CLI Mode (alternative)

```bash
# Interactive
./run_agent.sh

# Single query
./run_agent.sh -q "打开 /path/to/project 项目并查看状态"
```

### Chat UI Options

| Feature | Description |
|---------|-------------|
| Thread History (left sidebar) | Lists all conversations; click to switch |
| New Thread (top-right button) | Start a fresh conversation |
| Hide Tool Calls (bottom toggle) | Collapse tool call detail cards |
| Prompt Navigation (right dots) | Hover to preview, click to scroll to a user message |
| Regenerate (hover on AI message) | Re-run the AI response from that checkpoint |
| Cancel (bottom button) | Stop an in-progress AI response |

## Workflow

The agent follows a 5-step workflow enforced by the system prompt:

```
Step 0  ─  Clarify requirements (ask user if ambiguous)
Step 1  ─  Open project      (tcad_open_project)
Step 2  ─  Check status      (tcad_check_status)
Step 3  ─  Query details     (tcad_open_project with detail=...)
Step 4  ─  Execute & monitor (tcad_run_simulation + tcad_tail_output)
Step 5  ─  Report            (summarize results in Chinese)
```

The system prompt (`TCAD_SYSTEM_PROMPT.md`) enforces hard constraints:
- Never call tools before opening a project.
- Never run simulation without checking status first.
- One modification at a time.
- Always report errors with actionable diagnostics.

## Example Session

```
👤  打开 /path/to/STDB/SingleDevice 项目

💭 模型思考过程:
    用户要求打开项目，调用 tcad_open_project。
💭 思考结束

项目: /path/to/STDB/SingleDevice
  工具列表: ['sde', 'sdevice', 'svisual']
  参数列表: ['Lg']
  步骤数: 4
  场景数: 1
  实验数: 3

这是一个 SingleDevice 项目，包含 3 个工具和 1 个参数 (Lg)。
需要我查看详情或运行仿真吗？

👤  运行仿真

💭 模型思考过程:
    先检查状态再运行。
💭 思考结束

[调用 tcad_check_status → 状态正常]
[调用 tcad_run_simulation → 实时显示 .out 进度]
[调用 tcad_display_results → 打印 Id-Vg 表格]

✅ 仿真完成。节点 2/6/9 全部 done。
```

## Chat UI Screens

| Screen | Description |
|--------|-------------|
| Setup Form | First-time use: enter API URL, Assistant ID, API Key (or skip if `.env.local` configured) |
| Main Chat | Streaming conversation with tool result cards, thread sidebar, prompt navigation |
| Simulation Monitor | Real-time dashboard: progress bars, per-node status, convergence iteration table |
| Agent Inbox | Human-in-the-loop: accept/edit/reject agent actions with state inspection |
| Thread History | Left sidebar listing all threads with first-message preview |

## Extending

### Add a new tool

1. Define a Pydantic schema class in `tool.py` (inherit `ProjectPathSchema` or `BaseModel`).
2. Create a tool class inheriting `BaseTool` with `name`, `description`, `args_schema`, and `_run`.
3. Add it to the list in `get_tcad_tools()`.
4. (Optional) Add a frontend renderer in `components/thread/messages/tool-results/`.

### Add a new frontend tool result renderer

1. Create a new component in `tcad-chat-ui/apps/web/src/components/thread/messages/tool-results/`.
2. Register it in the `TOOL_RENDERERS` map in `index.tsx`.
3. The component receives `message: ToolMessage` and should handle both structured and raw text content.

### Update the system prompt

Edit `TCAD_SYSTEM_PROMPT.md` — changes take effect on next agent launch.

## Notes

- **Python version**: swbpy2 C++ extensions only work with TCAD's bundled Python 3.11. Always use `run_agent.sh` which sets the correct environment.
- **LD_LIBRARY_PATH**: Must include TCAD's `linux64/lib` for swbpy2 native extensions. Set automatically by `setup_tcad_environment()` and `run_agent.sh`.
- **DeepSeek streaming**: `streaming=False` on ChatOpenAI due to DeepSeek API limitations with streaming + tool calls in langchain.
- **Output files**: SWB places `.out` and `.plt` files in the project root (named `n{N}_des.out`, `IdVgsLin_n{N}_des.plt`, etc.), not in node subdirectories.
- **Chat UI port**: The dev server runs on port 5173 by default (configured in `tcad-chat-ui/apps/web/next.config.ts`).
- **Monitor sidecar**: The simulation progress monitor runs on port 2025. It is optional — the chat UI falls back to showing raw tool output if the monitor is unavailable.
