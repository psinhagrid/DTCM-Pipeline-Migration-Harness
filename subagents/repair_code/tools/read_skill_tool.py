import yaml
from pathlib import Path

_LOCAL_SKILLS_DIR  = Path(__file__).parents[1] / "skills"
_SHARED_SKILLS_DIR = Path(__file__).parents[3] / "skills"


def read_skill_tool(name: str) -> dict:
    """
    Read full instructions for a named skill.
    Checks agent-local skills first, falls back to shared skills/ at project root.
    Returns name, description, and full instruction text.
    """
    # Local first (agent-specific), then shared (cross-agent)
    path = _LOCAL_SKILLS_DIR / f"{name}.md"
    if not path.exists():
        path = _SHARED_SKILLS_DIR / f"{name}.md"

    if not path.exists():
        local   = [p.stem for p in sorted(_LOCAL_SKILLS_DIR.glob("*.md"))]
        shared  = [p.stem for p in sorted(_SHARED_SKILLS_DIR.glob("*.md"))]
        return {
            "error":            f"Skill '{name}' not found",
            "available_local":  local,
            "available_shared": shared,
        }

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
