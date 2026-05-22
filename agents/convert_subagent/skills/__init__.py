"""
Skills loader for convert_agent.

load_skills()   — reads all skill .md files and returns their full metadata catalog.
select_skills() — chooses which skills are relevant for a given task context.
                  Currently returns all skills; will use LLM reasoning once the
                  supervisor is wired up.
"""

import yaml
from pathlib import Path

_SKILLS_DIR = Path(__file__).parent


def load_skills() -> list[dict]:
    """
    Parse all *.md skill files in this directory.
    Returns a list of skill dicts:
      name, description, recommended_tools, examples, instructions
    """
    skills = []
    for path in sorted(_SKILLS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")

        meta: dict = {}
        body: str  = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()

        skills.append({
            "name":         meta.get("name",         path.stem),
            "description":  str(meta.get("description", "")).strip(),
            "examples":     meta.get("examples",     []),
            "instructions": body,
        })
    return skills


def select_skills(task_context: str, available_skills: list[dict]) -> list[dict]:
    """
    Choose which skills are relevant for the given task context.

    TODO: replace with LLM reasoning over skill metadata — the agent should
    select skills the same way it selects tools: by reading name, description,
    and recommended_tools, then deciding what fits the task.

    Current behaviour: return all skills (safe default for the deterministic agent).
    """
    return available_skills
