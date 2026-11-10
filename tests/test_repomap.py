"""Tests for engine/repomap.py on small generated trees."""
import tempfile
import unittest
from pathlib import Path

from engine import repomap as rm


def tree(root: Path, files: dict):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text, encoding="utf-8")


class RepoMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.cache = Path(self.tmp.name) / "cache"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **kw):
        return rm.build_map(self.root, self.cache, **kw)

    def test_python_graph_ranks_the_shared_module_first(self):
        tree(self.root, {
            "pkg/__init__.py": "",
            "pkg/core.py": "def load_items():\n    return []\n\nclass Store:\n    def save(self):\n        pass\n",
            "pkg/a.py": "from .core import load_items\nfrom pkg.core import Store\nload_items()\nStore().save()\n",
            "pkg/b.py": "from pkg import core\ncore.load_items()\n",
            "pkg/c.py": "import pkg.core\npkg.core.load_items()\n",
            "README.md": "See pkg/a.py for the entry point.\n",
        })
        res = self.build()
        self.assertEqual(res["files"][0]["path"], "pkg/core.py")
        self.assertEqual(res["files"][0]["symbols"][0], "load_items")
        self.assertGreater(res["edges"], 3)

    def test_js_ts_imports_and_definitions(self):
        tree(self.root, {
            "src/util.ts": "export function formatDate(d: Date) { return '' }\nexport const LIMIT = 3\n",
            "src/app.tsx": "import { formatDate } from './util'\nexport default function App() { return formatDate(new Date()) }\n",
            "src/page.js": "const { formatDate } = require('./util.js')\nformatDate()\n",
        })
        res = self.build()
        top = res["files"][0]
        self.assertEqual(top["path"], "src/util.ts")
        self.assertIn("formatDate", top["symbols"])

    def test_skips_vendor_binary_and_large_files(self):
        tree(self.root, {
            "main.py": "print(1)\n",
            "node_modules/lib/index.js": "export function x() {}\n",
            ".git/config": "x",
            ".brain/cache/ab/x.json": "{}",
            "image.png": b"\x89PNG\x00\x00binary",
            "big.txt": "a" * (rm.MAX_BYTES + 1),
        })
        paths = [f["path"] for f in self.build()["files"]]
        self.assertEqual(paths, ["main.py"])

    def test_skips_logs_and_files_git_ignores(self):
        # Review item M8: run logs and generated files were mapped.
        import subprocess
        tree(self.root, {
            "main.py": "print(1)\n",
            ".gitignore": "gen/\n",
            "gen/out.py": "x = 1\n",
            ".brain/log/run/1.log": "noise\n",
        })
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        paths = [f["path"] for f in self.build()["files"]]
        self.assertEqual(sorted(paths), [".gitignore", "main.py"])

    def test_cache_hit_and_invalidation(self):
        tree(self.root, {"a.py": "def f():\n    pass\n"})
        first = self.build()
        self.assertFalse(first["cached"])
        self.assertTrue(self.build()["cached"])
        tree(self.root, {"a.py": "def g():\n    pass\n"})
        changed = self.build()
        self.assertFalse(changed["cached"])
        self.assertEqual(changed["files"][0]["symbols"], ["g"])

    def test_empty_tree_prints_one_line(self):
        lines = rm.render(self.build())
        self.assertEqual(len(lines), 1)
        self.assertIn("no source files", lines[0])

    def test_render_respects_top_and_budget(self):
        tree(self.root, {f"m{i}.py": f"def function_number_{i}():\n    pass\n" for i in range(40)})
        res = self.build()
        self.assertEqual(len(rm.render(res, top=5)), 6)
        lines = rm.render(res, top=40, budget=30)
        self.assertLessEqual(sum(rm.c.est_tokens(l) + 1 for l in lines[:-1]), 30)

    def test_syntax_error_does_not_break(self):
        tree(self.root, {"bad.py": "def (:\n", "ok.py": "def fine():\n    pass\n"})
        self.assertEqual(len(self.build()["files"]), 2)

    def test_pagerank_sums_to_one(self):
        rank = rm.pagerank({"a": {"b": 1.0}, "b": {"c": 1.0}, "c": {}})
        self.assertAlmostEqual(sum(rank.values()), 1.0, places=6)
        self.assertGreater(rank["c"], rank["a"])


if __name__ == "__main__":
    unittest.main()
