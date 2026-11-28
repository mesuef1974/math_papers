"""حارس المصطلحات (قرار المالك 2026-11-28): «التقييم البنائي» حيث وجد المفهوم، ولا عودة للمصطلح القديم."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = ("apps", "config", "templates", "frontend/src", "docs", "automation", "scripts")
SUFFIXES = {".py", ".json", ".html", ".txt", ".md", ".ts", ".vue", ".yaml"}
RETIRED = "تكوين" + "ي"  # مقسّمة حتى لا يطابق الحارسُ نفسَه


def test_retired_assessment_term_does_not_return():
    found = [
        str(path.relative_to(ROOT))
        for folder in FOLDERS
        for path in (ROOT / folder).rglob("*")
        if path.suffix in SUFFIXES
        and "ledger" not in path.parts  # دفتر البطاقات سجل تاريخي لا يُعدَّل
        and path.is_file()
        and RETIRED in path.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not found, found
