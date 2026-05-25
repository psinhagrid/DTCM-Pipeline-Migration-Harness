from pathlib import Path


def write_file_tool(path: str, content: str) -> dict:
    """
    Write fixed content back to the original file location.
    Creates a .bak backup of the original before overwriting.
    """
    p = Path(path)
    if not p.exists():
        return {"error": f"File not found: {path}"}

    # Backup original
    bak = p.with_suffix(p.suffix + ".bak")
    bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    # Write fix
    p.write_text(content, encoding="utf-8")
    return {"status": "ok", "written_to": str(p), "backup": str(bak)}
