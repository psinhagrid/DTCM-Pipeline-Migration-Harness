from fastapi import APIRouter, HTTPException
from pathlib import Path
from pydantic import BaseModel

router = APIRouter(prefix="/skills-api")

_ROOT = Path(__file__).parents[1]

SKILL_DIRS: dict[str, Path] = {
    "assess_agent":    _ROOT / "agents" / "assess_agent"    / "skills",
    "convert_agent":   _ROOT / "agents" / "convert_agent"   / "skills",
    "reconcile_agent": _ROOT / "agents" / "reconcile_agent" / "skills",
    "deploy_agent":    _ROOT / "agents" / "deploy_agent"    / "skills",
    "orchestrator":    _ROOT / "agents" / "orchestrator"    / "skills",
}


@router.get("")
def list_skills():
    result = {}
    for agent, path in SKILL_DIRS.items():
        if path.exists():
            result[agent] = [f.name for f in sorted(path.glob("*.md"))]
        else:
            result[agent] = []
    return {"skills": result}


def _resolve(agent: str, filename: str) -> Path:
    if agent not in SKILL_DIRS:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent}")
    if not filename.endswith(".md") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return SKILL_DIRS[agent] / filename


@router.get("/{agent}/{filename}")
def get_skill(agent: str, filename: str):
    path = _resolve(agent, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"agent": agent, "filename": filename, "content": path.read_text(encoding="utf-8")}


class SkillUpdate(BaseModel):
    content: str


@router.put("/{agent}/{filename}")
def update_skill(agent: str, filename: str, body: SkillUpdate):
    path = _resolve(agent, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    path.write_text(body.content, encoding="utf-8")
    return {"status": "saved", "agent": agent, "filename": filename}


@router.delete("/{agent}/{filename}")
def delete_skill(agent: str, filename: str):
    path = _resolve(agent, filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    path.unlink()
    return {"status": "deleted", "agent": agent, "filename": filename}
