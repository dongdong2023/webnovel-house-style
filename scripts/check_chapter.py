#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""章长校验：统计非空白字符数（含标题行），核对是否落在目标区间。

用法:
    python check_chapter.py <文件或目录>... [--min 2000] [--max 2400] [--recursive]

统计口径与《章长统一记录》一致：去除所有空白字符（含全角空格、换行）后的字符数。
目录默认只扫当前层的 .txt/.md，--recursive 时递归。任一文件越界退出码为 1。
"""
import argparse
import sys
from pathlib import Path

DEFAULT_MIN, DEFAULT_MAX = 2000, 2400


def count_nonspace(path: Path) -> int | None:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    return sum(1 for ch in text if not ch.isspace())


def collect(paths: list[str], recursive: bool) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            it = path.rglob("*.txt") if recursive else path.glob("*.txt")
            files.extend(f for f in it if f.is_file())
            it = path.rglob("*.md") if recursive else path.glob("*.md")
            files.extend(f for f in it if f.is_file())
        else:
            files.append(path)
    return sorted(dict.fromkeys(files))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="网文章长校验（非空白字符数）")
    ap.add_argument("paths", nargs="+", help="章节文件或所在目录")
    ap.add_argument("--min", type=int, default=DEFAULT_MIN, dest="lo")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX, dest="hi")
    ap.add_argument("--recursive", action="store_true", help="目录递归扫描")
    args = ap.parse_args()

    files = collect(args.paths, args.recursive)
    if not files:
        print("没有找到可检查的文件")
        return 2

    bad = 0
    counts: list[int] = []
    for f in files:
        n = count_nonspace(f)
        if n is None:
            print(f"[无法解码] {f}")
            bad += 1
            continue
        counts.append(n)
        ok = args.lo <= n <= args.hi
        bad += 0 if ok else 1
        mark = "PASS" if ok else ("短" if n < args.lo else "超")
        print(f"[{mark}] {n:>5}  {f.name}")

    if counts:
        print(f"\n共 {len(counts)} 个可读文件：最短 {min(counts)}，最长 {max(counts)}，"
              f"区间 {args.lo}-{args.hi}，越界 {bad} 个")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
