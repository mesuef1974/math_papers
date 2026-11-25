"""أمر plan_metrics (المعلَم M0.1): مفتاح لكل مؤشر في الخطة، أعداد ونسب فقط، والملف نفسه في كل تشغيل."""

import json
import shutil
from io import StringIO
from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core import selectors
from apps.core.services import PLAN_FILE, plan_kpi_keys

pytestmark = pytest.mark.django_db

REAL_PLAN = Path(settings.BASE_DIR) / PLAN_FILE


def repo_with(tmp_path: Path, plan_text: str | None = None) -> Path:
    """جذر مؤقت فيه ملف الخطة (الحقيقي ما لم يُعطَ نص)، فلا يكتب الاختبار في المستودع."""
    target = tmp_path / PLAN_FILE
    target.parent.mkdir(parents=True)
    if plan_text is None:
        shutil.copyfile(REAL_PLAN, target)
    else:
        target.write_text(plan_text, encoding="utf-8")
    return tmp_path


def run(root: Path) -> bytes:
    call_command("plan_metrics", root=root, stdout=StringIO())
    return (root / "docs" / "innovation_metrics.json").read_bytes()


def plan_text(*keys: str, metrics_file: str = "docs/innovation_metrics.json") -> str:
    kpis = [{"key": key, "title": key, "unit": "%", "target": 1} for key in keys]
    return yaml.safe_dump({"metrics_file": metrics_file, "initiatives": [{"id": "M0", "kpis": kpis}]})


def test_metrics_are_idempotent(tmp_path):
    root = repo_with(tmp_path)
    first = run(root)
    assert run(root) == first
    assert first.endswith(b"\n") and b"\r" not in first


def test_every_plan_kpi_key_is_in_the_output(tmp_path):
    keys = plan_kpi_keys(yaml.safe_load(REAL_PLAN.read_text(encoding="utf-8")))
    assert keys, "الخطة بلا مؤشرات فلا يحرس الاختبار شيئًا"
    assert set(json.loads(run(repo_with(tmp_path)))) == set(keys)


def test_output_is_numbers_and_nulls_only(tmp_path):
    values = json.loads(run(repo_with(tmp_path))).values()
    assert all(v is None or (isinstance(v, int | float) and not isinstance(v, bool)) for v in values)


def test_measured_kpis_have_values_and_the_rest_are_null(tmp_path):
    metrics = json.loads(run(repo_with(tmp_path)))
    assert 0 <= metrics["tagged_objective_formulas_pct"] <= 100
    assert metrics["lessons_with_error_spotting"] >= 1
    assert metrics["results_with_error_kind_pct"] is None  # لا جدول لنتائج البنود بعد


def test_kpi_without_a_source_is_null(tmp_path):
    root = repo_with(tmp_path, plan_text("no_table_yet", "lessons_with_error_spotting"))
    metrics = json.loads(run(root))
    assert metrics["no_table_yet"] is None
    assert isinstance(metrics["lessons_with_error_spotting"], int)


def test_a_source_returning_rows_or_names_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(selectors, "plan_metric_sources", lambda: {"leaky": lambda: ["طالب"]})
    root = repo_with(tmp_path, plan_text("leaky"))
    with pytest.raises(TypeError, match="leaky"):
        run(root)
    assert not (root / "docs" / "innovation_metrics.json").exists()


def test_ratios_are_rounded_to_two_places(tmp_path, monkeypatch):
    monkeypatch.setattr(selectors, "plan_metric_sources", lambda: {"ratio": lambda: 200 / 3})
    assert json.loads(run(repo_with(tmp_path, plan_text("ratio")))) == {"ratio": 66.67}


def test_metrics_file_outside_the_repo_is_refused(tmp_path):
    root = repo_with(tmp_path / "repo", plan_text("k", metrics_file="../escaped.json"))
    with pytest.raises(CommandError, match="خارج المستودع"):
        run(root)
    assert not (tmp_path / "escaped.json").exists()


def test_missing_plan_is_a_command_error(tmp_path):
    with pytest.raises(CommandError, match="ملف الخطة غير موجود"):
        call_command("plan_metrics", root=tmp_path)
