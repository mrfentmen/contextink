"""Tests for Contextink: context acquisition, gap detection, routing, federation.

    python3 agents/contextink/tests/test_agent.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DIR = Path(__file__).resolve().parent
AGENT_DIR = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
for path in (str(REPO / "kit"), str(AGENT_DIR), str(DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import agent  # noqa: E402
import context  # noqa: E402
import questions  # noqa: E402
import federation as fed  # noqa: E402

FAKE_SIBLING = r"""
import sys, json
def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()
def recv():
    return json.loads(sys.stdin.readline())
req = recv()
send({"jsonrpc":"2.0","id":req["id"],"result":{"protocolVersion":1,"agentCapabilities":{},
      "authMethods":[],"agentInfo":{"name":"fake-sibling","title":"Fake","version":"1.0.0"}}})
while True:
    try:
        req = recv()
    except Exception:
        break
    method = req.get("method", "")
    if method == "session/new":
        send({"jsonrpc":"2.0","id":req["id"],"result":{"sessionId":"fake-session","modes":[]}})
    elif method == "session/prompt":
        text = "".join(b.get("text","") for b in req.get("params",{}).get("prompt",[]))
        send({"jsonrpc":"2.0","method":"session/update","params":{"update":{
            "sessionUpdate":"agent_message_chunk","content":{"type":"text",
            "text":"FAKE ANSWER for %r\n" % text}}}})
        send({"jsonrpc":"2.0","id":req["id"],"result":{"stopReason":"end-turn"}})
    elif method in ("session/cancel", "session/load"):
        continue
    else:
        send({"jsonrpc":"2.0","id":req.get("id"),"error":{"code":-32601,"message":"unhandled"}})
"""


class ScanTests(unittest.TestCase):
    def test_scan_reads_readme_package_and_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# My Project\nDoes things.\n")
            (root / "package.json").write_text(json.dumps({
                "name": "myproj", "scripts": {"test": "jest", "build": "tsc"},
                "dependencies": {"react": "18.0.0"}}))
            (root / "src").mkdir()
            (root / "src" / "index.js").write_text("console.log('hi')")
            ctx = context.scan_repo(str(root))
            self.assertIn("README (head): # My Project", context.render_context(ctx))
            self.assertEqual(ctx["package"]["name"], "myproj")
            self.assertIn("test", ctx["package"]["scripts"])
            self.assertIn("src/", ctx["tree"])
            self.assertIn("index.js", "\n".join(ctx["tree"]))

    def test_scan_reads_git_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
            (root / "a.txt").write_text("hi")
            subprocess.run(["git", "add", "a.txt"], cwd=str(root), check=True)
            subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t",
                            "commit", "-q", "-m", "first commit"], cwd=str(root), check=True)
            (root / "b.txt").write_text("bye")
            ctx = context.scan_repo(str(root))
            self.assertTrue(any("first commit" in c for c in ctx.get("git_log", [])))
            self.assertTrue(any("b.txt" in s for s in ctx.get("git_status", [])))

    def test_scan_handles_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = context.scan_repo(str(tmp))
            self.assertIn("cwd:", context.render_context(ctx))


class GapTests(unittest.TestCase):
    def test_terse_instruction_has_gaps(self):
        ctx = {"recent_files": []}
        gaps = context.detect_gaps("do this", ctx)
        kinds = [g["kind"] for g in gaps]
        self.assertIn("target", kinds)
        self.assertIn("success", kinds)
        self.assertIn("scope", kinds)
        self.assertIn("referent", kinds)

    def test_specific_instruction_has_fewer_gaps(self):
        ctx = {"recent_files": ["src/index.js"]}
        gaps = context.detect_gaps("fix the null check in src/index.js and run the tests", ctx)
        kinds = [g["kind"] for g in gaps]
        self.assertNotIn("target", kinds)
        self.assertNotIn("success", kinds)

    def test_questions_ranked_by_info_gain(self):
        gaps = [{"kind": "scope", "question": "scope?"}, {"kind": "target", "question": "target?"},
                {"kind": "success", "question": "success?"}]
        qs = questions.minimal_questions(gaps, max_n=2)
        self.assertEqual(qs[0], "target?")
        self.assertEqual(len(qs), 2)


class RouteTests(unittest.TestCase):
    def test_help_and_status(self):
        self.assertEqual(agent.route("help")[0], "help")
        self.assertEqual(agent.route("")[0], "help")
        self.assertEqual(agent.route("status")[0], "status")
        self.assertEqual(agent.route("what context")[0], "status")

    def test_bare_instruction_acquires(self):
        self.assertEqual(agent.route("fix the login bug"), ("acquire", {"instruction": "fix the login bug"}))

    def test_ask_sibling(self):
        self.assertEqual(agent.route("ask tides: what are the tides?"),
                         ("ask", {"agent": "tides", "question": "what are the tides?"}))


class ClientChildTests(unittest.TestCase):
    def _client(self, tmp):
        from acp_kit import AcpClient
        return AcpClient(command=[sys.executable, str(AGENT_DIR / "agent.py")],
                         permission="allow-once", fs_root=tmp, stderr=subprocess.DEVNULL)

    def test_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("help", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("Contextink", turn["text"])
                self.assertIn("acquire", turn["text"].lower())

    def test_acquire_on_real_repo_asks_minimal_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Proj\n")
            # terse instruction with no target/success/scope
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("do this", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("acquired context:", turn["text"])
                self.assertIn("I still need", turn["text"])
                # should ask at most 3 questions
                self.assertLessEqual(turn["text"].count("\n  - "), 3)

    def test_acquire_with_specific_instruction_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Proj\n")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print('hi')")
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                turn = c.prompt("fix the bug in src/main.py and run the tests", session_id=sid)
                self.assertEqual(turn["stopReason"], "end_turn")
                self.assertIn("no gaps detected", turn["text"])
                self.assertIn("src/main.py", turn["text"])

    def test_status_after_acquire(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("# Proj\n")
            c = self._client(tmp)
            with c:
                c.initialize()
                sid = c.new_session(cwd=tmp)
                c.prompt("do this", session_id=sid)
                turn = c.prompt("status", session_id=sid)
                self.assertIn("acquired context:", turn["text"])


class FederationChildTests(unittest.TestCase):
    def _with_fake(self, tmp):
        old = os.environ.get("POLYMATH_FAKE_SIBLING")
        os.environ["POLYMATH_FAKE_SIBLING"] = str(Path(tmp) / "fake_sibling.py")
        (Path(tmp) / "fake_sibling.py").write_text(FAKE_SIBLING)
        return old

    def _without_fake(self, old):
        if old is None:
            os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        else:
            os.environ["POLYMATH_FAKE_SIBLING"] = old

    def test_real_child_spawn_and_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = self._with_fake(tmp)
            try:
                turn = fed.run_sibling("air", "Denver")
            finally:
                self._without_fake(old)
            self.assertTrue(turn.ok, turn.error)
            self.assertIn("FAKE ANSWER", turn.text)

    def test_unconfigured_home_is_honest(self):
        old = os.environ.pop("POLYMATH_FAKE_SIBLING", None)
        home = os.environ.pop("AWESOME_SERVERS_HOME", None)
        try:
            turn = fed.run_sibling("air", "Denver")
        finally:
            if old is not None:
                os.environ["POLYMATH_FAKE_SIBLING"] = old
            if home is not None:
                os.environ["AWESOME_SERVERS_HOME"] = home
        self.assertFalse(turn.ok)
        self.assertIn("AWESOME_SERVERS_HOME", turn.error)


if __name__ == "__main__":
    unittest.main()
