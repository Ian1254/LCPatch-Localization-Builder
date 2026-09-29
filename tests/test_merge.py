import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import fill_speakers, merge_rows


class MergeTests(unittest.TestCase):
    def test_duplicate_ids_align_by_position_and_keep_metadata(self):
        base = {"dataList": [
            {"id": -1, "model": "a", "content": "old one"},
            {"id": -1, "model": "b", "content": "old two"},
        ]}
        source = {"dataList": [
            {"id": -1, "model": "a", "content": "第一句"},
            {"id": -1, "model": "b", "content": "第二句"},
        ]}
        stats = Counter()
        self.assertTrue(merge_rows(base, source, stats))
        self.assertEqual([r["content"] for r in base["dataList"]], ["第一句", "第二句"])
        self.assertEqual([r["model"] for r in base["dataList"]], ["a", "b"])

    def test_speaker_uses_llc_default_but_preserves_explicit_title(self):
        rows = [
            {"model": "a", "content": "話", "teller": "old", "title": "guide"},
            {"model": "a", "content": "話", "teller": "特殊稱呼", "title": "特別職稱"},
        ]
        stats = Counter()
        fill_speakers(rows, {"a": ("中文", "嚮導")}, {"a": ("old", "guide")}, stats)
        self.assertEqual((rows[0]["teller"], rows[0]["title"]), ("中文", "嚮導"))
        self.assertEqual((rows[1]["teller"], rows[1]["title"]), ("特殊稱呼", "特別職稱"))

    def test_unmatched_duplicate_ids_do_not_guess(self):
        base = {"dataList": [{"id": 3, "content": "existing"}]}
        source = {"dataList": [{"id": 3, "content": "a"}, {"id": 3, "content": "b"}]}
        stats = Counter()
        merge_rows(base, source, stats)
        self.assertEqual(base["dataList"][0]["content"], "existing")
        self.assertEqual(stats["ambiguous_source_rows_skipped"], 2)


if __name__ == "__main__":
    unittest.main()
