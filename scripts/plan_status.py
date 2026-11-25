#!/usr/bin/env python3
"""حالة خطة المبادرات: تُقاس من المستودع ودفتر البطاقات، وتُولَّد منها docs/innovation_plan.md.

المصدر الوحيد docs/innovation_plan.yaml. المعلَم منجز حين تنجح كل مجسّاته وتُدمج كل بطاقاته.

    python scripts/plan_status.py            ملخص الحالة
    python scripts/plan_status.py --write    يكتب الوثيقة (idempotent في اليوم الواحد)
    python scripts/plan_status.py --check    يتحقق من سلامة ملف الخطة وحده
    python scripts/plan_status.py --cards    أوامر بطاقات المعالم الجاهزة للبدء (تُعرض ولا تُنفَّذ)
    python scripts/plan_status.py --json     الحالة JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import ledger  # noqa: E402

PLAN = ROOT / "docs" / "innovation_plan.yaml"
DOC = ROOT / "docs" / "innovation_plan.md"

DONE, ACTIVE, BLOCKED, TODO = "done", "active", "blocked", "todo"
LABEL = {DONE: "منجز", ACTIVE: "جارٍ", BLOCKED: "متعثر", TODO: "لم يبدأ"}
CARD_DONE = {"merged", "deployed"}
CARD_BLOCKED = {"blocked", "prepush_failed"}


class PlanError(ValueError):
    """ملف الخطة لا يطابق عقده."""


@dataclass
class Milestone:
    id: str
    title: str
    done_when: str
    status: str
    probes: list[tuple[str, bool]]
    cards: list[tuple[str, str]]
    late: bool = False


@dataclass
class Kpi:
    key: str
    title: str
    unit: str
    baseline: float | None
    target: float
    value: float | None
    met: bool | None


@dataclass
class Initiative:
    id: str
    title: str
    wave: str
    goal: str
    depends: list[str]
    milestones: list[Milestone]
    kpis: list[Kpi]
    decisions: list[dict]
    risks: list[str]
    ready: bool = False
    waiting_on: list[str] = field(default_factory=list)

    @property
    def done_count(self) -> int:
        return sum(m.status == DONE for m in self.milestones)

    @property
    def status(self) -> str:
        states = {m.status for m in self.milestones}
        if states == {DONE}:
            return DONE
        if BLOCKED in states:
            return BLOCKED
        return TODO if states == {TODO} else ACTIVE


def load_plan(path: Path = PLAN) -> dict:
    """يقرأ ملف الخطة ويرفض ما يكسر القياس: معرّف مكرر، اعتماد أو موجة مجهولة، معلَم بلا شرط، مؤشر مكرر."""
    plan = yaml.safe_load(path.read_text(encoding="utf-8"))
    waves = {w["id"] for w in plan["waves"]}
    ids: set[str] = set()
    kpi_keys: set[str] = set()
    for ini in plan["initiatives"]:
        for item in (ini, *ini["milestones"]):
            if item["id"] in ids:
                raise PlanError(f"معرّف مكرر: {item['id']}")
            ids.add(item["id"])
        if ini["wave"] not in waves:
            raise PlanError(f"{ini['id']}: موجة مجهولة {ini['wave']}")
        if not ini["milestones"]:
            raise PlanError(f"{ini['id']}: بلا معالم")
        for m in ini["milestones"]:
            if not m.get("done_when"):
                raise PlanError(f"{m['id']}: بلا شرط إنجاز")
            if not m.get("probes") and not m.get("cards"):
                raise PlanError(f"{m['id']}: بلا مجسّ ولا بطاقة فلا يُقاس")
            for probe in m.get("probes", []):
                if set(probe) - {"path", "has"} or "path" not in probe:
                    raise PlanError(f"{m['id']}: مجسّ غير معروف {probe}")
        for k in ini.get("kpis", []):
            if k["key"] in kpi_keys:
                raise PlanError(f"مؤشر مكرر: {k['key']}")
            kpi_keys.add(k["key"])
            if k.get("target") is None:
                raise PlanError(f"{k['key']}: بلا هدف")
    for ini in plan["initiatives"]:
        for dep in ini.get("depends", []):
            if dep not in ids:
                raise PlanError(f"{ini['id']}: اعتماد مجهول {dep}")
            if dep == ini["id"] or dep.startswith(ini["id"] + "."):
                raise PlanError(f"{ini['id']}: يعتمد على نفسه")
    return plan


def probe_ok(probe: dict, root: Path) -> bool:
    target = root / probe["path"]
    if not target.is_file():
        return False
    return "has" not in probe or probe["has"] in target.read_text(encoding="utf-8", errors="ignore")


def card_state(card: str) -> str:
    last = ledger.state(card)
    return last["event"] if last else "missing"


def milestone_status(probes: list[bool], cards: list[str]) -> str:
    live = [c for c in cards if c != "cancelled"]
    if any(c in CARD_BLOCKED or c == "missing" for c in live):
        return BLOCKED
    if (probes or live) and all(probes) and all(c in CARD_DONE for c in live):
        return DONE
    return ACTIVE if live or any(probes) else TODO


def kpi_met(value: float | None, target: float, lower_is_better: bool) -> bool | None:
    if value is None:
        return None
    return value <= target if lower_is_better else value >= target


def evaluate(
    plan: dict, root: Path = ROOT, today: date | None = None, card_state=card_state
) -> list[Initiative]:
    today = today or date.today()
    due = {w["id"]: date.fromisoformat(str(w["due"])) for w in plan["waves"]}
    metrics_path = root / plan.get("metrics_file", "")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
    out: list[Initiative] = []
    for ini in plan["initiatives"]:
        milestones = []
        for m in ini["milestones"]:
            probes = [(p["path"], probe_ok(p, root)) for p in m.get("probes", [])]
            cards = [(c, card_state(c)) for c in m.get("cards", [])]
            status = milestone_status([ok for _, ok in probes], [s for _, s in cards])
            late = status != DONE and due[ini["wave"]] < today
            milestones.append(Milestone(m["id"], m["title"], m["done_when"], status, probes, cards, late))
        kpis = []
        for k in ini.get("kpis", []):
            value = metrics.get(k["key"])
            met = kpi_met(value, k["target"], k.get("lower_is_better", False))
            kpis.append(Kpi(k["key"], k["title"], k["unit"], k.get("baseline"), k["target"], value, met))
        out.append(
            Initiative(
                ini["id"],
                ini["title"],
                ini["wave"],
                ini["goal"],
                ini.get("depends", []),
                milestones,
                kpis,
                ini.get("decisions", []),
                ini.get("risks", []),
            )
        )
    state = {i.id: i.status for i in out} | {m.id: m.status for i in out for m in i.milestones}
    for ini in out:
        ini.waiting_on = [d for d in ini.depends if state[d] != DONE]
        ini.ready = not ini.waiting_on
    return out


def next_up(initiatives: list[Initiative]) -> list[tuple[Initiative, Milestone]]:
    """أول معلَم غير منجز في كل مبادرة اكتملت اعتمادياتها ولا بطاقة حيّة له: ما يصح أن تُفتح له بطاقة الآن."""
    out = []
    for ini in initiatives:
        if not ini.ready:
            continue
        pending = [m for m in ini.milestones if m.status != DONE]
        if pending and not any(s != "cancelled" for _, s in pending[0].cards):
            out.append((ini, pending[0]))
    return out


def card_commands(initiatives: list[Initiative]) -> list[str]:
    return [
        f'python automation/ledger.py new "{ini.title}: {m.title} ({m.id})" '
        f'--body "{m.title}. المبادرة {ini.id} في docs/innovation_plan.yaml: {ini.goal}" '
        f'--success "{m.done_when}"'
        for ini, m in next_up(initiatives)
    ]


def as_json(plan: dict, initiatives: list[Initiative], today: date) -> dict:
    total = sum(len(i.milestones) for i in initiatives)
    done = sum(i.done_count for i in initiatives)
    return {
        "date": today.isoformat(),
        "milestones_done": done,
        "milestones_total": total,
        "late": [m.id for i in initiatives for m in i.milestones if m.late],
        "next": [m.id for _, m in next_up(initiatives)],
        "initiatives": [
            {
                "id": i.id,
                "status": i.status,
                "ready": i.ready,
                "milestones": {m.id: m.status for m in i.milestones},
                "kpis": {k.key: {"value": k.value, "target": k.target, "met": k.met} for k in i.kpis},
            }
            for i in initiatives
        ],
    }


def num(value: float | None) -> str:
    if value is None:
        return "لم يُقَس"
    return str(int(value)) if float(value).is_integer() else str(value)


def render(plan: dict, initiatives: list[Initiative], today: date) -> str:
    waves = {w["id"]: w for w in plan["waves"]}
    total = sum(len(i.milestones) for i in initiatives)
    done = sum(i.done_count for i in initiatives)
    late = [m for i in initiatives for m in i.milestones if m.late]
    open_decisions = [(i, d) for i in initiatives for d in i.decisions if d.get("status") == "open"]
    kpis = [k for i in initiatives for k in i.kpis]
    lines = [
        f"# {plan['title']}",
        "",
        "وثيقة مولَّدة من `docs/innovation_plan.yaml` بالأمر `python scripts/plan_status.py --write`، فلا تُعدَّل يدويًا.",
        f"الحالة يوم {today.isoformat()}، مقيسة من المستودع ودفتر البطاقات.",
        "",
        "## الخلاصة",
        "",
        f"- المعالم المنجزة: {done} من {total} ({round(100 * done / total)}%).",
        f"- المعالم المتأخرة عن موعد موجتها: {len(late)}"
        + (f" ({'، '.join(m.id for m in late)})." if late else "."),
        f"- مؤشرات الأثر المحققة: {sum(k.met is True for k in kpis)} من {len(kpis)}،"
        f" وغير المقيسة {sum(k.met is None for k in kpis)}.",
        f"- قرارات تنتظر المالك: {len(open_decisions)}.",
        "",
        "## المبادئ",
        "",
        *[f"- {p}" for p in plan["principles"]],
        "",
        "## الموجات",
        "",
        "| الموجة | العنوان | الموعد | المبادرات | المعالم المنجزة |",
        "| :-: | :-: | :-: | :-: | :-: |",
    ]
    for w in plan["waves"]:
        inside = [i for i in initiatives if i.wave == w["id"]]
        lines.append(
            f"| {w['id']} | {w['title']} | {w['due']} | {'، '.join(i.id for i in inside)} | "
            f"{sum(i.done_count for i in inside)} من {sum(len(i.milestones) for i in inside)} |"
        )
    lines += ["", "## ما يُفتح له بطاقة الآن", ""]
    upcoming = next_up(initiatives)
    lines += [f"- {m.id} ({ini.title}): {m.title}. ينتهي حين: {m.done_when}" for ini, m in upcoming] or [
        "- لا شيء."
    ]
    lines += ["", "## قرارات تنتظر المالك", ""]
    lines += [f"- {i.id} ({i.title}): {d['text']}." for i, d in open_decisions] or ["- لا شيء."]
    lines += [
        "",
        "## مؤشرات الأثر",
        "",
        f"تُقرأ من `{plan['metrics_file']}` الذي يكتبه أمر `plan_metrics` (المعلَم M0.1)؛ قبل وجوده كلها «لم يُقَس».",
        "",
        "| المبادرة | المؤشر | خط الأساس | الهدف | الحالي | الحكم |",
        "| :-: | :-: | :-: | :-: | :-: | :-: |",
    ]
    for ini in initiatives:
        for k in ini.kpis:
            verdict = {True: "محقق", False: "دون الهدف", None: "لم يُقَس"}[k.met]
            lines.append(
                f"| {ini.id} | {k.title} | {num(k.baseline)} | {num(k.target)} {k.unit} | {num(k.value)} | {verdict} |"
            )
    lines += ["", "## المبادرات"]
    for ini in initiatives:
        wave = waves[ini.wave]
        gate = "جاهزة للبدء" if ini.ready else "تنتظر " + "، ".join(ini.waiting_on)
        lines += [
            "",
            f"### {ini.id}: {ini.title}",
            "",
            f"{ini.goal}",
            "",
            f"الموجة {ini.wave} (موعدها {wave['due']})، الحالة: {LABEL[ini.status]}،"
            f" المعالم {ini.done_count} من {len(ini.milestones)}، {gate}.",
            "",
            "| المعلَم | العمل | ينتهي حين | الحالة | القياس |",
            "| :-: | :-- | :-- | :-: | :-: |",
        ]
        for m in ini.milestones:
            measured = [f"مجسّات {sum(ok for _, ok in m.probes)}/{len(m.probes)}"] if m.probes else []
            measured += [f"{c}: {s}" for c, s in m.cards]
            status = LABEL[m.status] + ("، متأخر" if m.late else "")
            lines.append(f"| {m.id} | {m.title} | {m.done_when} | {status} | {'؛ '.join(measured)} |")
        if ini.risks:
            lines += ["", "المخاطر:", *[f"- {r}" for r in ini.risks]]
    lines += [
        "",
        "## كيف تُحدَّث",
        "",
        "- تعديل الخطة (معلَم، موعد، هدف، قرار): في `docs/innovation_plan.yaml` وحده، ثم `--write`.",
        "- ربط بطاقة بمعلَم: معرّفها في `cards` للمعلَم؛ حالتها تُقرأ من `automation/ledger/`.",
        "- بطاقات المعالم الجاهزة: `python scripts/plan_status.py --cards` يطبع أوامرها ولا ينفّذها.",
        "- سلامة الملف يحرسها `tests/test_plan_status.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    for flag in ("--write", "--check", "--cards", "--json"):
        mode.add_argument(flag, action="store_true")
    args = ap.parse_args(argv)
    try:
        plan = load_plan()
    except (PlanError, KeyError, yaml.YAMLError) as exc:
        print(f"ملف الخطة غير سليم: {exc}", file=sys.stderr)
        return 1
    if args.check:
        print("ملف الخطة سليم")
        return 0
    today = date.today()
    initiatives = evaluate(plan, today=today)
    if args.cards:
        print("\n".join(card_commands(initiatives)))
    elif args.json:
        print(json.dumps(as_json(plan, initiatives, today), ensure_ascii=False, indent=2))
    elif args.write:
        DOC.write_text(render(plan, initiatives, today), encoding="utf-8", newline="\n")
        print(f"كُتبت {DOC.relative_to(ROOT).as_posix()}")
    else:
        for ini in initiatives:
            gate = "" if ini.ready else f" (تنتظر {'، '.join(ini.waiting_on)})"
            print(
                f"{ini.id:<4} {LABEL[ini.status]:<8} {ini.done_count}/{len(ini.milestones)}  {ini.title}{gate}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
