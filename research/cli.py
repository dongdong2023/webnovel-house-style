from __future__ import annotations

import argparse
from pathlib import Path

from research.corpus import build_manifest, save_manifest
from research.discover import (
    discover_boards,
    load_records,
    save_records,
)
from research.report import generate_report, save_report
from research.settings import DATA_DIR, load_config
from research.sources.fanqie_boards import (
    all_boards,
    find_board,
)
from research.style_mining import (
    analyze_corpus,
    save_profile,
)


def main() -> None:

    config = load_config()

    parser = argparse.ArgumentParser(
        description="Web Novel Research Engine v0.3"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    discover = sub.add_parser(
        "discover",
        help="轮询番茄全部板块（只读公开榜单元数据）",
    )

    discover.add_argument(
        "--board",
        default=None,
        help="只抓单个板块，如 1_2_751",
    )

    report = sub.add_parser(
        "report",
        help="从 novels.json 生成各题材榜数据报告",
    )

    corpus = sub.add_parser(
        "manifest",
        help="建立合法语料 Manifest",
    )

    corpus.add_argument("directory")

    mine = sub.add_parser(
        "mine",
        help="提炼 Style Profile",
    )

    mine.add_argument("directory")

    args = parser.parse_args()

    if args.command == "discover":

        fanqie_cfg = config["sources"]["fanqie"]

        if args.board:
            board = find_board(args.board)
            if not board:
                raise SystemExit(
                    f"未知板块码: {args.board}"
                )
            boards = [board]
        else:
            boards = all_boards(
                genders=fanqie_cfg.get("genders"),
                rank_types=fanqie_cfg.get("rank_types"),
            )

        records, errors = discover_boards(
            boards,
            rank_weight=config["hotness"]["rank_weight"],
            read_weight=config["hotness"]["read_weight"],
            freshness_weight=config["hotness"][
                "freshness_weight"
            ],
            timeout=config["research"][
                "request_timeout"
            ],
            user_agent=config["research"]["user_agent"],
            delay_seconds=fanqie_cfg.get(
                "request_delay_seconds", 0.8
            ),
            top_per_board=fanqie_cfg.get(
                "top_per_board", 10
            ),
        )

        path = save_records(records)

        print(
            f"[PASS] boards={len(boards)} "
            f"records={len(records)}"
        )
        if errors:
            print(f"[WARN] failed boards: {len(errors)}")
            for code, msg in errors:
                print(f"  {code}: {msg}")
        print(path)

    elif args.command == "report":

        records = load_records()

        markdown = generate_report(records)

        output = save_report(markdown)

        print("[PASS] report generated")
        print(output)

    elif args.command == "manifest":

        root = Path(args.directory)

        items = build_manifest(root)

        path = save_manifest(items)

        print(f"[PASS] {len(items)} corpus files")
        print(path)

    elif args.command == "mine":

        root = Path(args.directory)

        try:
            profile = analyze_corpus(
                root,
                min_chinese_chars=config["style"][
                    "min_chinese_chars"
                ],
            )
        except RuntimeError as exc:
            # Rights Gate 未通过（无 manifest / 权利不符 / sha 不一致）时
            # 给出可读原因，而不是抛栈
            raise SystemExit(f"[FAIL] {exc}") from exc

        output = (
            DATA_DIR / "style_profiles" / "current.json"
        )

        save_profile(profile, output)

        print("[PASS] Style Profile generated")
        print(output)


if __name__ == "__main__":
    main()
