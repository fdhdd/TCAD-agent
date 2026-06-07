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

                # 获取工具的 acronym 用于 .cmd 文件命名
                acronym = db_tool_name  # 默认使用 db_tool_name
                try:
                    acronym = tree.GetDBToolCtxItem(f'{db_tool_name},acronym')
                except Exception:
                    pass

                # 自动创建 .cmd 脚本文件（如果不存在）
                cmd_filename = f"{tool_name}_{acronym}.cmd"
                cmd_filepath = os.path.join(os.path.abspath(project_path), cmd_filename)
                if not os.path.exists(cmd_filepath):
                    with open(cmd_filepath, "w") as f:
                        pass  # 创建空文件
                    return (
                        f"工具 '{tool_name}' (db: {db_tool_name}) 已添加到 step {step}\n"
                        f"已创建脚本文件: {cmd_filename}\n"
                        f"提示: 可使用 tcad_modify_script 工具编写脚本内容。"
                    )
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


class ReadScriptSchema(ProjectPathSchema):
    tool: Optional[str] = Field(
        default=None,
        description="工具名称（如 'sprocess', 'sdevice'）。不提供则列出所有脚本文件。"
    )
    node: Optional[int] = Field(
        default=None,
        description="指定节点编号。多实验项目中不同节点可能对应不同脚本文件。"
    )
    max_lines: int = Field(default=500, description="最大返回行数，默认 500")


class TCADReadScriptTool(BaseTool):
    name: str = "tcad_read_script"
    description: str = (
        "读取 SWB 项目中工具的 .cmd 仿真脚本文件内容。\n"
        "不指定 tool 时列出项目中所有 .cmd 脚本文件。\n"
        "指定 tool 时返回该工具对应的脚本内容（带行号）。\n"
        "脚本文件是 TCAD 仿真的实际指令，包含 Physics、Electrode、Solve 等配置。"
    )
    args_schema: Type[BaseModel] = ReadScriptSchema

    def _run(self, project_path: str, tool: Optional[str] = None,
             node: Optional[int] = None, max_lines: int = 500) -> str:
        try:
            import glob as _glob
            prj_abs = os.path.abspath(project_path)
            if not os.path.isdir(prj_abs):
                return f"项目路径不存在: {prj_abs}"

            # 查找所有 .cmd 文件
            cmd_files = sorted(_glob.glob(os.path.join(prj_abs, "*.cmd")))
            if not cmd_files:
                return (
                    f"项目中没有找到 .cmd 脚本文件: {prj_abs}\n"
                    f"提示: 新添加的工具需要先运行预处理才能生成 .cmd 脚本文件。\n"
                    f"请调用 tcad_run_simulation(project_path='...', mode='preprocess') 先执行预处理。"
                )

            # 不指定 tool 时，列出所有脚本文件
            if tool is None:
                lines = [f"项目: {prj_abs}", f"找到 {len(cmd_files)} 个脚本文件:"]
                for fpath in cmd_files:
                    fname = os.path.basename(fpath)
                    size = os.path.getsize(fpath)
                    # 尝试解析文件名: {label}_{type}.cmd
                    parts = fname.replace(".cmd", "").rsplit("_", 1)
                    if len(parts) == 2:
                        label, db_type = parts
                        lines.append(f"  - {label}_{db_type}.cmd  ({size} 字节)  工具标签: {label}, 类型: {db_type}")
                    else:
                        lines.append(f"  - {fname}  ({size} 字节)")
                return "\n".join(lines)

            # 指定了 tool，查找对应的 .cmd 文件
            _ensure_swbpy2()
            tree = _get_tree(project_path)

            # 获取工具的 acronym，用于精确匹配 .cmd 文件
            tool_acronym = None
            try:
                all_tools = tree.AllTools()
                if tool in all_tools:
                    db_tool_name = tree.DBTool(tool)
                    tool_acronym = tree.GetDBToolCtxItem(f'{db_tool_name},acronym')
            except Exception:
                pass

            # 策略1: 按命名规则 {tool_label}_{acronym}.cmd 匹配
            matched_files = []
            for fpath in cmd_files:
                fname = os.path.basename(fpath).replace(".cmd", "")
                parts = fname.rsplit("_", 1)
                if len(parts) == 2:
                    label, acronym = parts
                    # 优先匹配 tool_label + acronym 组合
                    if label.lower() == tool.lower() and tool_acronym and acronym.lower() == tool_acronym.lower():
                        matched_files = [fpath]  # 精确匹配，直接覆盖
                        break
                    # 匹配工具标签（不区分大小写）
                    if label.lower() == tool.lower():
                        matched_files.append(fpath)
                    # 匹配 acronym
                    elif acronym.lower() == tool.lower():
                        matched_files.append(fpath)

            # 策略2: 如果指定了节点，用节点信息匹配
            if node is not None and tree.NodeExists(node):
                node_tool = tree.NodeTool(node)
                db_tool = tree.DBTool(node_tool) if hasattr(tree, 'DBTool') else node_tool
                for fpath in cmd_files:
                    fname = os.path.basename(fpath).replace(".cmd", "")
                    parts = fname.rsplit("_", 1)
                    if len(parts) == 2:
                        label, db_type = parts
                        if label == node_tool and fpath not in matched_files:
                            matched_files.append(fpath)

            # 策略3: 模糊匹配文件名包含 tool 关键字
            if not matched_files:
                for fpath in cmd_files:
                    fname = os.path.basename(fpath).lower()
                    if tool.lower() in fname and fpath not in matched_files:
                        matched_files.append(fpath)

            if not matched_files:
                available = [os.path.basename(f) for f in cmd_files]
                return (
                    f"未找到工具 '{tool}' 对应的脚本文件。\n"
                    f"可用的脚本文件: {available}"
                )

            # 读取匹配的脚本文件内容
            result_parts = []
            for fpath in matched_files:
                fname = os.path.basename(fpath)
                try:
                    with open(fpath, "r", errors="replace") as f:
                        lines = f.readlines()
                except (OSError, IOError) as e:
                    result_parts.append(f"📄 {fname}: 读取失败 ({e})")
                    continue

                total = len(lines)
                content_lines = lines[:max_lines]
                # 添加行号
                numbered = []
                for i, line in enumerate(content_lines, 1):
                    numbered.append(f"{i:>4} | {line.rstrip()}")

                result_parts.append(f"📄 {fname} ({total} 行):")
                result_parts.append("\n".join(numbered))
                if total > max_lines:
                    result_parts.append(f"... (已截断，共 {total} 行，显示前 {max_lines} 行)")

            return "\n\n".join(result_parts)

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"读取脚本失败: {type(e).__name__}: {e}"


class ModifyScriptSchema(ProjectPathSchema):
    tool: str = Field(description="工具名称（如 'sprocess', 'sdevice', 'Gummel'）")
    action: str = Field(
        description=(
            "操作类型:\n"
            "  replace  — 替换文本: 需要 target + content\n"
            "  insert   — 在指定行号前插入: 需要 line_number + content\n"
            "  append   — 在文件末尾追加: 需要 content\n"
            "  delete   — 删除匹配的文本: 需要 target\n"
            "  replace_line — 替换指定行: 需要 line_number + content"
        )
    )
    target: Optional[str] = Field(default=None, description="要查找的目标文本（replace/delete 时使用）")
    content: Optional[str] = Field(default=None, description="新内容（replace/insert/append/replace_line 时使用）")
    line_number: Optional[int] = Field(default=None, description="行号（insert/replace_line 时使用，从1开始）")
    node: Optional[int] = Field(default=None, description="指定节点编号，用于定位具体脚本文件")
    preview: bool = Field(default=True, description="是否返回修改后的预览（默认开启）")


class TCADModifyScriptTool(BaseTool):
    name: str = "tcad_modify_script"
    description: str = (
        "修改 SWB 项目中工具的 .cmd 仿真脚本文件。\n"
        "支持的操作:\n"
        "  replace      — 替换脚本中的指定文本（精确匹配）\n"
        "  insert       — 在指定行号前插入新内容\n"
        "  append       — 在脚本末尾追加内容\n"
        "  delete       — 删除匹配的文本行\n"
        "  replace_line — 替换指定行号的整行内容\n"
        "注意: 修改 .cmd 文件是直接修改仿真脚本，不会同步到仿真树。"
    )
    args_schema: Type[BaseModel] = ModifyScriptSchema

    def _run(self, project_path: str, tool: str, action: str,
             target: Optional[str] = None, content: Optional[str] = None,
             line_number: Optional[int] = None, node: Optional[int] = None,
             preview: bool = True) -> str:
        try:
            import glob as _glob
            prj_abs = os.path.abspath(project_path)
            if not os.path.isdir(prj_abs):
                return f"项目路径不存在: {prj_abs}"

            # 查找对应的 .cmd 文件（复用 ReadScriptTool 的逻辑）
            cmd_files = sorted(_glob.glob(os.path.join(prj_abs, "*.cmd")))
            if not cmd_files:
                return (
                    f"项目中没有找到 .cmd 脚本文件: {prj_abs}\n"
                    f"提示: 新添加的工具需要先运行预处理才能生成 .cmd 脚本文件。\n"
                    f"请调用 tcad_run_simulation(project_path='...', mode='preprocess') 先执行预处理。"
                )

            # 获取工具的 acronym，用于精确匹配 .cmd 文件
            _ensure_swbpy2()
            tree = _get_tree(project_path)
            tool_acronym = None
            try:
                all_tools = tree.AllTools()
                if tool in all_tools:
                    db_tool_name = tree.DBTool(tool)
                    tool_acronym = tree.GetDBToolCtxItem(f'{db_tool_name},acronym')
            except Exception:
                pass

            matched_files = []
            for fpath in cmd_files:
                fname = os.path.basename(fpath).replace(".cmd", "")
                parts = fname.rsplit("_", 1)
                if len(parts) == 2:
                    label, acronym = parts
                    # 优先匹配 tool_label + acronym 组合
                    if label.lower() == tool.lower() and tool_acronym and acronym.lower() == tool_acronym.lower():
                        matched_files = [fpath]  # 精确匹配，直接覆盖
                        break
                    if label.lower() == tool.lower() or acronym.lower() == tool.lower():
                        matched_files.append(fpath)

            if not matched_files:
                for fpath in cmd_files:
                    fname = os.path.basename(fpath).lower()
                    if tool.lower() in fname and fpath not in matched_files:
                        matched_files.append(fpath)

            if not matched_files:
                available = [os.path.basename(f) for f in cmd_files]
                return (
                    f"未找到工具 '{tool}' 对应的脚本文件。\n"
                    f"可用的脚本文件: {available}"
                )

            if len(matched_files) > 1:
                names = [os.path.basename(f) for f in matched_files]
                return (
                    f"找到多个匹配的脚本文件: {names}\n"
                    f"请用更精确的工具名称指定。"
                )

            fpath = matched_files[0]
            fname = os.path.basename(fpath)

            # 读取原文件
            with open(fpath, "r", errors="replace") as f:
                original_lines = f.readlines()

            original_text = "".join(original_lines)
            new_lines = list(original_lines)
            modified = False

            action = action.strip().lower()

            if action == "replace":
                if not target:
                    return "replace 操作需要 target 参数（要替换的文本）"
                if content is None:
                    return "replace 操作需要 content 参数（新文本）"
                if target not in original_text:
                    # 显示附近的上下文帮助用户定位
                    similar = [l.rstrip() for l in original_lines if target[:20] in l]
                    msg = f"未在 {fname} 中找到目标文本:\n  '{target}'"
                    if similar:
                        msg += f"\n找到部分匹配的行:\n" + "\n".join(f"  {l}" for l in similar[:5])
                    return msg
                new_text = original_text.replace(target, content, 1)
                new_lines = new_text.splitlines(keepends=True)
                modified = True

            elif action == "insert":
                if line_number is None:
                    return "insert 操作需要 line_number 参数（在该行前插入）"
                if content is None:
                    return "insert 操作需要 content 参数"
                if line_number < 1 or line_number > len(original_lines) + 1:
                    return f"行号 {line_number} 超出范围 (1-{len(original_lines) + 1})"
                insert_line = content if content.endswith("\n") else content + "\n"
                new_lines.insert(line_number - 1, insert_line)
                modified = True

            elif action == "append":
                if content is None:
                    return "append 操作需要 content 参数"
                append_line = content if content.endswith("\n") else content + "\n"
                new_lines.append(append_line)
                modified = True

            elif action == "delete":
                if not target:
                    return "delete 操作需要 target 参数（要删除的文本）"
                new_lines = [l for l in original_lines if target not in l]
                if len(new_lines) == len(original_lines):
                    return f"未在 {fname} 中找到包含 '{target}' 的行"
                modified = True

            elif action == "replace_line":
                if line_number is None:
                    return "replace_line 操作需要 line_number 参数"
                if content is None:
                    return "replace_line 操作需要 content 参数"
                if line_number < 1 or line_number > len(original_lines):
                    return f"行号 {line_number} 超出范围 (1-{len(original_lines)})"
                new_lines[line_number - 1] = content if content.endswith("\n") else content + "\n"
                modified = True

            else:
                return (
                    f"不支持的操作: '{action}'\n"
                    f"支持: replace, insert, append, delete, replace_line"
                )

            if not modified:
                return f"文件 {fname} 未被修改"

            # 写回文件
            with open(fpath, "w") as f:
                f.writelines(new_lines)

            # 构建结果
            result_parts = [
                f"✅ 脚本已修改: {fname}",
                f"  操作: {action}",
            ]
            if target:
                result_parts.append(f"  目标: '{target}'")
            if content:
                result_parts.append(f"  新内容: '{content[:100]}{'...' if len(content) > 100 else ''}'")
            if line_number:
                result_parts.append(f"  行号: {line_number}")

            result_parts.append(f"  修改前行数: {len(original_lines)}")
            result_parts.append(f"  修改后行数: {len(new_lines)}")

            # 返回修改后的预览
            if preview:
                result_parts.append(f"\n📄 修改后的 {fname} (前 30 行):")
                for i, line in enumerate(new_lines[:30], 1):
                    marker = " >>>" if i == line_number else "    "
                    result_parts.append(f"{marker} {i:>4} | {line.rstrip()}")
                if len(new_lines) > 30:
                    result_parts.append(f"    ... (共 {len(new_lines)} 行)")

            return "\n".join(result_parts)

        except ImportError:
            return SWB_ERR_MSG
        except Exception as e:
            return f"修改脚本失败: {type(e).__name__}: {e}"


class WebSearchSchema(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5, description="最大返回结果数，默认 5")


class TCADWebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "在互联网上搜索信息并返回结果摘要。\n"
        "可用于搜索 TCAD 相关文档、技术资料、仿真参数等。\n"
        "返回搜索结果的标题、链接和摘要。"
    )
    args_schema: Type[BaseModel] = WebSearchSchema

    def _run(self, query: str, max_results: int = 5) -> str:
        import requests
        from bs4 import BeautifulSoup
        import urllib.parse
        import re

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        # 使用百度搜索
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.baidu.com/s?wd={encoded_query}&rn={max_results}"

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # 百度搜索结果
            for item in soup.select('.result, .c-container')[:max_results]:
                title_elem = item.select_one('h3 a, .t a')
                snippet_elem = item.select_one('.c-abstract, .c-span-last')

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else '无摘要'
                    # 过滤掉明显无关的结果
                    if title and len(title) > 5:
                        results.append({'title': title, 'link': link, 'body': snippet})

            if results:
                lines = [f"搜索结果: '{query}'\n{'=' * 50}"]
                for i, r in enumerate(results[:max_results], 1):
                    title = r.get('title', '无标题')
                    link = r.get('link', '无链接')
                    body = r.get('body', '无摘要')
                    lines.append(f"\n{i}. {title}")
                    lines.append(f"   链接: {link}")
                    lines.append(f"   摘要: {body[:200]}{'...' if len(body) > 200 else ''}")
                return "\n".join(lines)

        except Exception as e:
            pass

        # 备用方案: 使用搜狗搜索
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.sogou.com/web?query={encoded_query}"

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            for item in soup.select('.vrwrap, .rb')[:max_results]:
                title_elem = item.select_one('h3 a')
                snippet_elem = item.select_one('.space-txt, .str_info')

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else '无摘要'
                    if title and len(title) > 5:
                        results.append({'title': title, 'link': link, 'body': snippet})

            if results:
                lines = [f"搜索结果: '{query}'\n{'=' * 50}"]
                for i, r in enumerate(results[:max_results], 1):
                    title = r.get('title', '无标题')
                    link = r.get('link', '无链接')
                    body = r.get('body', '无摘要')
                    lines.append(f"\n{i}. {title}")
                    lines.append(f"   链接: {link}")
                    lines.append(f"   摘要: {body[:200]}{'...' if len(body) > 200 else ''}")
                return "\n".join(lines)

        except Exception:
            pass

        return (
            f"搜索失败: 无法获取搜索结果。\n"
            f"建议: 请检查网络连接或稍后重试。"
        )


class WebFetchSchema(BaseModel):
    url: str = Field(description="要获取的网页 URL")
    max_length: int = Field(default=5000, description="返回内容最大长度，默认 5000 字符")


class TCADWebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = (
        "获取指定网页的内容并返回文本摘要。\n"
        "可用于读取在线文档、技术文章等。"
    )
    args_schema: Type[BaseModel] = WebFetchSchema

    def _run(self, url: str, max_length: int = 5000) -> str:
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除脚本和样式
            for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()

            # 获取文本
            text = soup.get_text(separator='\n', strip=True)

            # 清理多余空行
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)

            if len(text) > max_length:
                text = text[:max_length] + f"\n\n... (内容已截断，共 {len(text)} 字符)"

            return f"网页内容: {url}\n{'=' * 50}\n{text}"

        except ImportError:
            return "错误: requests 或 beautifulsoup4 库未安装"
        except requests.exceptions.RequestException as e:
            return f"获取网页失败: {e}"
        except Exception as e:
            return f"处理网页失败: {type(e).__name__}: {e}"


class TCADDocSearchSchema(BaseModel):
    query: str = Field(description="搜索关键词（如命令名、功能描述等）")
    tool: Optional[str] = Field(
        default=None,
        description="指定工具文档: 'sde' | 'sdevice' | 'sprocess' | 'svisual'。不指定则搜索所有文档。"
    )
    max_results: int = Field(default=5, description="最大返回结果数，默认 5")


class TCADDocSearchTool(BaseTool):
    name: str = "tcad_doc_search"
    description: str = (
        "搜索 TCAD 本地文档和手册。\n"
        "可用于查找 sdevice、sde、sprocess 等工具的命令语法、参数说明、示例等。\n"
        "比 web_search 更精确地获取 TCAD 专业技术文档。"
    )
    args_schema: Type[BaseModel] = TCADDocSearchSchema

    def _run(self, query: str, tool: Optional[str] = None, max_results: int = 5) -> str:
        try:
            import re
            from bs4 import BeautifulSoup

            tcad_root = TCAD_ROOT
            tcad_release = TCAD_RELEASE

            # 文档目录映射
            doc_dirs = {
                'sde': [
                    os.path.join(tcad_root, 'tcad', tcad_release, 'Sentaurus_Training', 'sde'),
                    os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_sde_ug'),
                ],
                'sdevice': [
                    os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_sdevice_ug'),
                    os.path.join(tcad_root, 'tcad', tcad_release, 'Sentaurus_Training', 'sdevice'),
                ],
                'sprocess': [
                    os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_sprocess_ug'),
                ],
                'svisual': [
                    os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_svisual_ug'),
                ],
            }

            # 确定搜索目录
            if tool and tool.lower() in doc_dirs:
                search_dirs = doc_dirs[tool.lower()]
            else:
                search_dirs = []
                for dirs in doc_dirs.values():
                    search_dirs.extend(dirs)

            results = []
            query_lower = query.lower()

            for doc_dir in search_dirs:
                if not os.path.isdir(doc_dir):
                    continue

                for root, dirs, files in os.walk(doc_dir):
                    for fname in files:
                        if not fname.endswith('.html'):
                            continue

                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                            # 检查关键词是否出现
                            if query_lower not in content.lower():
                                continue

                            soup = BeautifulSoup(content, 'html.parser')

                            # 移除脚本和样式
                            for tag in soup(['script', 'style']):
                                tag.decompose()

                            text = soup.get_text(separator='\n', strip=True)

                            # 查找包含关键词的段落
                            paragraphs = text.split('\n\n')
                            relevant = []
                            for para in paragraphs:
                                if query_lower in para.lower():
                                    # 截取相关部分
                                    para_clean = para.strip()
                                    if len(para_clean) > 50:
                                        relevant.append(para_clean[:300])

                            if relevant:
                                rel_path = os.path.relpath(fpath, tcad_root)
                                results.append({
                                    'file': rel_path,
                                    'content': '\n'.join(relevant[:3]),
                                })

                        except Exception:
                            continue

            if not results:
                return f"未在 TCAD 文档中找到与 '{query}' 相关的内容"

            lines = [f"TCAD 文档搜索结果: '{query}'\n{'=' * 50}"]
            for i, r in enumerate(results[:max_results], 1):
                lines.append(f"\n{i}. 文件: {r['file']}")
                lines.append(f"   内容:\n{r['content'][:500]}{'...' if len(r['content']) > 500 else ''}")

            return "\n".join(lines)

        except Exception as e:
            return f"文档搜索失败: {type(e).__name__}: {e}"


class TCADExampleSearchSchema(BaseModel):
    tool: str = Field(description="工具名称: 'sde' | 'sdevice' | 'sprocess' | 'svisual'")
    keyword: Optional[str] = Field(default=None, description="可选关键词，用于过滤示例")


class TCADExampleSearchTool(BaseTool):
    name: str = "tcad_example_search"
    description: str = (
        "搜索 TCAD Applications_Library 中的示例项目。\n"
        "可用于查找特定工具的使用示例、脚本模板等。\n"
        "返回示例项目的路径和关键文件内容。"
    )
    args_schema: Type[BaseModel] = TCADExampleSearchSchema

    def _run(self, tool: str, keyword: Optional[str] = None) -> str:
        try:
            from bs4 import BeautifulSoup

            tcad_root = TCAD_ROOT
            tcad_release = TCAD_RELEASE

            # 示例目录
            examples_dir = os.path.join(tcad_root, 'tcad', tcad_release, 'Applications_Library')
            if not os.path.isdir(examples_dir):
                return f"示例目录不存在: {examples_dir}"

            results = []
            tool_lower = tool.lower()

            for root, dirs, files in os.walk(examples_dir):
                # 查找包含指定工具的目录
                if tool_lower not in root.lower():
                    continue

                # 检查是否有 .cmd 文件
                cmd_files = [f for f in files if f.endswith('.cmd') and tool_lower in f.lower()]
                if not cmd_files:
                    continue

                # 如果有关键词过滤
                if keyword:
                    keyword_lower = keyword.lower()
                    found = False
                    for cmd_file in cmd_files:
                        cmd_path = os.path.join(root, cmd_file)
                        try:
                            with open(cmd_path, 'r', errors='ignore') as f:
                                if keyword_lower in f.read().lower():
                                    found = True
                                    break
                        except Exception:
                            pass
                    if not found:
                        continue

                # 收集示例信息
                rel_path = os.path.relpath(root, examples_dir)
                readme = None
                for f in files:
                    if f.startswith('greadme') and f.endswith('.html'):
                        readme_path = os.path.join(root, f)
                        try:
                            with open(readme_path, 'r', errors='ignore') as f:
                                soup = BeautifulSoup(f.read(), 'html.parser')
                                readme = soup.get_text()[:200]
                        except Exception:
                            pass

                results.append({
                    'path': rel_path,
                    'cmd_files': cmd_files[:3],
                    'readme': readme,
                })

            if not results:
                return f"未找到包含 '{tool}' 工具的示例项目"

            lines = [f"TCAD 示例项目: {tool}\n{'=' * 50}"]
            for i, r in enumerate(results[:5], 1):
                lines.append(f"\n{i}. 路径: {r['path']}")
                lines.append(f"   脚本文件: {', '.join(r['cmd_files'])}")
                if r['readme']:
                    lines.append(f"   说明: {r['readme'][:150]}...")

            return "\n".join(lines)

        except Exception as e:
            return f"示例搜索失败: {type(e).__name__}: {e}"


class CommandRefSchema(BaseModel):
    command: str = Field(
        description=(
            "命令名称，支持以下格式:\n"
            "  'sdegeo:create-rectangle' — 完整命令名\n"
            "  'create-rectangle' — 命令名（自动匹配工具）\n"
            "  'Electrode' — sdevice 命令块\n"
            "  'Physics' — 物理模型命令\n"
            "  'Solve' — 求解命令"
        )
    )
    tool: Optional[str] = Field(
        default=None,
        description="指定工具: 'sde' | 'sdevice' | 'sprocess'。不指定则自动检测。"
    )
    max_length: int = Field(
        default=3000,
        description="返回内容最大长度，默认 3000 字符。设置为 0 表示返回全部内容。"
    )


class TCADCommandRefTool(BaseTool):
    name: str = "tcad_command_ref"
    description: str = (
        "TCAD 命令速查工具。\n"
        "快速查找特定命令的语法、参数和示例。\n"
        "比 tcad_doc_search 更精确，适合查找单个命令的详细用法。\n"
        "推荐在编写脚本前使用此工具确认命令语法。"
    )
    args_schema: Type[BaseModel] = CommandRefSchema

    def _run(self, command: str, tool: Optional[str] = None, max_length: int = 3000) -> str:
        try:
            from bs4 import BeautifulSoup

            tcad_root = TCAD_ROOT
            tcad_release = TCAD_RELEASE

            # 规范化命令名
            cmd_lower = command.lower().replace('_', '-').replace(' ', '-')

            # 自动检测工具
            if tool is None:
                if cmd_lower.startswith('sdegeo:') or cmd_lower.startswith('sdedr:') or cmd_lower.startswith('sde:'):
                    tool = 'sde'
                elif cmd_lower.startswith('sdegeo') or cmd_lower.startswith('sdedr'):
                    tool = 'sde'
                elif cmd_lower in ['electrode', 'physics', 'solve', 'math', 'file', 'plot', 'current']:
                    tool = 'sdevice'
                else:
                    tool = 'sde'  # 默认

            # 文档目录映射
            doc_dirs = {
                'sde': os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_sde_ug', 'commands'),
                'sdevice': os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_sdevice_ug'),
                'sprocess': os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus', 'tcad_sprocess_ug'),
            }

            doc_dir = doc_dirs.get(tool)
            if not doc_dir or not os.path.isdir(doc_dir):
                return f"文档目录不存在: {doc_dir}"

            # 构建文件名
            # sdegeo:create-rectangle -> sdegeo_create_rectangle.html
            cmd_file_name = cmd_lower.replace(':', '_').replace('-', '_') + '.html'

            # 尝试直接查找文件
            target_file = None

            # 策略1: 直接匹配文件名
            if os.path.exists(os.path.join(doc_dir, cmd_file_name)):
                target_file = os.path.join(doc_dir, cmd_file_name)

            # 策略2: 在子目录中查找
            if target_file is None:
                for root, dirs, files in os.walk(doc_dir):
                    for f in files:
                        if f == cmd_file_name:
                            target_file = os.path.join(root, f)
                            break
                    if target_file:
                        break

            # 策略3: 模糊匹配
            if target_file is None:
                cmd_keywords = cmd_lower.replace(':', ' ').replace('-', ' ').split()
                for root, dirs, files in os.walk(doc_dir):
                    for f in files:
                        if not f.endswith('.html'):
                            continue
                        fname_lower = f.lower()
                        if all(kw in fname_lower for kw in cmd_keywords):
                            target_file = os.path.join(root, f)
                            break
                    if target_file:
                        break

            if target_file is None:
                return f"未找到命令 '{command}' 的文档。请尝试使用 tcad_doc_search 搜索关键词。"

            # 读取文档
            with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup(['script', 'style']):
                tag.decompose()

            text = soup.get_text(separator='\n', strip=True)

            # 提取关键部分
            lines = text.split('\n')
            result_lines = []
            in_section = None
            section_content = []

            # 定义要提取的章节
            sections_to_extract = [
                'description', 'syntax', 'examples', 'example',
                'arguments', 'argument', 'parameters', 'parameters:',
                'options', 'usage', 'notes', 'related'
            ]

            for line in lines:
                line_stripped = line.strip()
                line_lower = line_stripped.lower()

                # 检测章节标题
                if line_lower in sections_to_extract or line_lower.endswith(':'):
                    section_name = line_lower.rstrip(':')
                    if section_name in sections_to_extract:
                        # 保存之前的章节内容
                        if in_section and section_content:
                            result_lines.append(f'\n── {in_section.upper()} ──')
                            result_lines.extend(section_content)
                        in_section = section_name
                        section_content = []
                        continue

                # 收集章节内容
                if in_section and line_stripped:
                    section_content.append(f"  {line_stripped}")

                # 如果章节内容太多，只保留关键部分
                if len(section_content) > 50:
                    section_content = section_content[:50]
                    section_content.append("  ... (章节内容过长，已截断)")

            # 保存最后一个章节
            if in_section and section_content:
                result_lines.append(f'\n── {in_section.upper()} ──')
                result_lines.extend(section_content)

            # 如果没有提取到结构化内容，返回文档的前部分内容
            if not result_lines:
                result_lines = [line for line in lines[:100] if line.strip()]

            # 构建结果
            result = f"📖 命令: {command}\n{'=' * 50}\n"
            result += '\n'.join(result_lines)

            # 应用 max_length 限制
            if max_length > 0 and len(result) > max_length:
                result = result[:max_length] + f"\n\n... (内容已截断，共 {len(result)} 字符，显示前 {max_length} 字符)"

            return result

        except Exception as e:
            return f"命令查询失败: {type(e).__name__}: {e}"


class DocReadSchema(BaseModel):
    file_path: str = Field(
        description=(
            "文档文件路径，支持以下格式:\n"
            "  'tcad_sdevice_ug/physics_in_sentaurus_device.html' — 相对于 TCAD 文档目录\n"
            "  'tcad_sde_ug/commands/sdegeo_create_rectangle.html' — 完整相对路径\n"
            "  绝对路径也可以直接使用"
        )
    )
    section: Optional[str] = Field(
        default=None,
        description="指定要读取的章节（如 'Mobility', 'Syntax', 'Examples'）。不指定则读取全文。"
    )
    max_length: int = Field(
        default=5000,
        description="返回内容最大长度，默认 5000 字符。设置为 0 表示返回全部内容。"
    )


class TCADDocReadTool(BaseTool):
    name: str = "tcad_doc_read"
    description: str = (
        "读取 TCAD 文档文件的完整内容。\n"
        "可用于深入阅读特定文档章节，获取详细的语法说明和示例。\n"
        "支持指定章节读取，避免返回过多无关内容。"
    )
    args_schema: Type[BaseModel] = DocReadSchema

    def _run(self, file_path: str, section: Optional[str] = None, max_length: int = 5000) -> str:
        try:
            from bs4 import BeautifulSoup

            tcad_root = TCAD_ROOT
            tcad_release = TCAD_RELEASE

            # 解析文件路径
            if os.path.isabs(file_path):
                full_path = file_path
            else:
                # 尝试在文档目录中查找
                doc_base = os.path.join(tcad_root, 'tcad', tcad_release, 'manuals', 'olh_sentaurus')
                full_path = os.path.join(doc_base, file_path)

                # 如果找不到，尝试其他目录
                if not os.path.exists(full_path):
                    training_base = os.path.join(tcad_root, 'tcad', tcad_release, 'Sentaurus_Training')
                    full_path = os.path.join(training_base, file_path)

            if not os.path.exists(full_path):
                return f"文档文件不存在: {full_path}"

            # 读取文档
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup(['script', 'style']):
                tag.decompose()

            text = soup.get_text(separator='\n', strip=True)
            lines = text.split('\n')

            # 如果指定了章节，只提取该章节
            if section:
                section_lower = section.lower()
                result_lines = []
                in_section = False
                section_found = False
                section_start_line = -1

                # 首先找到章节的起始位置
                for i, line in enumerate(lines):
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()

                    # 检测章节开始（更严格的匹配）
                    if section_lower in line_lower:
                        # 检查是否是独立的章节标题（不是目录项）
                        if (line_lower.endswith(':') or
                            (len(line_stripped) < 50 and not line_stripped.startswith('•'))):
                            section_start_line = i
                            section_found = True
                            break

                if not section_found:
                    return f"未找到章节 '{section}'。请尝试使用 tcad_doc_search 搜索相关关键词。"

                # 从章节开始位置提取内容
                in_section = True
                for i in range(section_start_line, len(lines)):
                    line_stripped = lines[i].strip()
                    line_lower = line_stripped.lower()

                    # 跳过章节标题本身
                    if i == section_start_line:
                        result_lines.append(f"── {line_stripped} ──")
                        continue

                    # 检测章节结束（遇到新的主章节标题）
                    if in_section and line_stripped:
                        # 新的主章节标题通常是大写开头，较短，且不是列表项
                        if (line_stripped[0].isupper() and
                            len(line_stripped) < 50 and
                            not line_stripped.startswith('•') and
                            not line_stripped.startswith('-') and
                            not line_stripped.startswith('(')):
                            # 检查是否是已知的章节标题
                            known_sections = [
                                'description', 'syntax', 'examples', 'example',
                                'arguments', 'argument', 'parameters', 'parameters:',
                                'options', 'usage', 'notes', 'related', 'returns',
                                'see also', 'references', 'generation', 'recombination',
                                'traps', 'tunneling', 'noise', 'radiation'
                            ]
                            if any(keyword in line_lower for keyword in known_sections):
                                in_section = False
                                continue

                    # 收集章节内容
                    if in_section and line_stripped:
                        result_lines.append(line_stripped)

                    # 限制章节内容长度
                    if len(result_lines) > 200:
                        result_lines.append("... (章节内容过长，已截断)")
                        break

                result_text = '\n'.join(result_lines)
            else:
                # 返回全文
                result_text = '\n'.join(line for line in lines if line.strip())

            # 构建结果
            rel_path = os.path.relpath(full_path, tcad_root)
            result = f"📖 文档: {rel_path}\n{'=' * 50}\n"

            # 应用 max_length 限制
            if max_length > 0 and len(result_text) > max_length:
                result += result_text[:max_length] + f"\n\n... (内容已截断，共 {len(result_text)} 字符，显示前 {max_length} 字符)"
            else:
                result += result_text

            return result

        except Exception as e:
            return f"文档读取失败: {type(e).__name__}: {e}"


def get_tcad_tools() -> List[BaseTool]:
    return [
        TCADProjectTool(),
        TCADSimulationTool(),
        TCADStatusTool(),
        TCADModifyTool(),
        TCADResultsTool(),
        TCADCleanupTool(),
        TCADTailOutputTool(),
        TCADReadScriptTool(),
        TCADModifyScriptTool(),
        TCADWebSearchTool(),
        TCADWebFetchTool(),
        TCADDocSearchTool(),
        TCADExampleSearchTool(),
        TCADCommandRefTool(),
        TCADDocReadTool(),
    ]


if __name__ == "__main__":
    print("可用 TCAD LangChain 工具:")
    for t in get_tcad_tools():
        print(f"  - {t.name}: {t.description[:60]}...")
