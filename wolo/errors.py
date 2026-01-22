"""Error handling and classification for Wolo."""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WoloAPIError(Exception):
    """Custom exception for API errors with status code."""

    def __init__(self, message: str, status_code: int = 0):
        self.status_code = status_code
        self.response = None  # Will be set if available
        super().__init__(message)


class ErrorCategory(str, Enum):
    """Categories of errors that can occur."""
    RETRYABLE = "retryable"  # Network timeout, rate limit - should retry
    AUTH = "auth"  # Authentication failure - don't retry
    INVALID_REQUEST = "invalid_request"  # Bad input - don't retry
    RESOURCE = "resource"  # Resource not found
    RATE_LIMIT = "rate_limit"  # Rate limiting - retry with backoff
    SERVER = "server"  # Server error - may retry
    UNKNOWN = "unknown"  # Unknown error


@dataclass
class ErrorInfo:
    """Structured error information."""
    category: ErrorCategory
    retryable: bool
    user_message: str
    technical_details: str
    suggestions: list[str]
    status_code: int | None = None


def classify_api_error(status_code: int, error_text: str, exception: Exception | None = None) -> ErrorInfo:
    """
    Classify an API error into categories and provide user-friendly messages.

    Args:
        status_code: HTTP status code
        error_text: Error message from API
        exception: The exception that occurred

    Returns:
        ErrorInfo with classification and user-friendly message
    """
    error_text_lower = error_text.lower() if error_text else ""

    # Authentication errors (401, 403)
    if status_code in (401, 403):
        return ErrorInfo(
            category=ErrorCategory.AUTH,
            retryable=False,
            user_message="Authentication failed. Please check your API key.",
            technical_details=f"HTTP {status_code}: {error_text}",
            suggestions=[
                "Verify GLM_API_KEY is set correctly",
                "Check if your API key has expired",
                "Ensure your account has API access enabled"
            ],
            status_code=status_code
        )

    # Rate limiting (429)
    if status_code == 429 or "rate limit" in error_text_lower:
        return ErrorInfo(
            category=ErrorCategory.RATE_LIMIT,
            retryable=True,
            user_message="Rate limit exceeded. Please wait and try again.",
            technical_details=f"HTTP {status_code}: {error_text}",
            suggestions=[
                "Wait a few seconds before trying again",
                "Reduce the frequency of requests",
                "Consider upgrading your API plan"
            ],
            status_code=status_code
        )

    # Not found (404)
    if status_code == 404:
        return ErrorInfo(
            category=ErrorCategory.RESOURCE,
            retryable=False,
            user_message="The requested resource was not found.",
            technical_details=f"HTTP {status_code}: {error_text}",
            suggestions=[
                "Check if the API endpoint URL is correct",
                "Verify the model name is supported"
            ],
            status_code=status_code
        )

    # Client errors (400, 422)
    if status_code in (400, 422):
        return ErrorInfo(
            category=ErrorCategory.INVALID_REQUEST,
            retryable=False,
            user_message="Invalid request. Please check your input.",
            technical_details=f"HTTP {status_code}: {error_text}",
            suggestions=[
                "Check if the model name is correct",
                "Verify your message format is valid",
                "Check if you're exceeding token limits"
            ],
            status_code=status_code
        )

    # Server errors (500, 502, 503, 504)
    if status_code >= 500:
        return ErrorInfo(
            category=ErrorCategory.SERVER,
            retryable=True,
            user_message="Server error. The service may be temporarily unavailable.",
            technical_details=f"HTTP {status_code}: {error_text}",
            suggestions=[
                "Wait a moment and try again",
                "Check if the GLM service status page",
                "Try again later if the problem persists"
            ],
            status_code=status_code
        )

    # Network/connection errors
    if isinstance(exception, (asyncio.TimeoutError, OSError, ConnectionError)):
        error_type = type(exception).__name__
        return ErrorInfo(
            category=ErrorCategory.RETRYABLE,
            retryable=True,
            user_message="Network error. Please check your connection.",
            technical_details=f"{error_type}: {str(exception)}",
            suggestions=[
                "Check your internet connection",
                "Verify you can access open.bigmodel.cn",
                "Try again in a moment"
            ],
            status_code=None
        )

    # Unknown error
    return ErrorInfo(
        category=ErrorCategory.UNKNOWN,
        retryable=False,
        user_message="An unexpected error occurred.",
        technical_details=error_text or str(exception) if exception else "Unknown error",
        suggestions=[
            "Check wolo.log for more details",
            "Try again with a simpler request",
            "Report this issue if it persists"
        ],
        status_code=status_code
    )


def get_retry_strategy(category: ErrorCategory, attempt: int, max_attempts: int) -> tuple[bool, float]:
    """
    Determine if an error is retryable and calculate delay.

    Args:
        category: Error category
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum retry attempts

    Returns:
        Tuple of (should_retry, delay_ms)
    """
    if not category.value in (ErrorCategory.RETRYABLE.value, ErrorCategory.RATE_LIMIT.value,
                              ErrorCategory.SERVER.value):
        return False, 0

    if attempt >= max_attempts:
        return False, 0

    # Exponential backoff with jitter
    # Rate limit: longer delays
    if category == ErrorCategory.RATE_LIMIT:
        delay = min(1000 * (3 ** (attempt - 1)), 30000)  # Max 30s
        return True, delay

    # Server errors: moderate backoff
    if category == ErrorCategory.SERVER:
        delay = min(1000 * (2 ** (attempt - 1)), 10000)  # Max 10s
        return True, delay

    # Retryable (network): short backoff
    if category == ErrorCategory.RETRYABLE:
        delay = 500 * (attempt)
        return True, delay

    return False, 0


def format_user_friendly_error(error_info: ErrorInfo) -> str:
    """Format error info as user-friendly message."""
    lines = [
        f"\n❌ Error: {error_info.user_message}",
        f"\nDetails: {error_info.technical_details}"
    ]

    if error_info.suggestions:
        lines.append("\nSuggestions:")
        for i, suggestion in enumerate(error_info.suggestions, 1):
            lines.append(f"  {i}. {suggestion}")

    return "\n".join(lines)
