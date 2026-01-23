"""Token estimation utilities.

Provides methods for estimating token counts from text and messages.
Uses character-based heuristics with special handling for Chinese text.
"""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wolo.session import Message


class TokenEstimator:
    """Estimates token counts for text and messages.

    Uses character-based heuristics since actual tokenization
    depends on the specific model. Provides reasonable estimates
    for planning purposes.

    Accuracy Notes:
        - English text: ~4 characters per token (±20% error)
        - Chinese text: ~1.5 characters per token (±20% error)
        - Mixed text: weighted average based on character types
    """

    # Character-to-token ratios
    CHARS_PER_TOKEN_ENGLISH: float = 4.0
    CHARS_PER_TOKEN_CHINESE: float = 1.5

    # Overhead constants
    MESSAGE_OVERHEAD_TOKENS: int = 10
    TOOL_CALL_BASE_OVERHEAD: int = 20

    @staticmethod
    def is_chinese_char(char: str) -> bool:
        """Check if a character is Chinese.

        Args:
            char: Single character to check

        Returns:
            True if the character is in the CJK Unified Ideographs range
        """
        if len(char) != 1:
            return False
        code_point = ord(char)
        # CJK Unified Ideographs: U+4E00 to U+9FFF
        return 0x4E00 <= code_point <= 0x9FFF

    @classmethod
    def estimate_text(cls, text: str | None, model: str = "default") -> int:
        """Estimate token count for a text string.

        Args:
            text: Text to estimate tokens for
            model: Model name (currently unused, for future extensibility)

        Returns:
            Estimated token count (0 for empty/None input, minimum 1 for non-empty)

        Algorithm:
            1. Count Chinese characters
            2. Count other characters
            3. Chinese tokens = chinese_chars / 1.5
            4. Other tokens = other_chars / 4.0
            5. Return sum, minimum 1 for non-empty text
        """
        if not text:
            return 0

        chinese_count = sum(1 for c in text if cls.is_chinese_char(c))
        other_count = len(text) - chinese_count

        chinese_tokens = chinese_count / cls.CHARS_PER_TOKEN_CHINESE
        other_tokens = other_count / cls.CHARS_PER_TOKEN_ENGLISH

        total = int(chinese_tokens + other_tokens)
        return max(1, total) if text else 0

    @classmethod
    def estimate_message(cls, message: "Message", model: str = "default") -> int:
        """Estimate token count for a message.

        Args:
            message: Message object to estimate
            model: Model name for estimation

        Returns:
            Estimated token count including overhead

        Algorithm:
            1. Start with MESSAGE_OVERHEAD_TOKENS
            2. For each TextPart: add estimate_text(text)
            3. For each ToolPart: add TOOL_CALL_BASE_OVERHEAD + input + output
        """
        from wolo.session import TextPart, ToolPart

        total = cls.MESSAGE_OVERHEAD_TOKENS

        for part in message.parts:
            if isinstance(part, TextPart):
                total += cls.estimate_text(part.text, model)
            elif isinstance(part, ToolPart):
                total += cls.TOOL_CALL_BASE_OVERHEAD
                # Estimate input JSON
                if part.input:
                    try:
                        input_json = json.dumps(part.input)
                        total += cls.estimate_text(input_json, model)
                    except (TypeError, ValueError):
                        total += 50  # Fallback estimate
                # Estimate output
                if part.output:
                    total += cls.estimate_text(part.output, model)

        return total

    @classmethod
    def estimate_messages(
        cls,
        messages: list["Message"],
        model: str = "default",
    ) -> int:
        """Estimate total token count for a list of messages.

        Args:
            messages: List of messages to estimate
            model: Model name for estimation

        Returns:
            Sum of estimated tokens for all messages
        """
        if not messages:
            return 0
        return sum(cls.estimate_message(msg, model) for msg in messages)
