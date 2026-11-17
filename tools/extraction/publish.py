"""مرحلتا load وpublish: تصلان خط الاستخراج بالطبقة القانونية في Django بأوامر الإدارة نفسها، فلا منطق ثانٍ للتحميل ولا للرفع.

- `load`: يشتق فهرس الكتاب من سجلات الدروس (`build_course_index <المقرر>`، إن كان `load.index` مفعّلًا) ثم يحمّل المقرر بالمحمِّل الواحد (`load_course`).
- `publish`: ينشر مقاطع الأمثلة (`dirs.<publish.clips>`) إلى تخزين الأصول (`publish_assets`)؛ يلزمه المقرر محمَّلًا فيأتي بعد `load`.

الأمران يعملان على قاعدة البيانات والتخزين اللذين تحددهما بيئة التشغيل (`DATABASE_URL` و`ASSETS_*`)، كأنهما شُغِّلا يدويًا. الشيفرة هنا لا
تستورد Django (تبقى الأداة مستقلة عنه)، وتستدعي `manage.py` في عملية فرعية بلا نافذة. ختم المرحلة يشمل بصمة الوجهة (لا القيم)، فتحميل القاعدة
المحلية لا يُسقط تحميل الإنتاج.

الإعداد (كلاهما اختياري، ووجوده يُدخلهما في `all`): `load: {course, index}` و`publish: {course, clips}` (مفتاح من `dirs`) و`django: {root, python}`
(الافتراضي جذر المستودع ومفسّر العملية الحالية).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import HERE, Book

REPO = HERE.parent.parent
SLUG = re.compile(r"^[a-z0-9-]+$")
# ما تتغير به وجهة المرحلة (أسماء المتغيرات تُبصَم قيمها ولا تُحفظ ولا تُطبع)
TARGET_ENV = {
    "load": ("DATABASE_URL", "DJANGO_SETTINGS_MODULE"),
    "publish": (
        "DATABASE_URL",
        "DJANGO_SETTINGS_MODULE",
        "ASSETS_STORAGE",
        "ASSETS_LOCAL_ROOT",
        "ASSETS_S3_ENDPOINT",
        "ASSETS_S3_BUCKET",
    ),
}

Runner = Callable[
    [Book, list[str]], str
]  # (الكتاب، وسائط manage.py) -> مخرج الأمر؛ يرفع PublishError عند فشله


class PublishError(RuntimeError):
    pass


def errors(cfg: dict[str, Any]) -> list[str]:
    """أخطاء إعداد load وpublish وdjango (قائمة فارغة = سليم أو غائب). لا يلمس القرص."""
    errs: list[str] = []
    for stage in ("load", "publish"):
        node = cfg.get(stage)
        if node is None:
            continue
        if not isinstance(node, dict):
            errs.append(f"{stage} يجب أن يكون خريطة")
            continue
        if not isinstance(node.get("course"), str) or not SLUG.match(node["course"]):
            errs.append(f"{stage}.course رمز مقرر (أحرف لاتينية صغيرة وأرقام وشرطات)")
    if isinstance(cfg.get("publish"), dict):
        clips = cfg["publish"].get("clips")
        if clips not in cfg.get("dirs", {}):
            errs.append("publish.clips يجب أن يسمّي مفتاحًا من dirs")
    if isinstance(cfg.get("load"), dict) and not isinstance(cfg["load"].get("index", False), bool):
        errs.append("load.index منطقي")
    if "django" in cfg and not isinstance(cfg["django"], dict):
        errs.append("django يجب أن يكون خريطة")
    return errs


def configured(book: Book, stage: str) -> bool:
    return isinstance(book.get(stage), dict)


def _django(book: Book) -> tuple[Path, str]:
    cfg = book.get("django", {})
    root = Path(cfg.get("root", REPO))
    return (root if root.is_absolute() else book.root / root), cfg.get("python", sys.executable)


def run_manage(book: Book, args: list[str]) -> str:
    """يشغّل `manage.py <args>` في جذر المستودع بلا نافذة، ويعيد مخرجه أو يرفع PublishError بمخرج الخطأ."""
    root, python = _django(book)
    if not (root / "manage.py").is_file():
        raise PublishError(f"لا manage.py في {root}")
    proc = subprocess.run(
        [python, "manage.py", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    if proc.returncode:
        detail = (proc.stderr.strip() or proc.stdout.strip()).splitlines()
        raise PublishError(f"فشل {args[0]}: {detail[-1] if detail else f'رمز الخروج {proc.returncode}'}")
    return proc.stdout.strip()


def target_token(stage: str) -> str:
    """بصمة وجهة المرحلة من البيئة: تدخل ختمها فتتغير بتغيّر القاعدة أو التخزين المستهدفين، ولا تكشف قيمًا."""
    h = hashlib.sha256()
    for name in TARGET_ENV[stage]:
        h.update(f"{name}={os.environ.get(name, '')}\n".encode())
    return h.hexdigest()


def build_load(book: Book, lessons_dir: Path, run: Runner | None = None) -> dict[str, Any]:
    run = run or run_manage
    cfg = book["load"]
    index = None
    if cfg.get("index", False):
        index = run(
            book,
            [
                "build_course_index",
                cfg["course"],
                "--source",
                str(book.root),
                "--lessons-dir",
                str(lessons_dir),
            ],
        )
    loaded = run(book, ["load_course", cfg["course"]])
    return {"course": cfg["course"], "index": index, "load": loaded}


def build_publish(book: Book, run: Runner | None = None) -> dict[str, Any]:
    run = run or run_manage
    cfg = book["publish"]
    source = book.dir(cfg["clips"])
    if not source.is_dir():
        raise PublishError(f"مجلد المقاطع غير موجود: dirs.{cfg['clips']}")
    reported = run(book, ["publish_assets", cfg["course"], "--source", str(source)])
    return {"course": cfg["course"], "clips": cfg["clips"], "publish": reported}


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    """سطر الملخص: المقرر وأول سطر من تقرير كل أمر."""
    out: dict[str, Any] = {}
    for key, value in result.items():
        out[key] = value.splitlines()[0] if key in ("index", "load", "publish") and value else value
    return out


def write_result(book: Book, stage: str, result: dict[str, Any]) -> None:
    path = book.output(stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
