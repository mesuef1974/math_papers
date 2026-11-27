"""يفحص رقم المثال في صيغ المقرر وأهدافه بنصوص أمثلة الكتاب (`example_text.json` خارج المستودع). قراءة فقط."""

from __future__ import annotations

import json
import random
from html import escape
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.domain.unit_prep import unit_files, unit_prep
from apps.papers.domain import generators
from apps.papers.domain.skill_match import match

SEEDS = 5


def items(course: str):
    """(الدرس، النوع، الاسم، المثال الموسوم، نصنا) لكل صيغة موسومة ولكل هدف مؤلَّف."""
    for (own, lesson), pool in sorted(generators.REGISTRY.items()):
        if own != course:
            continue
        for fn in pool:
            n = generators.skill_example(course, lesson, fn.__name__)
            if n is None:
                continue
            problems = [fn(random.Random(seed)) for seed in range(SEEDS)]  # noqa: S311 — عينات ثابتة
            text = " ".join(" ".join((p.stem, *p.steps)) for p in problems)
            yield lesson, "generator", fn.__name__, n, text
    for unit in unit_files(course):
        for entry in unit_prep(course, unit).lessons:
            for o in entry.objectives:
                text = f"{o.behavior} {o.condition} {o.criterion}"
                yield entry.lesson, "objective", "-", o.example, text


def page(rows: list[tuple], clips: Path) -> str:
    """صفحة محلية يراجعها المالك: نصنا وصورتا المثال الموسوم والمرجَّح من مقاطع الكتاب (تبقى خارج المستودع)."""

    def images(lesson: str, n: int) -> str:
        found = sorted(clips.glob(f"{lesson}_m{n}_p*.png"))
        return "".join(f'<img src="{f.resolve().as_uri()}">' for f in found) or "<p>لا مقطع</p>"

    body = []
    for i, (lesson, kind, name, tagged, best, text) in enumerate(rows, start=1):
        what = "هدف" if kind == "objective" else f"صيغة <code>{escape(name)}</code>"
        body.append(
            f"<section><h2>{i}) الدرس {lesson} — {what}</h2><p>{escape(text[:600])}</p><div>"
            f"<figure><figcaption>الموسوم: مثال {tagged}</figcaption>{images(lesson, tagged)}</figure>"
            f"<figure><figcaption>المرجَّح: مثال {best}</figcaption>{images(lesson, best)}</figure></div></section>"
        )
    return (
        '<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>مراجعة ربط الأمثلة</title>'
        "<style>body{font-family:sans-serif;margin:1rem}div{display:flex;gap:1rem}figure{flex:1;margin:0;"
        "min-inline-size:0}img{inline-size:100%;border:1px solid #888}section{border-block-end:2px solid #888}"
        "</style>" + "".join(body) + "</html>"
    )


class Command(BaseCommand):
    help = "يعلّم الصيغ والأهداف التي يشبه نصها مثالًا غير الموسومة به"

    def add_arguments(self, parser):
        parser.add_argument("course")
        parser.add_argument("--source", required=True, help="مجلد الكتاب خارج المستودع")
        parser.add_argument("--all", action="store_true", help="كل السطور لا المشتبه وحده")
        parser.add_argument("--report", help="صفحة HTML للمراجعة بصور المقاطع (خارج المستودع)")
        parser.add_argument("--clips", help="مجلد المقاطع؛ الافتراضي examples_student تحت المصدر")

    def handle(self, *args, course, source, **options):
        path = Path(source) / "example_text.json"
        if not path.is_file():
            raise CommandError(f"لا ملف {path}: شغّل python -m tools.extraction <الكتاب> example_text")
        texts = json.loads(path.read_text(encoding="utf-8"))
        counts = {"ok": 0, "suspect": 0, "unknown": 0, "no_text": 0}
        suspects = []
        for lesson, kind, name, tagged, text in items(course):
            examples = {int(n): t for n, t in texts.get(lesson, {}).items()}
            if tagged not in examples:
                counts["no_text"] += 1
                continue
            found = match(text, tagged, examples)
            counts[found.status] += 1
            if found.status == "suspect":
                suspects.append((lesson, kind, name, tagged, found.best, text))
            if options["all"] or found.status == "suspect":
                self.stdout.write(
                    f"{lesson} {kind} {name} tagged={tagged}:{found.tagged_score}"
                    f" best={found.best}:{found.best_score} {found.status}"
                )
        if report := options["report"]:
            clips = Path(options["clips"] or Path(source) / "examples_student")
            Path(report).write_text(page(suspects, clips), encoding="utf-8")
        self.stdout.write(json.dumps(counts))
