from fastapi import APIRouter, HTTPException
from pathlib import Path
from pydantic import BaseModel

router = APIRouter(prefix="/skills-api")

_ROOT = Path(__file__).parents[1]

SKILL_DIRS: dict[str, Path] = {
    "skills": _ROOT / "skills",
}


@router.get("")
def list_skills():
    d = _ROOT / "skills"
    if d.exists():
        return {"skills": [f.name for f in sorted(d.glob("*.md"))]}
    return {"skills": []}


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
