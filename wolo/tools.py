"""Tool system for Wolo."""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from wolo.events import bus
from wolo.file_time import FileModifiedError, FileTime
from wolo.session import ToolPart
from wolo.smart_replace import smart_replace
from wolo.tool_registry import get_registry
from wolo.truncate import truncate_output

logger = logging.getLogger(__name__)


# ==================== Shell Process Tracking ====================

# Track running shell processes for Ctrl+S viewing
_running_shells: dict[str, dict] = {}
_shell_history: list[dict] = []  # Recent completed shells
_MAX_SHELL_HISTORY = 10
_MAX_OUTPUT_LINES = 500


# Simple in-memory todo storage (per session)
_todos: dict[str, list[dict]] = {}


# Binary file extensions
_BINARY_EXTENSIONS = {
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".class",
    ".jar",
    ".war",
    ".7z",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".bin",
    ".dat",
    ".obj",
    ".o",
    ".a",
    ".lib",
    ".wasm",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wav",
    ".flac",
    ".pdf",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
}


def _is_binary_file(path: Path) -> bool:
    """Check if a file is binary."""
    # Check extension
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return True

    # Check content
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)

        if not chunk:
            return False

        # Check for NULL bytes
        if b"\x00" in chunk:
            return True

        # Check non-printable character ratio
        non_printable = sum(1 for b in chunk if b < 9 or (b > 13 and b < 32))
        if non_printable / len(chunk) > 0.3:
            return True

        return False
    except Exception:
        return False


def _suggest_similar_files(path: Path) -> list[str]:
    """Suggest similar file names when file not found."""
    if not path.parent.exists():
        return []

    base = path.name.lower()
    suggestions = []

    try:
        for entry in path.parent.iterdir():
            if entry.is_file():
                name = entry.name.lower()
                if base in name or name in base:
                    suggestions.append(str(entry))
    except OSError:
        pass

    return suggestions[:3]


def get_all_tools(excluded_tools: set[str] = None) -> list[dict]:
    """Get all tool schemas for LLM API.

    Args:
        excluded_tools: Set of tool names to exclude (e.g., {"question"})

    Returns built-in tools plus any MCP tools.
    The skill tool schema is generated dynamically to include available skills.
    """
    if excluded_tools is None:
        excluded_tools = set()

    # Get built-in tools from registry
    tools = get_registry().get_llm_schemas()

    # Filter out excluded tools
    tools = [t for t in tools if t.get("function", {}).get("name") not in excluded_tools]

    # Replace static skill schema with dynamic one that includes available skills
    if "skill" not in excluded_tools:
        try:
            from wolo.skill_tool import get_skill_tool_schema

            dynamic_skill_schema = get_skill_tool_schema()
            # Replace the skill tool schema
            tools = [t for t in tools if t.get("function", {}).get("name") != "skill"]
            tools.append(dynamic_skill_schema)
        except ImportError:
            pass  # skill_tool not available
        except Exception as e:
            logger.warning(f"Failed to generate dynamic skill schema: {e}")

    # Add MCP tools if available
    try:
        from wolo.mcp_integration import get_mcp_tool_schemas

        mcp_tools = get_mcp_tool_schemas()
        # Filter MCP tools too
        mcp_tools = [
            t for t in mcp_tools if t.get("function", {}).get("name") not in excluded_tools
        ]
        tools.extend(mcp_tools)
    except ImportError:
        pass  # MCP integration not available
    except Exception as e:
        logger.warning(f"Failed to get MCP tools: {e}")

    return tools


async def shell_execute(command: str, timeout: int = 30000) -> dict[str, Any]:
    """Execute a shell command and return the result."""
    import uuid

    shell_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Track this shell process
    shell_info = {
        "id": shell_id,
        "command": command,
        "start_time": start_time,
        "output_lines": [],
        "status": "running",
        "exit_code": None,
    }
    _running_shells[shell_id] = shell_info

    from wolo.subprocess_manager import managed_subprocess

    async with managed_subprocess(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, shell=True
    ) as process:
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout / 1000)

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            if error:
                output = output + "\n" + error if output else error

            # Store output (limited lines)
            lines = output.split("\n")
            shell_info["output_lines"] = (
                lines[-_MAX_OUTPUT_LINES:] if len(lines) > _MAX_OUTPUT_LINES else lines
            )
            shell_info["status"] = "completed"
            shell_info["exit_code"] = process.returncode
            shell_info["end_time"] = time.time()
            shell_info["duration"] = shell_info["end_time"] - start_time

            # Move to history
            del _running_shells[shell_id]
            _shell_history.insert(0, shell_info)
            if len(_shell_history) > _MAX_SHELL_HISTORY:
                _shell_history.pop()

            # Truncate output if too large
            truncated = truncate_output(output)

            return {
                "title": command,
                "output": truncated.content,
                "metadata": {
                    "exit_code": process.returncode,
                    "shell_id": shell_id,
                    "truncated": truncated.truncated,
                    "saved_path": truncated.saved_path,
                },
            }
        except TimeoutError:
            process.kill()
            await process.wait()

            shell_info["status"] = "timeout"
            shell_info["exit_code"] = -1
            shell_info["end_time"] = time.time()
            shell_info["duration"] = shell_info["end_time"] - start_time

            del _running_shells[shell_id]
            _shell_history.insert(0, shell_info)
            if len(_shell_history) > _MAX_SHELL_HISTORY:
                _shell_history.pop()

            return {
                "title": command,
                "output": f"Command timed out after {timeout}ms",
                "metadata": {"exit_code": -1, "shell_id": shell_id},
            }


def get_shell_status() -> dict:
    """Get current shell status for Ctrl+S display."""
    return {
        "running": list(_running_shells.values()),
        "history": _shell_history[:5],  # Last 5 completed
    }


# Image extensions that can be read
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# PDF extension
_PDF_EXTENSION = ".pdf"


async def read_execute(file_path: str, offset: int = 0, limit: int = 2000) -> dict[str, Any]:
    """Read a file and return its contents with line numbers.

    Supports:
    - Text files: Returns content with line numbers
    - Images: Returns base64-encoded image data
    - PDFs: Returns extracted text content
    """
    path = Path(file_path)

    if not path.exists():
        # Suggest similar files
        suggestions = _suggest_similar_files(path)
        output = f"File not found: {file_path}"
        if suggestions:
            output += "\n\nDid you mean one of these?\n" + "\n".join(
                f"  - {s}" for s in suggestions
            )
        return {
            "title": file_path,
            "output": output,
            "metadata": {"error": "not_found", "suggestions": suggestions},
        }

    if not path.is_file():
        return {
            "title": file_path,
            "output": f"Not a file: {file_path}",
            "metadata": {"error": "not_a_file"},
        }

    suffix = path.suffix.lower()

    # Handle images
    if suffix in _IMAGE_EXTENSIONS:
        return await _read_image(path)

    # Handle PDFs
    if suffix == _PDF_EXTENSION:
        return await _read_pdf(path)

    # Check for binary file (non-image, non-PDF)
    if _is_binary_file(path):
        return {
            "title": file_path,
            "output": f"Cannot read binary file: {file_path}",
            "metadata": {"error": "binary_file"},
        }

    # Regular text file
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        total_lines = len(lines)

        # Apply offset and limit
        start_line = offset
        end_line = min(offset + limit, total_lines) if limit > 0 else total_lines
        selected_lines = lines[start_line:end_line]
        truncated = end_line < total_lines

        # Format with line numbers (5-digit right-aligned)
        formatted_lines = []
        for i, line in enumerate(selected_lines):
            line_num = start_line + i + 1  # 1-based line number
            formatted_lines.append(f"{line_num:5d}| {line}")

        output = "\n".join(formatted_lines)

        # Add file info header and footer
        header = f'<file path="{file_path}" lines="{total_lines}">\n'
        footer = "\n</file>"

        if truncated:
            footer = (
                f"\n\n(File has more lines. Use offset={end_line} to continue reading)\n</file>"
            )
        elif offset > 0:
            header = f'<file path="{file_path}" lines="{total_lines}" offset="{offset}">\n'

        # Apply truncation for very large outputs
        full_output = header + output + footer
        truncated_result = truncate_output(full_output)

        return {
            "title": file_path,
            "output": truncated_result.content,
            "metadata": {
                "total_lines": total_lines,
                "showing_lines": len(selected_lines),
                "offset": offset,
                "truncated": truncated or truncated_result.truncated,
            },
        }
    except Exception as e:
        return {
            "title": file_path,
            "output": f"Error reading file: {e}",
            "metadata": {"error": str(e)},
        }


async def _read_image(path: Path) -> dict[str, Any]:
    """Read an image file and return base64-encoded data."""
    import base64

    try:
        from PIL import Image

        # Open and get image info
        with Image.open(path) as img:
            width, height = img.size
            format_name = img.format or "UNKNOWN"
            mode = img.mode

        # Read raw bytes
        image_bytes = path.read_bytes()
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        # Determine MIME type
        suffix = path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        mime_type = mime_types.get(suffix, "image/png")

        return {
            "title": str(path),
            "output": f'<image path="{path}" width="{width}" height="{height}" format="{format_name}">\n'
            f"data:{mime_type};base64,{base64_data}\n"
            f"</image>",
            "metadata": {
                "type": "image",
                "width": width,
                "height": height,
                "format": format_name,
                "mode": mode,
                "size_bytes": len(image_bytes),
            },
        }

    except ImportError:
        return {
            "title": str(path),
            "output": "Cannot read image: Pillow library not installed. Run: pip install pillow",
            "metadata": {"error": "missing_dependency"},
        }
    except Exception as e:
        return {
            "title": str(path),
            "output": f"Error reading image: {e}",
            "metadata": {"error": str(e)},
        }


async def _read_pdf(path: Path) -> dict[str, Any]:
    """Read a PDF file and extract text content."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        total_pages = len(doc)

        # Extract text from all pages
        text_parts = []
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

        doc.close()

        if not text_parts:
            return {
                "title": str(path),
                "output": f'<pdf path="{path}" pages="{total_pages}">\n'
                f"(PDF contains no extractable text - may be scanned/image-based)\n"
                f"</pdf>",
                "metadata": {
                    "type": "pdf",
                    "pages": total_pages,
                    "has_text": False,
                },
            }

        content = "\n\n".join(text_parts)

        # Truncate if too large
        truncated = truncate_output(content)

        return {
            "title": str(path),
            "output": f'<pdf path="{path}" pages="{total_pages}">\n{truncated.content}\n</pdf>',
            "metadata": {
                "type": "pdf",
                "pages": total_pages,
                "has_text": True,
                "truncated": truncated.truncated,
            },
        }

    except ImportError:
        return {
            "title": str(path),
            "output": "Cannot read PDF: PyMuPDF library not installed. Run: pip install pymupdf",
            "metadata": {"error": "missing_dependency"},
        }
    except Exception as e:
        return {
            "title": str(path),
            "output": f"Error reading PDF: {e}",
            "metadata": {"error": str(e)},
        }


async def write_execute(file_path: str, content: str) -> dict[str, Any]:
    """Write content to a file with path safety check."""
    from wolo.path_guard import get_path_guard, Operation
    from wolo.path_guard_exceptions import PathConfirmationRequired

    # Check path safety
    guard = get_path_guard()
    result = guard.check(file_path, Operation.WRITE)

    if result.requires_confirmation:
        raise PathConfirmationRequired(file_path, "write")

    if not result.allowed:
        return {
            "title": f"write: {file_path}",
            "output": f"Permission denied: {result.reason}",
            "metadata": {"error": "path_not_allowed"},
        }

    path = Path(file_path)

    try:
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        path.write_text(content, encoding="utf-8")

        return {
            "title": file_path,
            "output": f"Successfully wrote {len(content)} bytes to {file_path}",
            "metadata": {"size": len(content)},
        }
    except Exception as e:
        return {
            "title": file_path,
            "output": f"Error writing file: {e}",
            "metadata": {"error": str(e)},
        }


async def edit_execute(file_path: str, old_text: str, new_text: str) -> dict[str, Any]:
    """Edit a file by replacing old_text with new_text using smart matching."""
    from wolo.path_guard import get_path_guard, Operation
    from wolo.path_guard_exceptions import PathConfirmationRequired
    import difflib

    # Check path safety
    guard = get_path_guard()
    result = guard.check(file_path, Operation.WRITE)

    if result.requires_confirmation:
        raise PathConfirmationRequired(file_path, "edit")

    if not result.allowed:
        return {
            "title": f"edit: {file_path}",
            "output": f"Permission denied: {result.reason}",
            "metadata": {"error": "path_not_allowed"},
        }

    path = Path(file_path)

    if not path.exists():
        return {
            "title": file_path,
            "output": f"File not found: {file_path}",
            "metadata": {"error": "not_found"},
        }

    try:
        content = path.read_text(encoding="utf-8", errors="replace")

        # Use smart replace with multiple matching strategies
        try:
            new_content = smart_replace(content, old_text, new_text)
        except LookupError:
            return {
                "title": file_path,
                "output": f"Old text not found in file (tried multiple matching strategies).\nPreview: {old_text[:100]}...",
                "metadata": {"error": "text_not_found", "old_text_preview": old_text[:200]},
            }
        except ValueError as e:
            return {"title": file_path, "output": str(e), "metadata": {"error": "multiple_matches"}}

        # Generate diff
        diff_lines = list(
            difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )
        diff_text = "".join(diff_lines)

        # Count changes
        additions = sum(1 for ln in diff_lines if ln.startswith("+") and not ln.startswith("+++"))
        deletions = sum(1 for ln in diff_lines if ln.startswith("-") and not ln.startswith("---"))

        # Write file
        path.write_text(new_content, encoding="utf-8")

        output = f"Successfully edited {file_path}\n"
        output += f"Changes: +{additions} -{deletions} lines\n\n"
        if diff_text:
            output += f"```diff\n{diff_text}\n```"

        return {
            "title": file_path,
            "output": output,
            "metadata": {
                "additions": additions,
                "deletions": deletions,
                "diff": diff_text,
            },
        }
    except Exception as e:
        return {
            "title": file_path,
            "output": f"Error editing file: {e}",
            "metadata": {"error": str(e)},
        }


async def multiedit_execute(edits: list[dict[str, str]]) -> dict[str, Any]:
    """Edit multiple files at once."""
    results = []
    success_count = 0

    for edit in edits:
        file_path = edit.get("file_path", "")
        old_text = edit.get("old_text", "")
        new_text = edit.get("new_text", "")

        result = await edit_execute(file_path, old_text, new_text)
        results.append(result)

        if "error" not in result.get("metadata", {}):
            success_count += 1

    # Format output
    output_lines = [f"Multi-edit completed: {success_count}/{len(edits)} files edited\n"]
    for r in results:
        metadata = r.get("metadata", {})
        status = "✓" if "error" not in metadata else "✗"
        output_lines.append(f"{status} {r['title']}: {r['output'].split(chr(10))[0]}")

    return {
        "title": f"multiedit: {len(edits)} files",
        "output": "\n".join(output_lines),
        "metadata": {
            "total": len(edits),
            "success": success_count,
            "failed": len(edits) - success_count,
        },
    }


async def grep_execute(
    pattern: str, path: str = ".", include_pattern: str = None
) -> dict[str, Any]:
    """Search for a pattern in files using ripgrep (with fallback to grep)."""
    search_path = Path(path)

    if not search_path.exists():
        return {
            "title": f"grep: {pattern}",
            "output": f"Path not found: {path}",
            "metadata": {"error": "not_found"},
        }

    # Check if ripgrep is available
    rg_path = shutil.which("rg")

    try:
        if rg_path:
            # Use ripgrep
            cmd_parts = [
                rg_path,
                "-nH",  # Line numbers + file names
                "--hidden",  # Search hidden files
                "--follow",  # Follow symlinks
                "--no-messages",  # Suppress error messages
                "--field-match-separator=|",
                "--regexp",
                pattern,
            ]

            if include_pattern:
                cmd_parts.extend(["--glob", include_pattern])

            cmd_parts.append(str(search_path))

            from wolo.subprocess_manager import managed_subprocess

            async with managed_subprocess(
                *cmd_parts, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            ) as process:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)

                output = stdout.decode("utf-8", errors="replace")

                # Parse results and sort by modification time
                matches = []
                for line in output.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("|", 2)
                    if len(parts) >= 3:
                        file_path_str, line_num, content = parts
                        try:
                            mtime = Path(file_path_str).stat().st_mtime
                        except OSError:
                            mtime = 0
                        matches.append(
                            {
                                "path": file_path_str,
                                "line": int(line_num) if line_num.isdigit() else 0,
                                "content": content[:200],  # Limit line length
                                "mtime": mtime,
                            }
                        )

                # Sort by modification time (newest first)
                matches.sort(key=lambda x: x["mtime"], reverse=True)

                # Limit results
                max_results = 100
                truncated_results = len(matches) > max_results
                matches = matches[:max_results]

                if not matches:
                    return {
                        "title": f"grep: {pattern}",
                        "output": f"No matches found for pattern: {pattern}",
                        "metadata": {"matches": 0},
                    }

                # Format output
                output_lines = [f"Found {len(matches)} matches (sorted by modification time):"]
                current_file = ""
                for m in matches:
                    if m["path"] != current_file:
                        if current_file:
                            output_lines.append("")
                        current_file = m["path"]
                        output_lines.append(f"\n{m['path']}:")
                    output_lines.append(f"  Line {m['line']}: {m['content']}")

                if truncated_results:
                    output_lines.append("\n(Results truncated. Use a more specific pattern.)")

                result_output = "\n".join(output_lines)
                match_count = len(matches)

        else:
            # Fallback to system grep
            cmd_parts = ["grep", "-rn", pattern, str(search_path)]

            if include_pattern:
                cmd_parts.extend(["--include", include_pattern])

            from wolo.subprocess_manager import managed_subprocess

            async with managed_subprocess(
                *cmd_parts, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            ) as process:
                stdout, stderr = await process.communicate()
                output = stdout.decode("utf-8", errors="replace")

                if process.returncode != 0 and not output:
                    return {
                        "title": f"grep: {pattern}",
                        "output": f"No matches found for pattern: {pattern}",
                        "metadata": {"matches": 0},
                    }

                match_count = len(output.strip().split("\n")) if output.strip() else 0
                result_output = output

        # Truncate if too large
        truncated = truncate_output(result_output)

        return {
            "title": f"grep: {pattern}",
            "output": truncated.content,
            "metadata": {
                "matches": match_count,
                "truncated": truncated.truncated,
                "using_ripgrep": bool(rg_path),
            },
        }

    except TimeoutError:
        return {
            "title": f"grep: {pattern}",
            "output": "Search timed out after 30 seconds",
            "metadata": {"error": "timeout"},
        }
    except Exception as e:
        return {
            "title": f"grep: {pattern}",
            "output": f"Error running grep: {e}",
            "metadata": {"error": str(e)},
        }


async def ls_execute(path: str = ".") -> dict[str, Any]:
    """List directory contents."""
    target_path = Path(path)

    if not target_path.exists():
        return {
            "title": f"ls: {path}",
            "output": f"Path not found: {path}",
            "metadata": {"error": "not_found"},
        }

    if not target_path.is_dir():
        return {
            "title": f"ls: {path}",
            "output": f"Not a directory: {path}",
            "metadata": {"error": "not_a_directory"},
        }

    try:
        entries = []
        for entry in sorted(target_path.iterdir()):
            if entry.name.startswith("."):
                continue  # Skip hidden files

            if entry.is_dir():
                entries.append(f"{entry.name}/")
            else:
                # Include file size
                try:
                    size = entry.stat().st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size // 1024}K"
                    else:
                        size_str = f"{size // (1024 * 1024)}M"
                    entries.append(f"{entry.name} ({size_str})")
                except OSError:
                    entries.append(entry.name)

        if not entries:
            return {"title": f"ls: {path}", "output": "(empty directory)", "metadata": {"count": 0}}

        return {
            "title": f"ls: {path}",
            "output": "\n".join(entries),
            "metadata": {"count": len(entries)},
        }
    except Exception as e:
        return {
            "title": f"ls: {path}",
            "output": f"Error listing directory: {e}",
            "metadata": {"error": str(e)},
        }


async def glob_execute(pattern: str, path: str = ".") -> dict[str, Any]:
    """Find files matching a glob pattern, sorted by modification time."""
    import glob as glob_module

    search_path = Path(path)

    if not search_path.exists():
        return {
            "title": f"glob: {pattern}",
            "output": f"Path not found: {path}",
            "metadata": {"error": "not_found"},
        }

    try:
        full_pattern = str(search_path / pattern)
        raw_matches = glob_module.glob(full_pattern, recursive=True)

        if not raw_matches:
            return {
                "title": f"glob: {pattern}",
                "output": f"No files found matching pattern: {pattern}",
                "metadata": {"matches": 0},
            }

        # Get modification times and sort
        matches_with_mtime = []
        for m in raw_matches:
            try:
                mtime = Path(m).stat().st_mtime
            except OSError:
                mtime = 0
            matches_with_mtime.append((m, mtime))

        # Sort by modification time (newest first)
        matches_with_mtime.sort(key=lambda x: x[1], reverse=True)

        # Limit results
        max_results = 100
        truncated_results = len(matches_with_mtime) > max_results
        limited_matches = matches_with_mtime[:max_results]

        output = "\n".join(m[0] for m in limited_matches)
        if truncated_results:
            output += f"\n\n... and {len(matches_with_mtime) - max_results} more files (showing first {max_results})"

        # Apply truncation for very large outputs
        truncated = truncate_output(output)

        return {
            "title": f"glob: {pattern}",
            "output": truncated.content,
            "metadata": {
                "matches": len(matches_with_mtime),
                "truncated": truncated_results or truncated.truncated,
            },
        }
    except Exception as e:
        return {
            "title": f"glob: {pattern}",
            "output": f"Error running glob: {e}",
            "metadata": {"error": str(e)},
        }


async def file_exists_execute(path: str) -> dict[str, Any]:
    """Check if a file or directory exists."""
    p = Path(path)
    exists = p.exists()

    if exists:
        file_type = "directory" if p.is_dir() else "file"
        return {
            "title": f"file_exists: {path}",
            "output": f"Yes, {path} exists ({file_type})",
            "metadata": {"exists": True, "type": file_type, "path": str(p)},
        }
    else:
        return {
            "title": f"file_exists: {path}",
            "output": f"No, {path} does not exist",
            "metadata": {"exists": False, "path": path},
        }


async def get_env_execute(name: str, default: str = "") -> dict[str, Any]:
    """Get an environment variable value."""

    value = os.getenv(name, default)

    if value:
        # Hide sensitive values
        is_sensitive = any(
            keyword in name.lower() for keyword in ["key", "secret", "password", "token"]
        )
        display_value = "***HIDDEN***" if is_sensitive else value
        return {
            "title": f"get_env: {name}",
            "output": f"{name}={display_value}",
            "metadata": {"name": name, "exists": True, "is_sensitive": is_sensitive},
        }
    else:
        return {
            "title": f"get_env: {name}",
            "output": f"{name} is not set" + (f", using default: {default}" if default else ""),
            "metadata": {"name": name, "exists": False},
        }


async def task_execute(
    agent: str, message: str, description: str = "", parent_session_id: str = "", config: Any = None
) -> dict[str, Any]:
    """
    Execute a task by spawning a subagent.

    Args:
        agent: Agent type (general, plan, explore)
        message: Task message for the subagent
        description: Optional description for logging
        parent_session_id: Parent session ID
        config: Wolo config object

    Returns:
        Result dict with the subagent's response
    """
    import logging

    from wolo.agent import agent_loop
    from wolo.agents import get_agent
    from wolo.metrics import MetricsCollector
    from wolo.session import add_user_message, create_subsession, get_session_messages

    logger = logging.getLogger(__name__)

    # Get agent config
    agent_config = get_agent(agent)

    # Create subsession
    subsession_id = create_subsession(parent_session_id, agent)
    logger.info(f"Created subsession {subsession_id[:8]}... with {agent} agent")

    # Track subagent session in parent metrics
    collector = MetricsCollector()
    parent_metrics = collector.get_session(parent_session_id)
    if parent_metrics:
        parent_metrics.record_subagent_session(subsession_id)

    # Add user message to subsession
    add_user_message(subsession_id, message)

    # Run agent loop in subsession
    try:
        result = await agent_loop(config, subsession_id, agent_config)

        # Extract response from result
        text_parts = [p.text for p in result.parts if hasattr(p, "text")]
        response_text = "\n".join(text_parts).strip()

        output = f"Subagent ({agent}) response:\n{response_text}"

        # Get message count
        messages = get_session_messages(subsession_id)
        metadata = {
            "subsession_id": subsession_id,
            "agent": agent,
            "message_count": len(messages),
            "finish_reason": result.finish_reason,
        }

        return {"title": description or f"task: {agent}", "output": output, "metadata": metadata}

    except Exception as e:
        logger.error(f"Subagent error: {e}")
        return {
            "title": description or f"task: {agent}",
            "output": f"Subagent error: {e}",
            "metadata": {"error": str(e), "subsession_id": subsession_id},
        }


async def execute_tool(
    tool_part: ToolPart, agent_config: Any = None, session_id: str = None, config: Any = None
) -> None:
    """Execute a tool call and update the part with results."""
    registry = get_registry()

    # Check permissions if agent_config is provided
    if agent_config:
        from wolo.agents import check_permission

        permission = check_permission(agent_config, tool_part.tool)
        if permission == "deny":
            tool_part.status = "error"
            tool_part.output = (
                f"Permission denied: {tool_part.tool} is not allowed by {agent_config.name} agent"
            )
            # Publish both start and complete for consistent UI display
            start_event = registry.format_tool_start(tool_part.tool, tool_part.input)
            await bus.publish("tool-start", start_event)
            await bus.publish(
                "tool-complete",
                {
                    "tool": tool_part.tool,
                    "status": "error",
                    "duration": 0,
                    "brief": f"🚫 denied by {agent_config.name} agent",
                },
            )
            return
        elif permission == "ask":
            # For now, treat "ask" as "deny" since we don't have interactive prompts
            tool_part.status = "error"
            tool_part.output = f"Permission required: {tool_part.tool} requires user confirmation for {agent_config.name} agent"
            start_event = registry.format_tool_start(tool_part.tool, tool_part.input)
            await bus.publish("tool-start", start_event)
            await bus.publish(
                "tool-complete",
                {
                    "tool": tool_part.tool,
                    "status": "error",
                    "duration": 0,
                    "brief": "🔐 requires confirmation",
                },
            )
            return

    tool_part.status = "running"
    tool_part.start_time = time.time()

    # Use registry for tool-start event
    start_event = registry.format_tool_start(tool_part.tool, tool_part.input)
    await bus.publish("tool-start", start_event)

    try:
        if tool_part.tool == "shell":
            command = tool_part.input.get("command", "")
            timeout = tool_part.input.get("timeout", 30000)
            result = await shell_execute(command, timeout)
            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "command": command,
                "exit_code": result.get("metadata", {}).get("exit_code", 0),
            }

        elif tool_part.tool == "read":
            file_path = tool_part.input.get("file_path", "")
            offset = tool_part.input.get("offset", 0)
            limit = tool_part.input.get("limit", 2000)
            result = await read_execute(file_path, offset, limit)
            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "file_path": file_path,
                "total_lines": result.get("metadata", {}).get("total_lines", 0),
                "offset": offset,
                "showing_lines": result.get("metadata", {}).get("showing_lines", 0),
            }

            # Track file read time for modification detection
            if session_id and result["metadata"].get("error") is None:
                FileTime.read(session_id, file_path)

        elif tool_part.tool == "write":
            from wolo.path_guard_exceptions import PathConfirmationRequired
            from wolo.cli.path_confirmation import handle_path_confirmation, SessionCancelled

            file_path = tool_part.input.get("file_path", "")
            content = tool_part.input.get("content", "")

            # Check if file was modified externally since last read
            if session_id:
                try:
                    FileTime.assert_not_modified(session_id, file_path)
                except FileModifiedError:
                    tool_part.status = "error"
                    tool_part.output = (
                        f"File '{file_path}' has been modified since you last read it. "
                        f"Please read the file again to see the current contents before writing."
                    )
                    # Skip the write
                    raise

            # Try to write, handle confirmation if needed
            try:
                result = await write_execute(file_path, content)
            except PathConfirmationRequired as e:
                # Handle confirmation
                try:
                    allowed = await handle_path_confirmation(e.path, e.operation)
                    if allowed:
                        # Retry after confirmation
                        result = await write_execute(file_path, content)
                    else:
                        tool_part.status = "error"
                        tool_part.output = f"Permission denied by user: {e.path}"
                        return  # Don't continue with normal completion flow
                except SessionCancelled:
                    tool_part.status = "error"
                    tool_part.output = f"Session cancelled during path confirmation: {e.path}"
                    return  # Don't continue with normal completion flow

            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            lines = content.count("\n") + 1
            tool_part._metadata = {
                "file_path": file_path,
                "additions": lines,
                "deletions": 0,
                "size": len(content),
            }

            # Update file time after write
            if session_id:
                FileTime.update(session_id, file_path)

        elif tool_part.tool == "edit":
            from wolo.path_guard_exceptions import PathConfirmationRequired
            from wolo.cli.path_confirmation import handle_path_confirmation, SessionCancelled

            file_path = tool_part.input.get("file_path", "")
            old_text = tool_part.input.get("old_text", "")
            new_text = tool_part.input.get("new_text", "")

            # Check if file was modified externally since last read
            if session_id:
                try:
                    FileTime.assert_not_modified(session_id, file_path)
                except FileModifiedError:
                    tool_part.status = "error"
                    tool_part.output = (
                        f"File '{file_path}' has been modified since you last read it. "
                        f"Please read the file again to see the current contents before editing."
                    )
                    # Skip the edit
                    raise

            # Try to edit, handle confirmation if needed
            try:
                result = await edit_execute(file_path, old_text, new_text)
            except PathConfirmationRequired as e:
                # Handle confirmation
                try:
                    allowed = await handle_path_confirmation(e.path, e.operation)
                    if allowed:
                        # Retry after confirmation
                        result = await edit_execute(file_path, old_text, new_text)
                    else:
                        tool_part.status = "error"
                        tool_part.output = f"Permission denied by user: {e.path}"
                        return  # Don't continue with normal completion flow
                except SessionCancelled:
                    tool_part.status = "error"
                    tool_part.output = f"Session cancelled during path confirmation: {e.path}"
                    return  # Don't continue with normal completion flow

            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display (including diff)
            tool_part._metadata = {
                "file_path": file_path,
                "additions": result.get("metadata", {}).get("additions", 0),
                "deletions": result.get("metadata", {}).get("deletions", 0),
                "diff": result.get("metadata", {}).get("diff", ""),
            }

            # Update file time after edit
            if session_id and result["metadata"].get("error") is None:
                FileTime.update(session_id, file_path)

        elif tool_part.tool == "multiedit":
            edits = tool_part.input.get("edits", [])
            result = await multiedit_execute(edits)
            tool_part.output = result["output"]
            tool_part.status = "completed"

        elif tool_part.tool == "grep":
            pattern = tool_part.input.get("pattern", "")
            path = tool_part.input.get("path", ".")
            include_pattern = tool_part.input.get("include_pattern")
            result = await grep_execute(pattern, path, include_pattern)
            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "pattern": pattern,
                "path": path,
                "matches": result.get("metadata", {}).get("matches", 0),
            }

        elif tool_part.tool == "glob":
            pattern = tool_part.input.get("pattern", "")
            path = tool_part.input.get("path", ".")
            result = await glob_execute(pattern, path)
            tool_part.output = result["output"]
            tool_part.status = "completed"
            # Store metadata for verbose display
            tool_part._metadata = {
                "pattern": pattern,
                "path": path,
                "matches": result.get("metadata", {}).get("matches", 0),
            }

        elif tool_part.tool.startswith("mcp_"):
            # Handle MCP server tools
            from wolo.mcp_integration import call_mcp_tool

            result = await call_mcp_tool(tool_part.tool, tool_part.input)
            # Extract text content from MCP result
            content = result.get("content", [])
            if content and isinstance(content, list):
                text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                tool_part.output = "\n".join(text_parts)
            else:
                tool_part.output = str(result)
            tool_part.status = "error" if result.get("isError") else "completed"

        elif tool_part.tool == "task":
            agent = tool_part.input.get("agent", "")
            message = tool_part.input.get("message", "")
            description = tool_part.input.get("description", "")

            if not session_id:
                tool_part.status = "error"
                tool_part.output = "Task tool requires session_id"
            elif not config:
                tool_part.status = "error"
                tool_part.output = "Task tool requires config"
            elif not agent or not message:
                tool_part.status = "error"
                tool_part.output = "Task tool requires 'agent' and 'message' parameters"
            else:
                result = await task_execute(agent, message, description, session_id, config)
                tool_part.output = result["output"]
                tool_part.status = "completed"

        elif tool_part.tool == "todowrite":
            todos = tool_part.input.get("todos", [])
            sid = tool_part.input.get("session_id") or session_id

            if not sid:
                tool_part.status = "error"
                tool_part.output = "TodoWrite requires session_id"
            else:
                # Store todos in memory
                _todos[sid] = todos

                # Persist todos to disk
                from wolo.session import save_session_todos

                save_session_todos(sid, todos)

                # Format output
                [t for t in todos if t.get("status") == "in_progress"]
                completed = [t for t in todos if t.get("status") == "completed"]
                [t for t in todos if t.get("status") == "pending"]

                output_lines = ["Todo list updated:"]
                for t in todos:
                    status_sym = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
                    content = t.get("content", "")
                    status = t.get("status", "pending")
                    output_lines.append(f"  {status_sym.get(status, '[?]')} {content}")

                if completed:
                    output_lines.append(f"\nCompleted: {len(completed)}/{len(todos)}")

                tool_part.output = "\n".join(output_lines)
                tool_part.status = "completed"
                # Store metadata for verbose display
                tool_part._metadata = {
                    "todos": todos,
                    "total": len(todos),
                    "completed": len(completed),
                }

        elif tool_part.tool == "todoread":
            sid = tool_part.input.get("session_id") or session_id

            if not sid:
                tool_part.status = "error"
                tool_part.output = "TodoRead requires session_id"
            else:
                # Read from memory
                todos = _todos.get(sid, [])

                # If not in memory, try loading from disk
                if not todos:
                    from wolo.session import load_session_todos

                    todos = load_session_todos(sid)
                    if todos:
                        _todos[sid] = todos

                if not todos:
                    tool_part.output = "No todos found for this session."
                else:
                    # Format output
                    output_lines = [f"Current todo list ({len(todos)} items):"]
                    for t in todos:
                        status_sym = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
                        content = t.get("content", "")
                        status = t.get("status", "pending")
                        output_lines.append(f"  {status_sym.get(status, '[?]')} {content}")

                    completed = len([t for t in todos if t.get("status") == "completed"])
                    output_lines.append(f"\nProgress: {completed}/{len(todos)} completed")

                    tool_part.output = "\n".join(output_lines)

                tool_part.status = "completed"

        elif tool_part.tool == "question":
            from wolo.question import (
                QuestionCancelledError,
                QuestionInfo,
                QuestionOption,
                QuestionTimeoutError,
                ask_questions,
            )

            questions_data = tool_part.input.get("questions", [])

            if not questions_data:
                tool_part.status = "error"
                tool_part.output = "No questions provided"
            elif not session_id:
                tool_part.status = "error"
                tool_part.output = "Question tool requires session_id"
            else:
                questions = [
                    QuestionInfo(
                        question=q.get("question", ""),
                        options=[
                            QuestionOption(
                                label=o.get("label", ""), description=o.get("description", "")
                            )
                            for o in q.get("options", [])
                        ],
                        header=q.get("header", ""),
                        allow_custom=q.get("allow_custom", True),
                    )
                    for q in questions_data
                ]

                try:
                    answers = await ask_questions(session_id, questions, timeout=300.0)

                    # Format output
                    output_lines = ["User answers:"]
                    for i, (q, a) in enumerate(zip(questions, answers)):
                        output_lines.append(f"\nQ{i + 1}: {q.question}")
                        if a:
                            output_lines.append(f"A{i + 1}: {', '.join(a)}")
                        else:
                            output_lines.append(f"A{i + 1}: (no answer)")

                    tool_part.output = "\n".join(output_lines)
                    tool_part.status = "completed"

                except QuestionCancelledError:
                    tool_part.output = "User cancelled the question"
                    tool_part.status = "error"
                except QuestionTimeoutError:
                    tool_part.output = "Question timed out waiting for user response"
                    tool_part.status = "error"

        elif tool_part.tool == "batch":
            tool_calls = tool_part.input.get("tool_calls", [])

            if not tool_calls:
                tool_part.status = "error"
                tool_part.output = "No tool calls provided"
            else:
                # Check for nested batch calls
                has_nested_batch = any(tc.get("tool") == "batch" for tc in tool_calls)
                if has_nested_batch:
                    tool_part.status = "error"
                    tool_part.output = "Nested batch calls are not allowed"
                else:
                    # Limit parallel calls
                    max_parallel = 10
                    if len(tool_calls) > max_parallel:
                        tool_part.status = "error"
                        tool_part.output = (
                            f"Too many tool calls ({len(tool_calls)}). Maximum is {max_parallel}."
                        )
                    else:
                        # Create ToolPart for each call
                        sub_parts = []
                        for tc in tool_calls:
                            sub_part = ToolPart(
                                tool=tc.get("tool", ""),
                                input=tc.get("input", {}),
                            )
                            sub_parts.append(sub_part)

                        # Execute in parallel
                        tasks = [
                            execute_tool(sp, session_id=session_id, config=config)
                            for sp in sub_parts
                        ]
                        await asyncio.gather(*tasks, return_exceptions=True)

                        # Collect results
                        output_lines = [f"Batch execution results ({len(sub_parts)} tools):"]
                        success_count = 0
                        for i, sp in enumerate(sub_parts):
                            status_icon = "✓" if sp.status == "completed" else "✗"
                            if sp.status == "completed":
                                success_count += 1
                            output_lines.append(f"\n{i + 1}. [{status_icon}] {sp.tool}")
                            # Truncate individual outputs
                            if sp.output:
                                preview = sp.output[:200]
                                if len(sp.output) > 200:
                                    preview += "..."
                                output_lines.append(f"   {preview}")

                        output_lines.append(
                            f"\nSummary: {success_count}/{len(sub_parts)} succeeded"
                        )

                        tool_part.output = "\n".join(output_lines)
                        tool_part.status = (
                            "completed" if success_count == len(sub_parts) else "partial"
                        )

        elif tool_part.tool == "skill":
            from wolo.skill_tool import skill_execute

            skill_name = tool_part.input.get("name", "")
            if not skill_name:
                tool_part.status = "error"
                tool_part.output = "Skill name is required"
            else:
                result = await skill_execute(skill_name)
                tool_part.output = result
                tool_part.status = "completed"

        else:
            tool_part.status = "error"
            tool_part.output = f"Unknown tool: {tool_part.tool}"

    except Exception as e:
        tool_part.status = "error"
        tool_part.output = f"Error executing {tool_part.tool}: {e}"

    # Record end time and duration
    tool_part.end_time = time.time()
    duration = tool_part.end_time - tool_part.start_time

    # Collect metadata for display (used by verbose mode)
    tool_metadata = getattr(tool_part, "_metadata", {})

    # Use registry for tool-complete event
    complete_event = registry.format_tool_complete(
        tool_part.tool, tool_part.output, tool_part.status, duration, tool_metadata
    )
    await bus.publish("tool-complete", complete_event)
