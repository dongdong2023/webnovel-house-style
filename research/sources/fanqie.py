from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import requests

from research.models import NovelRecord

# 番茄页面文本走自定义字体反爬：部分汉字在 HTML 里是私有区(PUA)码点，
# 浏览器里由 woff2 字体渲染回可读汉字。码点与原字一一对应，
# 所以字符数/标点统计是准的，但抓到的书名显示会缺字，
# 用 title_obfuscated 标记；码点跨请求稳定，不影响去重和周度追踪。
PUA_RE = re.compile(r"[\ue000-\uf8ff]")

_STATE_ANCHOR_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*")

# "第85章 85-只是在气沈静芙" -> 85；"番外八 ..." -> 无匹配
CHAPTER_NUM_RE = re.compile(r"第(\d{1,6})章")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

ABSTRACT_MAX_CHARS = 600


def extract_initial_state(html: str) -> dict[str, Any]:
    """从番茄 SSR 页面里抠出 window.__INITIAL_STATE__ 的 JSON 对象。

    番茄是 JS 渲染页，榜单数据不落在 DOM 里，只能从这里取。
    """
    match = _STATE_ANCHOR_RE.search(html)
    if not match:
        raise ValueError(
            "页面里找不到 window.__INITIAL_STATE__，"
            "番茄榜单页结构可能已变化"
        )

    tail = html[match.end():]
    # 状态对象里混有 JS 字面量 undefined，不是合法 JSON，先替换成 null
    tail = tail.replace(":undefined", ":null")

    try:
        state, _ = json.JSONDecoder().raw_decode(tail)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"__INITIAL_STATE__ JSON 解析失败: {exc}"
        ) from exc

    return state


def _clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


def _timestamp_to_iso(value: Any) -> str:
    try:
        return datetime.fromtimestamp(
            int(value), tz=timezone.utc
        ).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FanqieAdapter:
    """番茄榜单适配器：只读公开榜单元数据，不碰正文。"""

    platform = "fanqie"

    def __init__(
        self,
        url: str,
        board_meta: dict | None = None,
        timeout: int = 15,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        self.url = url
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.board_meta = board_meta or {}
        self.board = (
            self.board_meta.get("code")
            or url.rstrip("/").rsplit("/", 1)[-1]
        )

    def fetch(self) -> str:
        response = requests.get(
            self.url,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        response.encoding = (
            response.apparent_encoding or response.encoding
        )
        return response.text

    def parse(self, html: str) -> list[NovelRecord]:
        state = extract_initial_state(html)

        book_list = (
            state.get("rank", {}).get("book_list") or []
        )

        if not book_list:
            raise ValueError(
                "state.rank.book_list 为空，"
                "榜单数据可能换了挂载位置"
            )

        discovered_at = datetime.now(
            timezone.utc
        ).isoformat()

        records: list[NovelRecord] = []

        for index, book in enumerate(book_list, start=1):

            book_id = str(book.get("bookId") or "").strip()
            title = _clean_space(
                str(book.get("bookName") or "")
            )

            # 列表末尾常有一个空占位项
            if not book_id or not title:
                continue

            rank = _safe_int(book.get("currentPos"))
            read_raw = book.get("read_count")

            read_count = None
            if read_raw not in (None, ""):
                try:
                    read_count = float(read_raw)
                except (TypeError, ValueError):
                    read_count = None

            last_chapter_title = _clean_space(
                str(book.get("lastChapterTitle") or "")
            )

            chapter_match = CHAPTER_NUM_RE.search(
                last_chapter_title
            )

            records.append(
                NovelRecord(
                    platform=self.platform,
                    title=title,
                    author=_clean_space(
                        str(book.get("author") or "")
                    ),
                    book_id=book_id,
                    board=self.board,
                    board_name="/".join(
                        part
                        for part in (
                            self.board_meta.get(
                                "gender", ""
                            ),
                            self.board_meta.get(
                                "rank_type", ""
                            ),
                            self.board_meta.get(
                                "category", ""
                            ),
                        )
                        if part
                    ),
                    gender=self.board_meta.get(
                        "gender", ""
                    ),
                    rank_type=self.board_meta.get(
                        "rank_type", ""
                    ),
                    category_name=self.board_meta.get(
                        "category", ""
                    ),
                    rank=rank if rank else index,
                    read_count=read_count,
                    word_count=_safe_int(
                        book.get("wordNumber")
                    ),
                    chapter_count=(
                        int(chapter_match.group(1))
                        if chapter_match
                        else None
                    ),
                    last_chapter_title=last_chapter_title,
                    creation_status=_safe_int(
                        book.get("creationStatus")
                    ),
                    updated_at=_timestamp_to_iso(
                        book.get("lastChapterUpdateTime")
                    ),
                    url=(
                        "https://fanqienovel.com/page/"
                        f"{book_id}"
                    ),
                    description=_truncate(
                        _clean_space(
                            str(book.get("abstract") or "")
                        ),
                        ABSTRACT_MAX_CHARS,
                    ),
                    discovered_at=discovered_at,
                    title_obfuscated=bool(
                        PUA_RE.search(title)
                    ),
                )
            )

        unique: dict[tuple[str, str, str], NovelRecord] = {}

        for record in records:
            unique.setdefault(
                (
                    record.platform,
                    record.board,
                    record.title,
                ),
                record,
            )

        return list(unique.values())
