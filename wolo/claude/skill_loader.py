"""
Skills loader.

Skills are Markdown files with YAML frontmatter that define
reusable prompts and scripts for the agent.

Supports loading from multiple directories with priority:
1. ~/.wolo/skills/ (highest priority - Wolo native)
2. ~/.claude/skills/ (if Claude compatibility enabled)

Format:
    <skills-dir>/<skill-name>/
        SKILL.md        # Main skill definition
        scripts/        # Optional scripts
        data/           # Optional data files
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


# Default skills directories
WOLO_SKILLS_DIR = Path.home() / ".wolo" / "skills"
CLAUDE_SKILLS_DIR = Path.home() / ".claude" / "skills"


@dataclass
class ClaudeSkill:
    """A Claude-format skill definition."""
    
    # Identity
    name: str
    description: str
    
    # Content
    content: str  # Markdown body (after frontmatter)
    
    # Paths
    skill_dir: Path = field(default_factory=Path)
    scripts_dir: Optional[Path] = None
    data_dir: Optional[Path] = None
    
    # Raw frontmatter for extension
    frontmatter: dict = field(default_factory=dict)
    
    def get_system_prompt(self) -> str:
        """
        Get the skill content as a system prompt.
        
        Replaces path variables like .claude/skills/<name>/scripts/
        or .wolo/skills/<name>/scripts/ with absolute paths.
        """
        content = self.content
        
        # Replace relative paths with absolute paths
        if self.scripts_dir and self.scripts_dir.exists():
            # Replace .claude/skills/<name>/scripts/ patterns
            content = re.sub(
                r'\.claude/skills/[^/]+/scripts/',
                str(self.scripts_dir) + '/',
                content
            )
            # Replace .wolo/skills/<name>/scripts/ patterns
            content = re.sub(
                r'\.wolo/skills/[^/]+/scripts/',
                str(self.scripts_dir) + '/',
                content
            )
        
        return content
    
    def matches(self, query: str) -> bool:
        """
        Check if this skill matches a query.
        
        Matching is based on name and description keywords.
        Also supports common aliases and translations.
        """
        query_lower = query.lower()
        
        # Check name
        if self.name.lower() in query_lower:
            return True
        
        # Check description keywords
        if self.description:
            desc_words = self.description.lower().split()
            for word in desc_words:
                if len(word) > 3 and word in query_lower:
                    return True
        
        # Check common aliases/translations for UI/UX
        ui_ux_keywords = [
            "ui", "ux", "界面", "设计", "design", "styling", "style",
            "前端", "frontend", "layout", "布局", "美化", "美观",
        ]
        if any(kw in query_lower for kw in ui_ux_keywords):
            if "ui" in self.name.lower() or "ux" in self.name.lower() or "design" in self.name.lower():
                return True
        
        return False


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from Markdown content.
    
    Args:
        content: Markdown content with optional frontmatter
    
    Returns:
        Tuple of (frontmatter dict, body content)
    """
    if not content.startswith("---"):
        return {}, content
    
    # Find the closing ---
    lines = content.split("\n")
    end_idx = -1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    
    if end_idx == -1:
        return {}, content
    
    # Parse YAML frontmatter
    frontmatter_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])
    
    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse frontmatter: {e}")
        frontmatter = {}
    
    return frontmatter, body.strip()


def load_skill(skill_dir: Path) -> Optional[ClaudeSkill]:
    """
    Load a single Claude skill from a directory.
    
    Args:
        skill_dir: Path to the skill directory
    
    Returns:
        ClaudeSkill if loaded successfully, None otherwise
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        logger.debug(f"No SKILL.md found in {skill_dir}")
        return None
    
    try:
        content = skill_md.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(content)
        
        # Get name and description from frontmatter
        name = frontmatter.get("name", skill_dir.name)
        description = frontmatter.get("description", "")
        
        # Check for scripts and data directories
        scripts_dir = skill_dir / "scripts"
        data_dir = skill_dir / "data"
        
        skill = ClaudeSkill(
            name=name,
            description=description,
            content=body,
            skill_dir=skill_dir,
            scripts_dir=scripts_dir if scripts_dir.exists() else None,
            data_dir=data_dir if data_dir.exists() else None,
            frontmatter=frontmatter,
        )
        
        logger.debug(f"Loaded skill: {name}")
        return skill
        
    except Exception as e:
        logger.warning(f"Failed to load skill from {skill_dir}: {e}")
        return None


def _load_skills_from_dir(skills_dir: Path) -> dict[str, ClaudeSkill]:
    """
    Load skills from a single directory.
    
    Args:
        skills_dir: Path to skills directory
    
    Returns:
        Dict mapping skill name to skill object
    """
    if not skills_dir.exists():
        logger.debug(f"Skills directory not found: {skills_dir}")
        return {}
    
    skills = {}
    for item in skills_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            skill = load_skill(item)
            if skill:
                skills[skill.name] = skill
    
    return skills


def load_claude_skills(skills_dir: Optional[Path] = None) -> list[ClaudeSkill]:
    """
    Load all Claude skills from the skills directory.
    
    Args:
        skills_dir: Path to skills directory (default: ~/.claude/skills)
    
    Returns:
        List of loaded skills
    """
    if skills_dir is None:
        skills_dir = CLAUDE_SKILLS_DIR
    
    skills = _load_skills_from_dir(skills_dir)
    
    if skills:
        logger.info(f"Loaded {len(skills)} Claude skills from {skills_dir}")
    
    return list(skills.values())


def load_all_skills(
    wolo_skills_dir: Optional[Path] = None,
    claude_skills_dir: Optional[Path] = None,
    claude_enabled: bool = False
) -> list[ClaudeSkill]:
    """
    Load skills from both Wolo and Claude directories.
    
    Priority:
    1. ~/.wolo/skills/ (highest - Wolo native)
    2. ~/.claude/skills/ (if enabled, no duplicates)
    
    Args:
        wolo_skills_dir: Path to Wolo skills (default: ~/.wolo/skills)
        claude_skills_dir: Path to Claude skills (default: ~/.claude/skills)
        claude_enabled: Whether to load Claude skills
    
    Returns:
        List of loaded skills (Wolo skills take precedence)
    """
    wolo_dir = wolo_skills_dir or WOLO_SKILLS_DIR
    claude_dir = claude_skills_dir or CLAUDE_SKILLS_DIR
    
    # Load Wolo skills first (highest priority)
    skills = _load_skills_from_dir(wolo_dir)
    wolo_count = len(skills)
    
    if wolo_count > 0:
        logger.info(f"Loaded {wolo_count} skills from {wolo_dir}")
    
    # Load Claude skills if enabled (skip duplicates)
    if claude_enabled:
        claude_skills = _load_skills_from_dir(claude_dir)
        claude_added = 0
        
        for name, skill in claude_skills.items():
            if name not in skills:
                skills[name] = skill
                claude_added += 1
            else:
                logger.debug(f"Skipping duplicate skill from Claude: {name}")
        
        if claude_added > 0:
            logger.info(f"Loaded {claude_added} additional skills from {claude_dir}")
    
    return list(skills.values())


def find_matching_skills(skills: list[ClaudeSkill], query: str) -> list[ClaudeSkill]:
    """
    Find skills that match a query.
    
    Args:
        skills: List of skills to search
        query: Query string to match
    
    Returns:
        List of matching skills
    """
    return [s for s in skills if s.matches(query)]
