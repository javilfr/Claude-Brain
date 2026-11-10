"""Tests for engine/cache.py."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine import cache
from engine import common as c


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "cache"

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_is_stable_and_sensitive(self):
        a = cache.key("tool", 1, {"b": 2, "a": 1}, ["h1", "h2"])
        self.assertEqual(a, cache.key("tool", 1, {"a": 1, "b": 2}, ["h1", "h2"]))
        self.assertNotEqual(a, cache.key("tool", 1, {"a": 1, "b": 2}, ["h1", "h3"]))
        self.assertEqual(len(a), 64)

    def test_get_put_roundtrip_and_miss(self):
        k = cache.key("x")
        self.assertIsNone(cache.get(k, self.dir))
        cache.put(k, {"files": [1, 2]}, self.dir)
        self.assertEqual(cache.get(k, self.dir), {"files": [1, 2]})
        self.assertTrue((self.dir / k[:2] / f"{k}.json").is_file())

    def test_corrupt_entry_is_a_miss(self):
        k = cache.key("y")
        path = cache.put(k, 1, self.dir)
        path.write_text("{broken")
        self.assertIsNone(cache.get(k, self.dir))

    def test_bad_key_rejected(self):
        with self.assertRaises(ValueError):
            cache.get("../../etc", self.dir)

    def test_prune_by_age(self):
        with mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-01-01T00:00:00Z"}):
            cache.put(cache.key("old"), 1, self.dir)
        with mock.patch.dict(os.environ, {"BRAIN_NOW": "2026-03-01T00:00:00Z"}):
            cache.put(cache.key("new"), 2, self.dir)
            self.assertEqual(cache.prune(30, self.dir), 1)
            self.assertIsNone(cache.get(cache.key("old"), self.dir))
            self.assertEqual(cache.get(cache.key("new"), self.dir), 2)
        self.assertEqual(cache.prune(1, Path(self.tmp.name) / "absent"), 0)

    def test_default_dir_never_inside_brain(self):
        proj = Path(self.tmp.name) / "proj"
        self.assertEqual(cache.default_dir(proj), proj / ".brain" / "cache")
        inside = cache.default_dir(c.BRAIN_ROOT)
        self.assertFalse(inside.resolve().is_relative_to(c.BRAIN_ROOT.resolve()))
        self.assertFalse(cache.default_dir(None).resolve().is_relative_to(c.BRAIN_ROOT.resolve()))


if __name__ == "__main__":
    unittest.main()
