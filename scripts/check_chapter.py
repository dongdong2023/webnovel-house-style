#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""网文章长校验 + 正文污染扫描 + 合规扫描 + 对话/数字分析。

用法:
    python check_chapter.py <文件或目录>... [--config house-style.toml]
        [--preset hanli_survival|fanqie_fast_pace] [--era ancient|modern]
        [--min 2000] [--max 2400] [--recursive] [--json] [--no-purity]

默认检查：
1. 非空白字符数是否落在章长区间（预设可覆盖）；
2. 正文污染：模型客套、prompt/系统提示、AI 自述、正文夹注、Markdown、
   未列入白名单的英文连续字母；
3. 合规扫描（blocking）：命中 config/compliance_words.txt 的平台红线词；
4. 对话分析（advisory）：主角单次发言超两句告警；
5. 数字提取（advisory/信息）：列出文中数字与量词，供人工核对咬合。

退出码：
    0 = 全部通过
    1 = 存在阻断问题（章长越界、污染、合规命中）
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
PRESET_CHAPTER_RANGES = {
    "hanli_survival": (1900, 2500),
    "fanqie_fast_pace": (1950, 2800),
}
# fanqie_fast_pace 允许交锋场景单次发言到 4 句
PRESET_DIALOGUE_MAX_SENTENCES = {
    "hanli_survival": 2,
    "fanqie_fast_pace": 4,
}
DEFAULT_DIALOGUE_MAX_SENTENCES = 2

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

# 对话：匹配中文引号 “...” 与直引号 "..."
DIALOGUE_RE = re.compile(r"[“\"]([^”\"\n]{1,400})[”\"]")
SENTENCE_SPLIT_RE = re.compile(r"[。！？…]+")

# 数字提取：阿拉伯数字 + 中文数字 + 常见量词
NUMBER_RE = re.compile(
    r"(\d+(?:\.\d+)?|[零一二三四五六七八九十百千万亿两几多半]+)"
    r"(个|位|名|只|条|件|张|块|枚|颗|粒|滴|株|柄|把|座|栋|层|间|家|户|口|"
    r"米|里|公里|丈|尺|寸|步|天|日|月|年|时|时辰|刻|分|秒|"
    r"两|斤|公斤|吨|元|块|文|枚|锭|贯|成|倍|品|阶|级|重|"
    r"人|马|车|船|袋|箱|桶|瓶|碗|盘|桌|椅|扇|盏|炷)?"
)


def read_text(path: Path) -> str | None:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def load_config(path: Path | None) -> dict:
    cfg: dict = {
        "workspace": {},
        "chapter": {"min_chars": DEFAULT_MIN, "max_chars": DEFAULT_MAX},
        "english": {"ancient": {"allowlist": []}, "modern": {"allowlist": []}},
        "compliance": {},
        "presets": {},
    }
    if path is None:
        return cfg
    if tomllib is None:
        raise RuntimeError("读取 TOML 配置需要 Python 3.11+")
    with path.open("rb") as f:
        loaded = tomllib.load(f)

    # 兼容旧格式：顶层 [english] allowlist 视为 modern
    if "english" in loaded and "allowlist" in loaded["english"]:
        loaded["english"] = {
            "ancient": {"allowlist": []},
            "modern": {"allowlist": loaded["english"]["allowlist"]},
        }
    for key in ("workspace", "chapter", "english", "compliance", "presets"):
        if key in loaded:
            if isinstance(cfg[key], dict) and isinstance(loaded[key], dict):
                cfg[key].update(loaded[key])
            else:
                cfg[key] = loaded[key]
    cfg["chapter"].setdefault("min_chars", DEFAULT_MIN)
    cfg["chapter"].setdefault("max_chars", DEFAULT_MAX)
    return cfg


def load_compliance_words(repo_root: Path, cfg: dict) -> list[str]:
    """读取合规词表；文件不存在返回空列表。"""
    rel = cfg.get("compliance", {}).get("wordlist", "config/compliance_words.txt")
    p = repo_root / rel if not Path(rel).is_absolute() else Path(rel)
    if not p.is_file():
        return []
    words = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def scan_compliance(text: str, words: list[str]) -> list[dict[str, str]]:
    """合规扫描：命中即 blocking。"""
    hits: list[dict[str, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for w in words:
            if w and w in line:
                start = max(0, line.find(w) - 12)
                hits.append({
                    "line": str(i),
                    "type": "合规红线词",
                    "severity": "blocking",
                    "snippet": f"…{line[start:start + 40]}…（命中：{w}）",
                })
                break  # 每行只报一次
    return hits


def scan_contamination(
    text: str,
    english_allowlist: set[str] | None = None,
) -> list[dict[str, str]]:
    """返回污染报告；每项包含行号、级别、类型和摘录。"""
    allowlist = english_allowlist or set()
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


def analyze_dialogue(text: str, max_sentences: int) -> list[dict[str, str]]:
    """对话分析：单次发言超句数上限 → advisory 告警。"""
    advisories: list[dict[str, str]] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for m in DIALOGUE_RE.finditer(line):
            speech = m.group(1).strip()
            sentences = [s for s in SENTENCE_SPLIT_RE.split(speech) if s.strip()]
            if len(sentences) > max_sentences:
                advisories.append({
                    "line": str(i),
                    "type": "对话超句数",
                    "severity": "advisory",
                    "snippet": f"单次发言{len(sentences)}句（上限{max_sentences}）：{speech[:40]}…",
                })
    return advisories


def extract_numbers(text: str, limit: int = 60) -> list[dict[str, str]]:
    """数字提取：列出文中数字+量词，供人工核对咬合。返回去重后的列表。"""
    seen: dict[str, dict[str, str]] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for m in NUMBER_RE.finditer(line):
            num, unit = m.group(1), m.group(2) or ""
            # 过滤纯序号噪音：单个小数字无量词且常见于标点环境的跳过
            key = f"{num}{unit}"
            if key not in seen:
                seen[key] = {
                    "line": str(i),
                    "value": key,
                    "context": line.strip()[max(0, m.start() - 10):m.end() + 10][:60],
                }
            if len(seen) >= limit:
                return list(seen.values())
    return list(seen.values())


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


def resolve_chapter_range(
    cfg: dict,
    preset: str | None,
    lo: int | None,
    hi: int | None,
) -> tuple[int, int]:
    """章长区间优先级：命令行 --min/--max > --preset > TOML active_preset > [chapter] 默认。"""
    active = preset or cfg.get("workspace", {}).get("active_preset")
    if lo is not None and hi is not None:
        return lo, hi
    presets_cfg = cfg.get("presets", {})
    if active and active in presets_cfg:
        pc = presets_cfg[active].get("chapter", {})
        p_lo = pc.get("min_chars")
        p_hi = pc.get("max_chars")
        if p_lo is not None and p_hi is not None:
            return (lo if lo is not None else int(p_lo),
                    hi if hi is not None else int(p_hi))
    if active in PRESET_CHAPTER_RANGES and lo is None and hi is None:
        return PRESET_CHAPTER_RANGES[active]
    chapter_cfg = cfg.get("chapter", {})
    return (lo if lo is not None else int(chapter_cfg.get("min_chars", DEFAULT_MIN)),
            hi if hi is not None else int(chapter_cfg.get("max_chars", DEFAULT_MAX)))


def resolve_allowlist(cfg: dict, era: str | None) -> set[str]:
    active_era = era or cfg.get("workspace", {}).get("active_era", "modern")
    english_cfg = cfg.get("english", {})
    era_cfg = english_cfg.get(active_era, {})
    return {str(x) for x in era_cfg.get("allowlist", [])}


def check_file(
    path: Path,
    min_chars: int,
    max_chars: int,
    purity: bool,
    english_allowlist: set[str],
    compliance_words: list[str] | None = None,
    dialogue_max_sentences: int = DEFAULT_DIALOGUE_MAX_SENTENCES,
) -> dict:
    compliance_words = compliance_words or []
    text = read_text(path)
    if text is None:
        return {
            "path": str(path),
            "file": path.name,
            "status": "FAIL",
            "blocking": [{"type": "无法解码", "severity": "blocking"}],
            "advisory": [],
            "numbers": [],
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

    # 合规扫描：命中即 blocking
    for hit in scan_compliance(text, compliance_words):
        blocking.append(hit)

    # 对话分析：advisory
    advisory.extend(analyze_dialogue(text, dialogue_max_sentences))

    # 数字提取：信息项，供人工核对
    numbers = extract_numbers(text)

    return {
        "path": str(path),
        "file": path.name,
        "chars": n,
        "status": "PASS" if not blocking else "FAIL",
        "blocking": blocking,
        "advisory": advisory,
        "numbers": numbers,
    }


def print_human(results: list[dict], min_chars: int, max_chars: int,
                show_numbers: bool = True) -> None:
    for result in results:
        if result["status"] == "PASS":
            print(f'[PASS] {result["chars"]:>5}  {result["file"]}')
        else:
            problems = result["blocking"]
            head = problems[0]["type"] if len(problems) == 1 else f"{len(problems)}项阻断问题"
            print(f'[FAIL:{head}] {result.get("chars", "-"):>5}  {result["file"]}')
            for problem in problems:
                line = f'行{problem["line"]} ' if problem.get("line", "-") != "-" else ""
                detail = f' {problem["detail"]}' if "detail" in problem else ""
                snippet = f' {problem["snippet"]}' if "snippet" in problem else ""
                print(f'    {line}[{problem["type"]}]{detail}{snippet}')

        for problem in result["advisory"]:
            line = f'行{problem["line"]} ' if problem.get("line", "-") != "-" else ""
            print(f'    [ADVISORY:{problem["type"]}] {line}{problem.get("snippet", "")}')

        if show_numbers and result.get("numbers"):
            nums = result["numbers"][:20]
            preview = "、".join(x["value"] for x in nums)
            extra = f"…（共{len(result['numbers'])}个）" if len(result["numbers"]) > 20 else ""
            print(f'    [数字] {preview}{extra}')

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

    ap = argparse.ArgumentParser(description="网文章长校验 + 正文污染/合规扫描 + 对话/数字分析")
    ap.add_argument("paths", nargs="+", help="章节文件或所在目录")
    ap.add_argument("--config", type=Path, help="TOML 配置文件，默认 house-style.toml")
    ap.add_argument("--preset", choices=["hanli_survival", "fanqie_fast_pace"],
                    default=None, help="题材预设：覆盖章长区间与对话句数上限")
    ap.add_argument("--era", choices=["ancient", "modern"], default=None,
                    help="时代背景：决定英文白名单（ancient 为空）")
    ap.add_argument("--min", type=int, default=None, dest="lo", help="覆盖配置中的最小章长")
    ap.add_argument("--max", type=int, default=None, dest="hi", help="覆盖配置中的最大章长")
    ap.add_argument("--recursive", action="store_true", help="目录递归扫描")
    ap.add_argument("--no-purity", action="store_true", help="跳过污染扫描")
    ap.add_argument("--no-numbers", action="store_true", help="不输出数字提取列表")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    config_path = args.config
    if config_path is None:
        candidate = Path("house-style.toml")
        config_path = candidate if candidate.exists() else None
    repo_root = config_path.parent if config_path else Path(".")

    try:
        cfg = load_config(config_path)
        min_chars, max_chars = resolve_chapter_range(cfg, args.preset, args.lo, args.hi)
        allowlist = resolve_allowlist(cfg, args.era)
        compliance_words = load_compliance_words(repo_root, cfg)
        active_preset = args.preset or cfg.get("workspace", {}).get("active_preset")
        dialogue_max = PRESET_DIALOGUE_MAX_SENTENCES.get(
            active_preset or "", DEFAULT_DIALOGUE_MAX_SENTENCES)
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
            compliance_words=compliance_words,
            dialogue_max_sentences=dialogue_max,
        )
        for f in files
    ]

    if args.json:
        print(json.dumps({
            "config": {
                "min_chars": min_chars,
                "max_chars": max_chars,
                "preset": active_preset,
                "era": args.era or cfg.get("workspace", {}).get("active_era"),
                "purity": not args.no_purity,
                "compliance_words": len(compliance_words),
            },
            "results": results,
            "status": "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL",
        }, ensure_ascii=False, indent=2))
    else:
        print_human(results, min_chars, max_chars, show_numbers=not args.no_numbers)

    return 0 if all(r["status"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
