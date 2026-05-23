import yaml
from pathlib import Path

_SKILLS_DIR = Path(__file__).parents[1] / "skills"


def read_skill_tool(name: str) -> dict:
    """
    Read full instructions for a named skill.
    Called by the agent when it decides to use a skill.
    Returns name, description, and full instruction text.
    """
    path = _SKILLS_DIR / f"{name}.md"
    if not path.exists():
        available = [p.stem for p in sorted(_SKILLS_DIR.glob("*.md"))]
        return {"error": f"Skill '{name}' not found", "available_skills": available}

    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body: str  = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()

    return {
        "name":         meta.get("name", name),
        "description":  str(meta.get("description", "")).strip(),
        "instructions": body,
    }
