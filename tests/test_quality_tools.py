import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


checker = load_module("check_chapter", ROOT / "scripts" / "check_chapter.py")
style = load_module("build_style_profile", ROOT / "scripts" / "build_style_profile.py")
compare = load_module("compare_style_profile", ROOT / "scripts" / "compare_style_profile.py")


class QualityToolsTest(unittest.TestCase):
    def test_count_nonspace(self):
        self.assertEqual(checker.count_nonspace("甲 乙\n丙"), 3)

    def test_english_allowlist(self):
        hits = checker.scan_contamination("她打开APP，随后连接GPS。", {"APP", "GPS"})
        self.assertEqual(hits, [])

    def test_unlisted_english_is_blocking(self):
        hits = checker.scan_contamination("她打开Claude。", {"APP"})
        self.assertTrue(any(h["type"] == "英文3字以上" for h in hits))

    def test_pollution_has_line_and_severity(self):
        hits = checker.scan_contamination("好的，以下是本章内容。")
        self.assertTrue(any(h["severity"] == "blocking" for h in hits))
        self.assertTrue(any(h["line"] == "1" for h in hits))

    def test_markdown_fence(self):
        hits = checker.scan_contamination("\x60\x60\x60")
        self.assertTrue(any(h["type"] == "Markdown记号" for h in hits))

    def test_style_profile(self):
        text = "他说：“走。”\n她点头。\n\n两人离开。"
        profile = style.analyze(text)
        self.assertGreater(profile["sentences"], 0)
        self.assertGreater(profile["dialogue_ratio"], 0)
        self.assertIn("p25", profile["sentence_length"])

    def test_style_profile_merge(self):
        a = style.analyze("他说：“走。”\n她点头。")
        merged = style.merge([a, a])
        self.assertEqual(merged["files"], 2)
        self.assertGreater(merged["chinese_chars"], 0)

    def test_compare_metrics(self):
        metrics = compare.metrics("他说：“走。”\n她点头。")
        self.assertGreater(metrics["dialogue_ratio"], 0)

    def test_config_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            chapter = root / "第十一章.txt"
            chapter.write_text("甲" * 2200, encoding="utf-8")
            result = checker.check_file(chapter, 2000, 2400, True, {"APP"})
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["chars"], 2200)


if __name__ == "__main__":
    unittest.main()
