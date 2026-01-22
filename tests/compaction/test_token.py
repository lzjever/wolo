"""Tests for token estimation."""

import pytest
from wolo.compaction.token import TokenEstimator
from wolo.session import Message, TextPart, ToolPart


class TestEstimateText:
    """Tests for estimate_text method."""
    
    def test_empty_string_returns_zero(self):
        """Empty string should return 0 tokens."""
        assert TokenEstimator.estimate_text("") == 0
    
    def test_none_returns_zero(self):
        """None should return 0 tokens."""
        assert TokenEstimator.estimate_text(None) == 0
    
    def test_english_text_4_chars_per_token(self):
        """English text should be approximately 4 characters per token.
        
        Input: "hello world" (11 characters)
        Expected: 11 / 4 = 2.75 -> 3 (rounded)
        """
        result = TokenEstimator.estimate_text("hello world")
        assert result == 2 or result == 3  # Allow for rounding differences
    
    def test_chinese_text_1_5_chars_per_token(self):
        """Chinese text should be approximately 1.5 characters per token.
        
        Input: "你好世界" (4 characters)
        Expected: 4 / 1.5 = 2.67 -> 3 (rounded)
        """
        result = TokenEstimator.estimate_text("你好世界")
        assert result == 2 or result == 3  # Allow for rounding differences
    
    def test_mixed_text(self):
        """Mixed Chinese and English text."""
        result = TokenEstimator.estimate_text("hello你好")
        # 5 English chars / 4 = 1.25
        # 2 Chinese chars / 1.5 = 1.33
        # Total ~= 2.58 -> 3
        assert result >= 2 and result <= 4
    
    def test_minimum_one_token_for_non_empty(self):
        """Non-empty text should return at least 1 token."""
        result = TokenEstimator.estimate_text("a")
        assert result >= 1
    
    def test_long_text(self):
        """Long text should scale appropriately.
        
        Input: 4000 English characters
        Expected: 4000 / 4 = 1000 tokens
        """
        text = "a" * 4000
        result = TokenEstimator.estimate_text(text)
        assert result == 1000
    
    def test_code_text(self):
        """Code text should be estimated reasonably."""
        code = '''def hello():
    print("Hello, World!")
    return True
'''
        result = TokenEstimator.estimate_text(code)
        # Code is mostly ASCII, so ~4 chars per token
        # About 50 characters -> ~12-15 tokens
        assert 10 <= result <= 20


class TestIsChineseChar:
    """Tests for is_chinese_char method."""
    
    def test_chinese_char_returns_true(self):
        """Chinese characters should return True."""
        assert TokenEstimator.is_chinese_char("你") is True
        assert TokenEstimator.is_chinese_char("好") is True
        assert TokenEstimator.is_chinese_char("世") is True
    
    def test_english_char_returns_false(self):
        """English characters should return False."""
        assert TokenEstimator.is_chinese_char("a") is False
        assert TokenEstimator.is_chinese_char("Z") is False
    
    def test_number_returns_false(self):
        """Numbers should return False."""
        assert TokenEstimator.is_chinese_char("1") is False
    
    def test_empty_string_returns_false(self):
        """Empty string should return False."""
        assert TokenEstimator.is_chinese_char("") is False
    
    def test_multi_char_string_returns_false(self):
        """Multi-character string should return False."""
        assert TokenEstimator.is_chinese_char("ab") is False


class TestEstimateMessage:
    """Tests for estimate_message method."""
    
    def test_text_only_message(self):
        """Message with only text should include overhead."""
        msg = Message(role="user", parts=[TextPart(text="hello")])
        result = TokenEstimator.estimate_message(msg)
        # MESSAGE_OVERHEAD (10) + text tokens (~1-2)
        assert result >= 11 and result <= 15
    
    def test_tool_call_message(self):
        """Message with tool call should include tool overhead."""
        msg = Message(
            role="assistant",
            parts=[
                ToolPart(
                    tool="read",
                    input={"path": "/test.py"},
                    output="file content here",
                    status="completed",
                )
            ]
        )
        result = TokenEstimator.estimate_message(msg)
        # MESSAGE_OVERHEAD (10) + TOOL_OVERHEAD (20) + input + output
        assert result > 30
    
    def test_mixed_parts_message(self):
        """Message with mixed parts should sum all parts."""
        msg = Message(
            role="assistant",
            parts=[
                TextPart(text="Let me read the file"),
                ToolPart(
                    tool="read",
                    input={"path": "/test.py"},
                    output="content",
                    status="completed",
                ),
            ]
        )
        result = TokenEstimator.estimate_message(msg)
        
        # Compare to text-only message
        text_only = TokenEstimator.estimate_message(
            Message(role="assistant", parts=[TextPart(text="Let me read the file")])
        )
        assert result > text_only
    
    def test_empty_message(self):
        """Empty message should have only overhead."""
        msg = Message(role="user", parts=[])
        result = TokenEstimator.estimate_message(msg)
        assert result == TokenEstimator.MESSAGE_OVERHEAD_TOKENS


class TestEstimateMessages:
    """Tests for estimate_messages method."""
    
    def test_empty_list_returns_zero(self):
        """Empty message list should return 0."""
        assert TokenEstimator.estimate_messages([]) == 0
    
    def test_single_message(self):
        """Single message should match estimate_message."""
        msg = Message(role="user", parts=[TextPart(text="hello")])
        result = TokenEstimator.estimate_messages([msg])
        expected = TokenEstimator.estimate_message(msg)
        assert result == expected
    
    def test_multiple_messages_sum(self):
        """Multiple messages should sum all tokens."""
        msg1 = Message(role="user", parts=[TextPart(text="hello")])
        msg2 = Message(role="assistant", parts=[TextPart(text="hi")])
        
        result = TokenEstimator.estimate_messages([msg1, msg2])
        expected = (
            TokenEstimator.estimate_message(msg1) +
            TokenEstimator.estimate_message(msg2)
        )
        assert result == expected
    
    def test_large_message_list(self):
        """Large message list should handle efficiently."""
        messages = [
            Message(role="user" if i % 2 == 0 else "assistant",
                   parts=[TextPart(text=f"Message {i}")])
            for i in range(100)
        ]
        result = TokenEstimator.estimate_messages(messages)
        assert result > 0
