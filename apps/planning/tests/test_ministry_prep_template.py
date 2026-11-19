"""قالبا Word الرسميان (نموذج التحضير وغلاف المدرسة) مجرّدان: رموزهما كما في الوثيقة، ولا سنة ثابتة ولا تظليل ولا وسم حساسية."""

import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PREP = ROOT / "apps" / "planning" / "word" / "assets" / "ministry" / "prep.docx"
COVER = ROOT / "apps" / "papers" / "word" / "assets" / "school" / "cover.docx"
PLAN = ROOT / "docs" / "lesson_prep_plan.md"

# أجزاء وسم Microsoft 365 وSharePoint: تحمل معرّف المؤسسة ولا مكان لها في مستودع عام
LABEL_PARTS = re.compile(r"^(docProps/custom\.xml|docMetadata/|customXml/(_rels/)?item(Props)?[2-9])")
LABEL_MARKERS = (b"MSIP_Label", b"siteId", b"SiteId", b"ContentTypeId", b"classificationlabels", b"sharepoint")


def xml_parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist() if name.endswith((".xml", ".rels"))}


def documented_tokens() -> set[str]:
    section = PLAN.read_text(encoding="utf-8").split("## نموذج الوزارة الفارغ", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| `{")]
    return {token for row in rows for token in re.findall(r"`(\{[a-z_]+\})`", row.split("|")[1])}


def test_prep_tokens_match_the_documented_table():
    parts = xml_parts(PREP)
    text = (parts["word/document.xml"] + parts["word/footer1.xml"]).decode()
    found = set(re.findall(r"\{[a-z_]+\}", text))
    assert found == documented_tokens()
    assert len(found) == 23


def test_prep_body_and_footer_carry_no_fixed_year_or_highlight():
    parts = xml_parts(PREP)
    for name in ("word/document.xml", "word/footer1.xml", "word/header1.xml"):
        xml = parts[name].decode()
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))
        assert "2026" not in text and "2027" not in text, name
        assert "<w:highlight" not in xml, name
    # العنوان غير مربوط بخاصية الغلاف، فلا يكتب Word سنة قديمة فوق {year}
    assert b"w:dataBinding" not in parts["word/footer1.xml"]
    assert b"<PublishDate/>" in parts["customXml/item1.xml"]


@pytest.mark.parametrize("path", [PREP, COVER], ids=["prep", "cover"])
def test_template_has_no_sensitivity_label_or_sharepoint_metadata(path):
    parts = xml_parts(path)
    assert not [name for name in parts if LABEL_PARTS.match(name)]
    for name, data in parts.items():
        assert not [marker for marker in LABEL_MARKERS if marker in data], name


@pytest.mark.parametrize("path", [PREP, COVER], ids=["prep", "cover"])
def test_template_package_has_no_dangling_parts(path):
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        overrides = re.findall(r'PartName="/([^"]+)"', archive.read("[Content_Types].xml").decode())
        assert set(overrides) <= names
        for rels in (name for name in names if name.endswith(".rels")):
            base = Path(rels).parent.parent
            for target, mode in re.findall(r'Target="([^"]+)"(?:[^>]*TargetMode="(\w+)")?', archive.read(rels).decode()):
                if mode != "External":
                    resolved = (Path("/") / base / target).resolve().as_posix()
                    assert re.sub(r"^[A-Za-z]:", "", resolved).lstrip("/") in names, (rels, target)
