#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""比较单章与 Style Profile 的可量化风格指标。

这是 advisory（建议项），不是硬性“像不像”判定。风格差异本身不等于质量问题。
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

SENTENCE_RE = re.compile(r"[^。！？!?；;…\n]+[。！？!?；;…]?")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
DIALOGUE_RE = re.compile(r'[“"「『].*?[”"」』]')
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法解码：{path}")


def metrics(text: str) -> dict[str, float]:
    chinese = len(CHINESE_RE.findall(text))
    sentences = [
        m.group(0) for m in SENTENCE_RE.finditer(text)
        if CHINESE_RE.search(m.group(0))
    ]
    sentence_lengths = [len(CHINESE_RE.findall(s)) for s in sentences]
    paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    paragraph_lengths = [len(CHINESE_RE.findall(p)) for p in paragraphs]
    dialogue = sum(
        len(CHINESE_RE.findall(m.group(0)))
        for m in DIALOGUE_RE.finditer(text)
    )
    return {
        "dialogue_ratio": dialogue / chinese if chinese else 0,
        "sentence_length_mean": statistics.mean(sentence_lengths) if sentence_lengths else 0,
        "paragraph_length_median": statistics.median(paragraph_lengths) if paragraph_lengths else 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="比较单章与 Style Profile")
    ap.add_argument("chapter", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument(
        "--tolerance",
        type=float,
        default=0.25,
        help="相对偏差阈值，默认 25%%；仅用于提示",
    )
    args = ap.parse_args()

    text = read_text(args.chapter)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    actual = metrics(text)

    # 兼容两套画像的字段命名：scripts 版 *_of_files 与 research 版短名
    targets = {
        "dialogue_ratio": profile.get("dialogue_ratio", 0),
        "sentence_length_mean": profile.get(
            "sentence_length_mean_of_files",
            profile.get("sentence_length_mean", 0)),
        "paragraph_length_median": profile.get(
            "paragraph_length_median_of_files",
            profile.get("paragraph_length_median", 0)),
    }

    print("Style Profile advisory")
    for key, target in targets.items():
        value = actual[key]
        if target <= 0:
            status = "NO_BASELINE"
            delta = "-"
        else:
            delta = (value - target) / target
            status = "OK" if abs(delta) <= args.tolerance else "DRIFT"
            delta = f"{delta:+.1%}"
        print(f"[{status}] {key}: chapter={value:.3f} profile={target:.3f} delta={delta}")

    print("\n结论：DRIFT 只表示统计特征偏离画像，不代表文本质量失败；需结合人工/语义审查。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
