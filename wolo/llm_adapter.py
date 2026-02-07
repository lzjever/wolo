"""
Wolo LLM Client Adapter using lexilux.

This adapter provides wolo-specific functionality while leveraging
lexilux's standard OpenAI-compatible client for HTTP/SSE/error handling.

Supports all OpenAI-compatible model services (OpenAI, Anthropic, DeepSeek, etc.)
"""

import json
import logging
import os
import platform
import time
from collections.abc import AsyncIterator
from typing import Any

from lexilux.chat import Chat
from lexilux.chat.params import ChatParams
from lexilux.chat.tools import FunctionTool
from lexilux.exceptions import APIError, AuthenticationError, RateLimitError
from lexilux.exceptions import TimeoutError as LexiluxTimeoutError

from wolo.agents import AgentConfig
from wolo.config import Config
from wolo.context_state.vars import _token_usage_ctx
from wolo.errors import WoloAPIError

logger = logging.getLogger(__name__)


class WoloLLMClient:
    """
    Wolo LLM client adapter using lexilux.

    支持所有 OpenAI 兼容的模型服务 (OpenAI, Anthropic, DeepSeek, 等)

    职责：
    1. 使用 lexilux 作为底层 HTTP/SSE 客户端
    2. 转换 lexilux 事件格式为 wolo 事件格式
    3. 构建 opencode-style headers
    4. 保留产品级调试日志
    5. 处理推理模型的 reasoning 模式
    """

    def __init__(
        self,
        config: Config,
        agent_config: AgentConfig | None = None,
        session_id: str | None = None,
        agent_display_name: str | None = None,
    ):
        """初始化 Wolo LLM 适配器 (支持所有 OpenAI 兼容模型)."""
        # 构建 opencode headers
        headers = self._build_opencode_headers(session_id, agent_display_name)

        # ✅ 配置 ChatParams
        extra_params = None
        if config.enable_think:
            # 推理模式: 部分 OpenAI-compatible providers 需要 thinking 参数
            extra_params = {"thinking": {"type": "enabled"}}

        temperature = config.temperature or 1.0
        max_tokens = config.max_tokens

        params = ChatParams(temperature=temperature, max_tokens=max_tokens, extra=extra_params)

        # 初始化 lexilux Chat 客户端
        # 超时配置:
        # - connect_timeout: 10秒连接超时
        # - read_timeout: 推理模式需要更长超时 (300s)，普通模式 120s
        read_timeout = 300.0 if config.enable_think else 120.0
        self._lexilux_chat = Chat(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            headers=headers,
            connect_timeout_s=10.0,  # 10秒连接超时
            read_timeout_s=read_timeout,  # 推理模式 5分钟，普通模式 2分钟
        )

        # 存储默认参数
        self._default_params = params

        # Wolo 产品配置
        self._debug_llm_file = config.debug_llm_file
        self._debug_full_dir = config.debug_full_dir
        self._request_count = 0
        self._finish_reason = None
        self._agent_display_name = agent_display_name
        self._session_id = session_id or "unknown"

        # Store config reference for compatibility (public API)
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.enable_think = config.enable_think  # Used for include_reasoning flag

        # Track which tool calls we've already emitted events for
        self._emitted_tool_call_starts: set[int] = set()

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        主要聊天完成方法 - 转换 lexilux 事件为 wolo 格式.

        Args:
            messages: List of message dicts
            tools: Optional tool definitions
            stream: Enable streaming (always True for wolo)

        Yields:
            Wolo 事件格式:
            - {"type": "reasoning-delta", "text": "..."}
            - {"type": "text-delta", "text": "..."}
            - {"type": "tool-call", "tool": "name", "input": {...}, "id": "..."}
            - {"type": "finish", "reason": "stop"}
        """
        # 1. 产品级调试日志
        self._log_request(messages)

        # 2. 格式转换
        lexilux_messages = self._to_lexilux_messages(messages)
        lexilux_tools = self._convert_tools(tools)

        # Reset finish reason, token usage, and tool call tracking
        self._finish_reason = None
        self._emitted_tool_call_starts = set()
        _token_usage_ctx.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

        try:
            # 3. ✅ 调用 lexilux 并启用 reasoning 解析
            lexilux_stream = await self._lexilux_chat.astream(
                messages=lexilux_messages,
                tools=lexilux_tools,
                params=self._default_params,
                include_reasoning=self.enable_think,  # ✅ 使用 lexilux reasoning 功能
            )

            # 4. 事件格式转换：lexilux → wolo
            async for lexilux_chunk in lexilux_stream:
                # Update token usage from chunk
                if lexilux_chunk.usage:
                    # Update context-state with new token counts
                    _token_usage_ctx.set(
                        {
                            "prompt_tokens": lexilux_chunk.usage.input_tokens or 0,
                            "completion_tokens": lexilux_chunk.usage.output_tokens or 0,
                            "total_tokens": lexilux_chunk.usage.total_tokens or 0,
                        }
                    )

                # ✅ Reasoning content (推理模型支持)
                if lexilux_chunk.reasoning_content:
                    yield {"type": "reasoning-delta", "text": lexilux_chunk.reasoning_content}

                # 标准文本内容
                if lexilux_chunk.delta:
                    yield {"type": "text-delta", "text": lexilux_chunk.delta}

                # 工具调用 - 使用 lexilux 的流式 tool call 追踪
                for stc in lexilux_chunk.streaming_tool_calls:
                    if stc.is_first and stc.index not in self._emitted_tool_call_starts:
                        # 首次看到这个 tool call - 立即发出 streaming 事件
                        self._emitted_tool_call_starts.add(stc.index)
                        yield {
                            "type": "tool-call-streaming",
                            "tool": stc.name,
                            "id": stc.id,
                            "length": stc.arguments_length,
                        }
                    elif not stc.is_first and stc.arguments_delta:
                        # 后续 chunk 且有新的 arguments - 发出 progress 事件
                        yield {
                            "type": "tool-call-progress",
                            "index": stc.index,
                            "length": stc.arguments_length,
                        }

                    if stc.is_complete:
                        # Tool call 完成 - 发出完整的 tool-call 事件
                        tc = stc.to_tool_call()
                        if tc:
                            yield {
                                "type": "tool-call",
                                "tool": tc.name,
                                "input": tc.get_arguments(),
                                "id": tc.id,
                            }

                # 完成
                if lexilux_chunk.done:
                    self._finish_reason = lexilux_chunk.finish_reason
                    yield {"type": "finish", "reason": lexilux_chunk.finish_reason}

        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            raise WoloAPIError(f"Authentication failed: {e}", 401)
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise WoloAPIError(f"Rate limit exceeded: {e}", 429)
        except LexiluxTimeoutError as e:
            logger.error(f"Request timeout: {e}")
            raise WoloAPIError(f"Request timeout: {e}", 408)
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            raise WoloAPIError(f"LLM API error: {e}", getattr(e, "status_code", 500))
        except Exception as e:
            # 转换异常为 wolo 格式
            logger.error(f"Chat completion failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def _build_opencode_headers(
        self, session_id: str | None, agent_display_name: str | None
    ) -> dict[str, str]:
        """构建 opencode-style headers (wolo 产品特性)."""
        try:
            project_id = os.path.basename(os.getcwd())
        except OSError:
            project_id = "unknown"

        return {
            "User-Agent": f"opencode/1.0.0 ({platform.system()} {platform.release()}; {platform.machine()})",
            "x-opencode-project": project_id,
            "x-opencode-session": session_id or "unknown",
            "x-opencode-request": "user",
            "x-opencode-client": "cli",
        }

    def _log_request(self, messages: list[dict]) -> None:
        """Wolo 产品特定的调试日志."""
        if not self._debug_llm_file and not self._debug_full_dir:
            return

        self._request_count += 1

        try:
            # 增量调试日志
            if self._debug_llm_file:
                with open(self._debug_llm_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{'=' * 60}\n")
                    f.write(f"[{time.strftime('%H:%M:%S')}] Request #{self._request_count}\n")
                    f.write(f"Model: {self.model}\n")

                    # 显示最后一个用户消息以提供上下文
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            content = str(msg.get("content", ""))[:100]
                            f.write(
                                f"User: {content}{'...' if len(str(msg.get('content', ''))) > 100 else ''}\n"
                            )
                            break
                    f.write(f"{'=' * 60}\n")
                    f.flush()

            # 完整调试日志
            if self._debug_full_dir:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                full_debug_file = os.path.join(self._debug_full_dir, f"req_{timestamp}.json")
                with open(full_debug_file, "w", encoding="utf-8") as f:
                    f.write("---INPUT---\n")
                    f.write(
                        json.dumps(
                            {
                                "model": self.model,
                                "messages": messages,
                                "timestamp": timestamp,
                                "request_count": self._request_count,
                            },
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                    f.write("\n---OUTPUT---\n")
                    f.flush()

        except Exception as e:
            logger.error(f"Failed to write debug logs: {e}")

    def _to_lexilux_messages(self, messages: list[dict]) -> list[dict]:
        """转换 wolo 消息格式为 lexilux 格式."""
        formatted_messages = []

        for msg in messages:
            # 工具消息保持原样
            if msg.get("role") == "tool":
                formatted_messages.append(msg)
            elif "tool_calls" in msg:
                # 带工具调用的消息：lexilux 现在支持省略 content 字段
                # 直接传递，不需要添加空的 content
                formatted_messages.append(msg)
            else:
                # 用户/助手/系统消息确保内容为字符串
                content = msg.get("content", "")
                if isinstance(content, list):
                    # 处理多模态内容
                    text_parts = []
                    for p in content:
                        if isinstance(p, dict) and p.get("type") == "text":
                            text_parts.append(p.get("text", ""))
                        elif isinstance(p, str):
                            # 简单字符串列表的情况
                            text_parts.append(p)
                    content = "\n".join(text_parts)

                formatted_messages.append({"role": msg.get("role", "user"), "content": content})

        return formatted_messages

    def _convert_tools(self, tools: list[dict] | None) -> list[FunctionTool] | None:
        """转换 wolo 工具格式为 lexilux FunctionTool 对象."""
        if not tools:
            return None

        lexilux_tools = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                func_def = tool["function"]
                lexilux_tool = FunctionTool(
                    name=func_def.get("name", ""),
                    description=func_def.get("description", ""),
                    parameters=func_def.get("parameters", {}),
                    strict=func_def.get("strict", False),
                )
                lexilux_tools.append(lexilux_tool)
            else:
                # 如果格式不匹配，记录警告但继续处理
                logger.warning(f"Unsupported tool format: {tool}")

        return lexilux_tools

    @property
    def finish_reason(self) -> str | None:
        """获取最后完成的原因."""
        return self._finish_reason

    @classmethod
    async def close_all_sessions(cls):
        """Close all sessions.

        Note: lexilux uses direct HTTP requests without connection pooling,
        so no cleanup is needed. This method exists for API consistency.
        """
        logger.debug("Connection cleanup not needed (lexilux uses direct HTTP requests)")


def get_token_usage() -> dict[str, int]:
    """Get token usage from last API call."""
    try:
        return _token_usage_ctx.get().copy()
    except LookupError:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def reset_token_usage() -> None:
    """Reset token usage tracking."""
    _token_usage_ctx.set({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
