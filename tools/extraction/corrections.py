"""التصحيحات اليدوية لكتاب: ملف `corrections.yaml` في مجلد الكتاب، لكل تصحيح سبب مكتوب لا يُقبل بدونه.

كل تصحيح يُطبَّق على مخرج مرحلته بعد بنائه، فإعادة تشغيل المرحلة من الصفر تعيد التصحيح نفسه (idempotent) ولا يضيع بإعادة
الاستخراج. التصحيح الذي لم يعد يصيب شيئًا (مسار زال، أو قيمة سابقة `expect` تغيّرت) خطأ صريح لا تجاهل صامت، فلا تتعفّن
التصحيحات. المخرج يحمل `corrections` بما طُبِّق (المسار وقيمته قبل وبعد وسببه) للمراجعة.

    - stage: examples                 # layout أو objectives أو examples أو checks
      path: [lessons, "2.1", value, 2, representations]   # أرقام = فهرس قائمة، نصوص = مفاتيح (رمز الدرس فيه نقطة فيبقى نصًّا)
      value: [جبري, جدول]
      expect: [جبري]                  # اختياري: القيمة المتوقعة قبل التصحيح؛ غيرها = تصحيح قديم
      reason: ذهبي 2-1 يشمل الجدول (حل معادلة)

حين يكون الهدف غلاف حقل `{value, source, status}` وقيمة التصحيح ليست خريطة تُبدَّل قيمته ويصير مصدره teacher وحالته ok.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from .config import Book

FILE = "corrections.yaml"
MIN_REASON = 8
STAGES = ("layout", "objectives", "examples", "checks")
ENVELOPE = {"value", "source", "status"}


class CorrectionError(ValueError):
    pass


def path_of(book: Book) -> Path:
    return book.out / book.get("corrections", FILE)


def load(book: Book) -> list[dict[str, Any]]:
    """تصحيحات الكتاب بعد فحص شكلها؛ لا ملف = لا تصحيحات."""
    path = path_of(book)
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise CorrectionError(f"{path.name}: يجب أن يكون قائمة")
    errors: list[str] = []
    for i, item in enumerate(raw, 1):
        where = f"{path.name} #{i}"
        if not isinstance(item, dict):
            errors.append(f"{where}: ليس خريطة")
            continue
        if item.get("stage") not in STAGES:
            errors.append(f"{where}: stage خارج {STAGES}")
        p = item.get("path")
        if not (
            isinstance(p, list)
            and p
            and all(isinstance(k, (str, int)) and not isinstance(k, bool) for k in p)
        ):
            errors.append(f"{where}: path قائمة غير فارغة من نصوص وأرقام")
        if "value" not in item:
            errors.append(f"{where}: value مفقود")
        reason = item.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON:
            errors.append(f"{where}: reason مطلوب (نص لا يقل عن {MIN_REASON} أحرف يشرح لماذا)")
    if errors:
        raise CorrectionError("؛ ".join(errors))
    return raw


def _walk(node: Any, keys: list[Any], where: str) -> tuple[Any, Any]:
    """(الحاوية، المفتاح الأخير) للمسار؛ مسار لا يصل خطأ."""
    for key in keys[:-1]:
        node = _child(node, key, where)
    last = keys[-1]
    _child(node, last, where)  # يتحقق من وجود الهدف نفسه
    return node, last


def _child(node: Any, key: Any, where: str) -> Any:
    try:
        if isinstance(node, dict) and isinstance(key, str):
            return node[key]
        if isinstance(node, list) and isinstance(key, int):
            return node[key]
    except (KeyError, IndexError):
        pass
    raise CorrectionError(f"{where}: المسار لا يصل عند {key!r}")


def apply(book: Book, stage: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    """يطبّق تصحيحات المرحلة على `result` في مكانه ويثبت ما طُبِّق في `result["corrections"]`، ويعيده."""
    applied: list[dict[str, Any]] = []
    for i, item in enumerate(load(book), 1):
        if item["stage"] != stage:
            continue
        where = f"{FILE} #{i} ({stage})"
        container, key = _walk(result, item["path"], where)
        before = container[key]
        if "expect" in item and before != item["expect"]:
            raise CorrectionError(f"{where}: تصحيح قديم، القيمة الحالية {before!r} لا تطابق المتوقعة")
        value = copy.deepcopy(item["value"])
        if isinstance(before, dict) and ENVELOPE <= set(before) and not isinstance(value, dict):
            after = {**before, "value": value, "source": "teacher", "status": "ok", "corrected": True}
        else:
            after = value
        container[key] = after
        applied.append(
            {"path": item["path"], "before": before, "after": after, "reason": item["reason"].strip()}
        )
    if applied:
        result["corrections"] = applied
    return applied
