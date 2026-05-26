from fastapi import APIRouter, HTTPException
from pathlib import Path
from pydantic import BaseModel

router = APIRouter(prefix="/skills-api")

_ROOT = Path(__file__).parents[1]

# All directories that contain skill .md files
SKILL_DIRS: dict[str, Path] = {
    "shared":      _ROOT / "skills",
    "assess":      _ROOT / "subagents/assess_subagent/skills",
    "convert":     _ROOT / "subagents/convert_subagent/skills",
    "reconcile":   _ROOT / "subagents/reconcile_subagent/skills",
    "deploy":      _ROOT / "subagents/deploy_subagent/skills",
    "repair_code": _ROOT / "subagents/repair_code/skills",
}


@router.get("")
def list_skills():
    """Return all skill files grouped by agent."""
    result = {}
    for agent, d in SKILL_DIRS.items():
        if d.exists():
            result[agent] = [f.name for f in sorted(d.glob("*.md"))]
    return result


def _resolve(agent: str, filename: str) -> Path:
    if agent not in SKILL_DIRS:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent}")
    if not filename.endswith(".md") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return SKILL_DIRS[agent] / filename


@router.get("/{agent}/{filename}")
def get_skill(agent: str, filename: str):
    """Return content of a single skill file."""
    path = _resolve(agent, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"agent": agent, "filename": filename, "content": path.read_text(encoding="utf-8")}


class SkillUpdate(BaseModel):
    content: str


@router.put("/{agent}/{filename}")
def update_skill(agent: str, filename: str, body: SkillUpdate):
    """Overwrite a skill file with new content."""
    path = _resolve(agent, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    path.write_text(body.content, encoding="utf-8")
    return {"status": "saved", "agent": agent, "filename": filename}
