"""خطة المبادرات: ملفها سليم، وحالة المعلَم تُقاس من المجسّات والبطاقات لا من ادّعاء."""

from datetime import date

import pytest
import yaml

from scripts import plan_status as ps

TODAY = date(2026, 12, 1)


def plan_with(tmp_path, **milestone) -> dict:
    data = {
        "title": "خطة",
        "metrics_file": "metrics.json",
        "principles": ["مبدأ"],
        "waves": [{"id": "W1", "title": "أولى", "due": "2026-12-24"}],
        "initiatives": [
            {
                "id": "A",
                "title": "أ",
                "wave": "W1",
                "goal": "غاية",
                "depends": [],
                "milestones": [
                    {
                        "id": "A.1",
                        "title": "معلَم",
                        "done_when": "شرط",
                        "probes": [{"path": "a.py", "has": "def test_x"}],
                    }
                    | milestone
                ],
                "kpis": [{"key": "k", "title": "مؤشر", "unit": "%", "baseline": 0, "target": 90}],
            },
            {
                "id": "B",
                "title": "ب",
                "wave": "W1",
                "goal": "غاية",
                "depends": ["A.1"],
                "milestones": [
                    {"id": "B.1", "title": "تالٍ", "done_when": "شرط", "probes": [{"path": "b.py"}]}
                ],
            },
        ],
    }
    path = tmp_path / "plan.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return ps.load_plan(path)


def test_real_plan_is_valid_and_renders_every_milestone():
    plan = ps.load_plan()
    initiatives = ps.evaluate(plan, today=TODAY, card_state=lambda card: "ready")
    doc = ps.render(plan, initiatives, TODAY)
    for ini in initiatives:
        for m in ini.milestones:
            assert f"| {m.id} |" in doc
    assert ps.render(plan, initiatives, TODAY) == doc


def test_probe_needs_the_file_and_its_text(tmp_path):
    plan = plan_with(tmp_path)
    assert ps.evaluate(plan, tmp_path, TODAY)[0].milestones[0].status == ps.TODO
    (tmp_path / "a.py").write_text("def test_y(): ...", encoding="utf-8")
    assert ps.evaluate(plan, tmp_path, TODAY)[0].milestones[0].status == ps.TODO
    (tmp_path / "a.py").write_text("def test_x(): ...", encoding="utf-8")
    assert ps.evaluate(plan, tmp_path, TODAY)[0].milestones[0].status == ps.DONE


@pytest.mark.parametrize(
    ("card", "expected"),
    [
        ("merged", ps.DONE),
        ("deployed", ps.DONE),
        ("pr_opened", ps.ACTIVE),
        ("blocked", ps.BLOCKED),
        ("missing", ps.BLOCKED),
    ],
)
def test_card_must_merge_before_done(tmp_path, card, expected):
    plan = plan_with(tmp_path, cards=["c1"])
    (tmp_path / "a.py").write_text("def test_x(): ...", encoding="utf-8")
    result = ps.evaluate(plan, tmp_path, TODAY, card_state=lambda _: card)
    assert result[0].milestones[0].status == expected


def test_cancelled_card_does_not_count(tmp_path):
    plan = plan_with(tmp_path, cards=["c1"])
    result = ps.evaluate(plan, tmp_path, TODAY, card_state=lambda _: "cancelled")
    assert result[0].milestones[0].status == ps.TODO
    assert [m.id for _, m in ps.next_up(result)] == ["A.1"]


def test_dependency_gates_next_and_opens_when_done(tmp_path):
    plan = plan_with(tmp_path)
    blocked = ps.evaluate(plan, tmp_path, TODAY)
    assert not blocked[1].ready and blocked[1].waiting_on == ["A.1"]
    assert [m.id for _, m in ps.next_up(blocked)] == ["A.1"]
    (tmp_path / "a.py").write_text("def test_x(): ...", encoding="utf-8")
    opened = ps.evaluate(plan, tmp_path, TODAY)
    assert [m.id for _, m in ps.next_up(opened)] == ["B.1"]
    assert "(B.1)" in ps.card_commands(opened)[0]


def test_late_only_after_wave_due_and_not_done(tmp_path):
    plan = plan_with(tmp_path)
    assert not ps.evaluate(plan, tmp_path, date(2026, 12, 24))[0].milestones[0].late
    assert ps.evaluate(plan, tmp_path, date(2026, 12, 25))[0].milestones[0].late


def test_kpi_reads_metrics_file(tmp_path):
    plan = plan_with(tmp_path)
    assert ps.evaluate(plan, tmp_path, TODAY)[0].kpis[0].met is None
    (tmp_path / "metrics.json").write_text('{"k": 92}', encoding="utf-8")
    assert ps.evaluate(plan, tmp_path, TODAY)[0].kpis[0].met is True
    assert ps.kpi_met(70, 60, lower_is_better=True) is False


def test_unknown_dependency_is_rejected(tmp_path):
    path = tmp_path / "plan.yaml"
    plan = plan_with(tmp_path)
    plan["initiatives"][1]["depends"] = ["Z"]
    path.write_text(yaml.safe_dump(plan, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ps.PlanError):
        ps.load_plan(path)
