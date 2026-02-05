"""Search tools - grep, ls, glob, file_exists."""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from wolo.truncate import truncate_output


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

    return {
        "title": f"file_exists: {path}",
        "output": f"No, {path} does not exist",
        "metadata": {"exists": False, "path": str(p)},
    }
