"""File writing and editing tools."""

from pathlib import Path
from typing import Any

from wolo.smart_replace import smart_replace


async def write_execute(file_path: str, content: str) -> dict[str, Any]:
    """Write content to a file. Wolo runs in sandbox; no path authorization checks."""
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
    import difflib

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
