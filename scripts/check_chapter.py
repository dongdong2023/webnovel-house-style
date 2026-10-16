#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网文章长校验 + 正文污染扫描。

用法:
    python check_chapter.py <文件或目录>... [--config house-style.toml]
        [--min 2000] [--max 2400] [--recursive] [--json]

默认检查：
1. 非空白字符数是否落在章长区间；
2. 正文污染：模型客套、prompt/系统提示、AI 自述、正文夹注、Markdown、
   未列入白名单的英文连续字母。

退出码：
    0 = 全部通过
    1 = 存在阻断问题（章长越界或污染）
    2 = 参数/文件错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None

DEFAULT_MIN, DEFAULT_MAX = 2000, 2400
DEFAULT_ENGLISH_ALLOWLIST = {
    "APP", "GPS", "USB", "DNA", "NPC", "VIP", "CPU", "GPU",
    "PDF", "URL", "WiFi", "wifi",
}

CONTAMINATION = [
    (re.compile(r"好的[，,！!]?.{0,4}(以下|这是)"), "模型客套开场", "blocking"),
    (re.compile(r"以下是.{0,15}章"), "复述章节指令", "blocking"),
    (re.compile(r"作为(一个)?AI|AI(助手|语言模型|生成)"), "AI自述", "blocking"),
    (re.compile(r"非常抱歉|很抱歉[，,]"), "模型道歉", "blocking"),
    (
        re.compile(
            r"(系统|用户)(提示|输入|指令)|system ?prompt|您的要求|"
            r"按照(您的)?要求|根据(您的)?要求"
        ),
        "提示词残留",
        "blocking",
    ),
    (
        re.compile(r"ChatGPT|Claude|Gemini|DeepSeek|GLM|Qwen|文心|通义|Kimi"),
        "模型名残留",
        "blocking",
    ),
    (
        re.compile(r"^\s*（?注[:：]|作者注|译者注|修订说明|修改说明|本章说明"),
        "正文夹注/修改说明",
        "blocking",
    ),
    (
        re.compile(r"^\s*#{1,6}\s|^\s*\*\*.+\*\*\s*$|^\s*-\s+\S|^\s*\x60{3}"),
        "Markdown记号",
        "blocking",
    ),
]
ENGLISH_RE = re.compile(r"[a-zA-Z]{3,}")


def read_text(path: Path) -> str | None:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def load_config(path: Path | None) -> dict:
    if path is None:
        return {
            "chapter": {"min_chars": DEFAULT_MIN, "max_chars": DEFAULT_MAX},
            "english": {"allowlist": sorted(DEFAULT_ENGLISH_ALLOWLIST)},
        }
    if tomllib is None:
        raise RuntimeError("读取 TOML 配置需要 Python 3.11+")
    with path.open("rb") as f:
        cfg = tomllib.load(f)

    chapter = cfg.setdefault("chapter", {})
    chapter.setdefault("min_chars", DEFAULT_MIN)
    chapter.setdefault("max_chars", DEFAULT_MAX)
    english = cfg.setdefault("english", {})
    english.setdefault("allowlist", sorted(DEFAULT_ENGLISH_ALLOWLIST))
    return cfg


def scan_contamination(
    text: str,
    english_allowlist: set[str] | None = None,
) -> list[dict[str, str]]:
    """返回污染报告；每项包含行号、级别、类型和摘录。"""
    allowlist = english_allowlist or DEFAULT_ENGLISH_ALLOWLIST
    hits: list[dict[str, str]] = []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        for pattern, name, severity in CONTAMINATION:
            if pattern.search(line):
                hits.append({
                    "line": str(i),
                    "type": name,
                    "severity": severity,
                    "snippet": line.strip()[:80],
                })

    english = sorted({
        m.group(0)
        for m in ENGLISH_RE.finditer(text)
        if m.group(0) not in allowlist
    })
    if english:
        hits.append({
            "line": "-",
            "type": "英文3字以上",
            "severity": "blocking",
            "snippet": ", ".join(english[:12]) + ("…" if len(english) > 12 else ""),
        })
    return hits


def count_nonspace(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def collect(paths: list[str], recursive: bool) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            it = path.rglob if recursive else path.glob
            files.extend(f for f in it("*.txt") if f.is_file())
            files.extend(f for f in it("*.md") if f.is_file())
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)
    return sorted(dict.fromkeys(files))


def check_file(
    path: Path,
    min_chars: int,
    max_chars: int,
    purity: bool,
    english_allowlist: set[str],
) -> dict:
    text = read_text(path)
    if text is None:
        return {
            "path": str(path),
            "file": path.name,
            "status": "FAIL",
            "blocking": [{"type": "无法解码", "severity": "blocking"}],
            "advisory": [],
        }

    n = count_nonspace(text)
    blocking: list[dict[str, str]] = []
    advisory: list[dict[str, str]] = []

    if n < min_chars:
        blocking.append({
            "type": "章长过短",
            "severity": "blocking",
            "detail": f"{n} < {min_chars}",
        })
    elif n > max_chars:
        blocking.append({
            "type": "章长过长",
            "severity": "blocking",
            "detail": f"{n} > {max_chars}",
        })

    if purity:
        for hit in scan_contamination(text, english_allowlist):
            if hit["severity"] == "blocking":
                blocking.append(hit)
            else:
                advisory.append(hit)

    return {
        "path": str(path),
        "file": path.name,
        "chars": n,
        "status": "PASS" if not blocking else "FAIL",
        "blocking": blocking,
        "advisory": advisory,
    }


def print_human(results: list[dict], min_chars: int, max_chars: int) -> None:
    for result in results:
        if result["status"] == "PASS":
            print(f'[PASS] {result["chars"]:>5}  {result["file"]}')
            continue

        problems = result["blocking"]
        head = problems[0]["type"] if len(problems) == 1 else f"{len(problems)}项阻断问题"
        print(f'[FAIL:{head}] {result.get("chars", "-"):>5}  {result["file"]}')
        for problem in problems:
            line = f'行{problem["line"]} ' if "line" in problem and problem["line"] != "-" else ""
            detail = f' {problem["detail"]}' if "detail" in problem else ""
            snippet = f' {problem["snippet"]}' if "snippet" in problem else ""
            print(f'    {line}[{problem["type"]}]{detail}{snippet}')

        for problem in result["advisory"]:
            print(f'    [ADVISORY:{problem["type"]}] {problem.get("snippet", "")}')

    readable = [r["chars"] for r in results if "chars" in r]
    bad = sum(r["status"] != "PASS" for r in results)
    if readable:
        print(
            f"\n共 {len(readable)} 个可读文件：最短 {min(readable)}，最长 {max(readable)}，"
            f"区间 {min_chars}-{max_chars}，阻断失败 {bad} 个"
        )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="网文章长校验 + 正文污染扫描")
    ap.add_argument("paths", nargs="+", help="章节文件或所在目录")
    ap.add_argument("--config", type=Path, help="TOML 配置文件，默认 house-style.toml")
    ap.add_argument("--min", type=int, default=None, dest="lo", help="覆盖配置中的最小章长")
    ap.add_argument("--max", type=int, default=None, dest="hi", help="覆盖配置中的最大章长")
    ap.add_argument("--recursive", action="store_true", help="目录递归扫描")
    ap.add_argument("--no-purity", action="store_true", help="跳过污染扫描")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    config_path = args.config
    if config_path is None:
        candidate = Path("house-style.toml")
        config_path = candidate if candidate.exists() else None

    try:
        cfg = load_config(config_path)
        chapter_cfg = cfg["chapter"]
        min_chars = args.lo if args.lo is not None else int(chapter_cfg["min_chars"])
        max_chars = args.hi if args.hi is not None else int(chapter_cfg["max_chars"])
        allowlist = {str(x) for x in cfg.get("english", {}).get("allowlist", [])}
        files = collect(args.paths, args.recursive)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, FileNotFoundError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if not files:
        print("没有找到可检查的文件", file=sys.stderr)
        return 2

    results = [
        check_file(
            f,
            min_chars,
            max_chars,
            purity=not args.no_purity,
            english_allowlist=allowlist,
        )
        for f in files
    ]

    if args.json:
        print(json.dumps({
            "config": {
                "min_chars": min_chars,
                "max_chars": max_chars,
                "purity": not args.no_purity,
            },
            "results": results,
            "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
        }, ensure_ascii=False, indent=2))
    else:
        print_human(results, min_chars, max_chars)

    return 0 if all(r["status"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
