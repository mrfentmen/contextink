"""Contextink: the agent that gets the context so you don't have to explain it.

The pain point: you say "do this" and the AI needs you to spell out everything. Contextink
scans the environment (repo, git, recent files, manifest) to acquire what's missing, and
only asks the minimal set of high-information-gain questions when acquisition fails.

    acquire <instruction>   (or just type the instruction)  -> scan + plan or ask
    status                  -> what context was acquired, what gaps remain
    ask <sibling>: question -> forward to a sibling over ACP, cited

The acquired context is the whole contract: it is printed, not hidden, and nothing is
invented. The vendored lockwork (kit, federation) carries its credit lines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for path in (str(REPO / "kit"), str(Path(__file__).resolve().parent)):
    if path not in sys.path:
        sys.path.insert(0, path)

from acp_kit import STOP_END_TURN, STOP_REFUSAL, AcpAgent, SessionContext, prompt_text  # noqa: E402

import context  # noqa: E402
import questions  # noqa: E402
import federation as fed  # noqa: E402

WELCOME = (
    "I am Contextink. You say 'do this'; I get the context so you don't have to explain it:\n"
    "  - <instruction>            (scan the repo/env, acquire context, plan or ask minimally)\n"
    "  - status                    (what was acquired, what gaps remain)\n"
    "  - ask tides: what are the tides in Boston?   (forward to a sibling, cited)\n"
    "Rules: acquire first, ask only what's genuinely missing, ranked by information gain."
)

_STATUS = re.compile(r"^\s*(status|what context|show context)\b", re.I)
_HELP = re.compile(r"^\s*(help|what can you do)\b", re.I)
_ASK = re.compile(r"^\s*ask\s+(.+)$", re.I | re.S)


def route(text: str) -> tuple[str, dict]:
    stripped = str(text or "").strip()
    if not stripped or _HELP.search(stripped):
        return "help", {}
    if _STATUS.search(stripped):
        return "status", {}
    pair = fed.ask_pair(stripped)
    if pair:
        return "ask", {"agent": pair[0], "question": pair[1]}
    m = _ASK.search(stripped)
    if m:
        return "ask", {"question": m.group(1).strip()}
    return "acquire", {"instruction": stripped}


class ContextinkAgent(AcpAgent):
    name = "contextink"
    title = "Contextink - acquires context from minimal info so you don't have to explain it"
    version = "1.0.0"

    def new_session(self, session) -> dict:
        session.remember("agent", "Contextink session opened.")
        return {}

    def prompt(self, ctx: SessionContext, prompt: list[dict]) -> str:
        text = prompt_text(prompt)
        skill, params = route(text)
        cwd = Path(ctx.session.cwd or ".")
        ctx.plan([
            (f"Take the prompt as Contextink ({skill})", "high"),
            ("Acquire context from the environment, no inventing", "high"),
            ("Plan or ask the minimal questions", "medium"),
        ])

        if skill == "help":
            ctx.stream_text(WELCOME + "\n")
            return STOP_END_TURN

        if skill == "status":
            acquired = getattr(self, "_last_context", None)
            if not acquired:
                ctx.stream_text("nothing acquired yet. give me an instruction first.\n")
                return STOP_END_TURN
            ctx.stream_text("acquired context:\n" + context.render_context(acquired) + "\n")
            return STOP_END_TURN

        if skill == "ask":
            if "agent" in params:
                call = "call_sibling"
                ctx.tool_call(call, f"Ask the {params['agent']} sibling", kind="run",
                              name="contextink-ask", raw_input=dict(params))
                ctx.tool_call_update(call, status="in_progress")
                try:
                    row = fed.run_sibling(params["agent"], params["question"])
                except fed.SiblingError as exc:
                    ctx.tool_call_update(call, status="failed",
                                         content=ctx.text_content(str(exc)[:200]))
                    ctx.message(f"the sibling missed: {exc}")
                    return STOP_END_TURN
                if not row.ok or not (row.text or "").strip():
                    ctx.tool_call_update(call, status="failed",
                                         content=ctx.text_content(row.error or "refused"))
                    ctx.message(f"the sibling missed: {row.error or 'refused'}")
                    return STOP_END_TURN
                ctx.tool_call_update(call, status="completed",
                                     content=ctx.text_content(
                                         f"{row.agent}: stopReason={row.stop_reason or 'end-turn'}"))
                ctx.stream_text((row.text or "").rstrip() + "\n\n"
                                f"Source: the {row.agent} sibling over ACP.\n")
                return STOP_END_TURN
            ctx.stream_text("no sibling named. try: ask <name>: <question>\n")
            return STOP_END_TURN

        # acquire
        instruction = params["instruction"]
        acquired = context.scan_repo(str(cwd))
        self._last_context = acquired
        gaps = context.detect_gaps(instruction, acquired)
        qs = questions.minimal_questions(gaps, max_n=3)
        ctx.stream_text("acquired context:\n" + context.render_context(acquired) + "\n\n")
        if qs:
            ctx.stream_text("I still need " + str(len(qs)) + " thing(s) to act safely:\n")
            for q in qs:
                ctx.stream_text(f"  - {q}\n")
            ctx.stream_text("(answer these and I'll plan; or say 'just do it' and I'll "
                           "proceed with best guess, flagged.)\n")
            return STOP_END_TURN
        # no gaps: produce a plan from acquired context
        plan_lines = ["no gaps detected - plan from acquired context:"]
        if acquired.get("recent_files"):
            plan_lines.append(f"  - focus on recently touched: {', '.join(acquired['recent_files'][:3])}")
        if acquired.get("git_status"):
            plan_lines.append(f"  - there are {len(acquired['git_status'])} uncommitted change(s) to be aware of")
        if acquired.get("package"):
            plan_lines.append(f"  - project: {acquired['package'].get('name')} "
                              f"(scripts: {', '.join(acquired['package'].get('scripts', []))})")
        if acquired.get("python_project"):
            plan_lines.append(f"  - python project ({acquired['python_project']})")
        plan_lines.append("  - instruction: " + instruction)
        ctx.stream_text("\n".join(plan_lines) + "\n")
        return STOP_END_TURN

    def on_cancel(self, session) -> None:
        return None


def main(argv=None) -> int:
    import logging
    logging.basicConfig(level="INFO", stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        ContextinkAgent().run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
