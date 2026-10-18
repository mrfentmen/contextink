"""Context acquisition: get the missing context from the environment, not from the user.

Given a terse instruction, the agent scans the repo (README, package manifest, git
state, recent files, tree) and reports what it found plus what is still genuinely
missing. Parsing is rules, not vibes: every signal comes from a file or a git
command, and a gap is named explicitly rather than papered over.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def scan_repo(cwd: str) -> dict:
    root = Path(cwd or ".")
    ctx: dict = {"cwd": str(root.resolve())}
    # README
    for name in ("README.md", "README.rst", "README.txt", "README"):
        p = root / name
        if p.is_file():
            try:
                ctx["readme_head"] = p.read_text(encoding="utf-8", errors="replace")[:600].splitlines()[:6]
            except OSError:
                pass
            break
    # package.json
    pj = root / "package.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            ctx["package"] = {
                "name": data.get("name"),
                "scripts": list((data.get("scripts") or {}).keys()),
                "deps": list((data.get("dependencies") or {}).keys())[:15],
            }
        except (ValueError, OSError):
            pass
    # python project
    for f in ("pyproject.toml", "setup.py", "setup.cfg"):
        p = root / f
        if p.is_file():
            ctx["python_project"] = f
            break
    # git state
    try:
        log = subprocess.run(["git", "log", "--oneline", "-5"], cwd=str(root),
                             capture_output=True, text=True, timeout=5)
        if log.returncode == 0:
            ctx["git_log"] = [l for l in log.stdout.splitlines() if l.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        status = subprocess.run(["git", "status", "--short"], cwd=str(root),
                                capture_output=True, text=True, timeout=5)
        if status.returncode == 0:
            ctx["git_status"] = [l for l in status.stdout.splitlines() if l.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass
    # file tree (top level + one level)
    tree = []
    try:
        for p in sorted(root.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                tree.append(p.name + "/")
                try:
                    for q in sorted(p.iterdir())[:6]:
                        if not q.name.startswith("."):
                            tree.append("  " + q.name + ("/" if q.is_dir() else ""))
                except OSError:
                    pass
            else:
                tree.append(p.name)
    except OSError:
        pass
    ctx["tree"] = tree[:50]
    # recent files by mtime
    recent = []
    try:
        files = [p for p in root.rglob("*")
                 if p.is_file() and not any(part.startswith(".") for part in p.relative_to(root).parts)]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        recent = [str(p.relative_to(root)) for p in files[:8]]
    except OSError:
        pass
    ctx["recent_files"] = recent
    return ctx


def detect_gaps(instruction: str, ctx: dict) -> list[dict]:
    """What is genuinely missing to act on this instruction? Returns gap dicts."""
    gaps = []
    low = (instruction or "").lower()
    words = (instruction or "").split()
    # target: does the instruction name a file/area, or do recent files give one?
    has_target = any(w in low for w in ("file", ".py", ".js", ".ts", ".md", ".json",
                                       ".rs", ".go", ".java", "in ", "at ", "under "))
    if not has_target and not ctx.get("recent_files"):
        gaps.append({"kind": "target", "question": "which file or area should I touch?"})
    # success criteria
    has_success = any(w in low for w in ("test", "verify", "check", "pass", "work",
                                         "fix", "make", "add", "remove", "update"))
    if not has_success:
        gaps.append({"kind": "success",
                     "question": "how will we know it's done — a test, a check, or 'it runs'?"})
    # scope
    if len(words) < 4:
        gaps.append({"kind": "scope",
                     "question": "is this a small tweak or a bigger change?"})
    # ambiguity markers
    if any(w in low for w in ("this", "that", "it", "stuff", "thing")) and len(words) < 6:
        gaps.append({"kind": "referent",
                     "question": "what does 'this/that/it' point at, specifically?"})
    return gaps


def render_context(ctx: dict) -> str:
    lines = [f"cwd: {ctx.get('cwd')}"]
    if ctx.get("readme_head"):
        lines.append("README (head): " + " | ".join(ctx["readme_head"][:2]))
    if ctx.get("package"):
        p = ctx["package"]
        lines.append(f"package: {p.get('name')} | scripts: {', '.join(p.get('scripts', []))}")
        if p.get("deps"):
            lines.append("deps: " + ", ".join(p["deps"][:10]))
    if ctx.get("python_project"):
        lines.append(f"python project: {ctx['python_project']}")
    if ctx.get("git_log"):
        lines.append("recent commits: " + "; ".join(ctx["git_log"][:3]))
    if ctx.get("git_status"):
        lines.append("uncommitted: " + ", ".join(ctx["git_status"][:5]))
    if ctx.get("recent_files"):
        lines.append("recently touched: " + ", ".join(ctx["recent_files"][:6]))
    if ctx.get("tree"):
        lines.append("tree: " + ", ".join(ctx["tree"][:15]))
    return "\n".join(lines)
