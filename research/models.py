from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class NovelRecord:
    platform: str
    title: str
    author: str = ""
    book_id: str = ""
    genre: str = ""
    # 板块码，如 "0_2_1139"（女频在读榜古风世情）
    board: str = ""
    board_name: str = ""
    gender: str = ""
    rank_type: str = ""
    category_name: str = ""
    rank: Optional[int] = None
    read_count: Optional[float] = None
    word_count: Optional[int] = None
    # 从最近章标题"第N章"解析出的章节数
    chapter_count: Optional[int] = None
    last_chapter_title: str = ""
    # 1=连载中 0=已完结
    creation_status: Optional[int] = None
    score: Optional[float] = None
    updated_at: str = ""
    url: str = ""
    description: str = ""
    discovered_at: str = ""
    # 番茄用自定义字体反爬，标题里的字被换成私有区码点，显示会缺字；
    # 码点与原字一一对应且跨请求稳定，长度/标点统计和去重不受影响，
    # 但拿书名去外部检索前要知道有这个问题
    title_obfuscated: bool = False
    hotness_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NovelRecord":
        fields = {
            f for f in cls.__dataclass_fields__
        }
        return cls(
            **{
                k: v
                for k, v in data.items()
                if k in fields
            }
        )


@dataclass
class CorpusItem:
    novel_title: str
    platform: str
    path: str
    rights: str
    source_url: str = ""
    notes: str = ""

    def allowed(self, allowed_rights: set[str]) -> bool:
        return self.rights in allowed_rights

    def to_dict(self) -> dict:
        return asdict(self)
