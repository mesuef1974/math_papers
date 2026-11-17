"""تمثيلات الأمثلة (جدول/بياني/جبري/سياق حياتي) بالرؤية: سلسلة تمريرات تُحسِّن قائمة كل مثال، ثم تتمة المثال الممتد على صفحتين.

كل تمريرة تقرأ مجلد رؤية (مفتاح في dirs) وتكتب آخر بالاسم نفسه لكل صفحة، فلا يُمَسّ مجلد سابق؛ ومن وُجد ملف صفحته لا يُعاد (مستأنَف).
الرؤية نفسها مُحقَنة: `ask(صورة، سؤال، مخطط) -> dict` (جواب الخادم المحلي بمخطط JSON)، فالمنطق يُختبر بجواب مختلق ولا يلزمه نموذج.
المقاطع المصغّرة `<صفحة>_<ك>_thumb.png` في dirs.crops (من مرحلة رؤية الأمثلة)؛ والتتمات `cont_<صفحة>.png` تُكتب فيه.

الإعداد `reps` في book.yaml:
- questions: أسئلة تتقدم على الافتراضية بالمعرّف (انظر QUESTIONS).
- passes: قائمة مرتبة. kind=replace (يستبدل تمثيلًا واحدًا بجواب سؤال واحد بلا تصويت)، أو add (يضيف التمثيل الغائب إن أجاب أحد أسئلته
  بنعم بأغلبية ثلاث إجابات، لأن النموذج غير حتمي). src وdst مفتاحا dirs، lessons بادئات معرّفات الدروس (فارغة = كل صفحات المجلد)،
  previous اسم الحقل الذي تُحفظ فيه القائمة السابقة، questions: التمثيل -> معرّفات الأسئلة.
- continuation: dst، groups (لكل مجموعة دروس lessons وsources بأولوية وquestions)، وعتبات الصورة (badge وright_x وthumb_x وtop وmin_gap
  وno_badge_bottom). numpy وPillow يُستورَدان كسولين وغيابهما يعطل التتمة وحدها.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import Book

Ask = Callable[[Path, str, dict[str, Any]], dict[str, Any]]


def schema(name: str, props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {"type": "object", "properties": props, "required": list(props)},
        },
    }


YES_NO = schema("y", {"yes": {"type": "boolean"}})
CONT = schema("c", {"continues": {"type": "boolean"}, "n": {"type": "integer"}})

QUESTIONS: dict[str, str] = {
    "table": "هل يظهر في هذه الصورة جدول قيم (صفوف وأعمدة أرقام)؟",
    "axes": "هل يظهر في هذه الصورة رسم بياني (محوران إحداثيان ومنحنى أو نقاط)؟",
    "context": (
        "هل المثال في هذه الصورة مسألة تطبيقية من الحياة الواقعية (نص لفظي عن موقف حقيقي مثل كرة أو أرضية أو تكلفة) "
        "وليس تعريفًا أو تمثيلًا مجردًا؟"
    ),
    "graphic": (
        "هل يظهر في هذه الصورة رسم بياني أو شكل رياضي توضيحي: محوران إحداثيان مع منحنى أو نقاط أو أشكال على مستوى إحداثي، "
        "أو شكل هندسي مرسوم (مثلثات أو مضلعات أو دوائر أو تحويل لشكل) أو مخطط مرسوم للمسألة؟ "
        "لا يكفي نص أو معادلات أو جدول وحده."
    ),
    "algebra": (
        "هل تُجرى في هذه الصورة خطوات جبرية على صيغة دالة: تعويض قيم مكان الرموز، أو استخراج معاملات من صيغة (مثل h وk وa)، "
        "أو تحويل صيغة إلى أخرى، أو حل معادلة؟"
    ),
    "solve": "هل يُطلب في هذه الصورة إيجاد حلول معادلة (قيم x التي تحقق المعادلة)؟",
    "geo_graphic": (
        "هل يظهر في هذه الصورة أي شكل مرسوم: شكل هندسي (مثلث أو مضلع أو دائرة أو مستطيل بأبعاد مكتوبة) أو مستوى إحداثي مع نقاط أو أشكال "
        "أو رسم توضيحي للمسألة أو صورة مع قياساتها؟ يكفي رسم واحد. لا يكفي نص أو معادلات وحدها."
    ),
    "geo_algebra": (
        "هل تحتوي هذه الصورة على علاقة رياضية مكتوبة بالرموز أو الأرقام، مثل مساواة بين كسرين أو قيمة معامل قياس "
        "(k = s/r أو 4/2 = 2) أو معادلة أو عملية حسابية؟"
    ),
    "geo_context": (
        "هل المسألة في هذه الصورة عن موقف أو شيء من الحياة الواقعية (مثل غرفة أو مكتبة أو أثاث أو مبنى أو مخطط حقيقي أو سعر أو حركة)، "
        "لا عن أشكال هندسية مجردة؟"
    ),
    "continue": "هل يظهر في هذه الصورة نص «تابع المثال» متبوعًا برقم؟ إن ظهر فاكتب الرقم في n وإلا فاكتب 0.",
}
CONTINUATION_DEFAULTS: dict[str, Any] = {
    "badge": [0, 105, 180],  # لون شارة المثال الزرقاء
    "right_x": [0.870, 0.940],  # شارة العمود الأيمن
    "thumb_x": [0.280, 0.400],  # شارة صورة الطالب المصغّرة (موضعها يتأرجح قليلًا فالنافذة أوسع)
    "top": 0.125,  # أعلى صفحة الطالب نسبةً لارتفاع الصفحة
    "min_gap": 140,  # أدنى ارتفاع يُعدّ تتمة
    "no_badge_bottom": 0.60,  # قاع المنطقة في صفحة بلا شارة
}
PASS_KINDS = ("replace", "add")


def settings(book: Book) -> dict[str, Any]:
    return book.get("reps", {})


def errors(cfg: dict[str, Any]) -> list[str]:
    """أخطاء قسم reps (قائمة فارغة = سليم أو غائب): المفاتيح والأسئلة المشار إليها يجب أن توجد. لا يلمس القرص."""
    reps = cfg.get("reps")
    if reps is None:
        return []
    if not isinstance(reps, dict):
        return ["reps ليس خريطة"]
    errs: list[str] = []
    dirs = cfg.get("dirs", {})
    known = set(QUESTIONS) | set(reps.get("questions", {}))

    def dir_key(where: str, key: Any) -> None:
        if key not in dirs:
            errs.append(f"{where}: مفتاح dirs غير معرَّف ({key})")

    def questions(where: str, spec: Any) -> None:
        if not isinstance(spec, dict) or not spec:
            errs.append(f"{where}.questions خريطة غير فارغة")
            return
        for name, ids in spec.items():
            if not isinstance(ids, list) or not ids:
                errs.append(f"{where}.questions.{name} قائمة غير فارغة")
                continue
            errs.extend(f"{where}: سؤال غير معرَّف ({i})" for i in ids if i not in known)

    for i, p in enumerate(reps.get("passes", [])):
        where = f"reps.passes[{i}]"
        if p.get("kind") not in PASS_KINDS:
            errs.append(f"{where}.kind خارج {PASS_KINDS}")
            continue
        dir_key(where, p.get("src"))
        dir_key(where, p.get("dst"))
        questions(where, p.get("questions"))
        if p["kind"] == "replace" and len(p.get("questions", {})) != 1:
            errs.append(f"{where}: replace يلزمه تمثيل واحد")
    cont = reps.get("continuation")
    if cont is not None:
        dir_key("reps.continuation", cont.get("dst"))
        for j, g in enumerate(cont.get("groups", [])):
            where = f"reps.continuation.groups[{j}]"
            for s in g.get("sources", []):
                dir_key(where, s)
            questions(where, g.get("questions"))
    return errs


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def question(book: Book, qid: str) -> str:
    return {**QUESTIONS, **settings(book).get("questions", {})}[qid]


def vote(ask: Ask, image: Path, text: str, tries: int = 3) -> bool:
    """أجوبة النموذج غير حتمية (نعم واحدة من ست على سؤال بعينه)، فالقرار بأغلبية ثلاث إجابات."""
    return sum(bool(ask(image, text, YES_NO).get("yes")) for _ in range(tries)) * 2 > tries


def lesson_pages(book: Book, prefixes: list[str] | None) -> set[int]:
    layout = _json(book.output("layout"))
    return {
        p
        for rec in layout["lessons"]
        if rec["pages_pdf"] and (not prefixes or any(str(rec["id"]).startswith(x) for x in prefixes))
        for p in range(rec["pages_pdf"][0], rec["pages_pdf"][1] + 1)
    }


def thumb(book: Book, page: int, k: int) -> Path:
    return book.dir("crops") / f"{page:04d}_{k}_thumb.png"


def run_pass(book: Book, ask: Ask, spec: dict[str, Any]) -> dict[str, int]:
    """تمريرة واحدة على صفحات src التي لها ملف؛ يعيد {pages: ما كُتب الآن، items: أمثلة سُئل عنها، added: تمثيلات أُضيفت}."""
    src, dst = book.dir(spec["src"]), book.dir(spec["dst"])
    dst.mkdir(parents=True, exist_ok=True)
    wanted = lesson_pages(book, spec["lessons"]) if spec.get("lessons") else None
    qs = {name: [question(book, q) for q in ids] for name, ids in spec["questions"].items()}
    replace = spec["kind"] == "replace"
    previous = spec.get("previous", "representations_v2")
    done = {"pages": 0, "items": 0, "added": 0}
    for f in sorted(src.glob("*.json")):
        page = int(f.stem)
        target = dst / f.name
        if target.exists() or (wanted is not None and page not in wanted):
            continue
        found = _json(f)
        for k, item in enumerate(found):
            image = thumb(book, page, k)
            if item.get("representations") is None or not image.exists():
                continue
            done["items"] += 1
            reps = list(item["representations"])
            for name, texts in qs.items():
                if replace:
                    reps = [r for r in reps if r != name]
                    if ask(image, texts[0], YES_NO).get("yes"):
                        reps.insert(0, name)
                elif name not in reps and any(vote(ask, image, t) for t in texts):
                    reps.append(name)
            done["added"] += len(set(reps) - set(item["representations"]))
            item[previous] = item["representations"]
            item["representations"] = reps
        _write(target, found)
        done["pages"] += 1
    return done


def _bands(flags: Any, min_h: int) -> list[tuple[int, int]]:
    out, start = [], None
    for y, v in enumerate([*list(flags), False]):
        if v and start is None:
            start = y
        if not v and start is not None:
            if y - start >= min_h:
                out.append((start, y))
            start = None
    return out


def badge_bands(
    page: Any, cfg: dict[str, Any], x: list[float], min_h: int, cover: float
) -> list[tuple[int, int]]:
    import numpy as np

    w = page.shape[1]
    near = (np.abs(page[:, int(w * x[0]) : int(w * x[1])].astype(int) - np.array(cfg["badge"])) <= 25).all(
        axis=2
    )
    return _bands(near.mean(axis=1) > cover, min_h)


def region(book: Book, page: int, cfg: dict[str, Any]) -> Any:
    """منطقة التتمة المحتملة في أعلى صفحة الطالب (صورة Pillow)، أو None إن لم تتسع لها أو خلت."""
    import numpy as np
    from PIL import Image

    src = book.dir("render") / f"{page:04d}.png"
    if not src.exists():
        return None
    img = Image.open(src).convert("RGB")
    arr = np.array(img)
    h, w, _ = arr.shape
    left = badge_bands(arr, cfg, cfg["thumb_x"], 15, 0.25)
    right = badge_bands(arr, cfg, cfg["right_x"], 35, 0.5)
    top = int(h * cfg["top"])
    bottom = left[0][0] - 15 if left else (int(h * cfg["no_badge_bottom"]) if not right else None)
    if bottom is None or bottom - top < cfg["min_gap"]:
        return None
    area = arr[top:bottom, int(w * 0.06) : int(w * 0.50)]
    if (area.min(axis=2) < 200).mean() < 0.01:
        return None  # منطقة فارغة لا تتمة فيها
    return img.crop((int(w * 0.06), top, int(w * 0.50), bottom))


def run_continuation(book: Book, ask: Ask, region_of: Callable[[int], Any] | None = None) -> dict[str, int]:
    """«تابع المثال n» في أعلى صفحة الطالب التالية كان خارج القص: تُسأل أسئلة التمثيلات على تلك المنطقة وحدها ويُضاف ما تجده
    لتمثيلات المثال n (اتحاد فقط). `region_of(صفحة)` يُستبدل في الاختبار بمنطقة مختلقة. يكتب كل صفحات الدرس إلى dst بحقل continuation_pages."""
    cfg = {**CONTINUATION_DEFAULTS, **settings(book)["continuation"]}
    dst = book.dir(cfg["dst"])
    dst.mkdir(parents=True, exist_ok=True)
    crops = book.dir("crops")
    crops.mkdir(parents=True, exist_ok=True)
    layout = _json(book.output("layout"))["lessons"]
    previous = cfg.get("previous", "representations_v4")
    grab = region_of or (lambda p: region(book, p, cfg))
    done = {"lessons": 0, "continuations": 0, "added": 0}
    for rec in layout:
        group = next(
            (
                g
                for g in cfg["groups"]
                if not g.get("lessons") or any(str(rec["id"]).startswith(x) for x in g["lessons"])
            ),
            None,
        )
        if group is None or not rec["pages_pdf"]:
            continue

        def source(page: int, group: dict[str, Any] = group) -> Any:
            for key in group["sources"]:
                f = book.dir(key) / f"{page:04d}.json"
                if f.exists():
                    return _json(f)
            return None

        a, z = rec["pages_pdf"]
        pages = [p for p in range(a, z + 1) if source(p) is not None]
        if not pages:
            continue
        where = {x["n"]: p for p in range(a, z + 1) for x in (source(p) or []) if x.get("n")}
        out = {p: source(p) for p in pages}
        if not where:
            continue
        last = max(where.values())
        texts = {name: [question(book, q) for q in ids] for name, ids in group["questions"].items()}
        for p in range(min(where.values()) + 1, last + 2):
            crop = grab(p)
            if crop is None:
                continue
            path = crops / f"cont_{p:04d}.png"
            crop.save(path)
            owners = [n for n, pg in where.items() if pg < p]
            if not owners:
                continue
            n = max(owners, key=lambda k: (where[k], k))  # أقرب مثال سابق: التتمة تتبعه
            if p == last + 1:  # بعد آخر مثال قد تكون صفحة تمارين لا تتمة: يقرّر النموذج بقراءة «تابع المثال»
                got = ask(path, question(book, "continue"), CONT)
                if not got.get("continues") or got.get("n") != n:
                    continue
            if where[n] not in out:
                continue
            item = next(x for x in out[where[n]] if x.get("n") == n)
            reps = list(item.get("representations") or [])
            before = len(reps)
            for name, qs in texts.items():
                if name not in reps and any(vote(ask, path, t) for t in qs):
                    reps.append(name)
            item["continuation_pages"] = sorted({*item.get("continuation_pages", []), p})
            item[previous] = item.get(previous, item.get("representations"))
            item["representations"] = reps
            done["continuations"] += 1
            done["added"] += len(reps) - before
        for p, found in out.items():
            _write(dst / f"{p:04d}.json", found)
        done["lessons"] += 1
    return done


def run(book: Book, ask: Ask) -> dict[str, Any]:
    """كل تمريرات الإعداد بترتيبها ثم التتمة (إن وُجدت)؛ ملخص عددي لكل منها."""
    cfg = settings(book)
    summary: dict[str, Any] = {
        f"{p['kind']}:{p['dst']}": run_pass(book, ask, p) for p in cfg.get("passes", [])
    }
    if "continuation" in cfg:
        summary["continuation"] = run_continuation(book, ask)
    return summary


def gold_items(book: Book, lessons: list[str]) -> list[tuple[str, int, int, set[str]]]:
    out = []
    for f in sorted(book.dir("gold").glob("lesson_*.json")):
        g = _json(f)
        if lessons and str(g["lesson"]) not in lessons:
            continue
        for e in g["examples"]:
            reps = {r.strip() for r in str(e.get("representation") or "").split("+") if r.strip()}
            out.append((str(g["lesson"]), e["page_pdf"], e["n"], reps))
    return out


def evaluate(book: Book, versions: list[str], lessons: list[str] | None = None) -> list[dict[str, Any]]:
    """قياس مجلدات الرؤية (مفاتيح dirs) على الذهبي: دقة واسترجاع وتطابق تام لكل إصدار. المطابقة بالصفحة ورقم المثال."""
    items = gold_items(book, lessons or [])
    rows = []
    for key in versions:
        root = book.dir(key)
        tp = fp = fn = exact = seen = 0
        per: dict[str, list[int]] = {}
        for lesson, page, n, gold in items:
            f = root / f"{page:04d}.json"
            pred = (
                next((set(x.get("representations") or []) for x in _json(f) if x.get("n") == n), None)
                if f.exists()
                else None
            )
            if pred is None:
                continue
            seen += 1
            tp, fp, fn = tp + len(gold & pred), fp + len(pred - gold), fn + len(gold - pred)
            row = per.setdefault(lesson, [0, 0])
            row[0] += gold == pred
            row[1] += 1
            exact += gold == pred
        if seen:
            rows.append(
                {
                    "version": key,
                    "n": seen,
                    "precision": round(tp / (tp + fp), 2) if tp + fp else 0.0,
                    "recall": round(tp / (tp + fn), 2) if tp + fn else 0.0,
                    "exact": exact,
                    "fp": fp,
                    "fn": fn,
                    "per_lesson": {k: f"{a}/{b}" for k, (a, b) in per.items()},
                }
            )
    return rows
