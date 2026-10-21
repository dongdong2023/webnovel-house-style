from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

from research.corpus import (
    default_allowed_rights,
    load_manifest,
    sha256_file,
    validate_manifest,
)
from research.models import CorpusItem
from research.settings import DATA_DIR


CHINESE_RE = re.compile(r"[\u3400-\u9fff]")

SENTENCE_RE = re.compile(
    r"[^。！？!?；;…\n]+[。！？!?；;…]?"
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


def _resolve_corpus_path(entry_path: str, corpus_root: Path) -> Path | None:
    """manifest 里的 path 是建单时相对当时工作目录记录的；
    先按原样找，找不到再按文件名到语料目录里找。"""
    raw = Path(entry_path)
    candidates = [raw] if raw.is_absolute() else [raw, corpus_root / raw.name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def analyze_corpus(
    corpus_root: Path,
    min_chinese_chars: int = 1000,
    manifest_path: Path | None = None,
) -> dict:
    """风格分析入口，强制走 Rights Gate（权利门禁）。

    只读取同时满足三条的文件，缺一不可：
    1. 在 corpus_manifest.json 里登记（未登记的文件一律不读）；
    2. rights 命中允许集合（validate_manifest + CorpusItem.allowed 双重校验）；
    3. 文件当前 sha256 与 manifest 记录一致（防登记后被替换）。
    没有 manifest 直接报错，先运行 `python -m research.cli manifest <目录>` 建单。
    """

    if manifest_path is None:
        manifest_path = DATA_DIR / "corpus_manifest.json"

    if not manifest_path.is_file():
        raise RuntimeError(
            f"未找到语料 manifest：{manifest_path}。"
            "请先运行 python -m research.cli manifest <语料目录> 建单，"
            "确认每份语料的 rights 后再 mine。"
        )

    allowed_rights = default_allowed_rights()
    allowed, rejected = validate_manifest(
        load_manifest(manifest_path),
        allowed_rights=allowed_rights,
    )

    profiles = []
    skipped: list[str] = []

    for entry in allowed:
        # manifest 是裸 dict（path/sha256/rights），这里转成 CorpusItem
        # 走 allowed() 做第二道权利校验，避免两处口径漂移
        item = CorpusItem(
            novel_title=Path(entry.get("path", "")).stem,
            platform="local",
            path=entry.get("path", ""),
            rights=entry.get("rights", ""),
        )
        if not item.allowed(allowed_rights):
            skipped.append(f"{item.path}（rights 不被允许）")
            continue

        path = _resolve_corpus_path(item.path, corpus_root)
        if path is None:
            skipped.append(f"{item.path}（文件不存在）")
            continue

        recorded_sha = entry.get("sha256")
        if not recorded_sha or sha256_file(path) != recorded_sha:
            skipped.append(f"{item.path}（sha256 与 manifest 不一致）")
            continue

        profile = analyze(read_text_best(path))

        if profile["chinese_chars"] < min_chinese_chars:
            continue

        profile["file"] = str(path)

        profiles.append(profile)

    if not profiles:
        raise RuntimeError(
            "没有找到足够的合法语料。"
            f"（manifest 拒绝 {len(rejected)} 份，门禁跳过 {len(skipped)} 份）"
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
