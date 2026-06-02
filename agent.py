"""
TCAD Agent — LangGraph-based agent with streaming support.

Assembles LLM model + TCAD tools + system prompt into an interactive agent.
Supports streaming output, conversation persistence, and CLI interaction.

Usage:
    python agent.py                          # Interactive chat mode
    python agent.py -q "帮我打开项目 /path/to/prj"  # Single query mode
"""

import os
import sys
import json
import logging
from typing import Any, Optional

from dotenv import load_dotenv

# Sentinel to distinguish "caller didn't pass checkpointer" from
# "caller explicitly passed None" (the latter means: use no checkpointer,
# e.g. when the LangGraph API server manages persistence itself).
_USE_DEFAULT_CHECKPOINTER: Any = object()

from langchain_openai import ChatOpenAI
from langchain_openai.chat_models import base as lc_openai_base
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from tool import get_tcad_tools

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "TCAD_SYSTEM_PROMPT.md")


# ── DeepSeek reasoning_content workaround ──────────────────────────────
# DeepSeek API returns `reasoning_content` in assistant messages, and
# requires it to be echoed back on subsequent turns.  langchain-openai's
# default converters drop this field, so we patch them here.

_orig_dict_to_msg = lc_openai_base._convert_dict_to_message
_orig_msg_to_dict = lc_openai_base._convert_message_to_dict


def _patched_dict_to_msg(d):
    msg = _orig_dict_to_msg(d)
    if isinstance(msg, AIMessage):
        reasoning = d.get("reasoning_content")
        if reasoning:
            msg.additional_kwargs["reasoning_content"] = reasoning
    return msg


def _patched_msg_to_dict(message, api="chat/completions"):
    result = _orig_msg_to_dict(message, api)
    if isinstance(message, AIMessage):
        reasoning = message.additional_kwargs.get("reasoning_content")
        if reasoning:
            result["reasoning_content"] = reasoning
    return result


lc_openai_base._convert_dict_to_message = _patched_dict_to_msg
lc_openai_base._convert_message_to_dict = _patched_msg_to_dict


# ── Prompt ───────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """Load the TCAD system prompt from file, with a fallback."""
    if not os.path.exists(SYSTEM_PROMPT_PATH):
        logger.warning("System prompt not found at %s, using fallback", SYSTEM_PROMPT_PATH)
        return (
            "你是 TCAD 仿真助手。使用可用工具帮助用户完成 Synopsys Sentaurus TCAD "
            "仿真任务。先打开项目再操作。"
        )
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ── Agent Builder ────────────────────────────────────────────────────────

def build_agent(
    model_name: Optional[str] = None,
    temperature: float = 0.1,
    checkpointer: Any = _USE_DEFAULT_CHECKPOINTER,
) -> Any:
    """Build a compiled TCAD LangGraph agent.

    Args:
        model_name: LLM model identifier (default from env ``LLM_MODEL_NAME``).
        temperature: Sampling temperature.
        checkpointer: Optional persistence backend.  When omitted (the
            default), a local ``MemorySaver`` is used.  Pass ``None`` to
            skip adding a checkpointer (used by the LangGraph API server
            which provides its own persistence).  Pass an explicit instance
            to inject a custom backend.

    Returns:
        A compiled ``CompiledStateGraph`` ready for streaming invocation.

    Raises:
        ValueError: If the API key is not configured.
    """
    api_key = os.getenv("API_KEY_NAME")
    base_url = os.getenv("API_BASE_URL")
    model = model_name or os.getenv("LLM_MODEL_NAME", "deepseek-v4-flash")

    if not api_key:
        raise ValueError(
            "API_KEY_NAME 未设置。请在 .env 文件中配置，或设置环境变量 API_KEY_NAME。"
        )

    tools = get_tcad_tools()
    system_prompt = load_system_prompt()

    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        streaming=True,
        api_key=api_key,
        base_url=base_url if base_url else None,
    )

    if checkpointer is _USE_DEFAULT_CHECKPOINTER:
        checkpointer = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=system_prompt),
        checkpointer=checkpointer,
    )

    return agent


# ── Streaming Runner ────────────────────────────────────────────────────

def run_streaming(
    agent: Any,
    user_input: str,
    thread_id: str = "tcad_default",
    show_intermediate: bool = False,
) -> None:
    """Run a single user turn with streaming output.

    Args:
        agent: Compiled LangGraph agent.
        user_input: The user's message.
        thread_id: Conversation thread identifier (for state persistence).
        show_intermediate: If True, also print tool-call thoughts.
    """
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content=user_input)]}

    for chunk in agent.stream(inputs, config=config, stream_mode="values"):
        messages = chunk.get("messages", [])
        if not messages:
            continue

        last_msg = messages[-1]

        if isinstance(last_msg, HumanMessage):
            print(f"\n👤  {last_msg.content}")

        elif isinstance(last_msg, AIMessage):
            # ── 显示模型思考过程 ──
            reasoning = last_msg.additional_kwargs.get("reasoning_content")
            if reasoning:
                lines = reasoning.strip().split("\n")
                if len(lines) > 30:
                    # 太长则显示前后各 15 行
                    print("\n💭 模型思考过程 (太长已截断，显示首尾):", flush=True)
                    for line in lines[:15]:
                        print(f"   {line}", flush=True)
                    print("   ... (中间省略) ...", flush=True)
                    for line in lines[-15:]:
                        print(f"   {line}", flush=True)
                    print("💭 思考结束\n", flush=True)
                else:
                    print("\n💭 模型思考过程:", flush=True)
                    for line in lines:
                        print(f"   {line}", flush=True)
                    print("💭 思考结束\n", flush=True)

            # ── 显示回复内容 ──
            text = last_msg.content
            if text:
                print(text, flush=True)
            else:
                print(flush=True)

            if show_intermediate and last_msg.tool_calls:
                for tc in last_msg.tool_calls:
                    args_preview = json.dumps(tc["args"], ensure_ascii=False)
                    print(
                        f"🔧  调用工具: {tc['name']}({args_preview})",
                        flush=True,
                    )

        elif show_intermediate and hasattr(last_msg, "name"):
            content_preview = str(last_msg.content)[:200]
            print(f"📎  工具返回 ({last_msg.name}): {content_preview}", flush=True)

    print()


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="TCAD Agent — 流式交互 CLI")
    parser.add_argument("-q", "--query", help="单轮查询模式（不进入交互循环）")
    parser.add_argument("-m", "--model", help="模型名称（覆盖环境变量 LLM_MODEL_NAME）")
    parser.add_argument("-t", "--temperature", type=float, default=0.1)
    parser.add_argument("-v", "--verbose", action="store_true", help="显示中间步骤")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s | %(message)s",
    )

    try:
        agent = build_agent(model_name=args.model, temperature=args.temperature)
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        sys.exit(1)

    if args.query:
        run_streaming(agent, args.query, show_intermediate=args.verbose)
        return

    print("╔══════════════════════════════════════════════╗")
    print("║        🤖  TCAD Agent  已启动                ║")
    print("║  输入 exit / quit 退出                       ║")
    print("╚══════════════════════════════════════════════╝")

    thread_id = "tcad_session_1"

    while True:
        try:
            user_input = input("\n👤  ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("再见！")
            break

        try:
            run_streaming(agent, user_input, thread_id=thread_id, show_intermediate=args.verbose)
        except Exception as e:
            print(f"\n❌ 错误: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
