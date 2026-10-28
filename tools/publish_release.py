"""Опубликовать собранный APK для автообновления Android-приложения.

Кладёт файл в ``data/releases`` и пишет ``version.json`` с контрольной суммой.
После этого ``/download/android`` и ``/api/v1/app/version`` начинают отдавать
новую версию без перезапуска приложения.

    python tools/publish_release.py dist/uchus-debug.apk \
        --version-code 10 --version-name 1.7.0 --notes "Что нового"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services import release as release_service  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Опубликовать APK")
    parser.add_argument("apk", help="путь к собранному APK")
    parser.add_argument("--version-code", type=int, required=True)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--file-name", default=release_service.DEFAULT_APK_NAME)
    args = parser.parse_args()

    source = Path(args.apk).expanduser().resolve()
    if not source.is_file() or source.stat().st_size == 0:
        print(f"APK не найден: {source}", file=sys.stderr)
        return 1
    if Path(args.file_name).name != args.file_name:
        print("Недопустимое имя файла", file=sys.stderr)
        return 1

    target_dir = release_service.release_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / args.file_name
    shutil.copyfile(source, target)

    metadata = {
        "version_code": int(args.version_code),
        "version_name": args.version_name,
        "file_name": args.file_name,
        "sha256": sha256(target),
        "notes": args.notes,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    release_service.metadata_path().write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    info = release_service.info()
    print("Опубликовано:")
    for key in ("version_code", "version_name", "file_name", "size", "sha256", "published_at"):
        print(f"  {key}: {info[key] if info else '—'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
