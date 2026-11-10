"""Helpers started by a workflow are found by the ledger, and a workflow's
journal is not mistaken for a helper (seen live on 2026-11-10: the ledger said
"1 helper" while seventeen workflow helpers were running)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import common as c


class HelperTranscripts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.sid = "sess-wf"
        proj = self.home / ".claude" / "projects" / "-some-folder"
        self.main = proj / f"{self.sid}.jsonl"
        subs = proj / self.sid / "subagents"
        run = subs / "workflows" / "wf_1234"
        run.mkdir(parents=True)
        self.main.write_text("{}\n")
        (subs / "agent-direct.jsonl").write_text("{}\n")
        (subs / "agent-direct.meta.json").write_text("{}")
        (run / "agent-in-workflow.jsonl").write_text("{}\n")
        (run / "agent-in-workflow.meta.json").write_text("{}")
        (run / "journal.jsonl").write_text("{}\n")

    def test_direct_and_workflow_helpers_are_both_found(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BRAIN_TRANSCRIPT", None)
            main, subs = c.transcript_paths(self.sid, home=self.home)
        self.assertEqual(main, self.main)
        self.assertEqual(sorted(p.name for p in subs), ["agent-direct.jsonl", "agent-in-workflow.jsonl"])

    def test_a_workflow_journal_is_not_a_helper(self):
        names = [p.name for p in c.helper_transcripts(self.main)]
        self.assertNotIn("journal.jsonl", names)

    def test_no_helper_folder_means_no_helpers(self):
        lone = self.home / "lone.jsonl"
        lone.write_text("{}\n")
        self.assertEqual(c.helper_transcripts(lone), [])


if __name__ == "__main__":
    unittest.main()
