"""Skills: instructions the model loads only when a task needs them."""
from pathlib import Path

SKILLS_DIR = Path.cwd() / ".claude" / "skills"  # same layout Claude Code uses


def frontmatter(text):
    """Read the name: and description: lines between the two --- markers."""
    if not text.startswith("---"):
        return {}
    header = text.split("---", 2)[1]
    pairs = (line.split(":", 1) for line in header.splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def list_skills():
    skills = {}
    for f in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta = frontmatter(f.read_text())
        skills[meta.get("name", f.parent.name)] = (meta.get("description", ""), f)
    return skills


def load_skill(name):
    skills = list_skills()
    if name not in skills:
        raise ValueError(f"No skill named {name}. Available: {', '.join(skills) or 'none'}")
    path = skills[name][1]
    return f"Skill folder: {path.parent}\n\n{path.read_text()}"
