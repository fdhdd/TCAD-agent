# TCAD Agent

> LangGraph-based AI agent for Synopsys Sentaurus TCAD — natural-language-driven semiconductor simulation.

## Overview

TCAD Agent wraps SWB (Sentaurus WorkBench) operations into LangChain tools and exposes them through a streaming CLI agent powered by DeepSeek (or any OpenAI-compatible LLM). You describe what you want in natural language — the agent opens projects, inspects structures, runs simulations, monitors progress, and displays results.

### Architecture

```
┌──────────────┐     ┌─────────────────────────────────┐     ┌──────────┐
│   CLI/User   │────▶│         LangGraph Agent          │────▶│  swbpy2  │
│  (agent.py)  │     │  create_react_agent + MemorySaver │     │  (SWB)   │
└──────────────┘     │                                  │     └──────────┘
                     │  ┌───────────────────────────┐   │
                     │  │    8 LangChain Tools       │   │
                     │  │  ┌─────────────────────┐  │   │
                     │  │  │TCADProjectTool       │  │   │
                     │  │  │TCADSimulationTool    │  │   │
                     │  │  │TCADStatusTool        │  │   │
                     │  │  │TCADModifyTool        │  │   │
                     │  │  │TCADResultsTool       │  │   │
                     │  │  │TCADTailOutputTool    │  │   │
                     │  │  │TCADCleanupTool       │  │   │
                     │  │  │TCADDisplayResultsTool│  │   │
                     │  │  └─────────────────────┘  │   │
                     │  └───────────────────────────┘   │
                     └─────────────────────────────────┘
```

## Project Structure

```
├── agent.py                  # LangGraph agent: build, stream, CLI
├── tool.py                   # All LangChain tools (8 tools, ~1230 lines)
├── TCAD_SYSTEM_PROMPT.md     # System prompt with workflow rules & constraints
├── run_agent.sh              # Launch script (uses TCAD Python 3.11)
├── .env                      # API key & model config
└── README.md
```

## Tools

| Tool                 | Function                                  | Key Schema Fields                          |
|----------------------|-------------------------------------------|--------------------------------------------|
| `tcad_open_project`  | Open SWB project; query tools/params/nodes| `project_path`, `detail`, `scenario`, `node`|
| `tcad_run_simulation`| Run preprocess + simulation with monitor  | `mode`, `nodes`, `monitor`, `monitor_timeout`|
| `tcad_check_status`  | Query project/node status                | `scenario`, `node`, `status_filter`        |
| `tcad_modify_project`| Add/delete tools, params, experiments     | `action`, `params`                         |
| `tcad_get_results`   | Extract results from completed node       | `node`, `trials`, `delay`                  |
| `tcad_tail_output`   | Tail .out file during simulation          | `node`, `max_lines`, `offset`              |
| `tcad_display_results`| SWB Workbench-style result display       | `detail` (`all`/`overview`/`electrical`)   |
| `tcad_cleanup`       | Clean intermediate files                  | `level`, `nodes`                           |

## Features

### 1. Streaming Output with Reasoning Visibility

Agent streams responses token-by-token. If the LLM provides `reasoning_content` (DeepSeek), it's printed as a collapsible thought block before the final answer.

```
💭 模型思考过程:
   用户要求打开 mosfet 项目，我需要先调用 tcad_open_project。
   项目路径需用户提供，先询问。
💭 思考结束

👤 请提供项目路径。
```

### 2. Simulation Monitoring

When `tcad_run_simulation` is called with `monitor=True` (default), a background thread polls `.out` file content and prints it alongside status changes in real time, without blocking the agent.

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

### 3. SWB Workbench-Style Results Display

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
+──────+──────+───────────────────┘     └──────────+──────────+
| 2    | 0.05 |      3.28e-05       |     | 0.432    | 0.398    |

  Id-Vg Curves (Detailed)

  Node 2:
    Linear region (Vd~0.1V):
          Vg (V)           Id (A/um)
         -0.5000        3.702280e-15
          0.0400        2.092418e-08
          2.2000        3.007258e-04
```

### 4. DeepSeek Compatibility

`agent.py` patches `langchain-openai`'s message converters to preserve `reasoning_content` across turns — required for DeepSeek API. The patch is transparent; no changes needed to user code.

## Setup

### Prerequisites

- Synopsys Sentaurus TCAD X-2025.06 (or compatible)
  - swbpy2 wheel installed into TCAD's Python 3.11
- Python 3.11+ (TCAD bundled)
- OpenAI-compatible API key (DeepSeek, etc.)

### Installation

```bash
# 1. Install swbpy2 into TCAD Python
cd /usr/synopsys/sentaurus/X-2025.06/tcad/X-2025.06/lib
/path/to/tcad/python3.11 -m pip install swbpy2-*.whl swbutils-*.whl

# 2. Install langchain dependencies into TCAD Python
/path/to/tcad/python3.11 -m pip install langchain langchain-openai langgraph python-dotenv numpy pydantic

# 3. Configure environment
cp .env.example .env   # edit with your API key and model settings
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

### Interactive Mode

```bash
./run_agent.sh
```

```
╔══════════════════════════════════════════════╗
║        🤖  TCAD Agent  已启动                ║
║  输入 exit / quit 退出                       ║
╚══════════════════════════════════════════════╝

👤  打开 /home/projects/mosfet 项目
```

### Single Query Mode

```bash
./run_agent.sh -q "打开 /home/projects/mosfet 项目并查看状态"
```

### Options

| Flag | Description |
|------|-------------|
| `-q`, `--query` | Single-turn query (no interactive loop) |
| `-m`, `--model` | Override model name |
| `-t`, `--temperature` | Sampling temperature (default: 0.1) |
| `-v`, `--verbose` | Show intermediate tool calls & returns |

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
👤  打开 /home/huaweitang/STDB/SingleDevice 项目

💭 模型思考过程:
   用户要求打开项目，调用 tcad_open_project。
💭 思考结束

项目: /home/huaweitang/STDB/SingleDevice
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

## Extending

### Add a new tool

1. Define a Pydantic schema class in `tool.py` (inherit `ProjectPathSchema` or `BaseModel`).
2. Create a tool class inheriting `BaseTool` with `name`, `description`, `args_schema`, and `_run`.
3. Add it to the list in `get_tcad_tools()`.

### Update the system prompt

Edit `TCAD_SYSTEM_PROMPT.md` — changes take effect on next agent launch (no restart needed, just re-run `agent.py`).

## Notes

- **Python version**: swbpy2 C++ extensions only work with TCAD's bundled Python 3.11. Always use `run_agent.sh` which sets the correct environment.
- **LD_LIBRARY_PATH**: Must include TCAD's `linux64/lib` for swbpy2 native extensions. Set automatically by `setup_tcad_environment()` and `run_agent.sh`.
- **DeepSeek streaming**: `streaming=False` on ChatOpenAI due to DeepSeek API limitations with streaming + tool calls in langchain.
- **Output files**: SWB places `.out` and `.plt` files in the project root (named `n{N}_des.out`, `IdVgsLin_n{N}_des.plt`, etc.), not in node subdirectories.
