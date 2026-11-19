"""تصدير العروض إلى PPTX من اليمين لليسار: كاتب OOXML بـzipfile بلا تبعية تشغيل جديدة.

عرضان بكاتب حزمة واحد (`_package`): عرض الدرس القديم (`build_pptx(Deck)`) وعرض الحصة من تحضيرها
(`build_period_pptx(PeriodDeck)`) بملاحظات المتحدث والنص البديل لكل مقطع. شريحة 16:9 بهوية «أوراق»: العنابي للشريط والعناوين
وترويسة الجدول، والذهبي خطًّا زخرفيًا فقط، والحبر الداكن للنص؛ كل لون رمز من `tokens.css` النهاري (`TOKENS`). العناوين بخط
Cairo والنص بـ Arial (خط الهوية لا يُضمَّن في PPTX؛ الجهاز الذي يخلو منه يعرض بديله). الاتجاه RTL على مستوى العرض
(`rtl="1"`) والفقرات والجداول. اسم كل شكل يبدأ بدوره (`ROLE_*`)، فمعايير الملف (`pptx_checks.py`) تقرأ الدور لا الموضع.
المخرج حتمي: طوابع الأرشيف ثابتة فيخرج الملف نفسه من العرض نفسه.
"""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from .domain.deck import (
    BulletsSlide,
    Deck,
    ExampleSlide,
    PeriodDeck,
    PeriodSlide,
    Slide,
    TableSlide,
    TitleSlide,
)

WIDTH, HEIGHT = 12192000, 6858000  # 13.333in × 7.5in
EMU_PER_INCH = 914400

# الألوان: كل قيمة رمز من tokens.css النهاري (يحرسه test_pptx_files.py::test_palette_is_the_light_tokens)
BRAND, BRAND_STRONG, GOLD, INK, INK_SOFT, WHITE, SOFT, SAND_SOFT, LINE_STRONG = (
    "8E2433",
    "740A21",
    "DB943C",
    "2A1D1A",
    "6F655C",
    "FFFFFF",
    "EED6C9",
    "F7E4CA",
    "8B8178",
)
TOKENS = {
    BRAND: "--color-brand",
    BRAND_STRONG: "--color-brand-strong",
    GOLD: "--color-accent",
    INK: "--color-ink",
    INK_SOFT: "--color-ink-soft",
    WHITE: "--color-sheet",
    SOFT: "--color-brand-soft",
    SAND_SOFT: "--color-sand-soft",
    LINE_STRONG: "--color-line-strong",
}
DECORATIVE = frozenset({GOLD})  # الذهبي زخرفة لا يحمل نصًا
BACKGROUND = WHITE  # خلفية الشريحة في القالب الرئيس

FONT = "Arial"
TITLE_FONT = "Cairo"
ROLE_TITLE, ROLE_TEXT, ROLE_CLIP, ROLE_LOGO, ROLE_SHAPE, ROLE_TABLE, ROLE_NOTES = (
    "عنوان",
    "نص",
    "مقطع",
    "شعار",
    "شكل",
    "جدول",
    "ملاحظات",
)

LOCKUP = Path(__file__).resolve().parents[1] / "papers" / "word" / "assets" / "lockup.png"
LOCKUP_RATIO = 2475 / 1024
COPYRIGHT_NAME = "سفيان مسيف"  # نظير COPYRIGHT_* في word/builder.py وutils/brand.ts
COPYRIGHT_PHONE = "55296286"
MARGIN = 600000
BAR_H = 1000000
FOOT_Y = 6330000
FOOT_H = 420000
# منطقة المحتوى تحت شريط العنوان وفوق التذييل: فيها النقاط ومقطع المثال (S7 يقيس المقطع بارتفاعها)
CONTENT_X, CONTENT_Y = MARGIN, BAR_H + 350000
CONTENT_W, CONTENT_H = WIDTH - 2 * MARGIN, FOOT_Y - 150000 - CONTENT_Y
IMAGE_BOX = (
    WIDTH - MARGIN - 6096000,
    1250000,
    6096000,
    4900000,
)  # عرض الدرس القديم: نصف عرض الشريحة والملاحظات بجانبه

NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
GROUP = (
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
    '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
)


def fit(width_px: int, height_px: int, box_cx: int, box_cy: int) -> tuple[int, int]:
    """أكبر مقاس داخل الصندوق بنسبة الصورة نفسها (يكبّر أو يصغّر ولا يشوّه)."""
    scale = min(box_cx / width_px, box_cy / height_px)
    return max(1, round(width_px * scale)), max(1, round(height_px * scale))


def clip_frame(width_px: int, height_px: int) -> tuple[int, int, int, int]:
    """موضع مقطع المثال في عرض الحصة: أكبر مقاس في منطقة المحتوى، في وسطها."""
    cx, cy = fit(width_px, height_px, CONTENT_W, CONTENT_H)
    return CONTENT_X + (CONTENT_W - cx) // 2, CONTENT_Y + (CONTENT_H - cy) // 2, cx, cy


def _run(text: str, size: int, color: str, bold: bool = False, font: str = FONT) -> str:
    return (
        f'<a:r><a:rPr lang="ar-SA" sz="{size}" b="{int(bold)}" dirty="0"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{font}"/><a:cs typeface="{font}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>'
    )


def _para(
    text: str,
    size: int,
    color: str,
    bold: bool = False,
    algn: str = "r",
    bullet: bool = False,
    font: str = FONT,
) -> str:
    if bullet:
        ppr = (
            f'<a:pPr marL="342900" indent="-342900" algn="{algn}" rtl="1"><a:spcBef><a:spcPts val="600"/></a:spcBef>'
            f'<a:buClr><a:srgbClr val="{BRAND}"/></a:buClr><a:buFont typeface="{FONT}"/><a:buChar char="•"/></a:pPr>'
        )
    else:
        ppr = f'<a:pPr algn="{algn}" rtl="1"><a:buNone/></a:pPr>'
    return f"<a:p>{ppr}{_run(text, size, color, bold, font)}</a:p>"


@dataclass
class _Canvas:
    """شريحة واحدة قيد البناء: أشكالها ووسائطها (الصورة: اسم الجزء ← بايتات)."""

    shapes: list[str] = field(default_factory=list)
    media: list[tuple[str, bytes]] = field(default_factory=list)
    next_id: int = 2

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def rect(self, x: int, y: int, cx: int, cy: int, fill: str) -> None:
        i = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{ROLE_SHAPE} {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>'
        )

    def text(
        self,
        x: int,
        y: int,
        cx: int,
        cy: int,
        paragraphs: list[str],
        anchor: str = "t",
        role: str = ROLE_TEXT,
    ) -> None:
        i = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{role} {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="91440" rIns="91440" rtlCol="1" anchor="{anchor}">'
            f"<a:normAutofit/></a:bodyPr><a:lstStyle/>{''.join(paragraphs)}</p:txBody></p:sp>"
        )

    def picture(
        self, png: bytes, x: int, y: int, cx: int, cy: int, descr: str, role: str = ROLE_LOGO
    ) -> None:
        i = self._id()
        name = f"image{len(self.media) + 1}.png"
        self.media.append((name, png))
        rid = f"rId{len(self.media) + 1}"  # rId1 للتخطيط
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="{role} {i}" descr="{escape(descr, {chr(34): "&quot;"})}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill>'
            f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        )

    def table(
        self, x: int, y: int, cx: int, header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]
    ) -> int:
        """جدول RTL: العمود الأول عند اليمين. يُعيد ارتفاعه ليضع المتصل به ما بعده."""
        i = self._id()
        row_h = 520000
        col_w = cx // len(header)
        grid = "".join(f'<a:gridCol w="{col_w}"/>' for _ in header)

        def cell(value: str, head: bool, shade: bool) -> str:
            color, fill = (WHITE, BRAND) if head else (INK, SOFT if shade else WHITE)
            return (
                f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{_para(value, 1800, color, bold=head)}</a:txBody>"
                f'<a:tcPr anchor="ctr"><a:lnB w="9525"><a:solidFill><a:srgbClr val="{GOLD}"/></a:solidFill></a:lnB>'
                f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>'
            )

        body = f'<a:tr h="{row_h}">{"".join(cell(h, True, False) for h in header)}</a:tr>' + "".join(
            f'<a:tr h="{row_h}">{"".join(cell(v, False, n % 2 == 1) for v in row)}</a:tr>'
            for n, row in enumerate(rows)
        )
        height = row_h * (len(rows) + 1)
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="{ROLE_TABLE} {i}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{height}"/></p:xfrm><a:graphic>'
            f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr rtl="1" firstRow="1"/>'
            f"<a:tblGrid>{grid}</a:tblGrid>{body}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
        )
        return height

    def xml(self) -> str:
        return (
            f"{XML}<p:sld {NS}><p:cSld><p:spTree>{GROUP}"
            f"{''.join(self.shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
        )


def _footer(c: _Canvas, lockup: bytes) -> None:
    c.rect(MARGIN, FOOT_Y - 30000, WIDTH - 2 * MARGIN, 12000, GOLD)
    lock_cy = FOOT_H - 60000
    lock_cx = round(lock_cy * LOCKUP_RATIO)
    c.picture(lockup, WIDTH - MARGIN - lock_cx, FOOT_Y + 20000, lock_cx, lock_cy, "أوراق")
    c.text(
        MARGIN,
        FOOT_Y,
        5000000,
        FOOT_H,
        [_para(f"© {COPYRIGHT_NAME}  {COPYRIGHT_PHONE}", 1100, INK, algn="l")],
        anchor="ctr",
    )


def _title_bar(c: _Canvas, title: str, size: int = 3200) -> None:
    c.rect(0, 0, WIDTH, BAR_H, BRAND)
    c.text(
        MARGIN,
        0,
        WIDTH - 2 * MARGIN,
        BAR_H,
        [_para(title, size, WHITE, bold=True, font=TITLE_FONT)],
        anchor="ctr",
        role=ROLE_TITLE,
    )


def _cover(c: _Canvas, title: str, lines: Sequence[str], size: int, lockup: bytes) -> None:
    """شريحة العنوان: الكتلة العنابية بالعنوان، وخط ذهبي، والأسطر تحته، والشعار المقفل."""
    inner_w = WIDTH - 2 * MARGIN
    c.rect(0, 0, WIDTH, 4000000, BRAND)
    c.text(
        MARGIN,
        900000,
        inner_w,
        2200000,
        [_para(title, 4800, WHITE, bold=True, algn="ctr", font=TITLE_FONT)],
        anchor="ctr",
        role=ROLE_TITLE,
    )
    c.rect(WIDTH // 2 - 900000, 4000000, 1800000, 36000, GOLD)
    if lines:
        c.text(
            MARGIN,
            4200000,
            inner_w,
            1300000,
            [_para(line, size, INK, algn="ctr") for line in lines],
            anchor="ctr",
        )
    lock_cy = 700000
    lock_cx = round(lock_cy * LOCKUP_RATIO)
    c.picture(lockup, WIDTH - MARGIN - lock_cx, HEIGHT - 400000 - lock_cy, lock_cx, lock_cy, "أوراق")


def _render(slide: Slide, lockup: bytes) -> _Canvas:
    c = _Canvas()
    inner_w = WIDTH - 2 * MARGIN
    if isinstance(slide, TitleSlide):
        _cover(c, slide.title, (slide.subtitle,), 2400, lockup)
        return c
    _title_bar(c, slide.title)
    _footer(c, lockup)
    body_y = CONTENT_Y
    if isinstance(slide, BulletsSlide):
        c.text(
            MARGIN,
            body_y,
            inner_w,
            FOOT_Y - body_y - 150000,
            [_para(b, 2600, INK, bullet=True) for b in slide.bullets],
        )
    elif isinstance(slide, TableSlide):
        height = c.table(MARGIN, body_y, inner_w, slide.header, slide.rows)
        if slide.footnote:
            c.text(MARGIN, body_y + height + 120000, inner_w, 450000, [_para(slide.footnote, 1600, INK)])
    elif isinstance(slide, ExampleSlide):
        bx, by, bw, bh = IMAGE_BOX
        cx, cy = fit(slide.clip.width_px, slide.clip.height_px, bw, bh)
        c.picture(slide.clip.png, bx + bw - cx, by + (bh - cy) // 2, cx, cy, slide.title, role=ROLE_CLIP)
        if slide.notes:
            c.text(MARGIN, by, bx - 2 * MARGIN, bh, [_para(n, 2000, INK, bullet=True) for n in slide.notes])
    return c


def _render_period(slide: PeriodSlide, lockup: bytes) -> _Canvas:
    """شريحة الحصة: العنوان والنقاط بأحجام النموذج (S6)، والمقطع بنصه البديل في منطقة المحتوى كلها (S7 وS10)."""
    c = _Canvas()
    body = slide.body_pt * 100
    if slide.kind == "title":
        _cover(c, slide.title, slide.bullets, body, lockup)
        return c
    _title_bar(c, slide.title, slide.title_pt * 100)
    _footer(c, lockup)
    if slide.clip is not None:
        x, y, cx, cy = clip_frame(slide.clip.width_px, slide.clip.height_px)
        c.picture(slide.clip.png, x, y, cx, cy, slide.alt, role=ROLE_CLIP)
    elif slide.bullets:
        c.text(
            CONTENT_X,
            CONTENT_Y,
            CONTENT_W,
            CONTENT_H,
            [_para(b, body, INK, bullet=True) for b in slide.bullets],
        )
    return c


def _theme(name: str = "أوراق") -> str:
    colors = {
        "dk1": INK,
        "lt1": WHITE,
        "dk2": BRAND,
        "lt2": SOFT,
        "accent1": BRAND,
        "accent2": GOLD,
        "accent3": INK_SOFT,
        "accent4": BRAND_STRONG,
        "accent5": SAND_SOFT,
        "accent6": LINE_STRONG,
        "hlink": BRAND,
        "folHlink": INK_SOFT,
    }
    scheme = "".join(f'<a:{k}><a:srgbClr val="{v}"/></a:{k}>' for k, v in colors.items())
    fills = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3
    lines = '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>' * 3
    effects = "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
    return (
        f'{XML}<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="{name}"><a:themeElements>'
        f'<a:clrScheme name="أوراق">{scheme}</a:clrScheme><a:fontScheme name="أوراق">'
        f'<a:majorFont><a:latin typeface="{TITLE_FONT}"/><a:ea typeface=""/><a:cs typeface="{TITLE_FONT}"/></a:majorFont>'
        f'<a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface="{FONT}"/></a:minorFont></a:fontScheme>'
        f'<a:fmtScheme name="أوراق"><a:fillStyleLst>{fills}</a:fillStyleLst><a:lnStyleLst>{lines}</a:lnStyleLst>'
        f"<a:effectStyleLst>{effects}</a:effectStyleLst><a:bgFillStyleLst>{fills}</a:bgFillStyleLst></a:fmtScheme>"
        "</a:themeElements></a:theme>"
    )


def _rels(items: list[tuple[str, str, str]]) -> str:
    body = "".join(f'<Relationship Id="{i}" Type="{t}" Target="{target}"/>' for i, t, target in items)
    return f'{XML}<Relationships xmlns="{REL_NS}">{body}</Relationships>'


EMPTY_TREE = f"<p:spTree>{GROUP}</p:spTree>"
CLR_MAP = (
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
    'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
)
BG = f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{BACKGROUND}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
MASTER = (
    f"{XML}<p:sldMaster {NS}><p:cSld>{BG}{EMPTY_TREE}</p:cSld>{CLR_MAP}"
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'
)
LAYOUT = (
    f'{XML}<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="فارغ">{EMPTY_TREE}</p:cSld>'
    "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
)
# صفحة الملاحظات (A4 طولية): نص المعلم في نصفها الأسفل
NOTES_W, NOTES_H = 6858000, 9144000
NOTES_BODY = (685800, 4343400, 5486400, 4114800)


def _notes_body(paragraphs: str, shape_id: int) -> str:
    x, y, cx, cy = NOTES_BODY
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{ROLE_NOTES} {shape_id}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm></p:spPr><p:txBody><a:bodyPr rtlCol="1"/><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    )


EMPTY_NOTE = '<a:p><a:pPr rtl="1"/><a:endParaRPr lang="ar-SA"/></a:p>'
NOTES_MASTER = (
    f"{XML}<p:notesMaster {NS}><p:cSld>{BG}<p:spTree>{GROUP}"
    f"{_notes_body(EMPTY_NOTE, 2)}</p:spTree></p:cSld>{CLR_MAP}</p:notesMaster>"
)


def _notes(notes: Sequence[str]) -> str:
    paragraphs = "".join(_para(n, 1400, INK) for n in notes)
    return (
        f"{XML}<p:notes {NS}><p:cSld><p:spTree>{GROUP}{_notes_body(paragraphs, 2)}</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>"
    )


CT_MAIN = "application/vnd.openxmlformats-officedocument.presentationml."
CONTENT_KINDS = {
    "presentation.main": CT_MAIN + "presentation.main+xml",
    "slideMaster": CT_MAIN + "slideMaster+xml",
    "slideLayout": CT_MAIN + "slideLayout+xml",
    "slide": CT_MAIN + "slide+xml",
    "notesMaster": CT_MAIN + "notesMaster+xml",
    "notesSlide": CT_MAIN + "notesSlide+xml",
    "theme": "application/vnd.openxmlformats-officedocument.theme+xml",
}


def _package(canvases: Sequence[_Canvas], title: str, notes: Sequence[Sequence[str]] | None = None) -> bytes:
    """حزمة PPTX من شرائح جاهزة، ومعها ملاحظات المتحدث لكل شريحة إن أُعطيت (بقالب ملاحظات وسمته)."""
    n = len(canvases)
    if notes is not None and len(notes) != n:
        raise ValueError("ملاحظات لكل شريحة")
    with_notes = notes is not None
    overrides = [
        ("/ppt/presentation.xml", "presentation.main"),
        ("/ppt/slideMasters/slideMaster1.xml", "slideMaster"),
        ("/ppt/slideLayouts/slideLayout1.xml", "slideLayout"),
        ("/ppt/theme/theme1.xml", "theme"),
        *((f"/ppt/slides/slide{k}.xml", "slide") for k in range(1, n + 1)),
    ]
    if with_notes:
        overrides += [
            ("/ppt/notesMasters/notesMaster1.xml", "notesMaster"),
            ("/ppt/theme/theme2.xml", "theme"),
            *((f"/ppt/notesSlides/notesSlide{k}.xml", "notesSlide") for k in range(1, n + 1)),
        ]
    content_types = (
        f'{XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
        + "".join(f'<Override PartName="{p}" ContentType="{CONTENT_KINDS[k]}"/>' for p, k in overrides)
        + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        "</Types>"
    )
    core = (
        f'{XML}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>أوراق</dc:creator>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created></cp:coreProperties>'
    )
    notes_master_list = (
        '<p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst>' if with_notes else ""
    )
    presentation = (
        f'{XML}<p:presentation {NS} rtl="1" saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
        f"</p:sldMasterIdLst>{notes_master_list}<p:sldIdLst>"
        + "".join(f'<p:sldId id="{255 + k}" r:id="rId{k + 2}"/>' for k in range(1, n + 1))
        + f'</p:sldIdLst><p:sldSz cx="{WIDTH}" cy="{HEIGHT}"/><p:notesSz cx="{NOTES_W}" cy="{NOTES_H}"/></p:presentation>'
    )
    presentation_rels = [("rId1", f"{REL}/slideMaster", "slideMasters/slideMaster1.xml")]
    if with_notes:
        presentation_rels.append(("rId2", f"{REL}/notesMaster", "notesMasters/notesMaster1.xml"))
    presentation_rels += [(f"rId{k + 2}", f"{REL}/slide", f"slides/slide{k}.xml") for k in range(1, n + 1)]
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": _rels(
            [
                ("rId1", f"{REL}/officeDocument", "ppt/presentation.xml"),
                (
                    "rId2",
                    "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
                    "docProps/core.xml",
                ),
            ]
        ),
        "docProps/core.xml": core,
        "ppt/presentation.xml": presentation,
        "ppt/_rels/presentation.xml.rels": _rels(presentation_rels),
        "ppt/slideMasters/slideMaster1.xml": MASTER,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _rels(
            [
                ("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", f"{REL}/theme", "../theme/theme1.xml"),
            ]
        ),
        "ppt/slideLayouts/slideLayout1.xml": LAYOUT,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _rels(
            [("rId1", f"{REL}/slideMaster", "../slideMasters/slideMaster1.xml")]
        ),
        "ppt/theme/theme1.xml": _theme(),
    }
    if with_notes:
        parts["ppt/notesMasters/notesMaster1.xml"] = NOTES_MASTER
        parts["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = _rels(
            [("rId1", f"{REL}/theme", "../theme/theme2.xml")]
        )
        parts["ppt/theme/theme2.xml"] = _theme("أوراق: الملاحظات")
    media: dict[str, bytes] = {}
    for k, c in enumerate(canvases, start=1):
        parts[f"ppt/slides/slide{k}.xml"] = c.xml()
        rels = [("rId1", f"{REL}/slideLayout", "../slideLayouts/slideLayout1.xml")] + [
            (f"rId{j + 2}", f"{REL}/image", f"../media/slide{k}_{name}")
            for j, (name, _) in enumerate(c.media)
        ]
        for name, data in c.media:
            media[f"slide{k}_{name}"] = data
        if notes is not None:
            rels.append((f"rId{len(c.media) + 2}", f"{REL}/notesSlide", f"../notesSlides/notesSlide{k}.xml"))
            parts[f"ppt/notesSlides/notesSlide{k}.xml"] = _notes(notes[k - 1])
            parts[f"ppt/notesSlides/_rels/notesSlide{k}.xml.rels"] = _rels(
                [
                    ("rId1", f"{REL}/notesMaster", "../notesMasters/notesMaster1.xml"),
                    ("rId2", f"{REL}/slide", f"../slides/slide{k}.xml"),
                ]
            )
        parts[f"ppt/slides/_rels/slide{k}.xml.rels"] = _rels(rels)
    for name, data in media.items():
        parts[f"ppt/media/{name}"] = data

    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, part in parts.items():  # [Content_Types].xml أولًا كما تشترط OPC عادةً
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, part.encode("utf-8") if isinstance(part, str) else part)
    return out.getvalue()


def build_pptx(deck: Deck) -> bytes:
    """عرض الدرس (الافتراض القديم: عرض واحد للدرس بكل أمثلته)."""
    lockup = LOCKUP.read_bytes()
    title = next((s.title for s in deck.slides if isinstance(s, TitleSlide)), deck.lesson)
    return _package([_render(s, lockup) for s in deck.slides], title)


def build_period_pptx(deck: PeriodDeck) -> bytes:
    """عرض الحصة: شريحة لكل شريحة في النموذج بترتيبه، وملاحظاتها (الطور والدقائق وجانب المعلم) في ملاحظات المتحدث."""
    lockup = LOCKUP.read_bytes()
    title = deck.slides[0].title if deck.slides else deck.lesson
    return _package(
        [_render_period(s, lockup) for s in deck.slides],
        title,
        notes=[s.notes for s in deck.slides],
    )
