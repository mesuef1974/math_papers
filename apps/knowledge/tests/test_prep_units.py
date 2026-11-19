"""ملفات تحضير الوحدات `prep/unit-<n>.json`: العقد يرفض ما يخالف المقرر وجدول الأفعال، والمحمِّل idempotent."""

from __future__ import annotations

import json
import shutil
from collections import Counter
from copy import deepcopy

import pytest
from pydantic import ValidationError

from apps.curriculum.courses import GRADE10_SLUG
from apps.curriculum.models import PrepObjective, PrepUnit
from apps.knowledge.domain.contract import CourseKnowledge, course_dir, read_course_dir, read_source
from apps.knowledge.domain.prep_units import PrepUnitData
from apps.knowledge.services import load_course


@pytest.fixture(scope="module")
def base():
    return read_source(GRADE10_SLUG).model_dump()


def _with(base, change):
    data = deepcopy(base)
    change(data["prep_units"])
    return CourseKnowledge(**data)


def test_every_core_example_of_the_three_units_has_one_objective(base):
    knowledge = CourseKnowledge(**base)
    assert [u.unit for u in knowledge.prep_units] == [1, 2, 3]
    assert [len(u.objectives) for u in knowledge.prep_units] == [14, 35, 11]
    assert {u.status for u in knowledge.prep_units} == {"draft"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda u: u[0]["objectives"][0].update(behavior="يفهم رأس القطع المكافئ"), "ليس من أفعال العمق"),
        (lambda u: u[0]["objectives"][0].update(behavior="يبرهن رأس القطع المكافئ"), "ليس من أفعال العمق"),
        (lambda u: u[0]["objectives"][0].update(example=9), "لا مثال بهذا الرقم"),
        (lambda u: u[1]["objectives"][13].update(example=5), "إثرائي"),  # 2.5 م5
        (lambda u: u.append(deepcopy(u[0])), "مكرر"),
    ],
)
def test_contract_rejects_objectives_outside_the_course(base, change, message):
    with pytest.raises(ValidationError, match=message):
        _with(base, change)


def test_unit_file_rules():
    objective = {
        "lesson": "1.1",
        "example": 1,
        "behavior": "يحدد الرأس",
        "condition": "من جدول",
        "criterion": "بلا خطأ",
    }
    data = {"unit": 1, "status": "draft", "audience": "طالب الصف العاشر", "objectives": [objective]}
    assert PrepUnitData(**data).objectives[0].verb == "يحدد"
    for wrong, message in [
        ({"status": "approved"}, "بلا سطر اعتماد"),
        ({"approval": "اعتمد"}, "مسودة ومعها سطر اعتماد"),
        ({"objectives": [objective, objective]}, "أكثر من هدف"),
        ({"unit": 2}, "من وحدة أخرى"),
        ({"objectives": [{**objective, "criterion": ""}]}, "at least 3"),
    ]:
        with pytest.raises(ValidationError, match=message):
            PrepUnitData(**{**data, **wrong})


def test_file_name_must_match_its_unit(tmp_path):
    folder = tmp_path / GRADE10_SLUG
    shutil.copytree(course_dir(GRADE10_SLUG), folder)
    unit = json.loads((folder / "prep" / "unit-1.json").read_text(encoding="utf-8"))
    (folder / "prep" / "unit-1.json").unlink()
    (folder / "prep" / "unit-4.json").write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="unit-4.json يحمل الوحدة 1"):
        read_course_dir(folder)
    (folder / "prep" / "unit-4.json").rename(folder / "prep" / "notes.json")
    with pytest.raises(ValueError, match="ملف غير متوقع"):
        read_course_dir(folder)


@pytest.mark.django_db
def test_loader_writes_units_and_objectives_idempotently():
    first = load_course(GRADE10_SLUG)
    assert first.changed["prep_units"] == 3 and first.changed["prep_objectives"] == 60
    assert PrepUnit.objects.filter(course__slug=GRADE10_SLUG).count() == 3
    assert PrepObjective.objects.filter(unit__course__slug=GRADE10_SLUG).count() == 60
    again = load_course(GRADE10_SLUG)
    assert Counter({k: v for k, v in again.changed.items() if k.startswith("prep")}) == Counter()
