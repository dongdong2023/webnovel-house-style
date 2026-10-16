#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本地真人网文语料提取可解释的风格画像。"""
from __future__ import annotations
import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

SENTENCE_RE = re.compile(r"[^。！？!?；;…\n]+[。！？!?；;…]?")
CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
DIALOGUE_RE = re.compile(r'[“"「『].*?[”"」』]')
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")
WORDLIKE_RE = re.compile(r"[\u3400-\u9fff]{2,6}")

def read_text(path: Path) -> str | None:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None

def percentile(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    frac = index - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac

def analyze(text: str) -> dict:
    compact = re.sub(r"\s+", "", text)
    paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    sentences = [re.sub(r"\s+", "", m.group(0)) for m in SENTENCE_RE.finditer(text) if CHINESE_RE.search(m.group(0))]
    sentence_lengths = [len(CHINESE_RE.findall(s)) for s in sentences if s]
    chinese_chars = len(CHINESE_RE.findall(text))
    dialogue_chars = sum(len(CHINESE_RE.findall(m.group(0))) for m in DIALOGUE_RE.finditer(text))
    punctuation = Counter(ch for ch in text if ch in "，。！？；：、")
    wordlike = Counter(WORDLIKE_RE.findall(text))
    return {
        "version": 1,
        "files": 1,
        "chars_nonspace": len(compact),
        "chinese_chars": chinese_chars,
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "dialogue_chars": dialogue_chars,
        "dialogue_ratio": round(dialogue_chars / chinese_chars, 4) if chinese_chars else 0,
        "sentence_length": {
            "mean": round(statistics.mean(sentence_lengths), 2) if sentence_lengths else 0,
            "median": round(statistics.median(sentence_lengths), 2) if sentence_lengths else 0,
            "p25": round(percentile(sentence_lengths, 0.25), 2),
            "p75": round(percentile(sentence_lengths, 0.75), 2),
            "max": max(sentence_lengths, default=0),
        },
        "paragraph_length_chars": {
            "median": round(statistics.median([len(CHINESE_RE.findall(p)) for p in paragraphs]), 2) if paragraphs else 0,
            "p75": round(percentile([len(CHINESE_RE.findall(p)) for p in paragraphs], 0.75), 2),
        },
        "punctuation_per_1000_chinese": {
            k: round(v / chinese_chars * 1000, 2) if chinese_chars else 0
            for k, v in punctuation.items()
        },
        "common_2_to_6_char_phrases": [
            {"phrase": phrase, "count": count}
            for phrase, count in wordlike.most_common(30)
            if count >= 3
        ],
    }

def merge(analyses: list[dict]) -> dict:
    if not analyses:
        return {"version": 1, "files": 0, "chars_nonspace": 0, "chinese_chars": 0}
    total_chars = sum(a["chars_nonspace"] for a in analyses)
    total_chinese = sum(a["chinese_chars"] for a in analyses)
    total_dialogue = sum(a["dialogue_chars"] for a in analyses)
    sentence_means = [a["sentence_length"]["mean"] for a in analyses if a["sentences"]]
    paragraph_medians = [a["paragraph_length_chars"]["median"] for a in analyses if a["paragraphs"]]
    punc = Counter()
    phrases = Counter()
    for a in analyses:
        for k, v in a["punctuation_per_1000_chinese"].items():
            punc[k] += v * a["chinese_chars"] / 1000
        for item in a["common_2_to_6_char_phrases"]:
            phrases[item["phrase"]] += item["count"]
    return {
        "version": 1,
        "files": len(analyses),
        "chars_nonspace": total_chars,
        "chinese_chars": total_chinese,
        "paragraphs": sum(a["paragraphs"] for a in analyses),
        "sentences": sum(a["sentences"] for a in analyses),
        "dialogue_ratio": round(total_dialogue / total_chinese, 4) if total_chinese else 0,
        "sentence_length_mean_of_files": round(statistics.mean(sentence_means), 2) if sentence_means else 0,
        "paragraph_length_median_of_files": round(statistics.mean(paragraph_medians), 2) if paragraph_medians else 0,
        "punctuation_per_1000_chinese": {k: round(v / total_chinese * 1000, 2) if total_chinese else 0 for k, v in punc.items()},
        "common_2_to_6_char_phrases": [{"phrase": phrase, "count": count} for phrase, count in phrases.most_common(50) if count >= 3],
    }

def collect(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md"})

def main() -> int:
    ap = argparse.ArgumentParser(description="从本地网文语料提取风格画像")
    ap.add_argument("corpus", type=Path, help="语料目录")
    ap.add_argument("--output", type=Path, default=Path("style_profile.json"))
    args = ap.parse_args()
    if not args.corpus.is_dir():
        print(f"[ERROR] 语料目录不存在：{args.corpus}")
        return 2
    files = collect(args.corpus)
    analyses = []
    skipped = 0
    for path in files:
        text = read_text(path)
        if text is None:
            skipped += 1
            continue
        analyses.append(analyze(text))
    profile = merge(analyses)
    profile["skipped_files"] = skipped
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[PASS] 分析 {profile['files']} 个文件，{profile['chars_nonspace']} 个非空白字符 → {args.output}")
    if skipped:
        print(f"[WARN] {skipped} 个文件无法解码")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
