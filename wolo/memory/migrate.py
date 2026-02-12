"""Migration tool for converting JSON memories to markdown format.

Usage:
    from wolo.memory.migrate import migrate_json_to_markdown

    count = migrate_json_to_markdown(
        old_dir=Path.home() / ".wolo" / "memories",
        new_dir=Path.cwd() / ".wolo" / "memories"
    )
    print(f"Migrated {count} memories")
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from wolo.memory.markdown_model import MarkdownMemory

logger = logging.getLogger(__name__)


def migrate_json_to_markdown(
    old_dir: Path,
    new_dir: Path,
    dry_run: bool = False,
) -> int:
    """Migrate all JSON memories to markdown format.

    Args:
        old_dir: Directory containing JSON memory files
        new_dir: Directory to write markdown files
        dry_run: If True, don't actually write files

    Returns:
        Number of memories migrated
    """
    if not old_dir.exists():
        logger.info(f"Source directory does not exist: {old_dir}")
        return 0

    # Create target directory
    if not dry_run:
        new_dir.mkdir(parents=True, exist_ok=True)

    migrated = 0
    errors = 0

    for json_file in old_dir.glob("*.json"):
        # Skip index files
        if json_file.name == "index.json":
            continue

        try:
            with open(json_file) as f:
                data = json.load(f)

            # Validate required fields
            if not all(k in data for k in ("id", "title", "content")):
                logger.warning(f"Skipping invalid memory: {json_file}")
                errors += 1
                continue

            # Parse timestamps
            created_at = datetime.fromisoformat(data["created_at"])
            updated_at = datetime.fromisoformat(data["updated_at"])

            # Create markdown filename (preserve original ID)
            md_filename = f"memory-{data['id']}.md"
            md_path = new_dir / md_filename

            # Create markdown memory
            memory = MarkdownMemory(
                file_path=md_path,
                title=data["title"],
                tags=data.get("tags", []),
                created_at=created_at,
                updated_at=updated_at,
                source_session=data.get("source_session"),
                content=data["content"],
            )

            if not dry_run:
                memory.save()
                logger.info(f"Migrated: {data['id']} -> {md_filename}")
            else:
                logger.info(f"[dry-run] Would migrate: {data['id']} -> {md_filename}")

            migrated += 1

        except Exception as e:
            logger.error(f"Failed to migrate {json_file}: {e}")
            errors += 1

    logger.info(f"Migration complete: {migrated} migrated, {errors} errors")
    return migrated


def cli_migrate(new_dir: Path | None = None, dry_run: bool = False) -> None:
    """CLI entry point for migration.

    Args:
        new_dir: Target directory for markdown files. Defaults to project .wolo/memories
                 if project config exists, otherwise ~/.wolo/memories
        dry_run: If True, don't actually write files
    """
    from wolo.config import Config

    # Determine source directory (always home)
    old_dir = Path.home() / ".wolo" / "memories"

    # Determine target directory
    if new_dir is None:
        # Check if project config exists
        config_source_dir, _ = Config._find_config_file()
        if config_source_dir:
            new_dir = config_source_dir / "memories"
        else:
            new_dir = Path.home() / ".wolo" / "memories"

    print("Migrating memories from JSON to markdown")
    print(f"  Source: {old_dir}")
    print(f"  Target: {new_dir}")
    if dry_run:
        print("  Mode: DRY RUN (no files will be written)")
    print()

    count = migrate_json_to_markdown(old_dir, new_dir, dry_run=dry_run)

    print(f"\nMigrated {count} memories")
    if not dry_run and count > 0:
        print("\nYou may want to remove the old JSON files:")
        print(f"  rm -rf {old_dir}/*.json")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate JSON memories to markdown")
    parser.add_argument(
        "--target",
        "-t",
        type=Path,
        help="Target directory for markdown files",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Don't actually write files",
    )

    args = parser.parse_args()
    cli_migrate(new_dir=args.target, dry_run=args.dry_run)
