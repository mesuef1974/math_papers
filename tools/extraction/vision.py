"""مراحل الرؤية بخادم محلي: أرقام الصفحة (pages)، وشارات الأمثلة ومقاطعها (examples)، وبطاقة المصطلحات (vocab).

كل مرحلة مستأنَفة (من وُجد ملفه لا يُعاد) وتأخذ `ask(صورة، سؤال، مخطط) -> dict` مُحقَنًا (`llama.asker`)، فالمنطق يُختبر بجواب مختلق.
المخرجات: pages في dirs.vision (NNNN.json: examples وexercises وpractices)؛ examples في dirs.badges (قائمة {n وtitle وfocus وrepresentations
وpaired} لكل صفحة) والمقاطع في dirs.crops (`<صفحة>_<ك>_head.png` و`_thumb.png`)؛ vocab في dirs.vocab (review وnew وflat) وقصّ البطاقة
في dirs.vocab/crops. الأسئلة تُستبدل من `vision.questions` بالمعرّف؛ وهندسة الصفحة (شارة المثال وأعمدتها) من `vision.examples`، وصندوق
بطاقة المصطلحات `vision.vocab.card_box` (إحداثيات صفحة التصيير، 220 dpi). numpy وPillow يُستورَدان كسولين.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import reps
from .config import Book
from .reps import YES_NO, Ask, schema

MODEL_FOR = {
    "pages": "small",
    "examples": "large",
    "vocab": "small",
    "reps": "large",
}  # حجم النموذج لكل مرحلة (الإعداد vision.models_for)
NUMS = schema("n", {"numbers": {"type": "array", "items": {"type": "integer"}}})
STRS = schema("s", {"items": {"type": "array", "items": {"type": "string"}}})
HEADING = schema("h", {"n": {"type": "integer"}, "title": {"type": "string"}, "focus": {"type": "string"}})
PAIR = {
    "type": "object",
    "properties": {"ar": {"type": "string"}, "en": {"type": "string"}},
    "required": ["ar", "en"],
}
TERMS = {"type": "array", "items": PAIR}
CARD = schema("v", {"review": TERMS, "new": TERMS})
FLAT = schema("f", {"terms": TERMS})
REPRESENTATIONS = (
    ("جدول", "table"),
    ("بياني", "axes"),
    ("جبري", "base_algebra"),
    ("سياق حياتي", "context"),
)  # (اسم التمثيل، معرّف سؤاله) بترتيب الظهور في القائمة
QUESTIONS: dict[str, str] = {
    "examples": "في هذه الصفحة، ما أرقام الأمثلة المحلولة التي عنوانها «مثال» متبوعًا برقم داخل شارة ملونة؟ أعد قائمة الأرقام فقط، أو قائمة فارغة.",
    "exercises": "في هذه الصفحة، ما أرقام التمارين المرقمة (مثل 36 و37)؟ أعد كل رقم تمرين ظاهر مرة واحدة، أو قائمة فارغة إن لم يوجد.",
    "practices": "في هذه الصفحة، ما رموز معايير الممارسات الرياضية الظاهرة بصيغة MP ثم نقطة ثم رقم (مثل MP.1 وMP.7)؟ أعد الرموز فقط، أو قائمة فارغة.",
    "heading": (
        "في هذه الصورة شارة زرقاء نصها «مثال» ثم رقم. اكتب رقم المثال، وعنوانه (النص الرمادي الكبير بجانب الشارة)، "
        "والسطر العريض الأسود تحته إن وُجد. انسخ النصوص حرفيًا."
    ),
    "card": (
        "في هذه الصفحة جدول «بناء المصطلحات» بعمودين (العربية والإنجليزية) وفيه فقرتان: «مراجعة المصطلحات» ثم «المصطلحات الجديدة». "
        "أعد مصطلحات كل فقرة بالعربية وبالإنجليزية كما هي مكتوبة بالضبط، وإن غابت فقرة فقائمتها فارغة. "
        "المصطلح سطر قصير فيه كلمة عربية وإنجليزية بينهما خط عمودي؛ أما فقرة «نشاط المصطلحات» وما تحتها من جمل فليست مصطلحات."
    ),
    "flat": (
        "في هذه الصورة قائمة نقطية أسطرها مصطلحات: كل سطر عربي وإنجليزي بينهما خط عمودي. "
        "أعد كل مصطلح بعربيته وإنجليزيته كما هي مكتوبة بالضبط، ولا تُدخل جملًا أو عناوين."
    ),
}
CARD_BOX = [
    150,
    275,
    1140,
    880,
]  # بطاقة «بناء المصطلحات» ثابتة الموضع في يسار صفحة الافتتاحية؛ القص يحجب نص النشاط تحتها


def settings(book: Book) -> dict[str, Any]:
    return book.get("vision", {})


def text(book: Book, key: str) -> str:
    return {**QUESTIONS, **settings(book).get("questions", {})}[key]


def model_size(book: Book, stage: str) -> str:
    return {**MODEL_FOR, **settings(book).get("models_for", {})}[stage]


def _write(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def run_pages(book: Book, ask: Ask, first: int = 1, last: int | None = None) -> dict[str, int]:
    """ثلاثة أسئلة ضيقة لكل صفحة مصيَّرة: أرقام الأمثلة، أرقام التمارين (1..99)، رموز الممارسات MP."""
    out = book.dir("vision")
    out.mkdir(parents=True, exist_ok=True)
    done = {"pages": 0}
    for n in range(first, (last or book["pages"]) + 1):
        target, img = out / f"{n:04d}.json", book.dir("render") / f"{n:04d}.png"
        if target.exists() or not img.exists():
            continue
        examples = ask(img, text(book, "examples"), NUMS).get("numbers", [])
        exercises = sorted(
            {x for x in ask(img, text(book, "exercises"), NUMS).get("numbers", []) if 1 <= x <= 99}
        )
        mp = sorted(
            {
                s.strip()
                for s in ask(img, text(book, "practices"), STRS).get("items", [])
                if s.strip().startswith("MP")
            }
        )
        _write(target, {"examples": examples, "exercises": exercises, "practices": mp})
        done["pages"] += 1
    return done


def geometry(book: Book) -> dict[str, Any]:
    return {**reps.CONTINUATION_DEFAULTS, **settings(book).get("examples", {})}


def crops_for(book: Book, path: Path) -> list[dict[str, Any]]:
    """لكل شارة في العمود الأيمن: مقطع الرأس (الشارة والعنوان)، ومقطع صورة الطالب المصغّرة إن تطابق عدد الشارات في العمودين."""
    import numpy as np
    from PIL import Image

    cfg = geometry(book)
    img = Image.open(path).convert("RGB")
    page = np.array(img)
    h, w, _ = page.shape
    right = reps.badge_bands(page, cfg, cfg["right_x"], 35, 0.5)
    left = reps.badge_bands(page, cfg, cfg["thumb_x"], 15, 0.25)
    out = []
    for i, (a, _) in enumerate(right):
        head = img.crop((int(w * 0.40), max(a - 15, 0), w, min(a + 200, h)))
        thumb = None
        if len(left) == len(right):
            top = left[i][0] - 15
            bottom = left[i + 1][0] - 10 if i + 1 < len(left) else min(left[i][0] + 780, h)
            thumb = img.crop((int(w * 0.06), top, int(w * 0.50), bottom))
        out.append({"head": head, "thumb": thumb, "paired": thumb is not None})
    return out


def run_examples(book: Book, ask: Ask, tags: list[str] | None = None) -> dict[str, int]:
    """شارة «مثال» تحدّد كل مثال: رقمه وعنوانه من مقطع الرأس بالرؤية، وتمثيلاته نعم/لا لكل تمثيل على مقطع المصغّرة."""
    out, crops = book.dir("badges"), book.dir("crops")
    out.mkdir(parents=True, exist_ok=True)
    crops.mkdir(parents=True, exist_ok=True)
    layout = json.loads(book.output("layout").read_text(encoding="utf-8"))
    pages = sorted(
        {
            p
            for rec in layout["lessons"]
            if rec["pages_pdf"] and (not tags or rec["id"] in tags)
            for p in range(rec["pages_pdf"][0], rec["pages_pdf"][1] + 1)
        }
    )
    done = {"pages": 0, "examples": 0}
    for page in pages:
        target, src = out / f"{page:04d}.json", book.dir("render") / f"{page:04d}.png"
        if target.exists() or not src.exists():
            continue
        found = []
        for k, c in enumerate(crops_for(book, src)):
            head = crops / f"{page:04d}_{k}_head.png"
            c["head"].save(head)
            got = ask(head, text(book, "heading"), HEADING)
            rep = None
            if c["thumb"] is not None:
                thumb = reps.thumb(book, page, k)
                c["thumb"].save(thumb)
                rep = [
                    name
                    for name, q in REPRESENTATIONS
                    if ask(thumb, reps.question(book, q), YES_NO).get("yes")
                ]
            found.append(
                {
                    "n": got.get("n"),
                    "title": got.get("title", "").strip(),
                    "focus": got.get("focus", "").strip(),
                    "representations": rep,
                    "paired": c["paired"],
                }
            )
        _write(target, found)
        done["pages"] += 1
        done["examples"] += len(found)
    return done


def crop_card(book: Book, page: int) -> Path:
    from PIL import Image

    crops = book.dir("vocab") / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    target = crops / f"{page:04d}.png"
    box = tuple(settings(book).get("vocab", {}).get("card_box", CARD_BOX))
    with Image.open(book.dir("render") / f"{page:04d}.png") as im:
        im.crop(box).save(target)
    return target


def opener_pages(book: Book) -> list[int]:
    layout = json.loads(book.output("layout").read_text(encoding="utf-8"))
    return [r["pages_pdf"][0] for r in layout["lessons"] if r["pages_pdf"]]


def run_vocab(book: Book, ask: Ask, pages: list[int] | None = None) -> dict[str, int]:
    """بطاقة المصطلحات من صفحة افتتاح كل درس؛ رد فارغ من الفقرتين يُتبع بسؤال أبسط بقائمة واحدة (flat)."""
    out = book.dir("vocab")
    out.mkdir(parents=True, exist_ok=True)
    done = {"pages": 0, "terms": 0}
    for n in pages if pages is not None else opener_pages(book):
        if (out / f"{n:04d}.json").exists():
            continue
        img = crop_card(book, n)
        data = ask(img, text(book, "card"), CARD)
        rec = {"review": data.get("review", []), "new": data.get("new", []), "flat": []}
        if not rec["review"] and not rec["new"]:
            rec["flat"] = ask(img, text(book, "flat"), FLAT).get("terms", [])
        _write(out / f"{n:04d}.json", rec)
        done["pages"] += 1
        done["terms"] += len(rec["review"]) + len(rec["new"]) + len(rec["flat"])
    return done
