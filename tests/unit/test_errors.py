"""Test suite for error handling."""

import pytest

from wolo.errors import (
    ErrorCategory,
    WoloAPIError,
    classify_api_error,
    format_user_friendly_error,
    get_retry_strategy,
)


class TestErrorClassification:
    """Test error classification."""

    def test_classify_auth_error(self):
        """Test classification of authentication errors."""
        error_info = classify_api_error(401, "Unauthorized", None)
        assert error_info.category == ErrorCategory.AUTH
        assert error_info.retryable is False
        assert error_info.status_code == 401

    def test_classify_rate_limit_error(self):
        """Test classification of rate limit errors."""
        error_info = classify_api_error(429, "Rate limit exceeded", None)
        assert error_info.category == ErrorCategory.RATE_LIMIT
        assert error_info.retryable is True

    def test_classify_server_error(self):
        """Test classification of server errors."""
        error_info = classify_api_error(500, "Internal server error", None)
        assert error_info.category == ErrorCategory.SERVER
        assert error_info.retryable is True

    def test_classify_not_found_error(self):
        """Test classification of not found errors."""
        error_info = classify_api_error(404, "Not found", None)
        assert error_info.category == ErrorCategory.RESOURCE
        assert error_info.retryable is False

    def test_classify_invalid_request_error(self):
        """Test classification of invalid request errors."""
        error_info = classify_api_error(400, "Bad request", None)
        assert error_info.category == ErrorCategory.INVALID_REQUEST
        assert error_info.retryable is False

    def test_classify_network_error(self):
        """Test classification of network errors."""
        error_info = classify_api_error(0, "Connection timeout", TimeoutError("Timeout"))
        assert error_info.category == ErrorCategory.RETRYABLE
        assert error_info.retryable is True


class TestRetryStrategy:
    """Test retry strategy logic."""

    def test_retryable_error_retry(self):
        """Test that retryable errors are retried."""
        should_retry, delay = get_retry_strategy(ErrorCategory.RETRYABLE, 1, 3)
        assert should_retry is True
        assert delay > 0

    def test_rate_limit_retry(self):
        """Test that rate limit errors are retried with longer delay."""
        should_retry, delay = get_retry_strategy(ErrorCategory.RATE_LIMIT, 1, 3)
        assert should_retry is True
        assert delay > 500  # Longer delay for rate limit

    def test_auth_error_no_retry(self):
        """Test that auth errors are not retried."""
        should_retry, delay = get_retry_strategy(ErrorCategory.AUTH, 1, 3)
        assert should_retry is False
        assert delay == 0

    def test_max_attempts_exceeded(self):
        """Test that no retry happens after max attempts."""
        should_retry, delay = get_retry_strategy(ErrorCategory.RETRYABLE, 3, 3)
        assert should_retry is False
        assert delay == 0


class TestErrorMessageFormatting:
    """Test user-friendly error message formatting."""

    def test_format_error_message(self):
        """Test formatting of error messages."""
        error_info = classify_api_error(401, "Unauthorized", None)
        formatted = format_user_friendly_error(error_info)

        assert "Error:" in formatted
        assert "Authentication failed" in formatted
        assert "Details:" in formatted
        assert "Suggestions:" in formatted

    def test_wolo_api_error(self):
        """Test WoloAPIError exception."""
        exc = WoloAPIError("Test error", 404)
        assert exc.status_code == 404
        assert str(exc) == "Test error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
