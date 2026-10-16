from __future__ import annotations

import json
import re
import statistics
from pathlib import Path


CHINESE_RE = re.compile(r"[\u3400-\u9fff]")

SENTENCE_RE = re.compile(
    r"[^。！？!?；;\n]+[。！？!?；;]?"
)

DIALOGUE_RE = re.compile(
    r'[“"「『].*?[”"」』]'
)

PARAGRAPH_SPLIT_RE = re.compile(
    r"\n\s*\n+"
)


def read_text_best(path: Path) -> str:
    """中文语料在 Windows 上 utf-8/gbk 都常见，逐个试。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(
            encoding="gbk", errors="replace"
        )


def analyze(text: str) -> dict:

    chinese_chars = len(
        CHINESE_RE.findall(text)
    )

    sentences = [
        m.group(0)
        for m in SENTENCE_RE.finditer(text)
        if CHINESE_RE.search(m.group(0))
    ]

    sentence_lengths = [
        len(CHINESE_RE.findall(s))
        for s in sentences
    ]

    paragraphs = [
        p.strip()
        for p in PARAGRAPH_SPLIT_RE.split(text)
        if p.strip()
    ]

    paragraph_lengths = [
        len(CHINESE_RE.findall(p))
        for p in paragraphs
    ]

    dialogue_chars = sum(
        len(CHINESE_RE.findall(m.group(0)))
        for m in DIALOGUE_RE.finditer(text)
    )

    return {
        "chinese_chars": chinese_chars,
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),

        "sentence_length": {
            "mean": (
                round(
                    statistics.mean(sentence_lengths), 2
                )
                if sentence_lengths
                else 0
            ),
            "median": (
                round(
                    statistics.median(
                        sentence_lengths
                    ),
                    2,
                )
                if sentence_lengths
                else 0
            ),
        },

        "paragraph_length": {
            "mean": (
                round(
                    statistics.mean(
                        paragraph_lengths
                    ),
                    2,
                )
                if paragraph_lengths
                else 0
            ),
            "median": (
                round(
                    statistics.median(
                        paragraph_lengths
                    ),
                    2,
                )
                if paragraph_lengths
                else 0
            ),
        },

        "dialogue_ratio": (
            round(
                dialogue_chars / chinese_chars, 4
            )
            if chinese_chars
            else 0
        ),
    }


def analyze_corpus(
    corpus_root: Path,
    min_chinese_chars: int = 1000,
) -> dict:

    profiles = []

    for path in corpus_root.rglob("*"):

        if not path.is_file():
            continue

        if path.suffix.lower() not in {".txt", ".md"}:
            continue

        text = read_text_best(path)

        profile = analyze(text)

        if profile["chinese_chars"] < min_chinese_chars:
            continue

        profile["file"] = str(path)

        profiles.append(profile)

    if not profiles:
        raise RuntimeError(
            "没有找到足够的合法语料。"
        )

    return aggregate(profiles)


def aggregate(profiles: list[dict]) -> dict:

    return {
        "version": 1,
        "files": len(profiles),

        "sentence_length_mean": round(
            statistics.mean(
                p["sentence_length"]["mean"]
                for p in profiles
            ),
            2,
        ),

        "sentence_length_median": round(
            statistics.median(
                p["sentence_length"]["median"]
                for p in profiles
            ),
            2,
        ),

        "paragraph_length_mean": round(
            statistics.mean(
                p["paragraph_length"]["mean"]
                for p in profiles
            ),
            2,
        ),

        "paragraph_length_median": round(
            statistics.median(
                p["paragraph_length"]["median"]
                for p in profiles
            ),
            2,
        ),

        "dialogue_ratio": round(
            statistics.mean(
                p["dialogue_ratio"] for p in profiles
            ),
            4,
        ),
    }


def save_profile(
    profile: dict,
    output: Path,
) -> None:

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            profile,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
