"""فهرس الصيغ: المزامنة من الشيفرة idempotent، والمحذوفة تُعطَّل، وتقرير الفجوات يطابق الأمثلة الأساسية."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.papers.domain.form_catalog import Gap, declared_forms, form_gaps
from apps.papers.models import GeneratorForm
from apps.papers.selectors import core_examples, generator_form_gaps
from apps.papers.services import sync_generator_forms

COURSE = "g10-s1"


def _snapshot():
    return list(GeneratorForm.objects.order_by("pk").values())


def test_form_gaps_lists_examples_below_two_forms():
    forms = {("1.1", 1): ["b", "a"], ("1.1", 2): ["c"]}
    assert form_gaps([("1.1", 1), ("1.1", 2), ("1.1", 3)], forms) == [
        Gap("1.1", 2, ("c",)),
        Gap("1.1", 3, ()),
    ]


@pytest.mark.django_db
def test_second_sync_changes_nothing(loaded_courses):
    first = sync_generator_forms()
    assert first["created"] == len(declared_forms()) - first["unchanged"]
    assert first["skipped_courses"] == []
    before = _snapshot()
    second = sync_generator_forms()
    assert (second["created"], second["updated"], second["deactivated"]) == (0, 0, 0)
    assert second["unchanged"] == len(before)
    assert _snapshot() == before


@pytest.mark.django_db
def test_removed_form_is_deactivated_and_drift_is_corrected(loaded_courses):
    sync_generator_forms()
    kept = GeneratorForm.objects.filter(course__slug=COURSE).first()
    GeneratorForm.objects.filter(pk=kept.pk).update(has_item=not kept.has_item, active=False)
    gone = GeneratorForm.objects.create(
        course=kept.course, lesson_code="1.1", name="removed_form", example=1, level="K", has_item=True
    )
    report = sync_generator_forms()
    assert (report["created"], report["updated"], report["deactivated"]) == (0, 1, 1)
    gone.refresh_from_db()
    assert not gone.active
    assert GeneratorForm.objects.get(pk=kept.pk).active
    assert sync_generator_forms()["deactivated"] == 0


@pytest.mark.django_db
def test_gap_report_covers_the_core_examples_of_unit_one(loaded_courses):
    call_command("sync_generator_forms", stdout=StringIO())
    total, gaps = generator_form_gaps(COURSE, 1)
    assert total == len(core_examples(COURSE, 1)) == 14
    out = StringIO()
    call_command("report_form_gaps", COURSE, stdout=out)
    assert len(out.getvalue().splitlines()) == len(gaps) + 1
