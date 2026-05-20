import os
import sys
import time
import threading
import logging
from typing import Any, Dict, List, Optional, Type
import numpy as np
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

TCAD_ROOT = os.environ.get("STROOT", "/usr/synopsys/sentaurus/X-2025.06")
TCAD_RELEASE = os.environ.get("STRELEASE", "X-2025.06")


def setup_tcad_environment() -> None:
    if not os.environ.get("STROOT"):
        os.environ["STROOT"] = TCAD_ROOT
    if not os.environ.get("STRELEASE"):
        os.environ["STRELEASE"] = TCAD_RELEASE
    lib_path = f"{TCAD_ROOT}/tcad/{TCAD_RELEASE}/linux64/lib/"
    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    if lib_path not in ld_path:
        os.environ["LD_LIBRARY_PATH"] = f"{lib_path}:{ld_path}" if ld_path else lib_path
    bin_path = f"{TCAD_ROOT}/bin"
    if bin_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{bin_path}:{os.environ['PATH']}"


_swb_imported: bool = False


def _ensure_swbpy2():
    global _swb_imported
    if _swb_imported:
        return
    setup_tcad_environment()
    try:
        # swbpy2 C++ extensions require LD_LIBRARY_PATH to point to TCAD libs
        global Deck, Gtree, Standards, SWB_ERR_MSG
        from swbpy2 import Deck as _Deck
        from swbpy2.gtree import Gtree as _Gtree
        from swbpy2.tool import Standards as _Standards
        Deck = _Deck
        Gtree = _Gtree
        Standards = _Standards
        SWB_ERR_MSG = None
        _swb_imported = True
        logger.info("swbpy2 导入成功")
    except ImportError as e:
        SWB_ERR_MSG = (
            f"swbpy2 导入失败: {e}\n"
            f"请确认 TCAD Python 环境已安装 swbpy2 wheel 包:\n"
            f"  cd {TCAD_ROOT}/tcad/{TCAD_RELEASE}/lib\n"
            f"  pip install swbpy2-*.whl swbutils-*.whl\n"
            f"并设置环境变量:\n"
            f"  export STROOT={TCAD_ROOT}\n"
            f"  export STRELEASE={TCAD_RELEASE}\n"
            f"  export LD_LIBRARY_PATH={TCAD_ROOT}/tcad/{TCAD_RELEASE}/linux64/lib:$LD_LIBRARY_PATH"
        )
        _swb_imported = False
        raise ImportError(SWB_ERR_MSG)


_open_decks: Dict[str, Any] = {}


def _get_deck(project_path: str, hierarchical: bool = True) -> Any:
    _ensure_swbpy2()
    abs_path = os.path.abspath(project_path)
    if abs_path in _open_decks:
        return _open_decks[abs_path]
    deck = Deck(abs_path, hierarchical)
    _open_decks[abs_path] = deck
    return deck


def _get_tree(project_path: str) -> Any:
    deck = _get_deck(project_path)
    return deck.getGtree()


class ProjectPathSchema(BaseModel):
    project_path: str = Field(description="SWB 项目目录的绝对路径")


class InspectProjectSchema(ProjectPathSchema):
    detail: str = Field(
        default="summary",
        description="查询级别: 'summary'(默认) | 'tools' | 'params' | 'nodes' | 'scenarios' | 'all'"
    )
    scenario: str = Field(default="all", description="场景名称，默认 'all' 表示全部")
    node: Optional[int] = Field(default=None, description="指定查询的节点编号")


class RunSimulationSchema(ProjectPathSchema):
    mode: str = Field(
        default="both",
        description="执行模式: 'preprocess' | 'run' | 'both'(默认) | 'run_nodes'"
    )
    nodes: Optional[List[int]] = Field(
        default=None,
        description="要运行的节点列表(仅 mode='run_nodes' 时有效)"
    )
    preprocess_kw: Optional[Dict[str, Any]] = Field(
        default=None,
        description="传递给 preprocess() 的额外参数"
    )
    run_kw: Optional[Dict[str, Any]] = Field(
        default=None,
        description="传递给 run() 的额外参数，如 queue='lsf', maxExperiments=4"
    )
    monitor: bool = Field(
        default=True,
        description="提交后自动监控仿真进度并实时打印 .out 输出（默认开启）"
    )
    monitor_timeout: int = Field(
        default=300,
        description="监控超时秒数，默认 300 秒（5 分钟）"
    )


class StatusSchema(ProjectPathSchema):
    scenario: str = Field(default="all", description="场景名称")
    node: Optional[int] = Field(default=None, description="指定节点编号；提供此项则只查询该节点状态")
    status_filter: Optional[str] = Field(
        default=None,
        description="按状态过滤: none|queued|ready|pending|running|done|failed|aborted"
    )


class ModifyProjectSchema(ProjectPathSchema):
    action: str = Field(
        description=(
            "修改操作类型:\n"
            "  add_tool      — 添加工具: tool_name(str), db_tool_name(str), step(int)\n"
            "  add_param     — 添加参数: param_name(str), default_value(str), step(int)\n"
            "  add_experiment— 添加实验: pvalues(list), scenario(str, 默认'default')\n"
            "  change_node   — 修改节点值: node(int), value(str)\n"
            "  change_param  — 修改参数值: param(str), values(list)\n"
            "  delete_param  — 删除参数: param(str)\n"
            "  delete_tool   — 删除工具: tool(str)\n"
            "  save          — 保存项目\n"
        )
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="操作参数字典，详见 action 描述"
    )


class ResultsSchema(ProjectPathSchema):
    node: int = Field(description="要提取结果的节点编号")
    trials: int = Field(default=3, description="等待结果文件的重试次数")
    delay: int = Field(default=3, description="每次重试间的等待秒数")


class TCADProjectTool(BaseTool):
    name: str = "tcad_open_project"
    description: str = (
        "打开一个 SWB 项目并返回其基本信息(工具列表、参数列表、场景数、实验数等)。"
        "在运行其他 TCAD 工具之前，通常需要先调用此工具。"
    )
    args_schema: Type[BaseModel] = InspectProjectSchema

    def _run(self, project_path: str, detail: str = "summary",
             scenario: str = "all", node: Optional[int] = None) -> str:
        try:
            _ensure_swbpy2()
            _get_deck(project_path)
            tree = _get_tree(project_path)

            if detail == "summary":
                tools = tree.AllTools()
                params = tree.AllPnames()
                n_scenarios = len(tree.AllScenarios())
                n_experiments = tree.NExperiments()
                n_steps = tree.NSteps()
                return (
                    f"项目: {os.path.abspath(project_path)}\n"
                    f"  工具列表: {tools}\n"
                    f"  参数列表: {params}\n"
                    f"  步骤数: {n_steps}\n"
                    f"  场景数: {n_scenarios}\n"
                    f"  实验数: {n_experiments}\n"
                )

            result_parts = [f"项目: {os.path.abspath(project_path)}"]

            if detail in ("tools", "all"):
                tools = tree.AllTools()
                tool_info = []
                for t in tools:
                    dbtool = tree.DBTool(t)
                    params_of_tool = tree.ToolPnames(t)
                    tool_info.append(f"  - {t} (db: {dbtool}, params: {params_of_tool})")
                result_parts.append("工具详情:\n" + "\n".join(tool_info))

            if detail in ("params", "all"):
                params = tree.AllPnames()
                param_info = []
                for p in params:
                    try:
                        default_val = tree.PdefaultValue(p)
                        values = tree.GetParamValues(p)
                        param_info.append(f"  - {p} (默认: {default_val}, 值: {values})")
                    except Exception:
                        param_info.append(f"  - {p}")
                result_parts.append("参数详情:\n" + "\n".join(param_info))

            if detail in ("scenarios", "all"):
                scenarios = tree.AllScenarios()
                result_parts.append(f"场景: {scenarios}")

            if detail in ("nodes", "all"):
                if node is not None:
                    if tree.NodeExists(node):
                        data = tree.NodeData(node)
                        status = tree.NodeStatus(node)
                        tool_name = tree.NodeTool(node)
                        pvals = tree.NodePvalues(node)
                        result_parts.append(
                            f"节点 {node}:\n"
                            f"  tool: {tool_name}\n"
                            f"  status: {status}\n"
                            f"  pvalues: {pvals}\n"
                            f"  data: {data}"
                        )
                    else:
                        result_parts.append(f"节点 {node} 不存在")
                else:
                    all_nodes = tree.AllNodes(scenario)
                    leaf_nodes = tree.AllLeafNodes(scenario)
                    result_parts.append(
                        f"全部节点: {all_nodes}\n"
                        f"叶子节点: {leaf_nodes}"
                    )

            return "\n".join(result_parts)

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"打开项目失败: {type(e).__name__}: {e}"


class TCADSimulationTool(BaseTool):
    name: str = "tcad_run_simulation"
    description: str = (
        "对 SWB 项目执行预处理(spp)和/或运行仿真(gsub)。\n"
        "mode 支持:\n"
        "  'preprocess'  — 只做预处理(生成 command 文件)\n"
        "  'run'         — 直接运行(需已预处理)\n"
        "  'both'        — 先预处理再运行(默认)\n"
        "可通过 run_kw 传递 gsub 参数，如 queue, maxExperiments 等。"
    )
    args_schema: Type[BaseModel] = RunSimulationSchema

    def _run(self, project_path: str, mode: str = "both",
             nodes: Optional[List[int]] = None,
             preprocess_kw: Optional[Dict[str, Any]] = None,
             run_kw: Optional[Dict[str, Any]] = None,
             monitor: bool = True,
             monitor_timeout: int = 300) -> str:
        try:
            _ensure_swbpy2()
            deck = _get_deck(project_path)
            tree = _get_tree(project_path)
            pp_kw = preprocess_kw or {}
            r_kw = run_kw or {}

            result_lines = []

            # ── 预处理 ──
            if mode in ("preprocess", "both"):
                if nodes:
                    pp_kw["nodes"] = nodes
                deck.preprocess(**pp_kw)
                result_lines.append("✅ 预处理(spp) 完成")

            # ── 确定将要仿真的节点 ──
            run_mode = mode in ("run", "both", "run_nodes")
            target_nodes: List[int] = []
            if run_mode:
                if mode == "run_nodes" and nodes:
                    target_nodes = nodes
                elif nodes:
                    target_nodes = nodes
                else:
                    leaves = tree.AllLeafNodes("all")
                    target_nodes = [
                        n for n in leaves
                        if tree.NodeStatus(n) in ("none", "ready")
                    ]
                    if not target_nodes:
                        target_nodes = list(leaves)

            # ── 自动监控（在 deck.run 之前启动监控线程） ──
            if run_mode and monitor and monitor_timeout > 0 and target_nodes:
                result_lines.append("\n📂 仿真节点:")
                for n in target_nodes:
                    if tree.NodeExists(n):
                        result_lines.append(
                            f"  节点 {n} ({tree.NodeTool(n)}) 路径: {tree.NodePath(n)}"
                        )
                result_lines.append("\n⏳ 启动仿真，同时监控 .out 输出...\n")
                initial_reply = "\n".join(result_lines)
                print(initial_reply, flush=True)

                track: Dict[int, Dict[str, Any]] = {}
                for n in target_nodes:
                    tool = tree.NodeTool(n) if tree.NodeExists(n) else "?"
                    track[n] = {"tool": tool, "positions": {}}

                stop_event = threading.Event()

                def _monitor_loop():
                    deadline = time.time() + monitor_timeout
                    last_status: Dict[int, str] = {}
                    while not stop_event.is_set() and time.time() < deadline:
                        time.sleep(3)

                        all_done = True
                        status_changed = False
                        for n in target_nodes:
                            if not tree.NodeExists(n):
                                continue
                            s = tree.NodeStatus(n)
                            if s != last_status.get(n):
                                status_changed = True
                            last_status[n] = s
                            if s not in ("done", "failed", "aborted"):
                                all_done = False

                            out_files = _find_node_out_files(project_path, n)
                            ti = track[n]
                            for fpath in out_files:
                                if fpath not in ti["positions"]:
                                    ti["positions"][fpath] = 0
                                try:
                                    with open(fpath, "r", errors="replace") as f:
                                        lines = f.readlines()
                                except (OSError, IOError):
                                    continue
                                total = len(lines)
                                pos = ti["positions"][fpath]
                                if pos < total:
                                    new_text = "".join(lines[pos:]).rstrip()
                                    if new_text:
                                        for line in new_text.split("\n"):
                                            stripped = line.strip()
                                            if stripped:
                                                print(
                                                    f"  [节点 {n} {ti['tool']}] {stripped}",
                                                    flush=True,
                                                )
                                    ti["positions"][fpath] = total

                        if status_changed:
                            status_str = ", ".join(
                                f"节点 {n}: {s}" for n, s in sorted(last_status.items())
                            )
                            print(f"  📊 {status_str}", flush=True)

                        if all_done:
                            print("  ✅ 全部节点仿真完成！", flush=True)
                            return

                    if not stop_event.is_set():
                        print(f"  ⏰ 监控超时 ({monitor_timeout}秒)", flush=True)

                monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
                monitor_thread.start()

                # 在监控线程运行的同时执行仿真
                if mode in ("run", "both"):
                    deck.run(**r_kw)
                elif mode == "run_nodes" and nodes:
                    r_kw["nodes"] = nodes
                    deck.run(**r_kw)

                # 仿真结束，停止监控
                stop_event.set()
                monitor_thread.join(timeout=5)

                final_lines = ["\n📊 仿真结果:"]
                for n in target_nodes:
                    if tree.NodeExists(n):
                        final_lines.append(f"  节点 {n} ({tree.NodeTool(n)}): {tree.NodeStatus(n)}")
                return "\n".join(final_lines)

            # ── 非监控模式（仅提交，不等待） ──
            if mode in ("run", "both"):
                if nodes:
                    r_kw["nodes"] = nodes
                deck.run(**r_kw)
                result_lines.append("✅ 仿真已提交")

            if mode == "run_nodes" and nodes:
                r_kw["nodes"] = nodes
                deck.run(**r_kw)
                result_lines.append(f"✅ 节点 {nodes} 仿真已提交")

            status = deck.status()
            result_lines.append(f"项目状态: {status}")
            return "\n".join(result_lines)

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"运行仿真失败: {type(e).__name__}: {e}"


class TCADStatusTool(BaseTool):
    name: str = "tcad_check_status"
    description: str = (
        "查询 SWB 项目的整体状态或指定节点的详细状态。\n"
        "如果提供 node 参数，只查询该节点。\n"
        "如果提供 status_filter，则搜索所有匹配指定状态的节点。"
    )
    args_schema: Type[BaseModel] = StatusSchema

    def _run(self, project_path: str, scenario: str = "all",
             node: Optional[int] = None,
             status_filter: Optional[str] = None) -> str:
        try:
            _ensure_swbpy2()
            deck = _get_deck(project_path)
            tree = _get_tree(project_path)

            if node is not None:
                if not tree.NodeExists(node):
                    return f"节点 {node} 不存在"
                status = tree.NodeStatus(node)
                data = tree.NodeData(node)
                return (
                    f"节点 {node} 状态: {status}\n"
                    f"详细信息: {data}"
                )

            if status_filter:
                from swbpy2.core.core import (
                    STATE_NONE, STATE_QUEUED, STATE_READY, STATE_PENDING,
                    STATE_RUNNING, STATE_DONE, STATE_FAILED, STATE_ABORTED
                )
                state_map = {
                    "none": STATE_NONE, "queued": STATE_QUEUED,
                    "ready": STATE_READY, "pending": STATE_PENDING,
                    "running": STATE_RUNNING, "done": STATE_DONE,
                    "failed": STATE_FAILED, "aborted": STATE_ABORTED,
                }
                state_val = state_map.get(status_filter.lower())
                if state_val is None:
                    return f"不支持的状态过滤: {status_filter}。支持: {list(state_map.keys())}"
                matched = tree.SearchNodesByStatus(scenario, state_val)
                return f"状态 '{status_filter}' 的节点: {matched}"

            project_status = deck.status()
            summary = (
                f"项目状态: {project_status}\n"
                f"所有工具: {tree.AllTools()}\n"
                f"所有参数: {tree.AllPnames()}\n"
                f"总节点数: {len(tree.AllNodes(scenario))}\n"
                f"叶子节点: {len(tree.AllLeafNodes(scenario))}\n"
            )

            leaf_nodes = tree.AllLeafNodes(scenario)
            status_counts: Dict[str, int] = {}
            for n in leaf_nodes:
                s = tree.NodeStatus(n)
                status_counts[s] = status_counts.get(s, 0) + 1
            summary += "叶子节点状态统计:\n"
            for s, cnt in sorted(status_counts.items(), key=lambda x: -x[1]):
                summary += f"  {s}: {cnt}\n"

            return summary

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"查询状态失败: {type(e).__name__}: {e}"


class TCADModifyTool(BaseTool):
    name: str = "tcad_modify_project"
    description: str = (
        "修改 SWB 项目的仿真流程。支持的操作:\n"
        "  add_tool      — params: {'tool_name': '标签', 'db_tool_name': 'sdevice', 'step': -1}\n"
        "  add_param     — params: {'param_name': 'x', 'default_value': '1.0', 'step': 0}\n"
        "  add_experiment— params: {'pvalues': [0.25, 1e17], 'scenario': 'default'}\n"
        "  change_node   — params: {'node': 5, 'value': '0.5'}\n"
        "  change_param  — params: {'param': 'GateLength', 'values': ['0.1', '0.2']}\n"
        "  delete_param  — params: {'param': 'GateLength'}\n"
        "  delete_tool   — params: {'tool': 'sprocess'}\n"
        "  save          — 保存当前项目到磁盘(不需要额外 params)"
    )
    args_schema: Type[BaseModel] = ModifyProjectSchema

    def _run(self, project_path: str, action: str,
             params: Dict[str, Any] = None) -> str:
        try:
            _ensure_swbpy2()
            tree = _get_tree(project_path)
            deck = _get_deck(project_path)
            params = params or {}

            action = action.strip().lower()

            if action == "add_tool":
                tool_name = params.get("tool_name", "")
                db_tool_name = params.get("db_tool_name", "")
                step = params.get("step", -1)
                if not tool_name or not db_tool_name:
                    return "add_tool 需要 tool_name 和 db_tool_name 参数"
                tree.AddTool(tool_name, db_tool_name, step, toSave=True)
                return f"工具 '{tool_name}' (db: {db_tool_name}) 已添加到 step {step}"

            elif action == "add_param":
                param_name = params.get("param_name", "")
                default_value = params.get("default_value", "--")
                step = params.get("step", -1)
                if not param_name:
                    return "add_param 需要 param_name 参数"
                tree.AddParam(param_name, default_value, step, toSave=True)
                return f"参数 '{param_name}' (默认值: {default_value}) 已添加到 step {step}"

            elif action == "add_experiment":
                pvalues = params.get("pvalues", [])
                scenario = params.get("scenario", "default")
                if not pvalues:
                    return "add_experiment 需要 pvalues 列表"
                tree.AddPath(pvalues=pvalues, scenario=scenario, toSave=True)
                return f"实验 {pvalues} 已添加到场景 '{scenario}'"

            elif action == "change_node":
                node = params.get("node")
                value = params.get("value", "")
                if node is None:
                    return "change_node 需要 node 参数"
                if not tree.NodeExists(node):
                    return f"节点 {node} 不存在"
                old_vals = tree.NodePvalues(node)
                tree.ChangeNodeValue(node, value, toSave=True)
                return f"节点 {node} 的值已从 {old_vals} 变更为 {value}"

            elif action == "change_param":
                param = params.get("param", "")
                values = params.get("values", [])
                if not param or not values:
                    return "change_param 需要 param 和 values 参数"
                old_vals = tree.GetParamValues(param)
                tree.ChangeParamValues(param, values, toSave=True)
                return f"参数 '{param}' 的值已从 {old_vals} 变更为 {values}"

            elif action == "delete_param":
                param = params.get("param", "")
                if not param:
                    return "delete_param 需要 param 参数"
                tree.DeleteParam(param, toSave=True)
                return f"参数 '{param}' 已删除"

            elif action == "delete_tool":
                tool = params.get("tool", "")
                if not tool:
                    return "delete_tool 需要 tool 参数"
                tree.DeleteTool(tool, toSave=True)
                return f"工具 '{tool}' 已删除"

            elif action == "save":
                deck.save()
                return f"项目已保存到 {os.path.abspath(project_path)}"

            else:
                return (f"不支持的操作: '{action}'。支持: add_tool, add_param, "
                        f"add_experiment, change_node, change_param, "
                        f"delete_param, delete_tool, save")

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"项目修改失败: {type(e).__name__}: {e}"


class TCADResultsTool(BaseTool):
    name: str = "tcad_get_results"
    description: str = (
        "从已完成仿真的节点提取结果数据。\n"
        "默认使用 NodeReconstructResults 从输出文件重建结果。"
    )
    args_schema: Type[BaseModel] = ResultsSchema

    def _run(self, project_path: str, node: int,
             trials: int = 3, delay: int = 3) -> str:
        try:
            _ensure_swbpy2()
            tree = _get_tree(project_path)

            if not tree.NodeExists(node):
                return f"节点 {node} 不存在"
            try:
                results = tree.NodeReconstructResults(node, trials, delay)
                tool_name = tree.NodeTool(node)
                status = tree.NodeStatus(node)
                node_path = tree.NodePath(node)
                return (
                    f"节点 {node} ({tool_name}) 结果:\n"
                    f"  状态: {status}\n"
                    f"  路径: {node_path}\n"
                    f"  数据: {results}"
                )
            except Exception as inner_e:
                return (
                    f"节点 {node} 结果提取失败(可能未完成或无输出文件): {inner_e}\n"
                    f"请先用 tcad_check_status 确认节点状态。"
                )

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"提取结果失败: {type(e).__name__}: {e}"


class TCADCleanupTool(BaseTool):
    name: str = "tcad_cleanup"
    description: str = (
        "清理 SWB 项目的中间文件、日志或结果。"
        "可指定清理级别: default | log | pp(files) | node_files | all"
    )
    args_schema: Type[BaseModel] = None  # type: ignore

    class CleanupSchema(ProjectPathSchema):
        level: str = Field(default="default", description="清理级别: default | log | pp | node | all")
        nodes: Optional[List[int]] = Field(default=None, description="指定要清理的节点列表(可选)")

    args_schema = CleanupSchema

    def _run(self, project_path: str, level: str = "default",
             nodes: Optional[List[int]] = None) -> str:
        try:
            _ensure_swbpy2()
            deck = _get_deck(project_path)

            kwargs = {}
            if nodes:
                kwargs["nodes"] = nodes

            level = level.strip().lower()
            if level == "default":
                kwargs["default"] = True
            elif level == "log":
                kwargs["logFiles"] = True
            elif level == "pp":
                kwargs["preprocessorFiles"] = True
            elif level == "node":
                kwargs["nodeFiles"] = True
            elif level == "all":
                kwargs["default"] = True
                kwargs["logFiles"] = True
                kwargs["preprocessorFiles"] = True
                kwargs["nodeFiles"] = True
            else:
                kwargs["default"] = True

            deck.cleanup(**kwargs)
            return f"项目清理完成 (level: {level})"

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"项目清理失败: {type(e).__name__}: {e}"


def _find_node_out_files(project_path: str, node: int) -> List[str]:
    """Find .out files for a simulation node.

    SWB writes simulation stdout/stderr to ``.out`` files inside each
    node's working directory.  This helper discovers them by globbing
    the node directory.

    Returns:
        Sorted list of absolute .out file paths (may be empty if the
        node hasn't been run yet).
    """
    try:
        _ensure_swbpy2()
        tree = _get_tree(project_path)
        if not tree.NodeExists(node):
            return []
        tool_name = tree.NodeTool(node)
        node_path = tree.NodePath(node)
        scenarios = tree.AllScenarios()
        for sc in scenarios:
            node_dir = os.path.join(os.path.abspath(project_path), sc, node_path)
            if os.path.isdir(node_dir):
                import glob as _glob
                out_files = _glob.glob(os.path.join(node_dir, "*.out"))
                out_files += _glob.glob(os.path.join(node_dir, "n*", "*.out"))
                tool_out = _glob.glob(os.path.join(node_dir, f"{tool_name}*.out"))
                out_files += tool_out
                return sorted(set(out_files))
        return []
    except Exception:
        return []


class DisplayResultsSchema(ProjectPathSchema):
    detail: str = Field(
        default="all",
        description="显示级别: 'all'(默认, 完整显示) | 'overview'(项目概览) | 'electrical'(电学参数摘要)"
    )


class TCADDisplayResultsTool(BaseTool):
    name: str = "tcad_display_results"
    description: str = (
        "Display project simulation results in SWB Workbench style.\n"
        "Parses the project parameter table, node status, and .plt electrical\n"
        "output files to generate a formatted results summary including:\n"
        "  - Project overview (experiments, nodes, status)\n"
        "  - Parameter/experiment table (like SWB project view)\n"
        "  - Node status list\n"
        "  - Electrical parameter extraction (Id-Vg, drive current)"
    )
    args_schema: Type[BaseModel] = DisplayResultsSchema

    def _run(self, project_path: str, detail: str = "all") -> str:
        try:
            _ensure_swbpy2()
            deck = _get_deck(project_path)
            tree = _get_tree(project_path)
            prj_abs = os.path.abspath(project_path)
            lines: List[str] = []
            sep = "─" * 72

            # ── 1) 项目概览 ──
            lines.append(f"{'═' * 72}")
            lines.append(f"  TCAD Project: {os.path.basename(prj_abs)}")
            lines.append(f"{'═' * 72}")
            lines.append(f"  Path : {prj_abs}")

            try:
                proj_status = deck.status()
                lines.append(f"  Status: {proj_status}")
            except Exception:
                pass

            tools = tree.AllTools()
            params = tree.AllPnames()
            all_nodes_list = tree.AllNodes("all")
            leaf_nodes_list = tree.AllLeafNodes("all")
            n_nodes = len(all_nodes_list)
            n_leaves = len(leaf_nodes_list)
            leaf_set = set(leaf_nodes_list)
            try:
                n_exp = tree.NExperiments()
            except Exception:
                n_exp = "?"
            try:
                n_steps = tree.NSteps()
            except Exception:
                n_steps = "?"

            lines.append(f"  Tools : {len(tools)} | Params: {len(params)} | Steps: {n_steps}")
            lines.append(f"  Nodes : {n_nodes} total, {n_leaves} leaf, {n_exp} experiments")
            lines.append("")

            if detail in ("all", "overview"):
                # ── 2) 参数/实验表格 (从 export CSV) ──
                lines.append(sep)
                lines.append("  📋 Experiment Table (Workbench Style)")
                lines.append(sep)

                csv_data = deck.export()
                if csv_data and csv_data.strip():
                    rows = csv_data.strip().split("\n")
                    table = [r.strip().split(",") for r in rows]

                    if table:
                        ncols = max(len(r) for r in table)
                        widths = []
                        for ci in range(ncols):
                            col_vals = []
                            for r in table:
                                if ci < len(r):
                                    col_vals.append(r[ci].strip().rstrip("\r"))
                            max_w = max(len(v) for v in col_vals) if col_vals else 4
                            widths.append(min(max_w + 2, 30))

                        hdr_sep = "+" + "+".join("─" * w for w in widths) + "+"

                        for ri, row in enumerate(table):
                            cells = []
                            for ci in range(ncols):
                                val = row[ci].strip().rstrip("\r") if ci < len(row) else ""
                                cells.append(f" {val:<{widths[ci] - 1}}")
                            lines.append("|" + "|".join(cells) + "|")
                            if ri == 0 or ri == 1:
                                lines.append(hdr_sep)
                lines.append("")

            # ── 3) 节点状态概览 ──
            lines.append(sep)
            lines.append("  🔧 Node Status")
            lines.append(sep)

            node_statuses = []
            for n in all_nodes_list:
                if tree.NodeExists(n):
                    s = tree.NodeStatus(n)
                    t = tree.NodeTool(n)
                    node_statuses.append((n, t, s))

            # Print status counts
            status_counts: Dict[str, int] = {}
            for _, _, s in node_statuses:
                status_counts[s] = status_counts.get(s, 0) + 1
            lines.append("  Status: " + ", ".join(f"{k}: {v}" for k, v in sorted(status_counts.items())))
            lines.append("")

            if detail in ("all", "overview"):
                # Print full node table
                header = f"  {'Node':>4}  {'Tool':<20}  {'Status':<10}  {'Type':<10}"
                lines.append(header)
                lines.append("  " + "─" * (len(header) - 2))
                for n, t, s in sorted(node_statuses, key=lambda x: x[0]):
                    is_leaf = n in leaf_set
                    ntype = "leaf" if is_leaf else "split"
                    lines.append(f"  {n:>4}  {t:<20}  {s:<10}  {ntype:<10}")
                lines.append("")

            # ── 4) 电学参数提取 (for sdevice nodes) ──
            if detail in ("all", "electrical"):
                sdevice_nodes = []
                for n in all_nodes_list:
                    if tree.NodeExists(n) and tree.NodeStatus(n) == "done":
                        t = tree.NodeTool(n)
                        try:
                            db_tool = tree.DBTool(n)
                        except Exception:
                            db_tool = t
                        if 'sdevice' in db_tool.lower() or 'sdevice' in t.lower():
                            sdevice_nodes.append(n)

                if not sdevice_nodes:
                    for n in all_nodes_list:
                        if tree.NodeExists(n) and tree.NodeStatus(n) == "done":
                            t = tree.NodeTool(n)
                            out_prefix = _get_node_out_prefix(prj_abs, n)
                            if out_prefix and '_des' in out_prefix:
                                sdevice_nodes.append(n)

                if sdevice_nodes:
                    lines.append(sep)
                    lines.append("  ⚡ Electrical Results (from .plt files)")
                    lines.append(sep)
                    lines.append("")

                    param_names = tree.AllPnames()
                    result_rows: List[Dict] = []
                    for n in sorted(sdevice_nodes):
                        node_info: Dict = {"node": n}
                        try:
                            pvals = tree.NodePvalues(n)
                            for pi, pn in enumerate(param_names):
                                if pi < len(pvals):
                                    node_info[pn] = pvals[pi]
                        except Exception:
                            pass
                        plt_data = _parse_node_plt_files(prj_abs, n)
                        node_info.update(plt_data)
                        result_rows.append(node_info)

                    col_names = ["Node"] + list(param_names) + [
                        "Id_lin@Vg=1V (A/µm)", "Id_sat@Vg=1V (A/µm)",
                        "Ioff_lin (A/µm)", "Ioff_sat (A/µm)",
                        "Vt_lin (V)", "Vt_sat (V)"]

                    col_widths = [max(len(c), 6) for c in col_names]
                    for rr in result_rows:
                        col_widths[0] = max(col_widths[0], len(str(rr["node"])))
                        for ci, cn in enumerate(col_names):
                            if cn in rr:
                                val = str(rr[cn])
                                if len(val) > col_widths[ci]:
                                    col_widths[ci] = len(val)

                    sep_line = "+" + "+".join("─" * w for w in col_widths) + "+"
                    hdr_cells = []
                    for ci, cn in enumerate(col_names):
                        hdr_cells.append(f" {cn:<{col_widths[ci] - 1}}")
                    lines.append("|" + "|".join(hdr_cells) + "|")
                    lines.append(sep_line)

                    for rr in result_rows:
                        cells = [f" {rr['node']:<{col_widths[0] - 1}}"]
                        for ci, cn in enumerate(col_names):
                            if ci == 0:
                                continue
                            if cn in rr:
                                val = rr[cn]
                                if isinstance(val, float):
                                    val_str = f"{val:.4e}"
                                else:
                                    val_str = str(val)
                            else:
                                val_str = ""
                            cells.append(f" {val_str:<{col_widths[ci] - 1}}")
                        if len(cells) >= 2:
                            lines.append("|" + "|".join(cells) + "|")
                    lines.append("")

                if result_rows:
                    lines.append(sep)
                    lines.append("  Id-Vg Curves (Detailed)")
                    lines.append(sep)
                    for rr in result_rows:
                        n = rr["node"]
                        lines.append(f"\n  Node {n}:")
                        if "vg_lin" in rr and "id_lin" in rr:
                            lines.append("    Linear region (Vd~0.1V):")
                            lines.append(f"      {'Vg (V)':>10}  {'Id (A/um)':>18}")
                            for vg, id_val in zip(rr["vg_lin"], rr["id_lin"]):
                                lines.append(f"      {vg:>10.4f}  {id_val:>18.6e}")
                        if "vg_sat" in rr and "id_sat" in rr:
                            lines.append("    Saturation region (Vd~1.1V):")
                            lines.append(f"      {'Vg (V)':>10}  {'Id (A/um)':>18}")
                            for vg, id_val in zip(rr["vg_sat"], rr["id_sat"]):
                                lines.append(f"      {vg:>10.4f}  {id_val:>18.6e}")
                else:
                    lines.append("  (no sdevice results extracted)")
            else:
                lines.append("\n  (no completed sdevice nodes found)")

            return "\n".join(lines)

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            import traceback
            return f"显示结果失败: {type(e).__name__}: {e}\n{traceback.format_exc()}"


def _get_node_out_prefix(project_path: str, node: int) -> str:
    """Determine the output file prefix for a node."""
    # Files are named n{N}_{suffix}.out in project root
    import glob
    matches = sorted(glob.glob(os.path.join(project_path, f"n{node}_*.out")))
    if matches:
        base = os.path.basename(matches[0])
        return base.replace(".out", "")
    # Also check n{N}_*.log
    matches = sorted(glob.glob(os.path.join(project_path, f"n{node}_*.log")))
    if matches:
        base = os.path.basename(matches[0])
        return base.replace(".log", "")
    return f"n{node}"


def _parse_node_plt_files(project_path: str, node: int) -> Dict:
    """Parse .plt files for a given node and extract electrical parameters.

    Returns dict with keys:
        vg_lin, id_lin, id_lin_max, id_lin_min,
        vg_sat, id_sat, id_sat_max, id_sat_min,
        vt_lin, vt_sat
    """
    result: Dict = {}
    try:
        # Add the svisual_bin plt reader to Python path
        svisual_pkgs = (
            f"{TCAD_ROOT}/tcad/{TCAD_RELEASE}/linux64/bin/svisual_bin/site-packages"
        )
        if svisual_pkgs not in sys.path:
            sys.path.insert(0, svisual_pkgs)

        from common.readers.pltreader import PltReader

        # Try to find plt files
        import glob

        # Check for IdVgsLin and IdVgsSat patterns
        lin_plt = os.path.join(project_path, f"IdVgsLin_n{node}_des.plt")
        sat_plt = os.path.join(project_path, f"IdVgsSat_n{node}_des.plt")

        # Also try the generic n{N}_des.plt
        generic_plt = os.path.join(project_path, f"n{node}_des.plt")

        # Parse linear region
        if os.path.exists(lin_plt):
            try:
                reader = PltReader(lin_plt)
                df = reader.data
                if "gate OuterVoltage" in df.columns and "drain TotalCurrent" in df.columns:
                    vg = df["gate OuterVoltage"].values
                    id_val = df["drain TotalCurrent"].values
                    vd = df["drain OuterVoltage"].values[0] if len(df["drain OuterVoltage"]) > 0 else 0

                    result["vg_lin"] = vg.tolist()
                    result["id_lin"] = id_val.tolist()
                    result["id_lin_max"] = float(max(id_val))
                    result["id_lin_min"] = float(min(id_val))
                    result["vd_lin"] = float(vd)

                    # Simple Vt extraction (linear extrapolation at max gm)
                    try:
                        gm = np.gradient(id_val, vg)
                        vg_sat_idx = int(np.argmax(gm))
                        if vg_sat_idx > 0 and vg_sat_idx < len(vg):
                            vt = vg[vg_sat_idx] - id_val[vg_sat_idx] / gm[vg_sat_idx]
                            result["vt_lin"] = float(vt)
                    except Exception:
                        pass
            except Exception as e:
                result["_lin_error"] = str(e)

        # Parse saturation region
        if os.path.exists(sat_plt):
            try:
                reader = PltReader(sat_plt)
                df = reader.data
                if "gate OuterVoltage" in df.columns and "drain TotalCurrent" in df.columns:
                    vg = df["gate OuterVoltage"].values
                    id_val = df["drain TotalCurrent"].values
                    vd = df["drain OuterVoltage"].values[0] if len(df["drain OuterVoltage"]) > 0 else 0

                    result["vg_sat"] = vg.tolist()
                    result["id_sat"] = id_val.tolist()
                    result["id_sat_max"] = float(max(id_val))
                    result["id_sat_min"] = float(min(id_val))
                    result["vd_sat"] = float(vd)

                    # Simple Vt extraction (saturation)
                    try:
                        gm = np.gradient(id_val, vg)
                        vg_max_idx = int(np.argmax(gm))
                        if vg_max_idx > 0 and vg_max_idx < len(vg):
                            vt = vg[vg_max_idx] - id_val[vg_max_idx] / gm[vg_max_idx]
                            result["vt_sat"] = float(vt)
                    except Exception:
                        pass
            except Exception as e:
                result["_sat_error"] = str(e)

        # Fallback: try generic .plt
        if not result and os.path.exists(generic_plt):
            try:
                reader = PltReader(generic_plt)
                df = reader.data
                if "gate OuterVoltage" in df.columns and "drain TotalCurrent" in df.columns:
                    vg = df["gate OuterVoltage"].values
                    id_val = df["drain TotalCurrent"].values
                    vd = df["drain OuterVoltage"].values[0] if len(df["drain OuterVoltage"]) > 0 else 0

                    result["vg_gen"] = vg.tolist()
                    result["id_gen"] = id_val.tolist()
                    result["id_gen_max"] = float(max(id_val))
                    result["id_gen_min"] = float(min(id_val))
            except Exception as e:
                result["_gen_error"] = str(e)

    except Exception as e:
        result["_error"] = str(e)

    return result


def _build_experiment_map(project_path: str) -> Dict:
    """Build a mapping of node → experiment parameter values from Deck.export()."""
    result: Dict = {"params": [], "values": {}}
    try:
        _ensure_swbpy2()
        deck = _get_deck(project_path)
        tree = deck.getGtree()

        csv_data = deck.export()
        if not csv_data:
            return result

        rows = csv_data.strip().split("\n")
        if len(rows) < 3:
            return result

        table = [r.split(",") for r in rows]

        # Row 0: tool names (header)
        # Row 1: tool instance names
        # Row 2: parameter names (for each column)
        # Rows 3+: parameter values

        param_cols: List[int] = []
        param_names: List[str] = []
        for ci in range(len(table[2])):
            pname = table[2][ci].strip()
            if pname:
                param_cols.append(ci)
                param_names.append(pname)
                if pname not in result["params"]:
                    result["params"].append(pname)

        # Map data rows to nodes
        # The export data has one row per experiment/split
        # Each row has parameter values in the parameter columns
        # Node mapping: first sdevice node per experiment
        data_rows = table[3:]

        all_nodes_ids = sorted(tree.AllNodes("all"))
        leaf_nodes_set = set(tree.AllLeafNodes("all"))

        sdevice_node_ids = []
        for n in all_nodes_ids:
            if n in leaf_nodes_set:
                continue
            if tree.NodeExists(n):
                t = tree.NodeTool(n)
                try:
                    db_t = tree.DBTool(n)
                except Exception:
                    db_t = t
                if 'sdevice' in db_t.lower() or 'sdevice' in t.lower():
                    sdevice_node_ids.append(n)

        # Map data rows to sdevice nodes
        for ri, row in enumerate(data_rows):
            if ri < len(sdevice_node_ids):
                nid = sdevice_node_ids[ri]
                result["values"][nid] = {}
                for pi, pn in zip(param_cols, param_names):
                    if pi < len(row):
                        result["values"][nid][pn] = row[pi].strip()

    except Exception:
        pass

    return result


def _find_node_out_files(project_path: str, node: int) -> List[str]:
    """Find .out files for a simulation node.

    SWB simulation output files sit directly in the project root directory,
    named ``n{N}_{suffix}.out`` (e.g. ``n2_des.out``, ``n3_vis.out``).

    This replaces the old implementation that tried tree.NodePath subdirectories
    which don't exist in newer SWB projects.
    """
    import glob
    # Direct glob in project root for this node's .out files
    pattern = os.path.join(os.path.abspath(project_path), f"n{node}_*.out")
    matches = sorted(glob.glob(pattern))
    return matches


class TCADTailOutputTool(BaseTool):
    name: str = "tcad_tail_output"
    description: str = (
        "读取 SWB 仿真节点正在生成的 .out 文件内容。\n"
        "在仿真运行中调用此工具可以查看实时进度和日志。\n"
        "参数 offset=0 从头读取；指定 offset 可从上次位置继续读取。"
    )
    args_schema: Type[BaseModel] = None

    class TailOutputSchema(ProjectPathSchema):
        node: int = Field(description="要读取输出文件的节点编号")
        max_lines: int = Field(default=200, description="最大返回行数，默认 200")
        offset: int = Field(default=0, description="跳过开头 N 行，用于增量读取")

    args_schema = TailOutputSchema

    def _run(self, project_path: str, node: int,
             max_lines: int = 200, offset: int = 0) -> str:
        try:
            _ensure_swbpy2()
            tree = _get_tree(project_path)
            if not tree.NodeExists(node):
                return f"节点 {node} 不存在"
            status = tree.NodeStatus(node)

            out_files = _find_node_out_files(project_path, node)
            if not out_files:
                return (
                    f"节点 {node} 状态: {status}\n"
                    f"未找到 .out 文件。仿真可能尚未开始生成输出，"
                    f"或该节点未运行过。"
                )

            result_parts = [f"节点 {node} 状态: {status}"]
            for fpath in out_files:
                try:
                    with open(fpath, "r", errors="replace") as f:
                        lines = f.readlines()
                except (OSError, IOError) as e:
                    result_parts.append(f"  文件 {os.path.basename(fpath)}: 读取失败 ({e})")
                    continue

                total_lines = len(lines)
                start = min(offset, total_lines)
                tail_lines = lines[start:][:max_lines]
                tail_text = "".join(tail_lines).rstrip()
                result_parts.append(
                    f"  📄 {os.path.basename(fpath)} ({total_lines} 行)"
                )
                if tail_text:
                    result_parts.append(tail_text)

            if max_lines and len("\n".join(result_parts)) > 5000:
                result_parts.append("\n... (输出过长，已截断)")
                result_parts = result_parts[:10]

            return "\n".join(result_parts)

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"读取输出失败: {type(e).__name__}: {e}"


def get_tcad_tools() -> List[BaseTool]:
    return [
        TCADProjectTool(),
        TCADSimulationTool(),
        TCADStatusTool(),
        TCADModifyTool(),
        TCADResultsTool(),
        TCADCleanupTool(),
        TCADTailOutputTool(),
    ]


if __name__ == "__main__":
    print("可用 TCAD LangChain 工具:")
    for t in get_tcad_tools():
        print(f"  - {t.name}: {t.description[:60]}...")
