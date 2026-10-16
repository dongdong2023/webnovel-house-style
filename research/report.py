from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from research.models import NovelRecord
from research.settings import DATA_DIR

BRACKET_TAG_RE = re.compile(r"【([^】]{2,80})】")
TAG_SPLIT_RE = re.compile(r"[+＋/／、｜|,，\s]+")

GROUP_ORDER = [
    ("男频", "在读榜"),
    ("男频", "新书榜"),
    ("女频", "在读榜"),
    ("女频", "新书榜"),
]


def _fmt_int(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def _median(values) -> float | None:
    values = [
        v for v in values if v is not None
    ]
    return statistics.median(values) if values else None


def _fmt_med(values, digits=0) -> str:
    med = _median(values)
    if med is None:
        return "-"
    return f"{med:.{digits}f}"


def _pct(records, predicate) -> str:
    if not records:
        return "-"
    hit = sum(1 for r in records if predicate(r))
    return f"{100 * hit / len(records):.1f}%"


def _title_len(title: str) -> int:
    return len(re.sub(r"\s+", "", title))


def _hours_since_update(record: NovelRecord):
    try:
        updated = datetime.fromisoformat(
            record.updated_at
        )
        seen = datetime.fromisoformat(
            record.discovered_at
        )
        return (seen - updated).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def _per_chapter_words(record: NovelRecord):
    if (
        record.word_count
        and record.chapter_count
        and record.chapter_count >= 10
    ):
        return record.word_count / record.chapter_count
    return None


def _group_records(records):
    groups: dict[tuple[str, str], list[NovelRecord]] = {}
    for r in records:
        key = (r.gender, r.rank_type)
        groups.setdefault(key, []).append(r)
    return groups


def _group_boards(records):
    boards: dict[str, list[NovelRecord]] = {}
    for r in records:
        boards.setdefault(r.board, []).append(r)
    return boards


def _board_tables(records) -> list[str]:
    lines: list[str] = []
    groups = _group_records(records)

    for gender, rank_type in GROUP_ORDER:
        key = (gender, rank_type)
        if key not in groups:
            continue

        board_records = _group_boards(groups[key])
        boards = sorted(
            board_records.items(),
            key=lambda item: _median(
                [r.read_count for r in item[1]]
            )
            or 0,
            reverse=True,
        )

        lines.append(f"\n## {gender}·{rank_type}\n")

        for board, recs in boards:
            first = recs[0]
            recs = sorted(
                recs, key=lambda r: r.rank or 99
            )
            lines.append(
                f"\n### {first.category_name}"
                f"（{board}，在读中位数 "
                f"{_fmt_med([r.read_count for r in recs])}）\n"
            )
            lines.append(
                "| 排名 | 书名 | 在读 | 章节 | 字数 | 章均字数 | 状态 | 最近更新 |"
            )
            lines.append("|---|---|---|---|---|---|---|---|")

            for r in recs[:3]:
                status = {
                    1: "连载",
                    0: "完结",
                }.get(r.creation_status, "-")

                updated = "-"
                hours = _hours_since_update(r)
                if hours is not None:
                    updated = f"{hours:.0f}小时前"

                lines.append(
                    f"| {r.rank or '-'} "
                    f"| {r.title} "
                    f"| {_fmt_int(r.read_count)} "
                    f"| {_fmt_int(r.chapter_count)} "
                    f"| {_fmt_int(r.word_count)} "
                    f"| {_fmt_med([_per_chapter_words(r)])} "
                    f"| {status} "
                    f"| {updated} |"
                )

    return lines


def _name_style_section(records) -> list[str]:
    lines = [
        "\n## 书名风格\n",
        "> 反爬乱码是一对一码点替换，字符数和标点不受影响，",
        "> 本节统计可信；表格里的书名显示可能缺字。\n",
        "| 分组 | 书数 | 长度中位 | 含逗号 | 含冒号 | 含数字 | 含？！ |",
        "|---|---|---|---|---|---|---|",
    ]

    groups = _group_records(records)

    for gender, rank_type in GROUP_ORDER:
        recs = groups.get((gender, rank_type), [])
        if not recs:
            continue

        lines.append(
            f"| {gender}·{rank_type} "
            f"| {len(recs)} "
            f"| {_fmt_med([_title_len(r.title) for r in recs])} "
            f"| {_pct(recs, lambda r: '，' in r.title or ',' in r.title)} "
            f"| {_pct(recs, lambda r: '：' in r.title or ':' in r.title)} "
            f"| {_pct(recs, lambda r: any(c.isdigit() for c in r.title))} "
            f"| {_pct(recs, lambda r: any(c in r.title for c in '？！!?'))} |"
        )

    return lines


def _blurb_section(records) -> list[str]:
    tag_counter: Counter = Counter()
    tagged = 0

    for r in records:
        blocks = BRACKET_TAG_RE.findall(r.description)
        if blocks:
            tagged += 1
        for block in blocks:
            for tag in TAG_SPLIT_RE.split(block):
                tag = tag.strip()
                if len(tag) >= 2:
                    tag_counter[tag] += 1

    lines = [
        "\n## 简介风格\n",
        f"- 带【】标签块的书：{tagged}/{len(records)}"
        f"（{_pct(records, lambda r: bool(BRACKET_TAG_RE.search(r.description)))}）",
        f"- 简介长度中位数："
        f"{_fmt_med([len(r.description) for r in records])} 字符",
        "",
        "高频标签（【】内按 +/、切分）：",
        "",
    ]

    for tag, count in tag_counter.most_common(20):
        lines.append(f"- {tag} ×{count}")

    if not tag_counter:
        lines.append("（无）")

    return lines


def _pacing_section(records) -> list[str]:
    lines = [
        "\n## 篇幅与更新节奏\n",
        "| 分组 | 书数 | 章均字数中位 | 连载中 | 24h内更新 | 72h内更新 |",
        "|---|---|---|---|---|---|",
    ]

    groups = _group_records(records)

    def within(recs, hours):
        return _pct(
            recs,
            lambda r: (
                (h := _hours_since_update(r)) is not None
                and h <= hours
            ),
        )

    for gender, rank_type in GROUP_ORDER:
        recs = groups.get((gender, rank_type), [])
        if not recs:
            continue

        lines.append(
            f"| {gender}·{rank_type} "
            f"| {len(recs)} "
            f"| {_fmt_med([_per_chapter_words(r) for r in recs])} "
            f"| {_pct(recs, lambda r: r.creation_status == 1)} "
            f"| {within(recs, 24)} "
            f"| {within(recs, 72)} |"
        )

    lines.extend(
        [
            "",
            "注：更新节奏目前只能看\"最近一次更新距现在多久\"。",
            "data/snapshots/ 攒下多期快照后，可以算出真实日更字数和涨速。",
        ]
    )

    return lines


def _cross_board_section(records) -> list[str]:
    by_book: dict[str, list[NovelRecord]] = {}
    for r in records:
        if r.book_id:
            by_book.setdefault(r.book_id, []).append(r)

    hits = [
        (book_id, recs)
        for book_id, recs in by_book.items()
        if len({r.board for r in recs}) >= 2
    ]

    hits.sort(
        key=lambda item: max(
            r.read_count or 0 for r in item[1]
        ),
        reverse=True,
    )

    lines = [
        "\n## 跨榜书（同书出现在 ≥2 个板块）\n",
    ]

    if not hits:
        lines.append("（本轮无）")
        return lines

    lines.append("| 书名 | 在读 | 上榜板块 |")
    lines.append("|---|---|---|")

    for book_id, recs in hits[:15]:
        first = sorted(
            recs, key=lambda r: -(r.read_count or 0)
        )[0]
        boards = "、".join(
            sorted({r.board for r in recs})
        )
        lines.append(
            f"| {first.title} "
            f"| {_fmt_int(first.read_count)} "
            f"| {boards} |"
        )

    return lines


def generate_report(
    records: list[NovelRecord],
) -> str:
    now = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    groups = _group_records(records)
    obfuscated = sum(
        1 for r in records if r.title_obfuscated
    )

    lines = [
        f"# 番茄各题材榜数据报告",
        "",
        f"- 生成时间：{now}",
        f"- 样本：{len(records)} 本书，"
        f"{len(_group_boards(records))} 个板块",
        f"- 分组："
        + "；".join(
            f"{g}·{t} {len(groups[(g, t)])}本"
            for g, t in GROUP_ORDER
            if (g, t) in groups
        ),
        f"- 书名反爬乱码：{obfuscated}/{len(records)}"
        f"（{_pct(records, lambda r: r.title_obfuscated)}）",
    ]

    lines.extend(_board_tables(records))
    lines.extend(_name_style_section(records))
    lines.extend(_blurb_section(records))
    lines.extend(_pacing_section(records))
    lines.extend(_cross_board_section(records))

    lines.extend(
        [
            "\n---",
            "",
            "数据来源：番茄小说网公开榜单页元数据（书名/作者/排名/在读数/",
            "字数/章节数/最近更新时间/简介）。本报告不含任何正文内容。",
        ]
    )

    return "\n".join(lines) + "\n"


def save_report(
    markdown: str,
    output: Path | None = None,
) -> Path:

    if output is None:
        stamp = datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M"
        )
        output = (
            DATA_DIR
            / "reports"
            / f"fanqie_{stamp}.md"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    return output
