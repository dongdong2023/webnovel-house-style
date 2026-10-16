from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from research.models import NovelRecord
from research.settings import DATA_DIR
from research.sources.fanqie import (
    DEFAULT_USER_AGENT,
    FanqieAdapter,
)
from research.sources.fanqie_boards import all_boards


def minmax(values: list[float]) -> dict[float, float]:
    if not values:
        return {}

    lo = min(values)
    hi = max(values)

    if math.isclose(lo, hi):
        return {value: 1.0 for value in values}

    return {
        value: (value - lo) / (hi - lo)
        for value in values
    }


def calculate_hotness(
    records: list[NovelRecord],
    rank_weight: float = 0.35,
    read_weight: float = 0.45,
    freshness_weight: float = 0.20,
) -> list[NovelRecord]:
    """每个分量先各自 min-max 归一化再加权求和。

    不先归一化的话，log1p(在读数) 量级在 10~18，
    会把 0~1 的排名分量彻底淹没，配置里的权重形同虚设。
    某条记录缺字段时跳过该分量并把剩余权重重新归一。
    """

    # 排名取负号：第 1 名 -> 归一化后 1.0
    rank_scores = minmax(
        [
            -float(r.rank)
            for r in records
            if r.rank is not None
        ]
    )

    read_scores = minmax(
        [
            math.log1p(r.read_count)
            for r in records
            if r.read_count is not None
        ]
    )

    for record in records:

        parts: list[tuple[float, float]] = []

        if record.rank is not None:
            parts.append(
                (
                    rank_scores.get(
                        -float(record.rank), 0.0
                    ),
                    rank_weight,
                )
            )

        if record.read_count is not None:
            parts.append(
                (
                    read_scores.get(
                        math.log1p(record.read_count),
                        0.0,
                    ),
                    read_weight,
                )
            )

        # 单次快照里没有历史数据，新鲜度先给常量基础分；
        # data/snapshots/ 攒下多期数据后替换成真实增长率
        parts.append((1.0, freshness_weight))

        total_weight = sum(w for _, w in parts)

        record.hotness_score = (
            sum(s * w for s, w in parts) / total_weight
        )

    normalized = minmax(
        [r.hotness_score for r in records]
    )

    for record in records:
        record.hotness_score = round(
            normalized.get(record.hotness_score, 0.0),
            6,
        )

    return sorted(
        records,
        key=lambda x: x.hotness_score,
        reverse=True,
    )


def save_records(
    records: list[NovelRecord],
    path: Path | None = None,
) -> Path:

    if path is None:
        path = DATA_DIR / "novels.json"

    payload = {
        "version": 2,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "records": [r.to_dict() for r in records],
    }

    text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    # 每次抓取同时落一份带时间戳的快照。
    # novels.json 会被覆盖，快照是更新节奏/增长率分析的数据底座。
    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    snapshot = (
        DATA_DIR / "snapshots" / f"fanqie_{stamp}.json"
    )
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(text, encoding="utf-8")

    return path


def load_records(
    path: Path | None = None,
) -> list[NovelRecord]:

    if path is None:
        path = DATA_DIR / "novels.json"

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    return [
        NovelRecord.from_dict(item)
        for item in payload.get("records", [])
    ]


def discover_boards(
    boards: list[dict],
    *,
    rank_weight: float = 0.35,
    read_weight: float = 0.45,
    freshness_weight: float = 0.20,
    timeout: int = 15,
    user_agent: str = DEFAULT_USER_AGENT,
    delay_seconds: float = 0.8,
    top_per_board: int = 10,
) -> tuple[list[NovelRecord], list[tuple[str, str]]]:
    """轮询全部板块。单个板块失败不拖垮整轮，返回 (records, errors)。

    热度分只在板块内部计算——不同板块的排名和在读量纲不可比。
    """

    all_records: list[NovelRecord] = []
    errors: list[tuple[str, str]] = []

    for index, board in enumerate(boards):

        adapter = FanqieAdapter(
            board["url"],
            board_meta=board,
            timeout=timeout,
            user_agent=user_agent,
        )

        try:
            records = adapter.parse(adapter.fetch())
            records = calculate_hotness(
                records,
                rank_weight=rank_weight,
                read_weight=read_weight,
                freshness_weight=freshness_weight,
            )
            all_records.extend(records[:top_per_board])
        except Exception as exc:
            errors.append((board["code"], str(exc)))

        if index < len(boards) - 1:
            time.sleep(delay_seconds)

    if boards and len(errors) >= max(1, len(boards) // 2):
        preview = "; ".join(
            f"{code}: {msg}" for code, msg in errors[:3]
        )
        raise RuntimeError(
            f"过半板块抓取失败（{len(errors)}/{len(boards)}）: "
            f"{preview}"
        )

    return all_records, errors


def main() -> None:

    from research.settings import load_config

    config = load_config()

    fanqie_cfg = config["sources"]["fanqie"]

    boards = all_boards(
        genders=fanqie_cfg.get("genders"),
        rank_types=fanqie_cfg.get("rank_types"),
    )

    records, errors = discover_boards(
        boards,
        rank_weight=config["hotness"]["rank_weight"],
        read_weight=config["hotness"]["read_weight"],
        freshness_weight=config["hotness"][
            "freshness_weight"
        ],
        timeout=config["research"]["request_timeout"],
        user_agent=config["research"]["user_agent"],
        delay_seconds=fanqie_cfg.get(
            "request_delay_seconds", 0.8
        ),
        top_per_board=fanqie_cfg.get("top_per_board", 10),
    )

    path = save_records(records)

    print(f"[PASS] boards={len(boards)} records={len(records)}")
    if errors:
        print(f"[WARN] failed boards: {len(errors)}")
        for code, msg in errors:
            print(f"  {code}: {msg}")
    print(f"[PASS] database={path}")


if __name__ == "__main__":
    main()
