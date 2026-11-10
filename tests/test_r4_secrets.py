"""The secret scan knows the common credential formats, names the kind and
never the value, and stays quiet on ordinary text. Samples are built by
concatenation so this file itself passes the scan."""
import subprocess
import unittest
from pathlib import Path

from engine import common as c

ROOT = Path(__file__).resolve().parents[1]
A, N, H = "Ab3dEf6hIj", "0123456789", "0a1b2c3d4e5f6071"


SAMPLES = [
    ("anthropic", "sk-" + "ant-" + A * 3),
    ("openai project", "sk-" + "proj-" + A * 3),
    ("github classic", "gh" + "p_" + A * 3),
    ("github fine-grained", "github" + "_pat_" + A * 4),
    ("aws key id", "AK" + "IA" + "ABCDEFGHIJKLMNOP"),
    ("slack", "xo" + "xb-" + N + "-" + A),
    ("private key", "-----BEGIN RSA " + "PRIVATE KEY-----"),
    ("assignment", "API_KEY" + "=" + A * 3),
    ("google", "AI" + "za" + (A * 4)[:35]),
    ("stripe live", "sk" + "_live_" + A * 2),
    ("stripe restricted", "rk" + "_live_" + A * 2),
    ("web token", "ey" + "J" + A + "." + "ey" + "J" + A + "." + A),
    ("bearer", "Authorization: Bea" + "rer " + A * 3),
    ("database address", "postgres" + "://admin:" + "s3cretPass" + "@db.example.com:5432/app"),
    ("npm", "np" + "m_" + A * 4),
    ("telegram", "123456789" + ":AA" + A * 4),
    ("sendgrid", "S" + "G." + A * 2 + "." + A * 3),
    ("twilio", "S" + "K" + H * 2),
    ("aws secret", "aws_secret" + "_access_key = \"" + (A * 4) + "\""),
]

HARMLESS = [
    "Fix the median for even-length lists and run the tests",
    "password = getpass.getpass()",
    "see https://example.com/docs/tokens for how tokens are counted",
    "the gate command is python3 -m unittest discover -s tests",
    "Authorization: Bearer <token>",
    "contact the owner through NEEDS_YOU.md, never by email",
    "sk-short",
    "the header task-budgets-2026-03-13 switches the feature on",
    "commit 9e4b158a7c0d1e2f3a4b5c6d7e8f901234567890 is on the branch",
]


class SecretScan(unittest.TestCase):
    def test_find_secrets_catches_the_common_token_formats(self):
        missed = [name for name, text in SAMPLES if not c.find_secrets("deploy with " + text + " please")]
        self.assertEqual(missed, [])

    def test_ordinary_text_is_not_flagged(self):
        flagged = [text for text in HARMLESS if c.find_secrets(text)]
        self.assertEqual(flagged, [])

    def test_the_refusal_names_the_kind_and_never_the_value(self):
        for name, text in SAMPLES:
            line = c.secret_problem("note: " + text)
            self.assertTrue(line.startswith("refused:"), name)
            self.assertNotIn(text, line, name)
            self.assertIn("credential form", line)
        self.assertEqual(c.secret_problem("nothing secret here"), "")

    def test_redaction_keeps_the_rest_of_the_line(self):
        for name, text in SAMPLES:
            out = c.redact_secrets("run deploy --key " + text + " --env prod")
            self.assertNotIn(text, out, name)
            self.assertIn("[redacted]", out, name)
            self.assertTrue(out.startswith("run deploy"), name)

    def test_the_brain_itself_holds_nothing_the_scan_flags(self):
        """New patterns must not turn the brain's own files into findings."""
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        flagged = []
        for rel in files:
            path = ROOT / rel
            if path.suffix in {".png", ".jpg", ".sqlite"} or not path.is_file() or rel.startswith("tests/"):
                continue  # tests hold deliberate samples
            if c.find_secrets(path.read_text(encoding="utf-8", errors="replace")):
                flagged.append(rel)
        self.assertEqual(flagged, [])


if __name__ == "__main__":
    unittest.main()
