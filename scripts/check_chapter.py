#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""章长校验 + 正文污染扫描。

用法:
    python check_chapter.py <文件或目录>... [--min 2000] [--max 2400] [--recursive]

章长口径与《章长统一记录》一致：去除所有空白字符（含全角空格、换行）后的字符数。
目录默认只扫当前层的 .txt/.md，--recursive 时递归。

污染扫描（默认开启，--no-purity 关闭）：检查正文是否混入与小说无关的内容——
模型客套开场、prompt/系统提示残留、AI自述、正文夹注、Markdown 记号、3 字以上英文。
章长越界或检出污染，退出码均为 1。
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_MIN, DEFAULT_MAX = 2000, 2400

# 污染特征（正则, 名称）。发现即计失败；新增特征往这里加。
CONTAMINATION = [
    (r"好的[，,！!]?.{0,4}(以下|这是)", "模型客套开场"),
    (r"以下是.{0,15}章", "复述章节指令"),
    (r"作为(一个)?AI|AI(助手|语言模型|生成)", "AI自述"),
    (r"非常抱歉|很抱歉[，,]", "模型道歉"),
    (r"(系统|用户)(提示|输入|指令)|system ?prompt|您的要求|按照(您的)?要求|根据(您的)?要求", "提示词残留"),
    (r"ChatGPT|Claude|Gemini|DeepSeek|GLM|Qwen|文心|通义|Kimi", "模型名残留"),
    (r"^\s*（?注[:：]|作者注|译者注|修订说明|修改说明|本章说明", "正文夹注/修改说明"),
    (r"^#{1,6}\s|^\*\*.+\*\*\s*$|^- \S|^```", "Markdown记号"),
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


def scan_contamination(text: str) -> list[str]:
    """返回污染报告行（含行号与摘录）。"""
    hits: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for pattern, name in CONTAMINATION:
            if re.search(pattern, line):
                snippet = line.strip()[:30]
                hits.append(f"行{i} [{name}] {snippet}")
    english = sorted(set(m.group(0) for m in ENGLISH_RE.finditer(text)))
    if english:
        hits.append(f"[英文3字以上] {', '.join(english[:8])}"
                    + ("…" if len(english) > 8 else ""))
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
        else:
            files.append(path)
    return sorted(dict.fromkeys(files))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="网文章长校验 + 正文污染扫描")
    ap.add_argument("paths", nargs="+", help="章节文件或所在目录")
    ap.add_argument("--min", type=int, default=DEFAULT_MIN, dest="lo")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX, dest="hi")
    ap.add_argument("--recursive", action="store_true", help="目录递归扫描")
    ap.add_argument("--no-purity", action="store_true", help="跳过污染扫描")
    args = ap.parse_args()

    files = collect(args.paths, args.recursive)
    if not files:
        print("没有找到可检查的文件")
        return 2

    bad = 0
    counts: list[int] = []
    for f in files:
        text = read_text(f)
        if text is None:
            print(f"[无法解码] {f}")
            bad += 1
            continue
        n = count_nonspace(text)
        counts.append(n)
        problems: list[str] = []
        if not (args.lo <= n <= args.hi):
            problems.append("短" if n < args.lo else "超")
        if not args.no_purity:
            problems.extend(scan_contamination(text))
        if not problems:
            print(f"[PASS] {n:>5}  {f.name}")
        else:
            bad += 1
            head = problems[0] if len(problems) == 1 else f"{len(problems)}项问题"
            print(f"[FAIL:{head}] {n:>5}  {f.name}")
            for p in problems:
                print(f"    {p}")

    if counts:
        print(f"\n共 {len(counts)} 个可读文件：最短 {min(counts)}，最长 {max(counts)}，"
              f"区间 {args.lo}-{args.hi}，章长越界或污染 {bad} 个")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
