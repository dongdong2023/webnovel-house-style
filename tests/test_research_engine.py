import json
import tempfile
import unittest
from pathlib import Path

from research.corpus import (
    build_manifest,
    validate_manifest,
)
from research.discover import calculate_hotness
from research.models import NovelRecord
from research.report import generate_report
from research.sources.fanqie import FanqieAdapter
from research.sources.fanqie_boards import (
    all_boards,
    find_board,
)
from research.style_mining import analyze

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "fanqie_rank.html"
)


class StyleMiningTest(unittest.TestCase):

    def test_style_analysis(self):

        text = (
            "他说：“走。”"
            "\n"
            "她点了点头。"
            "\n\n"
            "两个人一起离开。"
        )

        result = analyze(text)

        self.assertGreater(
            result["chinese_chars"],
            0,
        )

        self.assertGreater(
            result["sentences"],
            0,
        )

        self.assertGreater(
            result["dialogue_ratio"],
            0,
        )


class ManifestTest(unittest.TestCase):

    def test_manifest(self):

        with tempfile.TemporaryDirectory() as td:

            root = Path(td)

            file = root / "chapter.txt"

            file.write_text(
                "这是测试文本。",
                encoding="utf-8",
            )

            manifest = build_manifest(root)

            self.assertEqual(len(manifest), 1)

            self.assertIn("sha256", manifest[0])

    def test_rights_gate(self):

        allowed, rejected = validate_manifest(
            [
                {
                    "path": "a.txt",
                    "rights": "user_provided",
                },
                {
                    "path": "b.txt",
                    "rights": "unknown",
                },
            ],
            allowed_rights={"user_provided"},
        )

        self.assertEqual(len(allowed), 1)

        self.assertEqual(len(rejected), 1)


class BoardsTest(unittest.TestCase):

    def test_taxonomy(self):

        boards = all_boards()

        # 19 男频 + 18 女频，各两种榜
        self.assertEqual(len(boards), 74)

        codes = {b["code"] for b in boards}
        self.assertIn("1_2_751", codes)
        self.assertIn("0_1_1139", codes)

        board = find_board("1_2_751")
        self.assertEqual(board["category"], "悬疑灵异")
        self.assertEqual(board["gender"], "男频")
        self.assertEqual(board["rank_type"], "在读榜")

    def test_filter(self):

        boards = all_boards(
            genders=["女频"],
            rank_types=["新书榜"],
        )

        self.assertEqual(len(boards), 18)
        self.assertTrue(
            all(
                b["rank_type"] == "新书榜"
                for b in boards
            )
        )


class FanqieAdapterTest(unittest.TestCase):

    def test_parse_fixture(self):

        adapter = FanqieAdapter(
            "https://fanqienovel.com/rank/0_1"
        )

        records = adapter.parse(
            FIXTURE.read_text(encoding="utf-8")
        )

        self.assertEqual(len(records), 10)

        first = records[0]

        self.assertEqual(first.rank, 1)
        self.assertEqual(first.board, "0_1")
        self.assertEqual(
            first.book_id,
            "7680148815046773822",
        )
        self.assertEqual(first.read_count, 120014.0)
        self.assertEqual(
            first.url,
            "https://fanqienovel.com/page/"
            "7680148815046773822",
        )
        # "第85章 85-只是在气沈静芙"
        self.assertEqual(first.chapter_count, 85)
        self.assertEqual(first.creation_status, 1)
        self.assertTrue(first.title_obfuscated)
        self.assertTrue(
            first.updated_at.startswith("20")
        )

    def test_missing_state_raises(self):

        adapter = FanqieAdapter(
            "https://fanqienovel.com/rank/0_1"
        )

        with self.assertRaises(ValueError):
            adapter.parse("<html></html>")


class HotnessTest(unittest.TestCase):

    def test_ordering_and_range(self):

        records = [
            NovelRecord(
                platform="fanqie",
                title="a",
                rank=1,
                read_count=100000,
            ),
            NovelRecord(
                platform="fanqie",
                title="b",
                rank=2,
                read_count=50000,
            ),
            NovelRecord(
                platform="fanqie",
                title="c",
                rank=3,
                read_count=10000,
            ),
            NovelRecord(
                platform="fanqie",
                title="d",
                rank=None,
                read_count=None,
            ),
        ]

        scored = calculate_hotness(records)

        titles = [r.title for r in scored]

        # 排名和读数同序时，双料第一必须排最前
        self.assertEqual(titles[0], "a")

        # 缺字段的记录不崩溃、不丢失
        self.assertIn("d", titles)

        for r in scored:
            self.assertGreaterEqual(r.hotness_score, 0.0)
            self.assertLessEqual(r.hotness_score, 1.0)


class ReportTest(unittest.TestCase):

    def test_report_smoke(self):

        records = [
            NovelRecord(
                platform="fanqie",
                title="测试书名，带逗号",
                book_id="111",
                board="1_2_751",
                board_name="男频/在读榜/悬疑灵异",
                gender="男频",
                rank_type="在读榜",
                category_name="悬疑灵异",
                rank=1,
                read_count=800000,
                word_count=5000000,
                chapter_count=2000,
                creation_status=1,
                description="【穿越+无敌+爽文】主角很强。",
                discovered_at="2026-10-16T12:00:00+00:00",
                updated_at="2026-10-16T10:00:00+00:00",
            ),
            NovelRecord(
                platform="fanqie",
                title="另一本书",
                book_id="111",
                board="1_2_8",
                board_name="男频/在读榜/科幻末世",
                gender="男频",
                rank_type="在读榜",
                category_name="科幻末世",
                rank=5,
                read_count=120000,
            ),
            NovelRecord(
                platform="fanqie",
                title="缺字段的书",
                board="0_1_23",
                gender="女频",
                rank_type="新书榜",
                category_name="种田",
                rank=2,
            ),
        ]

        markdown = generate_report(records)

        self.assertIn("番茄各题材榜数据报告", markdown)
        self.assertIn("书名风格", markdown)
        self.assertIn("简介风格", markdown)
        self.assertIn("篇幅与更新节奏", markdown)
        self.assertIn("跨榜书", markdown)
        # 跨榜：book_id=111 出现在两个板块
        self.assertIn("1_2_751、1_2_8", markdown)
        # 标签提取
        self.assertIn("穿越", markdown)

    def test_roundtrip_dict(self):

        record = NovelRecord(
            platform="fanqie",
            title="x",
            chapter_count=85,
            creation_status=1,
        )

        restored = NovelRecord.from_dict(
            record.to_dict()
        )

        self.assertEqual(restored.chapter_count, 85)
        self.assertEqual(restored.creation_status, 1)


if __name__ == "__main__":
    unittest.main()
