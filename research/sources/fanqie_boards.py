from __future__ import annotations

# 番茄榜单板块表，提取自 fanqienovel.com/rank 页面导航（2026-10-16）。
# 板块码: /rank/{gender}{type}_{category}
#   gender: 0=女频 1=男频
#   type:   1=新书榜（上升期新书） 2=在读榜（累计热读，含完结书）

MALE_CATEGORIES = {
    "1141": "西方奇幻",
    "1140": "东方仙侠",
    "8": "科幻末世",
    "261": "都市日常",
    "124": "都市修真",
    "1014": "都市高武",
    "273": "历史古代",
    "27": "战神赘婿",
    "263": "都市种田",
    "258": "传统玄幻",
    "272": "历史脑洞",
    "539": "悬疑脑洞",
    "262": "都市脑洞",
    "257": "玄幻脑洞",
    "751": "悬疑灵异",
    "504": "抗战谍战",
    "746": "游戏体育",
    "718": "动漫衍生",
    "1016": "男频衍生",
}

FEMALE_CATEGORIES = {
    "1139": "古风世情",
    "8": "科幻末世",
    "746": "游戏体育",
    "1015": "女频衍生",
    "248": "玄幻言情",
    "23": "种田",
    "79": "年代",
    "267": "现言脑洞",
    "246": "宫斗宅斗",
    "539": "悬疑脑洞",
    "253": "古言脑洞",
    "24": "快穿",
    "749": "青春甜宠",
    "745": "星光璀璨",
    "747": "女频悬疑",
    "750": "职场婚恋",
    "748": "豪门总裁",
    "1017": "民国言情",
}

GENDER_PREFIX = {"0": "女频", "1": "男频"}
RANK_TYPES = {"1": "新书榜", "2": "在读榜"}

BASE_URL = "https://fanqienovel.com/rank"


def all_boards(
    genders: list[str] | None = None,
    rank_types: list[str] | None = None,
) -> list[dict]:

    boards: list[dict] = []

    for prefix, gender in GENDER_PREFIX.items():
        if genders and gender not in genders:
            continue

        categories = (
            MALE_CATEGORIES
            if gender == "男频"
            else FEMALE_CATEGORIES
        )

        for digit, rank_type in RANK_TYPES.items():
            if rank_types and rank_type not in rank_types:
                continue

            for cat_id, cat_name in categories.items():
                code = f"{prefix}_{digit}_{cat_id}"
                boards.append(
                    {
                        "code": code,
                        "url": f"{BASE_URL}/{code}",
                        "gender": gender,
                        "rank_type": rank_type,
                        "category": cat_name,
                    }
                )

    return boards


def find_board(code: str) -> dict | None:
    for board in all_boards():
        if board["code"] == code:
            return board
    return None
