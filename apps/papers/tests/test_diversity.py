from io import StringIO

from django.core.management import call_command

from apps.papers.domain.generators import diversity_report

MIN_DISTINCT = 20  # من 60 بذرة؛ ما دونه صيغة ضيقة تكرر نفسها في أوراق الصف


def test_every_variant_is_diverse_enough():
    weak = [(r["variant"], r["distinct"]) for r in diversity_report(60) if r["distinct"] < MIN_DISTINCT]
    assert not weak, weak


def test_command_prints_report():
    out = StringIO()
    call_command("paper_diversity", "--seeds", "12", "--min", "1", stdout=out)
    text = out.getvalue()
    assert "صيغة، منها 0 دون الحد 1" in text
    assert "limit_from_piecewise" in text
