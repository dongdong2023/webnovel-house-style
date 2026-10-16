from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research.settings import DATA_DIR, load_config


def default_allowed_rights() -> set[str]:
    return set(
        load_config()["corpus"]["allowed_rights"]
    )


def sha256_file(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def build_manifest(
    corpus_root: Path,
) -> list[dict]:
    """清点语料目录。默认全部标 user_provided（用户自己的文件），
    外来语料必须手动改 rights，门禁才会放行。"""

    results = []

    for path in corpus_root.rglob("*"):

        if not path.is_file():
            continue

        if path.suffix.lower() not in {".txt", ".md"}:
            continue

        results.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "rights": "user_provided",
            }
        )

    return results


def save_manifest(
    items: list[dict],
    output: Path | None = None,
) -> Path:

    if output is None:
        output = DATA_DIR / "corpus_manifest.json"

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            {
                "version": 1,
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return output


def validate_manifest(
    manifest: list[dict],
    allowed_rights: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:

    if allowed_rights is None:
        allowed_rights = default_allowed_rights()

    allowed = []
    rejected = []

    for item in manifest:

        if item.get("rights") in allowed_rights:
            allowed.append(item)
        else:
            rejected.append(item)

    return allowed, rejected
