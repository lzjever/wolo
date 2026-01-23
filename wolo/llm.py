"""GLM API client for Wolo."""

import asyncio
import json
import logging
import os
import platform
import time
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from wolo.config import Config
from wolo.errors import (
    WoloAPIError,
    classify_api_error,
    format_user_friendly_error,
    get_retry_strategy,
)

logger = logging.getLogger(__name__)

# Version for User-Agent header (mimicking opencode)
WOLO_VERSION = "1.0.0"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_MS = 1000  # Base delay in milliseconds

# Track last error for user reporting
_last_error_info = None

# Token usage from API response
_api_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

# Fallback system prompt (only used if no agent_config provided)
FALLBACK_SYSTEM_PROMPT = """You are Wolo, an AI coding agent that helps users with software engineering tasks.

## CRITICAL RULE: You MUST use tool calls for ALL actions

You are FORBIDDEN from:
- Writing code in markdown code blocks - use the write tool instead
- Describing what you "would" do - actually DO it with tools

Instead, you MUST:
- Use the **write** tool to create files with code
- Use the **shell** tool to execute commands
- Use the **read** tool to show file contents
- Use the **edit** tool to modify existing files
- Use the **task** tool to spawn subagents for parallel work
- Use the **todowrite** tool to track your progress on complex tasks

Remember: The user wants you to ACT, not talk. Use tools! Complete ALL tasks!
"""


class GLMClient:
    """
    GLM API client with connection pooling.

    Reuses HTTP connections across requests for better performance.
    """

    # Class-level session pool for connection reuse across instances
    _session_pool: dict[str, aiohttp.ClientSession] = {}
    _session_lock = asyncio.Lock()

    def __init__(
        self,
        config: Config,
        agent_config: Any = None,
        session_id: str | None = None,
        agent_display_name: str | None = None,
    ) -> None:
        self.api_key = config.api_key
        self.base_url = config.base_url
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.enable_think = config.enable_think  # GLM thinking mode
        self._finish_reason = None  # Track the actual finish reason
        self._agent_config = agent_config  # Store for system prompt
        self._session_id = session_id or "unknown"  # Track session for opencode-style headers
        self._agent_display_name = (
            agent_display_name  # Agent display name (replaces "Wolo" in prompts)
        )
        self._project_id = os.path.basename(os.getcwd())  # Use current directory as project ID
        self._debug_llm_file = config.debug_llm_file  # Debug file for LLM requests/responses
        self._debug_full_dir = config.debug_full_dir  # Directory for full request/response logs
        self._request_count = 0  # Track request count for debug file naming

        # Connection pool key based on base_url
        self._pool_key = self.base_url

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create a shared aiohttp session for connection reuse.

        Sessions are pooled by base_url to allow connection reuse
        while supporting multiple API endpoints.
        """
        async with GLMClient._session_lock:
            if self._pool_key not in GLMClient._session_pool:
                # Create session with connection pooling settings
                connector = aiohttp.TCPConnector(
                    limit=10,  # Max connections per host
                    limit_per_host=2,  # Max connections to same host
                    keepalive_timeout=30,  # Keep connections alive for 30s
                    enable_cleanup_closed=True,
                )
                timeout = aiohttp.ClientTimeout(
                    total=None,  # No total timeout (LLM can take long for complex tasks)
                    connect=10,  # 10 seconds to connect
                    sock_read=120,  # 2 minutes without any data = timeout
                )
                GLMClient._session_pool[self._pool_key] = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                )
                logger.debug(f"Created new HTTP session for {self._pool_key}")

            return GLMClient._session_pool[self._pool_key]

    @classmethod
    async def close_all_sessions(cls):
        """Close all pooled sessions. Call on application shutdown."""
        async with cls._session_lock:
            for key, session in cls._session_pool.items():
                if not session.closed:
                    await session.close()
                    logger.debug(f"Closed HTTP session for {key}")
            cls._session_pool.clear()

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Call GLM API with streaming support and retry logic.

        Args:
            messages: List of message dicts
            tools: Optional tool definitions
            stream: Enable streaming

        Yields:
            Event dictionaries: delta, tool_call, etc.
        """
        global _last_error_info

        for attempt in range(MAX_RETRIES):
            try:
                async for event in self._chat_completion_attempt(messages, tools, stream):
                    yield event
                _last_error_info = None  # Clear error on success
                return  # Success - exit retry loop

            except (TimeoutError, aiohttp.ClientError, RuntimeError, WoloAPIError) as e:
                # Classify the error
                status_code = getattr(e, "status", None)
                if hasattr(e, "response") and hasattr(e.response, "status"):
                    status_code = e.response.status

                error_text = str(e)
                _last_error_info = classify_api_error(status_code or 0, error_text, e)

                # Check if we should retry
                should_retry, delay = get_retry_strategy(
                    _last_error_info.category, attempt + 1, MAX_RETRIES
                )

                if not should_retry or attempt >= MAX_RETRIES - 1:
                    # Don't retry or out of attempts - raise with user-friendly message
                    user_message = format_user_friendly_error(_last_error_info)
                    logger.error(f"API call failed after {attempt + 1} attempts: {error_text}")
                    raise RuntimeError(user_message) from e

                delay = delay or RETRY_DELAY_MS * (2**attempt)
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{MAX_RETRIES}): {_last_error_info.user_message}. "
                    f"Retrying in {delay}ms..."
                )
                await asyncio.sleep(delay / 1000)

    async def _chat_completion_attempt(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        """Single attempt at calling GLM API with opencode-style headers."""
        url = f"{self.base_url}/chat/completions"

        # opencode-style headers to make requests indistinguishable from opencode
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"opencode/{WOLO_VERSION} ({platform.system()} {platform.release()}; {platform.machine()})",
            "x-opencode-project": self._project_id,
            "x-opencode-session": self._session_id,
            "x-opencode-request": "user",  # Mimicking opencode's user request ID
            "x-opencode-client": "cli",  # Mimicking opencode's client type
        }

        # Add system prompt if not present
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            # Use agent's system prompt if available, otherwise use fallback
            if self._agent_config and hasattr(self._agent_config, "system_prompt"):
                system_prompt = self._agent_config.system_prompt
            else:
                system_prompt = FALLBACK_SYSTEM_PROMPT

            # Replace "Wolo" with agent_display_name if provided
            # Use word boundaries to avoid replacing "Wolo" in the middle of other words
            if self._agent_display_name:
                import re

                # Replace "Wolo" (case-sensitive) with agent_display_name
                system_prompt = re.sub(r"\bWolo\b", self._agent_display_name, system_prompt)
                # Replace "wolo" (lowercase) with lowercase agent_display_name
                system_prompt = re.sub(r"\bwolo\b", self._agent_display_name.lower(), system_prompt)

            # Note: Skills are now loaded on-demand via the skill tool
            # instead of being auto-injected into the system prompt

            messages = [{"role": "system", "content": system_prompt}] + messages

        # Messages are already formatted by to_llm_messages() for OpenAI-compatible APIs
        # Just ensure content is a string (not list) for compatibility
        formatted_messages = []
        for msg in messages:
            # For tool messages and messages with tool_calls, keep as-is
            if msg.get("role") == "tool" or "tool_calls" in msg:
                formatted_messages.append(msg)
            else:
                # For user/assistant/system messages, ensure content is a string
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                    content = "\n".join(text_parts)
                formatted_messages.append({"role": msg.get("role", "user"), "content": content})

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": stream,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            # opencode-style additional parameters
            "topP": 0.9,  # Default topP matching opencode
            "topK": 40,  # Default topK matching opencode
            "maxOutputTokens": self.max_tokens,  # opencode uses maxOutputTokens
            "maxRetries": MAX_RETRIES,  # opencode includes maxRetries
        }

        if tools:
            payload["tools"] = tools

        # GLM thinking mode (CoT)
        if self.enable_think:
            payload["thinking"] = {
                "type": "enabled",
                "clear_thinking": False,  # False for Preserved Thinking
            }
            logger.debug("GLM thinking mode enabled")

        logger.debug(f"Request payload: {json.dumps(payload, ensure_ascii=False)[:500]}...")
        self._finish_reason = None  # Reset for new request

        # Debug logging: write request to file
        self._request_count += 1

        # Full debug logging: create a new file for this request
        full_debug_file = None
        if self._debug_full_dir:
            try:
                import os

                timestamp = time.strftime("%Y%m%d_%H%M%S")
                full_debug_file = os.path.join(self._debug_full_dir, f"req_{timestamp}.json")
                with open(full_debug_file, "w") as f:
                    f.write("---INPUT---\n")
                    f.write(
                        json.dumps(
                            {
                                "url": url,
                                "headers": {
                                    k: v for k, v in headers.items() if k != "Authorization"
                                },
                                "payload": payload,
                            },
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                    f.write("\n---OUTPUT---\n")
                    f.flush()
                logger.debug(f"Full debug log: {full_debug_file}")
            except Exception as e:
                logger.error(f"Failed to create full debug log: {e}")

        if self._debug_llm_file:
            try:
                with open(self._debug_llm_file, "a") as f:
                    f.write(f"\n{'=' * 60}\n")
                    f.write(f"[{time.strftime('%H:%M:%S')}] Request #{self._request_count}\n")
                    f.write(f"Model: {self.model}\n")
                    # Show last user message for context
                    for msg in reversed(formatted_messages):
                        if msg.get("role") == "user":
                            content = msg.get("content", "")[:100]
                            f.write(
                                f"User: {content}{'...' if len(msg.get('content', '')) > 100 else ''}\n"
                            )
                            break
                    f.write(f"{'=' * 60}\n")
                    f.flush()
                logger.debug(f"Debug log opened: {self._debug_llm_file}")
            except Exception as e:
                logger.error(f"Failed to write debug log: {e}")

        session = await self._get_session()
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"GLM API error: {response.status} - {error_text}")
                raise WoloAPIError(
                    f"GLM API error: {response.status} - {error_text}", response.status
                )

            # Handle streaming response
            buffer = ""
            async for line_bytes in response.content:
                line_str = line_bytes.decode("utf-8", errors="ignore")

                # Write raw SSE to full debug file
                if full_debug_file:
                    try:
                        with open(full_debug_file, "a") as f:
                            f.write(line_str)
                            f.flush()
                    except Exception:
                        pass

                # Accumulate buffer
                buffer += line_str

                # Process complete SSE lines
                while "\n" in buffer:
                    line_part, buffer = buffer.split("\n", 1)
                    line_part = line_part.strip()

                    if not line_part or not line_part.startswith("data: "):
                        continue

                    data_str = line_part[6:]
                    if data_str.strip() == "[DONE]":
                        logger.debug("Stream ended with [DONE]")
                        # Add finish reason to debug file
                        if self._debug_llm_file:
                            try:
                                with open(self._debug_llm_file, "a") as f:
                                    f.write(
                                        f"\n(finish_reason: {self._finish_reason or 'unknown'})\n"
                                    )
                                    f.flush()
                            except Exception:
                                pass
                        # Only yield finish if we haven't already
                        if self._finish_reason:
                            yield {"type": "finish", "reason": self._finish_reason}
                        return

                    try:
                        data = json.loads(data_str)

                        # Debug logging: extract and write delta content
                        if self._debug_llm_file:
                            try:
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})

                                    # Write text content
                                    content = delta.get("content", "")
                                    if content:
                                        with open(self._debug_llm_file, "a") as f:
                                            f.write(content)
                                            f.flush()

                                    # Write tool call info (streaming)
                                    tool_calls = delta.get("tool_calls", [])
                                    if tool_calls:
                                        for tc in tool_calls:
                                            index = tc.get("index", 0)
                                            func = tc.get("function", {})
                                            name = func.get("name", "")
                                            args = func.get("arguments", "")

                                            # Track tool calls per index
                                            if not hasattr(self, "_debug_tool_calls"):
                                                self._debug_tool_calls = {}

                                            if name:
                                                self._debug_tool_calls[index] = {
                                                    "name": name,
                                                    "args_shown": 0,
                                                }
                                                with open(self._debug_llm_file, "a") as f:
                                                    f.write(f"\n[Calling: {name}]\n")
                                                    f.flush()

                                            if index in self._debug_tool_calls and args:
                                                # Stream the raw arguments JSON as-is
                                                total_args = (
                                                    self._debug_tool_calls[index].get(
                                                        "total_args", ""
                                                    )
                                                    + args
                                                )
                                                self._debug_tool_calls[index]["total_args"] = (
                                                    total_args
                                                )
                                                self._debug_tool_calls[index]["args_shown"] = len(
                                                    total_args
                                                )

                                                # Show newly added portion
                                                if args:
                                                    with open(self._debug_llm_file, "a") as f:
                                                        f.write(args)
                                                        f.flush()
                            except Exception as debug_e:
                                logger.debug(f"Debug write error: {debug_e}")

                        async for event in self._process_sse_data(data):
                            yield event
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE data: {e}")
                        continue

            # Process any remaining buffer
            if buffer.strip():
                line_part = buffer.strip()
                if line_part.startswith("data: "):
                    data_str = line_part[6:]
                    if data_str.strip() != "[DONE]":
                        try:
                            data = json.loads(data_str)
                            async for event in self._process_sse_data(data):
                                yield event
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse remaining SSE data: {e}")

            # Final finish if not already sent
            if self._finish_reason:
                yield {"type": "finish", "reason": self._finish_reason}

            # Close full debug file
            if full_debug_file:
                try:
                    with open(full_debug_file, "a") as f:
                        f.write(
                            f"\n---END--- (finish_reason: {self._finish_reason or 'unknown'})\n"
                        )
                        f.flush()
                except Exception:
                    pass

    async def _process_sse_data(self, data: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Process SSE data and yield events."""
        choices = data.get("choices", [])
        if not choices:
            return

        # Extract token usage from response
        global _api_token_usage
        if "usage" in data:
            usage = data["usage"]
            _api_token_usage["prompt_tokens"] = usage.get("prompt_tokens", 0)
            _api_token_usage["completion_tokens"] = usage.get("completion_tokens", 0)
            _api_token_usage["total_tokens"] = usage.get("total_tokens", 0)
            logger.debug(f"Token usage: {_api_token_usage}")

        choice = choices[0]
        delta = choice.get("delta", {})

        # Reasoning content (GLM thinking mode)
        reasoning = delta.get("reasoning_content", "")
        if reasoning:
            # Don't log every delta - too noisy
            yield {"type": "reasoning-delta", "text": reasoning}

        # Text content
        content = delta.get("content", "")
        if content:
            # Don't log every delta - too noisy, content is shown via event handler
            yield {"type": "text-delta", "text": content}

        # Tool calls - handle incremental arguments
        tool_calls = delta.get("tool_calls", [])
        for tool_call in tool_calls:
            index = tool_call.get("index", 0)
            tool_call_id = tool_call.get("id", "")  # Capture the tool call ID
            function = tool_call.get("function", {})
            name = function.get("name", "")
            arguments = function.get("arguments", "")

            # Store partial tool call data
            if not hasattr(self, "_tool_call_buffer"):
                self._tool_call_buffer = {}

            if name:
                self._tool_call_buffer[index] = {"name": name, "arguments": "", "id": tool_call_id}
                logger.info(f"Tool call started: {name}")

            if index in self._tool_call_buffer:
                if arguments:
                    self._tool_call_buffer[index]["arguments"] += arguments
                # Update ID if provided in subsequent chunks (some APIs send it separately)
                if tool_call_id:
                    self._tool_call_buffer[index]["id"] = tool_call_id

                # Check if we have a complete tool call (has name and arguments look complete)
                tool_data = self._tool_call_buffer[index]
                if tool_data["name"]:
                    try:
                        # Try to parse arguments - if successful, yield the event
                        if tool_data["arguments"]:
                            parsed_args = json.loads(tool_data["arguments"])
                            logger.info(
                                f"Tool call complete: {tool_data['name']} with args {list(parsed_args.keys())}"
                            )
                            yield {
                                "type": "tool-call",
                                "tool": tool_data["name"],
                                "input": parsed_args,
                                "id": tool_data.get("id", ""),
                            }
                            del self._tool_call_buffer[index]
                    except json.JSONDecodeError:
                        # Arguments not complete yet, waiting for more data
                        pass

        # Finish reason - only set once
        finish_reason = choice.get("finish_reason")
        if finish_reason and not self._finish_reason:
            self._finish_reason = finish_reason
            yield {"type": "finish", "reason": finish_reason}


def get_token_usage() -> dict[str, int]:
    """Get the token usage from the last API call."""
    return _api_token_usage.copy()


def reset_token_usage() -> None:
    """Reset the token usage tracking."""
    global _api_token_usage
    _api_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
