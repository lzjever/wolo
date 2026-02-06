"""File reading tools."""

from pathlib import Path
from typing import Any

from wolo.tools_pkg.utils import _is_binary_file, _suggest_similar_files
from wolo.truncate import truncate_output

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
