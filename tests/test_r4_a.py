"""Package A (CB-212): continuity between chats, and the state a chat leaves.

Every test here failed on the code before the package and names the audit
finding(s) it pins. Secret-shaped samples are built by concatenation so this
file passes the secret scan itself.
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import common as c, contract, detect, gate, req, state  # noqa: E402

T0, T1, T2 = "2026-11-08T09:00:00Z", "2026-11-08T10:00:00Z", "2026-11-08T10:05:00Z"


def sh(cwd, *args):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def git(cwd, *args) -> str:
    return sh(cwd, "git", *args).stdout.strip()


def commit_all(path: Path, msg="c") -> None:
    sh(path, "git", "add", "-A")
    sh(path, "git", "commit", "-q", "-m", msg)


def cli(*argv, brain_root=None):
    """Run a state/detect command in-process through its real argument parser."""
    parser = argparse.ArgumentParser(prog="brain")
    sub = parser.add_subparsers(dest="command")
    state.register(sub)
    detect.register(sub)
    args = parser.parse_args(list(argv))
    if brain_root is not None:
        args.brain_root = brain_root
    out = io.StringIO()
    with redirect_stdout(out):
        rc = args.func(args)
    return rc, out.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve()
        self._env = dict(os.environ)
        for k in ("BRAIN_PROJECT", "BRAIN_NO_NETWORK", "BRAIN_NO_PUSH", "BRAIN_TRANSCRIPT", "CLAUDE_CODE_SESSION_ID"):
            os.environ.pop(k, None)
        os.environ.update(BRAIN_SESSION_ID="chat-one", BRAIN_NOW=T0, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                          GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                          GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
        # A stand-in brain: nothing in these tests may read or write the real one.
        self.brain = self.stand_in_brain(self.ws / "Claude-Brain")
        self._root = c.BRAIN_ROOT
        c.BRAIN_ROOT = self.brain

    def tearDown(self):
        c.BRAIN_ROOT = self._root
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def stand_in_brain(self, path: Path) -> Path:
        (path / "memory").mkdir(parents=True)
        c.write_json(path / "memory" / "models.json", {"verified_on": "2026-11-08", "recheck_days": 90, "models": {}})
        return path

    def project(self, name="proj", branch="work", rule=None, push=("main",)) -> Path:
        """A managed project in its own git repository with a local bare remote.
        ``push`` names the remote branches that receive the first commit."""
        self.remote = self.ws / f".{name}.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        p = self.ws / name
        p.mkdir()
        sh(p, "git", "init", "-q", "-b", branch)
        sh(p, "git", "remote", "add", "origin", str(self.remote))
        (p / "README.md").write_text("# x\n")
        contract.init(p, name.title(), "software", {"release": {"rule": rule}} if rule else None)
        commit_all(p, "contract")
        for b in push:
            sh(p, "git", "push", "-q", "origin", f"HEAD:refs/heads/{b}")
        sh(p, "git", "fetch", "-q", "origin")
        return p

    def new_chat(self, branch="claude/two", base="main") -> tuple[Path, Path]:
        """What a new chat gets: a fresh clone of the default branch, on a new
        branch, beside a fresh copy of the brain."""
        home = self.ws / "chat2"
        clone = home / "proj"
        sh(self.ws, "git", "clone", "-q", "-b", base, str(self.remote), str(clone))
        sh(clone, "git", "switch", "-q", "-c", branch)
        brain2 = home / "Claude-Brain"
        if not brain2.exists():
            self.stand_in_brain(brain2)
        os.environ.update(BRAIN_SESSION_ID="chat-two", BRAIN_NOW=T2)
        c.BRAIN_ROOT = brain2
        return clone, brain2

    def remote_file(self, branch: str, rel: str) -> str:
        return sh(self.remote, "git", "show", f"{branch}:{rel}").stdout

    def remote_head(self, branch: str) -> str:
        return git(self.remote, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")


# ---------------------------------------------------------------- continuity
class ContinuityTests(Base):
    def session_one(self, p: Path, branch="claude/one") -> None:
        sh(p, "git", "switch", "-q", "-c", branch)
        (p / "cart.py").write_text("x = 1\n")
        commit_all(p, "feat: cart totals")
        os.environ["BRAIN_NOW"] = T1
        state.checkpoint(p, stage="build", done="CB-1 cart totals", item="CB-2 checkout page", note="half built in checkout.py")

    def test_a_new_chat_is_told_where_the_last_checkpoint_is_and_adopts_it(self):
        """core-01, owner-docs-01, e2e-trial-02: a fresh clone of main on a new
        branch must see the state the last chat pushed to its own branch."""
        p = self.project()
        self.session_one(p)
        self.assertEqual(state.push_bookkeeping(p).status, "pushed")
        problems, _ = state.handover(p, brain_root=self.brain)
        self.assertEqual(problems, [])
        clone, brain2 = self.new_chat()
        found = state.newer_checkpoints(clone)
        self.assertEqual([(f["ref"], f["item"]) for f in found], [("origin/claude/one", "CB-2 checkout page")])
        lines = detect.boot_lines("Continue", brain2)
        blob = "\n".join(lines)
        self.assertIn("newer checkpoint on origin/claude/one", blob)
        self.assertIn("CB-2 checkout page", blob)
        self.assertIn("brain resume --adopt", blob)
        self.assertLessEqual(len(blob.encode()), 1500)
        self.assertFalse((clone / ".brain" / "log" / "open-session.json").exists(),
                         "boot must not write into a checkout it is about to fast-forward")
        rc, out = cli("resume", "--adopt", "--project", str(clone))
        self.assertEqual(rc, 0, out)
        self.assertIn("adopted origin/claude/one", out)
        self.assertIn("CB-2 checkout page", out)
        self.assertEqual(state.read_state(clone)["item"], "CB-2 checkout page")
        self.assertEqual(git(clone, "rev-parse", "--abbrev-ref", "HEAD"), "claude/two", "the new chat keeps its own branch")
        blob = "\n".join(detect.boot_lines("Continue", brain2))
        self.assertNotIn("newer checkpoint", blob)
        self.assertIn("item: CB-2 checkout page", blob)
        self.assertNotIn("another session", blob, "a clean handover releases the lease (core-12)")

    def test_state_on_a_work_branch_is_found_when_main_has_no_contract(self):
        """e2e-trial-02: main still holds only the first commit; boot must name
        the branch with the state and must not tell the lead to run init."""
        self.remote = self.ws / ".proj.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        p = self.ws / "proj"
        p.mkdir()
        sh(p, "git", "init", "-q", "-b", "main")
        sh(p, "git", "remote", "add", "origin", str(self.remote))
        (p / "README.md").write_text("# x\n")
        commit_all(p, "first")
        sh(p, "git", "push", "-q", "-u", "origin", "main")
        sh(p, "git", "switch", "-q", "-c", "work")
        contract.init(p, "Proj", "software")
        commit_all(p, "contract")
        os.environ["BRAIN_NOW"] = T1
        state.checkpoint(p, item="P2 monthly summary", done="P1 add form")
        self.assertEqual(state.push_bookkeeping(p).status, "pushed")
        clone, brain2 = self.new_chat()
        blob = "\n".join(detect.boot_lines("Continúa", brain2))
        self.assertIn("origin/work", blob)
        self.assertIn("P2 monthly summary", blob)
        self.assertNotIn("brain init", blob)
        rc, out = cli("resume", "--adopt")     # no --project: the checkout is not managed yet
        self.assertEqual(rc, 0, out)
        self.assertTrue(c.is_managed(clone))
        self.assertEqual(state.read_state(clone)["item"], "P2 monthly summary")

    def test_boot_fetches_branch_heads_once_and_stays_silent_when_it_cannot(self):
        """core-01 (decision D-17): one bounded fetch, silence on failure, no
        network use when BRAIN_NO_NETWORK is set or there is no remote."""
        p = self.project()
        clone, _ = self.new_chat()           # cloned before session one pushed anything
        os.environ.update(BRAIN_SESSION_ID="chat-one")
        self.session_one(p)
        state.push_bookkeeping(p)
        os.environ.update(BRAIN_SESSION_ID="chat-two", BRAIN_NOW=T2)
        os.environ["BRAIN_NO_NETWORK"] = "1"
        self.assertEqual(state.newer_checkpoints(clone), [], "no fetch when network use is switched off")
        os.environ.pop("BRAIN_NO_NETWORK")
        calls = []
        real = subprocess.run

        def spy(cmd, *a, **k):
            calls.append(list(cmd))
            return real(cmd, *a, **k)
        with mock.patch.object(state.subprocess, "run", spy):
            found = state.newer_checkpoints(clone)
        self.assertEqual([f["branch"] for f in found], ["claude/one"])
        fetches = [x for x in calls if "fetch" in x]
        self.assertEqual(len(fetches), 1)
        self.assertNotIn("--depth", " ".join(fetches[0]))
        self.assertTrue(any(a.endswith("refs/heads/*:refs/remotes/origin/*") for a in fetches[0]), fetches[0])
        sh(clone, "git", "remote", "set-url", "origin", str(self.ws / "gone.git"))
        self.assertIsInstance(state.newer_checkpoints(clone), list)   # a failed fetch is silence, not an error
        sh(clone, "git", "remote", "remove", "origin")
        self.assertEqual(state.newer_checkpoints(clone), [])

    def test_adopt_is_fast_forward_only_and_a_refusal_gives_the_next_step(self):
        """core-01 (decision D-17): adoption can never lose work."""
        p = self.project()
        self.session_one(p)
        state.push_bookkeeping(p)
        clone, _ = self.new_chat()
        (clone / "mine.py").write_text("y = 2\n")
        commit_all(clone, "work the new chat already did")
        before = git(clone, "rev-parse", "HEAD")
        ok, line = state.adopt_checkpoint(clone)
        self.assertFalse(ok)
        self.assertIn("git merge origin/claude/one", line)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), before)
        rc, out = cli("resume", "--adopt", "--project", str(clone))
        self.assertEqual(rc, 1)
        self.assertLessEqual(len(out.strip().splitlines()), 2)
        rc, out = cli("resume", "--adopt", "nowhere", "--project", str(clone))
        self.assertEqual(rc, 1)
        self.assertIn("nowhere", out)

    def test_adopt_with_nothing_newer_says_so_and_resumes(self):
        p = self.project()
        state.checkpoint(p, item="T-1")
        rc, out = cli("resume", "--adopt", "--project", str(p))
        self.assertEqual(rc, 0)
        self.assertIn("nothing newer", out)
        self.assertIn("T-1", out)

    def test_handover_names_the_branch_in_the_line_to_paste(self):
        """e2e-trial-02, core-01: the line the owner pastes carries the branch."""
        p = self.project()
        self.session_one(p)
        commit_all(p, "x")
        rc, out = cli("handover", "--project", str(p), brain_root=self.brain)
        self.assertEqual(rc, 0, out)
        last = out.strip().splitlines()[-1]
        self.assertIn("Continue (branch claude/one)", last)
        self.assertIn("claude/one", (p / ".brain" / "HANDOVER.md").read_text())

    def test_a_checkpoint_on_an_unreleased_release_branch_still_reaches_the_remote(self):
        """e2e-trial-01, core-08: on the release branch the state goes to a side
        branch, never to the release branch, and a new chat finds it there."""
        p = self.project(branch="main", rule="main-on-green", push=())
        sh(p, "git", "commit", "-q", "--allow-empty", "-m", "x")
        os.environ["BRAIN_NOW"] = T1
        rc, out = cli("checkpoint", "--item", "P1 first screen", "--push", "--project", str(p))
        self.assertEqual(rc, 0, out)
        self.assertIn("origin/brain/wip", out)
        self.assertEqual(self.remote_head("main"), "", "the release branch moves only through brain release")
        self.assertIn("P1 first screen", self.remote_file("brain/wip", ".brain/STATE.md"))
        self.assertLessEqual(len(out.strip().splitlines()), 3)
        # a later checkpoint from the same line of work fast-forwards the side branch
        (p / "a.py").write_text("a = 1\n")
        commit_all(p, "feat")
        res = state.push_bookkeeping(p)
        self.assertEqual((res.status, res.branch), ("side", "brain/wip"))
        self.assertEqual(self.remote_head("brain/wip"), git(p, "rev-parse", "HEAD"))
        problems, _ = state.handover(p, brain_root=self.brain)
        self.assertEqual(problems, [], "work saved on the side branch is on the remote: handover is ready")
        rc, out = cli("handover", "--project", str(p), brain_root=self.brain)
        self.assertIn("Continue (branch brain/wip)", out)

    def test_a_side_branch_that_cannot_fast_forward_gets_a_session_name_never_a_forced_push(self):
        """e2e-trial-01: plain pushes only."""
        p = self.project(branch="main", rule="main-on-green", push=())
        other = self.ws / "other"
        sh(self.ws, "git", "init", "-q", "-b", "x", str(other))
        (other / "f").write_text("1")
        commit_all(other, "unrelated")
        sh(other, "git", "push", "-q", str(self.remote), "HEAD:refs/heads/brain/wip")
        taken = self.remote_head("brain/wip")
        state.checkpoint(p, item="P1")
        calls = []
        real = subprocess.run

        def spy(cmd, *a, **k):
            calls.append(list(cmd))
            return real(cmd, *a, **k)
        with mock.patch.object(state.subprocess, "run", spy):
            res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "side")
        self.assertTrue(res.branch.startswith("brain/wip-"), res.branch)
        self.assertEqual(self.remote_head("brain/wip"), taken)
        pushes = [x for x in calls if "push" in x]
        self.assertTrue(pushes)
        for x in pushes:
            self.assertFalse(any(a in ("-f", "--force", "--force-with-lease") or a.startswith("+") for a in x), x)

    def test_checkpoint_push_exit_code_says_whether_the_remote_has_the_state(self):
        """core-08, e2e-trial-01: exit 0 only when the state is on the remote;
        every failure is one line with the next step."""
        p = self.project()
        rc, out = cli("checkpoint", "--item", "x", "--push", "--project", str(p))
        self.assertEqual(rc, 0, out)
        self.assertIn("checkpoint pushed to work", out)
        # the remote moved on: rejected, with the command that fixes it
        other = self.ws / "other"
        sh(self.ws, "git", "clone", "-q", "-b", "work", str(self.remote), str(other))
        (other / "z").write_text("1")
        commit_all(other, "from elsewhere")
        sh(other, "git", "push", "-q", "origin", "work")
        rc, out = cli("checkpoint", "--item", "y", "--push", "--project", str(p))
        self.assertEqual(rc, 1)
        self.assertIn("PUSH FAILED", out)
        self.assertIn("git pull --rebase origin work", out)
        self.assertNotIn(str(self.remote), out, "the line is spent on the fix, not on the address")
        # detached HEAD
        sh(p, "git", "checkout", "-q", "--detach")
        rc, out = cli("checkpoint", "--item", "y", "--push", "--project", str(p))
        self.assertEqual(rc, 1)
        self.assertIn("git switch -c", out)
        sh(p, "git", "switch", "-q", "work")
        # no remote
        sh(p, "git", "remote", "remove", "origin")
        rc, out = cli("checkpoint", "--item", "z", "--push", "--project", str(p))
        self.assertEqual(rc, 1)
        self.assertIn("NOT PUSHED", out)
        self.assertIn("no remote", out)
        # not a repository at all
        plain = self.ws / "plain"
        plain.mkdir()
        contract.init(plain, "Plain", "knowledge")
        rc, out = cli("checkpoint", "--item", "z", "--push", "--project", str(plain))
        self.assertEqual(rc, 1)
        self.assertIn("not a git repository", out)

    def test_a_slow_or_refused_push_is_one_line_not_a_traceback(self):
        """core-08: a push over the time limit, and a commit git refuses."""
        p = self.project()
        state.checkpoint(p, item="x")
        real = subprocess.run

        def slow(cmd, *a, **k):
            if "push" in cmd:
                raise subprocess.TimeoutExpired(cmd, 120)
            return real(cmd, *a, **k)
        with mock.patch.object(state.subprocess, "run", slow):
            res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "failed")
        self.assertIn("PUSH FAILED", res)
        self.assertIn("again", res)
        # no author identity: the two commands that fix it
        for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
            os.environ.pop(k)
        sh(p, "git", "config", "user.useConfigOnly", "true")
        state.checkpoint(p, item="y")
        res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "failed")
        self.assertIn("git config user.email", res)

    def test_a_missing_owner_file_does_not_block_the_checkpoint_commit(self):
        """core-08: an unmatched pathspec used to make git add nothing at all."""
        p = self.project()
        sh(p, "git", "rm", "-q", "NEEDS_YOU.md")
        commit_all(p, "no owner file")
        os.environ["BRAIN_NOW"] = T1
        state.checkpoint(p, item="T-2 still saved")
        res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "pushed", res)
        self.assertIn("T-2 still saved", self.remote_file("work", ".brain/STATE.md"))

    def test_handover_is_not_ready_without_a_git_repository(self):
        """core-08: nothing can be pushed from a folder that is not a repository."""
        plain = self.ws / "plain"
        plain.mkdir()
        contract.init(plain, "Plain", "knowledge")
        problems, _ = state.handover(plain, brain_root=self.brain)
        self.assertTrue(any("not a git repository" in x for x in problems), problems)
        rc, out = cli("handover", "--project", str(plain), brain_root=self.brain)
        self.assertEqual(rc, 1)
        self.assertNotIn("ready:", out)


# ---------------------------------------------------------------- what a checkpoint may commit and push
class BookkeepingTests(Base):
    def test_bookkeeping_is_an_allow_list_not_the_whole_folder(self):
        """quality-path-11, redteam-06, core-04 (decision 3)."""
        for path in ("STATUS.md", "NEEDS_YOU.md", ".brain/STATE.md", ".brain/PLAN.md", ".brain/DECISIONS.md",
                     ".brain/REQUIREMENTS.md", ".brain/requirements.jsonl", ".brain/CHECKLIST.md", ".brain/HANDOVER.md",
                     ".brain/log/gates.jsonl", ".brain/log/2026-11-08-s.json", ".brain/memory/lessons.jsonl"):
            self.assertTrue(state.is_bookkeeping(path), path)
        for path in (".brain/project.json", ".brain/ext/tool.sh", ".brain/tests/check.sh", ".brain/app.py",
                     ".brain/", ".brain", "src/app.ts", "CLAUDE.md", ".brain/logs.py", "STATUS.md.bak"):
            self.assertFalse(state.is_bookkeeping(path), path)

    def test_checkpoint_never_commits_the_manifest_or_project_tools(self):
        """core-04, quality-path-11: they change what green means, so they are
        left for their author, and the count in the message is true."""
        p = self.project()
        sh(p, "git", "push", "-q", "-u", "origin", "work")
        m = c.load_manifest(p)
        m["gates"] = [{"id": "checks", "kind": "command", "command": "true"}]
        c.write_json(p / ".brain" / "project.json", m)
        (p / ".brain" / "ext" / "tool.sh").write_text("echo hi\n")
        (p / "app.py").write_text("x = 1\n")
        state.checkpoint(p, item="x")
        res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "pushed", res)
        self.assertIn("3 other uncommitted change(s)", res)
        self.assertIn(".brain/project.json", res)
        left = sh(p, "git", "status", "--porcelain", "--untracked-files=all").stdout
        for rel in (".brain/project.json", ".brain/ext/tool.sh", "app.py"):
            self.assertIn(rel, left)
        self.assertEqual(self.remote_file("work", ".brain/ext/tool.sh"), "")
        self.assertNotIn('"true"', self.remote_file("work", ".brain/project.json"))
        self.assertIn("item: x", self.remote_file("work", ".brain/STATE.md"))

    def test_first_checkpoint_after_init_says_the_contract_is_not_committed(self):
        """core-04, e2e-trial-01: a pushed state without its manifest cannot be
        resumed, so the line names the files and the commit to make."""
        self.remote = self.ws / ".fresh.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.remote))
        p = self.ws / "fresh"
        p.mkdir()
        sh(p, "git", "init", "-q", "-b", "work")
        sh(p, "git", "remote", "add", "origin", str(self.remote))
        contract.init(p, "Fresh", "software")
        state.checkpoint(p, item="P1")
        res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "pushed", res)
        self.assertIn(".brain/project.json", res)
        self.assertIn("git add", res)
        self.assertEqual(self.remote_file("work", ".brain/project.json"), "")
        self.assertIn("P1", self.remote_file("work", ".brain/STATE.md"))
        problems, _ = state.handover(p, brain_root=self.brain)
        self.assertTrue(any("CLAUDE.md" in x or ".brain/project.json" in x for x in problems),
                        f"handover names the uncommitted files: {problems}")

    def released_on_main(self, rule: str, name="proj") -> Path:
        p = self.project(name=name, branch="main", rule=rule, push=("main",))
        sh(p, "git", "branch", "-q", "--set-upstream-to=origin/main")
        return p

    def test_checkpoint_cannot_push_work_to_the_release_branch_under_the_pr_rule(self):
        """core-04, quality-path-12, redteam-06: rule pr is guarded like main-on-green."""
        p = self.released_on_main("pr")
        before = self.remote_head("main")
        (p / "feature.py").write_text("x = 1\n")
        commit_all(p, "feat: ungated work")
        state.checkpoint(p, item="x")
        res = state.push_bookkeeping(p)
        self.assertEqual(self.remote_head("main"), before)
        self.assertEqual(res.status, "side", res)
        self.assertIn("pull request", res)
        self.assertEqual(self.remote_file("main", "feature.py"), "")

    def test_bookkeeping_alone_still_reaches_the_release_branch(self):
        """quality-path-12: the guard is about work, not about state."""
        for rule in ("pr", "main-on-green"):
            with self.subTest(rule=rule):
                p = self.released_on_main(rule, name=f"p-{rule}")
                state.checkpoint(p, item=f"T-9 {rule}")
                res = state.push_bookkeeping(p)
                self.assertEqual((res.status, res.branch), ("pushed", "main"), res)
                self.assertIn(f"T-9 {rule}", self.remote_file("main", ".brain/STATE.md"))

    def test_a_file_moved_into_the_bookkeeping_folders_is_still_work(self):
        """redteam-06, quality-path-11: rename detection must not hide a change
        from the release-branch check."""
        p = self.released_on_main("main-on-green")
        (p / "app.py").write_text("print('the app')\n" * 5)
        commit_all(p, "app")
        sh(p, "git", "push", "-q", "origin", "main")
        before = self.remote_head("main")
        sh(p, "git", "mv", "app.py", ".brain/log/app.py")
        commit_all(p, "tidy")
        self.assertEqual(git(p, "diff", "--name-only", "origin/main", "HEAD"), ".brain/log/app.py",
                         "git's rename detection shows only the bookkeeping side")
        state.checkpoint(p, done="tidy")
        res = state.push_bookkeeping(p)
        self.assertEqual(self.remote_head("main"), before, res)
        self.assertEqual(res.status, "side")
        self.assertIn("app.py", state.release_branch_block(p, "main"))


# ---------------------------------------------------------------- the brain's own records
class BrainRecordTests(Base):
    def brain_repo(self, origin: str | None = None) -> Path:
        b = self.ws / "B" / "Claude-Brain"
        b.mkdir(parents=True)
        self.bremote = self.ws / ".brain-remote.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.bremote))
        sh(b, "git", "init", "-q", "-b", "work")
        sh(b, "git", "remote", "add", "origin", origin or str(self.bremote))
        (b / "CLAUDE.md").write_text("kernel\n")
        commit_all(b, "init")
        (b / "learning" / "inbox").mkdir(parents=True)
        (b / "learning" / "radar").mkdir(parents=True)
        return b

    def record(self, b: Path, name: str, session: str, **extra) -> Path:
        f = b / "learning" / "inbox" / name
        c.append_jsonl(f, {"kind": "ledger", "session": session, "at": T0, **extra})
        return f

    def test_only_this_sessions_inbox_files_are_committed(self):
        """owner-docs-11, quality-path-06, redteam-12, e2e-trial-11: whatever
        else sits in the inbox is left alone and named."""
        b = self.brain_repo()
        self.record(b, "2026-11-08-chat-one.jsonl", "chat-one")
        self.record(b, "2026-11-08-timing-test.jsonl", "timing-test")
        self.record(b, "2026-11-08-radar.jsonl", "some-earlier-chat")
        c.write_json(b / "learning" / "radar" / "state.json", {"sources": {}})
        (b / "CLAUDE.md").write_text("kernel edited by hand\n")
        line = state.push_brain_records(b)
        self.assertIn("brain records pushed to work", line)
        self.assertIn("timing-test", line)
        shown = sh(self.bremote, "git", "show", "--stat", "--format=", "work").stdout
        self.assertIn("2026-11-08-chat-one.jsonl", shown)
        self.assertIn("2026-11-08-radar.jsonl", shown)
        self.assertIn("radar/state.json", shown)
        self.assertNotIn("timing-test", shown)
        self.assertNotIn("CLAUDE.md", shown)
        self.assertIn("timing-test", sh(b, "git", "status", "--porcelain", "--untracked-files=all").stdout)

    def test_a_session_this_chat_repaired_counts_as_its_own(self):
        """owner-docs-11: boot records an earlier unclosed session under that
        session's id; this chat wrote the file, so this chat may commit it."""
        b = self.brain_repo()
        self.record(b, "2026-11-08-died.jsonl", "died", unrecorded=True)
        self.assertNotIn("pushed", state.push_brain_records(b))
        state.remember_repaired("died", b)
        self.assertIn("brain records pushed to work", state.push_brain_records(b))

    def test_no_push_and_no_commit_when_pushing_is_switched_off(self):
        """quality-path-06, e2e-trial-11, redteam-12: BRAIN_NO_NETWORK and
        BRAIN_NO_PUSH are honoured for a remote that is not a local folder."""
        b = self.brain_repo(origin="https://example.invalid/owner/Claude-Brain")
        self.record(b, "2026-11-08-chat-one.jsonl", "chat-one")
        head = git(b, "rev-parse", "HEAD")
        real = subprocess.run
        for flag in ("BRAIN_NO_NETWORK", "BRAIN_NO_PUSH"):
            os.environ[flag] = "1"
            calls = []

            def spy(cmd, *a, **k):
                calls.append(list(cmd))
                return real(cmd, *a, **k)
            with mock.patch.object(state.subprocess, "run", spy):
                line = state.push_brain_records(b)
            self.assertIn("not pushed", line)
            self.assertIn(flag, line)
            self.assertFalse([x for x in calls if "push" in x], "no push may even be attempted")
            self.assertEqual(git(b, "rev-parse", "HEAD"), head, "and nothing is committed")
            os.environ.pop(flag)

    def test_a_scratch_copy_of_the_brain_never_pushes_to_a_real_remote(self):
        """owner-docs-11, lead-03, e2e-trial-11: a copy under the system temp
        folder keeps the real origin; it must not push there."""
        b = self.brain_repo(origin="https://example.invalid/owner/Claude-Brain")
        self.record(b, "2026-11-08-chat-one.jsonl", "chat-one")
        head = git(b, "rev-parse", "HEAD")
        sh(b, "git", "update-ref", "refs/remotes/origin/work", "HEAD")     # as if 'work' had been pushed
        self.assertIn("scratch copy", state.brain_push_block(b))
        line = state.push_brain_records(b)
        self.assertIn("not pushed", line)
        self.assertIn("scratch copy", line)
        self.assertEqual(git(b, "rev-parse", "HEAD"), head)
        with mock.patch.object(state.tempfile, "gettempdir", lambda: str(self.ws / "elsewhere")):
            self.assertEqual(state.brain_push_block(b), "", "a real checkout with a real remote may push")

    def test_other_unpushed_commits_are_not_carried_along(self):
        """redteam-12: the push would carry every other local commit with it."""
        b = self.brain_repo(origin="https://example.invalid/owner/Claude-Brain")
        sh(b, "git", "update-ref", "refs/remotes/origin/work", "HEAD")     # as if 'work' had been pushed
        with mock.patch.object(state.tempfile, "gettempdir", lambda: str(self.ws / "elsewhere")):
            self.record(b, "2026-11-08-chat-one.jsonl", "chat-one")
            commit_all(b, "learn: session records")
            self.assertEqual(state.brain_push_block(b), "", "unpushed inbox commits are what this push is for")
            (b / "CLAUDE.md").write_text("kernel changed locally\n")
            commit_all(b, "learn: consolidate")
            why = state.brain_push_block(b)
        self.assertIn("unpushed", why)
        self.assertIn("CLAUDE.md", why)

    def test_a_local_remote_is_pushed_even_when_network_use_is_off(self):
        """quality-path-06: local bare remotes (tests, CI) stay allowed."""
        b = self.brain_repo()
        self.record(b, "2026-11-08-chat-one.jsonl", "chat-one")
        os.environ["BRAIN_NO_NETWORK"] = "1"
        line = state.push_brain_records(b)
        self.assertIn("brain records pushed to work", line)
        self.assertIn("1 file", line)

    def test_a_credential_in_the_inbox_is_refused_before_the_commit(self):
        """quality-path-06, redteam-07: the staged lines are scanned."""
        b = self.brain_repo()
        secret = "gh" + "p_" + "Ab3dEf6hIj" * 3
        self.record(b, "2026-11-08-chat-one.jsonl", "chat-one", text="token " + secret)
        head = git(b, "rev-parse", "HEAD")
        line = state.push_brain_records(b)
        self.assertIn("not committed", line)
        self.assertNotIn(secret, line)
        self.assertEqual(git(b, "rev-parse", "HEAD"), head)
        self.assertEqual(sh(b, "git", "diff", "--cached", "--name-only").stdout, "", "nothing is left staged")
        self.assertEqual(self.remote_head_of(self.bremote, "work"), "")

    def remote_head_of(self, remote: Path, branch: str) -> str:
        return git(remote, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")

    def test_a_slow_brain_push_is_one_line(self):
        """core-08: the brain push had the same unguarded timeout."""
        b = self.brain_repo()
        self.record(b, "2026-11-08-chat-one.jsonl", "chat-one")
        real = subprocess.run

        def slow(cmd, *a, **k):
            if "push" in cmd:
                raise subprocess.TimeoutExpired(cmd, 120)
            return real(cmd, *a, **k)
        with mock.patch.object(state.subprocess, "run", slow):
            line = state.push_brain_records(b)
        self.assertIn("PUSH FAILED", line)

    def test_checkpoint_help_says_the_brain_is_pushed_too(self):
        """e2e-trial-11: the flag's help named the project only."""
        parser = argparse.ArgumentParser()
        state.register(parser.add_subparsers())
        buf = io.StringIO()
        with redirect_stdout(buf), self.assertRaises(SystemExit):
            parser.parse_args(["checkpoint", "--help"])
        self.assertIn("brain", " ".join(buf.getvalue().split()).split("--push")[-1])

    def test_a_project_push_honours_the_same_switch(self):
        """quality-path-06: pushes ignored BRAIN_NO_NETWORK."""
        p = self.project()
        sh(p, "git", "remote", "set-url", "origin", "https://example.invalid/owner/proj")
        os.environ["BRAIN_NO_NETWORK"] = "1"
        state.checkpoint(p, item="x")
        real = subprocess.run
        calls = []

        def spy(cmd, *a, **k):
            calls.append(list(cmd))
            return real(cmd, *a, **k)
        with mock.patch.object(state.subprocess, "run", spy):
            res = state.push_bookkeeping(p)
        self.assertEqual(res.status, "local")
        self.assertIn("NOT PUSHED", res)
        self.assertFalse([x for x in calls if "push" in x or "fetch" in x])


# ---------------------------------------------------------------- the state file itself
class StateFileTests(Base):
    def test_a_damaged_state_file_is_reported_and_never_overwritten(self):
        """core-05: one bad byte used to wipe stage, item, notes and log at the
        next checkpoint."""
        p = self.project()
        state.checkpoint(p, item="CB-7 importer", done="CB-6 header", note="n1", stage="build")
        path = p / ".brain" / "STATE.md"
        good = path.read_bytes()
        self.assertEqual(state.state_problem(p), "")
        cases = {"bad byte": good + b"\xff\n",
                 "conflict markers": b"<<<<<<< HEAD\n" + good + b"=======\n" + good + b">>>>>>> theirs\n",
                 "empty": b""}
        for name, data in cases.items():
            with self.subTest(name):
                path.write_bytes(data)
                self.assertIn(".brain/STATE.md", state.state_problem(p))
                blob = "\n".join(detect.boot_lines(None, self.brain))
                self.assertIn("PROBLEM", blob)
                self.assertIn(".brain/STATE.md", blob)
                self.assertIn(".brain/STATE.md", "\n".join(state.resume_lines(p)))
                rc, out = cli("checkpoint", "--note", "small note", "--project", str(p))
                self.assertEqual(rc, 1)
                self.assertIn("git checkout", out)
                self.assertEqual(len(out.strip().splitlines()), 1)
                self.assertEqual(path.read_bytes(), data)
                with self.assertRaises(state.StateError):
                    state.checkpoint(p, note="again")
        path.write_bytes(good + b"\xff\n")
        self.assertEqual(state.read_state(p)["item"], "CB-7 importer", "one bad byte costs one character, not the position")
        path.unlink()
        self.assertIn("PROBLEM", "\n".join(detect.boot_lines(None, self.brain)))
        rc, _ = cli("checkpoint", "--item", "fresh start", "--project", str(p))   # nothing is left to lose
        self.assertEqual(rc, 0)
        self.assertEqual(state.state_problem(p), "")

    def test_finished_work_leaves_the_next_list(self):
        """e2e-trial-04: the checklist kept an open line for finished work."""
        p = self.project()
        state.checkpoint(p, item="P1", nxt=["P2", "P3"])
        self.assertEqual(state.checkpoint(p, done="P1", item="P2")["next"], "P3")
        self.assertEqual(state.checkpoint(p, done="P2", item="P3")["next"], "")
        state.checkpoint(p, done="P3")
        state.write_checklist(p)
        text = (p / ".brain" / "CHECKLIST.md").read_text()
        self.assertIn("- nothing open", text)
        self.assertNotIn("[ ]", text)
        state.checkpoint(p, item="T-1", nxt=["T-2 search page", "T-3", "T-20 later"])
        self.assertEqual(state.checkpoint(p, done="T-1", item="T-2")["next"], "T-3; T-20 later", "an id matches its titled entry")
        rc, _ = cli("checkpoint", "--next", "", "--project", str(p))
        self.assertEqual((rc, state.read_state(p)["next_list"]), (0, []))

    def test_checkpoint_refuses_text_that_holds_a_credential(self):
        """redteam-07 (decision 10): chat and git history cannot be cleaned."""
        p = self.project()
        state.checkpoint(p, item="safe")
        path = p / ".brain" / "STATE.md"
        before = path.read_bytes()
        secret = "gh" + "p_" + "Ab3dEf6hIj" * 3
        for flag in ("--note", "--done", "--item", "--blockers", "--next"):
            with self.subTest(flag):
                rc, out = cli("checkpoint", flag, "use " + secret + " for the deploy", "--project", str(p))
                self.assertEqual(rc, 1)
                self.assertIn("refused", out)
                self.assertNotIn(secret, out)
                self.assertEqual(path.read_bytes(), before)

    def test_boot_and_resume_show_the_newest_note(self):
        """core-10: notes were clipped from the front, hiding the latest."""
        p = self.project()
        for n in ("NOTE-1 oldest: " + "the importer is half done " * 5, "NOTE-2 middle: " + "the css moved to styles " * 6,
                  "NOTE-3 newest: STOPPED mid-migration; do NOT run release"):
            state.checkpoint(p, note=n)
        boot = "\n".join(detect.boot_lines(None, self.brain))
        res = "\n".join(state.resume_lines(p))
        self.assertIn("NOTE-3 newest: STOPPED mid-migration; do NOT run release", boot)
        self.assertIn("NOTE-3 newest: STOPPED mid-migration; do NOT run release", res)
        self.assertIn("older", boot, "boot says that older notes exist")
        state.checkpoint(p, note="NOTE-3 newest: STOPPED mid-migration; do NOT run release")
        self.assertEqual(state.read_state(p)["notes"].count("NOTE-3"), 1, "the same note twice in a row is stored once")
        for i in range(12):
            state.checkpoint(p, note=f"note number {i}")
        notes = state.read_state(p)["notes"].splitlines()
        self.assertLessEqual(len(notes), 8, "notes do not grow without bound")
        self.assertIn("note number 11", notes[-1])

    def test_resume_names_project_branch_and_unpushed_commits(self):
        """core-10: after compaction the lead got no project, branch or count."""
        p = self.project()
        sh(p, "git", "push", "-q", "-u", "origin", "work")
        (p / "a.py").write_text("x = 1\n")
        commit_all(p, "feat")
        (p / "café menú.py").write_text("x = 1\n")
        state.checkpoint(p, item="T-1", stage="build")
        lines = state.resume_lines(p)
        self.assertIn("proj", lines[0])
        self.assertIn("branch work", lines[0])
        self.assertIn("1 commit(s) not pushed", lines[0])
        self.assertIn("café menú.py", "\n".join(lines))
        self.assertLessEqual(len(lines), 12)

    def test_long_fields_never_cost_the_position(self):
        """redteam-10, core-07: one long --done text emptied the next boot."""
        p = self.project()
        state.checkpoint(p, item="Email receipts", done="word " * 370, blockers="payment key missing",
                         nxt=["Wire the payment webhook", "Ask the owner for the mail key"])
        self.assertLessEqual(len(state.read_state(p)["last_done"]), 160)
        big = "y" * 5000     # a state file written by hand, or by an older brain
        path = p / ".brain" / "STATE.md"
        text = re.sub(r"(?m)^(item|last_done): .*$", lambda m: f"{m.group(1)}: {big}", path.read_text())
        path.write_text(text.replace("## Notes\n", f"## Notes\n\n- {big}\n"))
        m = c.load_manifest(p)
        m["project"]["title"] = big
        c.write_json(p / ".brain" / "project.json", m)
        lines = detect.boot_lines("Continue", self.brain)
        blob = "\n".join(lines)
        self.assertLessEqual(len(blob.encode()), 1500)
        self.assertIn("next: Wire the payment webhook", blob)
        self.assertIn("blockers: payment key missing", blob)
        res = state.resume_lines(p)
        self.assertLessEqual(len(res), 12)
        self.assertLessEqual(max(len(l) for l in res), 240)


# ---------------------------------------------------------------- what boot prints
class BootTests(Base):
    def boot(self, request="Continue") -> list[str]:
        return detect.boot_lines(request, c.BRAIN_ROOT)

    def test_boot_keeps_problem_and_warning_lines_when_the_state_is_full(self):
        """core-07: the cap dropped lines blindly from the end, with no notice."""
        p = self.project(rule="main-on-green")
        os.environ["BRAIN_SESSION_ID"] = "other-session"
        state.checkpoint(p, item="Añadir " + "reserva " * 18, nxt=["siguiente paso número uno " * 4] * 3,
                         blockers="b" * 130, note="n" * 180, done="hecho " * 46)
        with open(p / ".brain" / "requirements.jsonl", "a") as f:
            f.write('{"id":"R1"\n')
        os.environ["BRAIN_SESSION_ID"] = "chat-two"
        hits = [{"id": f"lsn-{i}", "text": "t" * 170} for i in range(3)]
        with mock.patch("engine.recall.recall", return_value=hits):
            lines = self.boot()
        blob = "\n".join(lines)
        self.assertLessEqual(len(blob.encode()), 1500)
        self.assertLessEqual(len(lines), 15)
        self.assertIn("WARNING: another session", blob)
        self.assertIn("PROBLEM", blob)
        self.assertTrue(any(l.startswith("size:") for l in lines), blob)
        self.assertRegex(lines[-1], r"\d+ more line\(s\)")
        self.assertIn("brain resume", lines[-1])

    def test_boot_resumes_at_the_checkpointed_size(self):
        """core-12: the manifest's first size won over the checkpoint's."""
        p = self.project()
        state.checkpoint(p, tier=3, stage="build", item="Phase 2 stream B")
        size = [l for l in self.boot() if l.startswith("size:")][0]
        self.assertIn("3 programme", size)
        self.assertNotIn("size 2", size)

    def test_no_second_session_warning_after_a_ready_handover(self):
        """core-12: the flow the owner is told to use produced the warning."""
        p = self.project()
        sh(p, "git", "push", "-q", "-u", "origin", "work")
        state.checkpoint(p, item="x")
        problems, _ = state.handover(p, brain_root=self.brain)
        self.assertEqual(problems, [])
        self.assertIn("session: none", self.remote_file("work", ".brain/STATE.md"))
        os.environ.update(BRAIN_SESSION_ID="chat-two", BRAIN_NOW=T2)
        self.assertNotIn("another session", "\n".join(self.boot()))
        os.environ["BRAIN_SESSION_ID"] = "chat-three"      # a chat that left without handing over
        state.checkpoint(p, item="y")
        os.environ["BRAIN_SESSION_ID"] = "chat-four"
        self.assertIn("WARNING: another session", "\n".join(self.boot()))

    def test_recall_on_a_bare_trigger_follows_the_recorded_work(self):
        """core-13, instructions-04: recall matched the trigger word."""
        p = self.project()
        seen = []

        def fake(query, **k):
            seen.append(query)
            return []
        with mock.patch("engine.recall.recall", fake):
            self.boot("Continue")
            self.assertEqual(seen, [], "nothing recorded yet: nothing to recall about")
            state.checkpoint(p, item="CB-7 payment form: card validation", nxt=["CB-8 deploy to Vercel"], blockers="Stripe key missing")
            for request in ("Continue", "Sigue", "Start running"):
                seen.clear()
                self.boot(request)
                self.assertEqual(len(seen), 1, request)
                q = seen[0].lower()
                for w in ("payment", "vercel", "stripe"):
                    self.assertIn(w, q)
                for w in ("continue", "sigue", "running"):
                    self.assertNotIn(w, q)
            seen.clear()
            self.boot("Go deep: which database for offline sync")
            self.assertEqual(len(seen), 1)
            self.assertIn("database", seen[0])
            self.assertNotIn("deep", seen[0].lower())
            seen.clear()
            self.boot("Hand over")
            self.assertEqual(seen, [])

    def test_one_boot_line_only_when_the_learning_loop_needs_attention(self):
        """redteam-20: a wedged consolidation showed nothing at boot."""
        self.project()
        self.assertEqual(detect.learning_line(self.brain), "")
        self.assertFalse([l for l in self.boot(None) if l.startswith("learning:")])
        inbox = self.brain / "learning" / "inbox"
        for i in range(9):
            c.append_jsonl(inbox / f"2026-11-0{i + 1}-s{i}.jsonl", {"kind": "ledger", "session": f"s{i}", "at": T0})
        (inbox / "2026-11-01-bad.jsonl").write_text("{ not json\n")
        c.write_jsonl(self.brain / "memory" / "items.jsonl", [{"id": f"lsn-{i}", "text": "x"} for i in range(370)])
        c.write_jsonl(self.brain / "memory" / "facts.jsonl",
                      [{"id": "fact-old", "type": "fact", "text": "x", "verified_on": "2020-01-01", "recheck_days": 90},
                       {"id": "fact-new", "type": "fact", "text": "x", "verified_on": "2026-11-01", "recheck_days": 90}])
        lines = [l for l in self.boot(None) if l.startswith("learning:")]
        self.assertEqual(len(lines), 1)
        for needle in ("10 inbox file(s)", "unreadable", "memory/items.jsonl", "1 fact(s)"):
            self.assertIn(needle, lines[0])
        self.assertLessEqual(len("\n".join(self.boot(None)).encode()), 1500)


# ---------------------------------------------------------------- the owner's marks
class OwnerMarkTests(Base):
    def test_resolved_is_a_mark_at_the_start_of_a_line_in_english_or_spanish(self):
        """owner-docs-05: a substring match hid an open item, and his Spanish
        answers were ignored."""
        p = self.project()
        (p / "NEEDS_YOU.md").write_text(
            "# Needs you\n\n## 1. Connect Vercel (3 minutes)\nsteps\n\n"
            "## 2. Point the domain\nWhy: until the domain name is resolved by DNS to Vercel, the address is the long one.\n\n"
            "## 3. Elige el color principal\nRESUELTO: verde\n\n## 4. Stripe key\nHecho, ya está guardada.\n\n"
            "## 5. Pick a font\n- **RESOLVED:** the round one\n\n## 6. Logo\nlisto\n\n## 7. Nombre\n> Resuelta: Gastos\n\n"
            "## 8. Dominio\nEl dominio todavía no está resuelto ni hecho.\n")
        self.assertEqual(state.open_needs(p), ["1. Connect Vercel (3 minutes)", "2. Point the domain", "8. Dominio"])

    def test_overturned_decisions_are_listed_until_marked_applied(self):
        """owner-docs-04, instructions-05: no script surfaced his override."""
        p = self.project()
        d = p / ".brain" / "DECISIONS.md"
        self.assertEqual(state.owner_marks(p), "", "the template's own sentence names the word; that is not a mark")
        with open(d, "a") as f:
            f.write("| D-01 | 2026-11-08 | Store data on the device only | simplest | active |\n"
                    "OVERTURNED: I want it synced between my phone and laptop\n"
                    "| D-02 | 2026-11-08 | Prices in dollars | default | REVERTIDA: en euros |\n"
                    "| D-03 | 2026-11-08 | La decisión anterior queda anulada en parte | nota | active |\n")
        line = state.owner_marks(p)
        self.assertIn("OVERTURNED", line)
        self.assertIn("D-01, D-02", line)
        self.assertNotIn("D-03", line)
        boot = detect.boot_lines("Continue", self.brain)
        self.assertLessEqual(len("\n".join(boot).encode()), 1500)
        for out in ("\n".join(boot), "\n".join(state.resume_lines(p))):
            self.assertIn("OVERTURNED", out)
            self.assertIn("D-01, D-02", out)
        d.write_text(d.read_text().replace("phone and laptop\n", "phone and laptop\nAPPLIED 2026-11-09\n")
                     .replace("en euros |", "en euros (applied 2026-11-09) |"))
        self.assertEqual(state.owner_marks(p), "")
        self.assertNotIn("OVERTURNED", "\n".join(detect.boot_lines("Continue", self.brain)))

    def test_an_answer_under_a_needs_you_item_is_shown_until_applied(self):
        """instructions-05: boot said only 'needs owner: 1'."""
        p = self.project()
        path = p / "NEEDS_YOU.md"
        path.write_text("# Needs you\n\n## 1. Connect Vercel\nsteps\n\n## 2. Pick a colour\nRESOLVED: blue\n")
        line = state.owner_marks(p)
        self.assertIn("RESOLVED", line)
        self.assertIn("2", line)
        self.assertIn(line, "\n".join(detect.boot_lines("Continue", self.brain)))
        path.write_text(path.read_text() + "APPLIED 2026-11-09\n")
        self.assertEqual(state.owner_marks(p), "")
        self.assertEqual(state.open_needs(p), ["1. Connect Vercel"])


# ---------------------------------------------------------------- STATUS.md
class StatusTests(Base):
    def test_status_says_what_to_open_first_and_in_plain_words(self):
        """owner-docs-08: it began with a machine timestamp and a stage name,
        and never said what to open."""
        p = self.project()
        m = c.load_manifest(p)
        m["release"].update(rule="main-on-green", live_url="https://gastos.example.app")
        c.write_json(p / ".brain" / "project.json", m)
        rel = p / ".brain" / "log" / "releases.jsonl"
        c.append_jsonl(rel, {"at": "2026-11-08T18:00:00Z", "commit": "abcdef1234567", "branch": "main", "session": "s"})
        state.checkpoint(p, stage="build", item="P2 monthly summary", done="P1 add form", nxt=["P3 export"])
        text = state.write_status(p)
        head = text.splitlines()[:4]
        self.assertIn("Proj", head[0])
        self.assertIn("building", head[0])
        self.assertTrue(any("https://gastos.example.app" in l for l in head), head)
        self.assertIn("8 Nov 2026", "\n".join(head))
        self.assertNotRegex(text, r"\dT\d\d:\d\d:\d\dZ")
        self.assertLessEqual(len(text.splitlines()), 40)
        self.assertIn("Working on: P2 monthly summary", text)
        m["release"]["live_url"] = ""
        c.write_json(p / ".brain" / "project.json", m)
        rel.unlink()
        self.assertTrue(any("Nothing to open yet" in l for l in state.write_status(p).splitlines()[:4]))

    def test_status_is_written_in_the_owners_language(self):
        """e2e-trial-13, owner-docs-08: --language es was stored and never read."""
        p = self.project()
        m = c.load_manifest(p)
        m["languages"] = ["es"]
        c.write_json(p / ".brain" / "project.json", m)
        state.checkpoint(p, stage="build", item="P2 resumen mensual", done="P1 formulario", nxt=["P3 exportar"])
        text = state.write_status(p)
        for s in ("Trabajando en: P2 resumen mensual", "Siguiente: P3 exportar", "en construcción", "Te necesita", "Coste"):
            self.assertIn(s, text)
        for s in ("Working on", "Next:", "Needs you", "Last finished", "Cost\n"):
            self.assertNotIn(s, text)

    def test_dropped_requirements_are_shown_with_their_reasons(self):
        """quality2-02 (decision 9): dropping was invisible to the owner."""
        p = self.project()
        rows = [{"id": f"R-{i:03d}", "quote": f"it must do thing number {i}", "passes_when": "x", "status": "dropped",
                 "reason": f"out of scope {i}", "evidence": []} for i in range(1, 8)]
        req.save(p, rows + [{"id": "R-008", "quote": "keep this one", "status": "open", "evidence": []}])
        text = state.write_status(p)
        shown = [l for l in text.splitlines() if "out of scope" in l]
        self.assertEqual(len(shown), 5)
        self.assertIn("thing number 1", shown[0])
        self.assertIn("2 more", text)
        self.assertLessEqual(len(text.splitlines()), 40)

    def test_status_file_is_rewritten_only_when_its_content_changes(self):
        """instructions-20: every status question dirtied the tree."""
        p = self.project()
        state.checkpoint(p, item="x")
        state.write_status(p)
        commit_all(p, "state")
        writes = []
        real = c.write_text

        def spy(path, text):
            writes.append(Path(path).name)
            return real(path, text)
        with mock.patch.object(c, "write_text", spy):
            for _ in range(2):
                rc, _out = cli("status", "--project", str(p))
                self.assertEqual(rc, 0)
        self.assertNotIn("STATUS.md", writes)
        self.assertEqual(git(p, "status", "--porcelain"), "")

    def test_short_status_keeps_the_cost_lines_within_fifteen_lines(self):
        """owner-docs-08, instructions-20: the short view cut off before the
        project's cost."""
        p = self.project()
        state.checkpoint(p, stage="build", item="P2", done="P1", nxt=["P3", "P4", "P5"], blockers="waiting for a key")
        (p / "NEEDS_YOU.md").write_text("# Needs you\n" + "".join(f"\n## {i}. thing {i}\nsteps\n" for i in range(1, 6)))
        c.write_json(p / ".brain" / "log" / "2026-11-08-s1.json", {"session": "s1", "totals": {"cost": 4.36, "out": 44911}, "helpers": 1})
        rc, out = cli("status", "--project", str(p))
        self.assertEqual(rc, 0)
        self.assertLessEqual(len(out.strip().splitlines()), 15)
        self.assertIn("Project to date", out)
        self.assertIn("$4.36", out)
        self.assertIn("5", [l for l in out.splitlines() if "Needs you" in l][0])


# ---------------------------------------------------------------- the brain on its own
class BrainOnlyTests(Base):
    def solo(self) -> Path:
        b = self.stand_in_brain(self.ws / "solo" / "Claude-Brain")
        c.write_json(b / "VERSION.json", {"brain": "0.9.0", "contract": 1})
        c.write_json(b / "docs" / "plan" / "tickets.json", {"tickets": [
            {"id": "A-1", "title": "finished", "status": "done"},
            {"id": "A-2", "title": "ready one", "deps": ["A-1"], "status": "open"}]})
        (b / "NEEDS_YOU.md").write_text("# Needs you\n\n## 1. Merge to main\nsteps\n\n## 2. Old thing\nRESOLVED: done\n\n## 3. Protect main\nsteps\n")
        c.append_jsonl(b / "learning" / "inbox" / "2026-11-08-chat-one.jsonl", {"kind": "ledger", "session": "chat-one", "at": T0})
        self.bremote = self.ws / ".solo.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.bremote))
        sh(b, "git", "init", "-q", "-b", "claude/x")
        sh(b, "git", "remote", "add", "origin", str(self.bremote))
        commit_all(b, "brain")
        sh(b, "git", "push", "-q", "origin", "HEAD:refs/heads/main")
        sh(b, "git", "fetch", "-q", "origin")
        c.BRAIN_ROOT = b
        return b

    def test_status_with_only_the_brain_attached_reports_on_the_brain(self):
        """owner-docs-06: 'Status' in a brain-only chat exited 1."""
        b = self.solo()
        (b / "x.md").write_text("new\n")
        commit_all(b, "work")
        rc, out = cli("status")
        self.assertEqual(rc, 0, out)
        lines = out.strip().splitlines()
        self.assertLessEqual(len(lines), 12)
        for needle in ("0.9.0", "claude/x", "1 commit(s) not on main", "A-2 ready one", "1 inbox file(s)"):
            self.assertIn(needle, out)
        self.assertTrue(any(l.startswith("needs you: 1, 3") for l in lines), out)
        self.assertIn("needs owner: 2", "\n".join(detect.boot_lines(None, b)))

    def test_handover_with_only_the_brain_attached_checks_the_brain_alone(self):
        """owner-docs-06: 'Hand over' in a brain-only chat exited 1."""
        b = self.solo()
        (b / "x.md").write_text("new\n")
        rc, out = cli("handover")
        self.assertEqual(rc, 1)
        self.assertIn("uncommitted", out)
        self.assertIn("x.md", out)
        commit_all(b, "work")
        sh(b, "git", "push", "-q", "-u", "origin", "claude/x")
        rc, out = cli("handover")
        self.assertEqual(rc, 0, out)
        self.assertIn("only Claude-Brain attached", out)
        self.assertIn("Continue (branch claude/x)", out.strip().splitlines()[-1])


# ---------------------------------------------------------------- one command to end a session
class OneCommandTests(Base):
    def test_one_call_ends_a_session(self):
        """core-15, e2e-trial-16: checkpoint, close, pushes, lease and checks
        in one call and in the right order."""
        b = self.brain
        self.bremote = self.ws / ".brain.git"
        sh(self.ws, "git", "init", "-q", "--bare", "-b", "main", str(self.bremote))
        sh(b, "git", "init", "-q", "-b", "work")
        sh(b, "git", "remote", "add", "origin", str(self.bremote))
        commit_all(b, "brain")
        sh(b, "git", "push", "-q", "-u", "origin", "work")
        p = self.project()
        sh(p, "git", "push", "-q", "-u", "origin", "work")
        m = c.load_manifest(p)
        m["gates"] = [{"id": "checks", "kind": "command", "command": "true"}]
        c.write_json(p / ".brain" / "project.json", m)
        commit_all(p, "gate command")
        detect.boot_lines("Continue", b)                     # the session opens
        self.assertTrue((p / ".brain" / "log" / "open-session.json").exists())
        gate.run_gates(p)
        os.environ["BRAIN_NOW"] = T1
        call = ("handover", "--project", str(p), "--note", "half done in src/x.py", "--item", "T-2 list",
                "--outcome", "ok", "--class", "software.feature", "--tier", "2", "--request", "build the list view")
        rc, out = cli(*call, brain_root=b)
        self.assertEqual(rc, 0, out)
        lines = out.strip().splitlines()
        self.assertLessEqual(len(lines), 6)
        self.assertIn("Continue (branch work)", lines[-1])
        st = state.read_state(p)
        self.assertEqual((st["item"], st["session"]), ("T-2 list", "none"))
        self.assertIn("half done in src/x.py", st["notes"])
        self.assertFalse((p / ".brain" / "log" / "open-session.json").exists(), "the session was closed before the push")
        runs = list((p / ".brain" / "log").glob("*-chat-one.json"))
        self.assertEqual(len(runs), 1)
        self.assertEqual((c.read_json(runs[0])["outcome"], c.read_json(runs[0])["tier"]), ("ok", 2))
        inbox = list((b / "learning" / "inbox").glob("*.jsonl"))
        self.assertEqual(len(inbox), 1)
        kinds = [r["kind"] for r in c.read_jsonl(inbox[0])]
        self.assertEqual((kinds.count("ledger"), kinds.count("outcome")), (1, 1))
        for repo, remote in ((p, self.remote), (b, self.bremote)):
            self.assertEqual(git(repo, "status", "--porcelain"), "")
            self.assertEqual(git(remote, "rev-parse", "work"), git(repo, "rev-parse", "HEAD"))
        self.assertEqual(sh(self.remote, "git", "show", "work:.brain/log/open-session.json").stdout, "")
        rc, out = cli(*call, brain_root=b)                   # again: still ready, nothing doubled
        self.assertEqual(rc, 0, out)
        self.assertEqual(state.read_state(p)["notes"].count("half done in src/x.py"), 1)
        self.assertEqual([r["kind"] for r in c.read_jsonl(inbox[0])].count("ledger"), 1)
        clone, brain2 = self.new_chat()
        rc, out = cli("resume", "--adopt", "--project", str(clone))
        self.assertEqual(rc, 0, out)
        blob = "\n".join(detect.boot_lines("Continue", brain2))
        self.assertIn("item: T-2 list", blob)
        self.assertNotIn("another session", blob)
        self.assertNotIn("earlier session", blob)

    def test_handover_without_new_options_prints_what_it_did_before(self):
        """core-15: called as before it behaves as before (two lines when ready)."""
        p = self.project()
        sh(p, "git", "push", "-q", "-u", "origin", "work")
        rc, out = cli("handover", "--project", str(p), brain_root=self.brain)
        self.assertEqual(rc, 0, out)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("ready:"))
        self.assertIn("paste in a new chat", lines[1])
        self.assertEqual(sorted(x.name for x in (p / ".brain" / "log").glob("*.json")), [], "no ledger capture without the new options")


if __name__ == "__main__":
    unittest.main()
