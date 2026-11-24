"""تصدير عرض الحصة `PeriodDeck` إلى PPTX من اليمين لليسار: كاتب OOXML بـzipfile بلا تبعية جديدة (python-pptx خارج lockfile).

شريحة 16:9 بهوية «أوراق»: العنابي للشريط والعناوين، والذهبي خطًّا زخرفيًا فقط، والحبر الداكن للنص على الأبيض. الاتجاه RTL
على مستوى العرض (`rtl="1"`) وفي كل فقرة. العناوين بخط Cairo (خط الهوية) والنص بـArial. مقطع المثال يملأ منطقة المحتوى
بنسبته، ونصه البديل رقم المثال وصفحته، وجانب المعلم (الطور والدقائق والعمق والتمايز) في ملاحظات المتحدث لا على الشريحة.
المخرج حتمي: طوابع الأرشيف ثابتة فيخرج الملف نفسه من العرض نفسه. معايير الملف (S7 وS8 وS12) في `pptx_checks.py`.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from apps.papers.domain.bidi import isolate_number_ranges

from .domain.deck import MINUTES_BADGE, STAGE_SHORT, PeriodDeck, PeriodSlide

WIDTH, HEIGHT = 12192000, 6858000  # 13.333in × 7.5in
EMU_PER_INCH = 914400
BRAND, GOLD, INK, WHITE = "8E2433", "DB943C", "1F2430", "FFFFFF"  # BRAND = --color-brand في print.css
PALETTE = frozenset({BRAND, GOLD, INK, WHITE})
FONT = "Arial"
TITLE_FONT = "Cairo"
LOCKUP = Path(__file__).resolve().parents[1] / "papers" / "word" / "assets" / "lockup.png"
LOCKUP_RATIO = 2475 / 1024
LOCKUP_ALT = "أوراق"
COPYRIGHT_NAME = "سفيان مسيف"  # نظير COPYRIGHT_* في word/builder.py وutils/brand.ts
COPYRIGHT_PHONE = "55296286"
FOOT_PT = 14
MARGIN = 600000
BAR_H = 1000000
FOOT_Y = 6330000
FOOT_H = 420000
TITLE_H = 700000  # ارتفاع العنوان داخل الشريط؛ تحته صف المراحل
STRIP_PT = 14
BADGE_W = 1200000
# منطقة المحتوى بين شريط العنوان والتذييل: فيها النقاط ومقطع المثال (S7 يقيس المقطع بها)
CONTENT_BOX = (MARGIN, BAR_H + 200000, WIDTH - 2 * MARGIN, FOOT_Y - 150000 - (BAR_H + 200000))
CLIP_PREFIX = "مقطع"  # اسم شكل صورة المثال، يميّزه عن الشعار في الفحص

NS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_PML = "application/vnd.openxmlformats-officedocument.presentationml."
GROUP = (
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm>'
    '<a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
)


# تخطيطات الماستر بأسمائها فيختار المعلم منها حين يضيف شريحة: الزخرفة على الشرائح نفسها لا على التخطيطات (S8 يقيسها)
LAYOUTS = {1: "عنوان", 2: "محتوى", 3: "مقطع من الكتاب"}


def layout_of(slide: PeriodSlide) -> int:
    if slide.kind == "title":
        return 1
    return 3 if slide.clip is not None else 2


def fit(width_px: int, height_px: int, box_cx: int, box_cy: int) -> tuple[int, int]:
    """أكبر مقاس داخل الصندوق بنسبة الصورة نفسها (يكبّر أو يصغّر ولا يشوّه)."""
    scale = min(box_cx / width_px, box_cy / height_px)
    return max(1, round(width_px * scale)), max(1, round(height_px * scale))


def _run(text: str, pt: int, color: str, bold: bool = False, font: str = FONT) -> str:
    return (
        f'<a:r><a:rPr lang="ar-SA" sz="{pt * 100}" b="{int(bold)}" dirty="0"><a:solidFill><a:srgbClr val="{color}"/>'
        f'</a:solidFill><a:latin typeface="{font}"/><a:cs typeface="{font}"/></a:rPr><a:t>{escape(text)}</a:t></a:r>'
    )


def _para(
    text: str,
    pt: int,
    color: str,
    bold: bool = False,
    algn: str = "r",
    bullet: bool = False,
    font: str = FONT,
) -> str:
    if bullet:
        ppr = (
            f'<a:pPr marL="457200" indent="-342900" algn="{algn}" rtl="1"><a:spcBef><a:spcPts val="900"/></a:spcBef>'
            f'<a:buClr><a:srgbClr val="{BRAND}"/></a:buClr><a:buFont typeface="{FONT}"/><a:buChar char="•"/></a:pPr>'
        )
    else:
        ppr = f'<a:pPr algn="{algn}" rtl="1"><a:buNone/></a:pPr>'
    return f"<a:p>{ppr}{_run(text, pt, color, bold, font)}</a:p>"


@dataclass
class _Canvas:
    """شريحة واحدة قيد البناء: أشكالها بترتيب القراءة ووسائطها (اسم الجزء ← بايتات)."""

    shapes: list[str] = field(default_factory=list)
    media: list[tuple[str, bytes]] = field(default_factory=list)
    next_id: int = 2
    layout: int = 2  # رقم التخطيط في الماستر (LAYOUTS)

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id - 1

    def rect(self, x: int, y: int, cx: int, cy: int, fill: str) -> None:
        i = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="شكل {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>'
        )

    def text(
        self, x: int, y: int, cx: int, cy: int, paragraphs: list[str], anchor: str = "t", name: str = "نص"
    ) -> None:
        i = self._id()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:noFill/></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="91440" rIns="91440" rtlCol="1" anchor="{anchor}">'
            f"<a:normAutofit/></a:bodyPr><a:lstStyle/>{''.join(paragraphs)}</p:txBody></p:sp>"
        )

    def picture(self, png: bytes, x: int, y: int, cx: int, cy: int, descr: str, name: str = "صورة") -> None:
        i = self._id()
        part = f"image{len(self.media) + 1}.png"
        self.media.append((part, png))
        rid = f"rId{len(self.media) + 1}"  # rId1 للتخطيط
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="{name} {i}" descr="{escape(descr, {chr(34): "&quot;"})}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill>'
            f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        )

    def xml(self) -> str:
        return (
            f"{XML}<p:sld {NS}><p:cSld><p:spTree>{GROUP}{''.join(self.shapes)}</p:spTree></p:cSld>"
            "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
        )


def _lockup(c: _Canvas, lockup: bytes, cy: int, y: int) -> None:
    cx = round(cy * LOCKUP_RATIO)
    c.picture(lockup, WIDTH - MARGIN - cx, y, cx, cy, LOCKUP_ALT, name="شعار")


def _footer(c: _Canvas, lockup: bytes, k: int, n: int) -> None:
    c.rect(MARGIN, FOOT_Y - 30000, WIDTH - 2 * MARGIN, 12000, GOLD)
    _lockup(c, lockup, FOOT_H - 60000, FOOT_Y + 20000)
    c.text(
        MARGIN,
        FOOT_Y,
        5000000,
        FOOT_H,
        [_para(f"© {COPYRIGHT_NAME}  {COPYRIGHT_PHONE}", FOOT_PT, INK, algn="l")],
        anchor="ctr",
        name="تذييل",
    )
    # رقم الشريحة بكلمات عربية لا «k / n»: الخطوط المائلة بين رقمين تنقلب في فقرة RTL فتُقرأ «n / k»
    c.text(
        WIDTH // 2 - 1500000,
        FOOT_Y,
        3000000,
        FOOT_H,
        [_para(f"شريحة {k} من {n}", FOOT_PT, INK, algn="ctr")],
        anchor="ctr",
        name="رقم الشريحة",
    )


def _stage_strip(c: _Canvas, slide: PeriodSlide, phases: tuple[str, ...]) -> None:
    """صف المراحل أسفل الشريط: المرحلة الحالية بخط ثقيل وخط ذهبي تحتها (الذهبي زخرفة لا نص)، والبقية بالأبيض الخفيف،
    وعلى يسار العنوان شارة دقائق المرحلة. الأسماء أقصر من تسميات المراحل في التحضير فتتسع للصف."""
    x, _, cx, _ = CONTENT_BOX
    seg = cx // len(phases)
    for i, phase in enumerate(phases):  # الأولى عند اليمين: ترتيب القراءة من اليمين
        sx = x + cx - (i + 1) * seg
        current = phase == slide.phase
        c.text(
            sx,
            TITLE_H,
            seg,
            BAR_H - TITLE_H - 40000,
            [_para(STAGE_SHORT[phase], STRIP_PT, WHITE, bold=current, algn="ctr")],
            anchor="ctr",
            name="مرحلة",
        )
        if current:
            c.rect(sx + seg // 6, BAR_H - 40000, seg - seg // 3, 30000, GOLD)
    c.text(
        x,
        0,
        BADGE_W,
        TITLE_H,
        [
            _para(
                isolate_number_ranges(MINUTES_BADGE.format(minutes=slide.minutes)),
                STRIP_PT + 4,
                WHITE,
                bold=True,
                algn="l",
            )
        ],
        anchor="ctr",
        name="دقائق",
    )


def _render(slide: PeriodSlide, lockup: bytes, k: int, n: int, phases: tuple[str, ...] = ()) -> _Canvas:
    """الترتيب في الشجرة ترتيب القراءة: العنوان أولًا ثم المحتوى ثم التذييل."""
    c = _Canvas(layout=layout_of(slide))
    x, y, cx, cy = CONTENT_BOX
    if slide.kind == "title":
        c.rect(0, 0, WIDTH, 4000000, BRAND)
        c.text(
            MARGIN,
            900000,
            cx,
            2200000,
            [_para(slide.title, slide.title_pt + 12, WHITE, bold=True, algn="ctr", font=TITLE_FONT)],
            anchor="ctr",
            name="عنوان",
        )
        c.rect(WIDTH // 2 - 900000, 4000000, 1800000, 36000, GOLD)
        c.text(
            MARGIN,
            4250000,
            cx,
            1300000,
            [_para(b, slide.body_pt, INK, algn="ctr") for b in slide.bullets],
            anchor="ctr",
        )
        _lockup(c, lockup, 600000, HEIGHT - 300000 - 600000)
        return c
    c.rect(0, 0, WIDTH, BAR_H, BRAND)
    staged = bool(phases) and slide.phase in phases
    c.text(
        MARGIN + (BADGE_W if staged else 0),
        0,
        cx - (BADGE_W if staged else 0),
        TITLE_H if staged else BAR_H,
        [_para(slide.title, slide.title_pt, WHITE, bold=True, font=TITLE_FONT)],
        anchor="ctr",
        name="عنوان",
    )
    if staged:
        _stage_strip(c, slide, phases)
    if slide.clip is not None:
        w, h = fit(slide.clip.width_px, slide.clip.height_px, cx, cy)
        c.picture(slide.clip.png, x + (cx - w) // 2, y + (cy - h) // 2, w, h, slide.alt, name=CLIP_PREFIX)
    elif slide.bullets:
        c.text(x, y, cx, cy, [_para(b, slide.body_pt, INK, bullet=True) for b in slide.bullets])
    _footer(c, lockup, k, n)
    return c


def _notes(k: int, notes: tuple[str, ...]) -> str:
    body = "".join(_para(n, 12, INK) for n in notes) or "<a:p/>"
    return (
        f'{XML}<p:notes {NS}><p:cSld><p:spTree>{GROUP}<p:sp><p:nvSpPr><p:cNvPr id="2" name="ملاحظات {k}"/>'
        '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody></p:sp></p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>"
    )


def _theme() -> str:
    colors = {
        "dk1": INK,
        "lt1": WHITE,
        "dk2": BRAND,
        "lt2": WHITE,
        "accent1": BRAND,
        "accent2": GOLD,
        "accent3": INK,
        "accent4": BRAND,
        "accent5": GOLD,
        "accent6": INK,
        "hlink": BRAND,
        "folHlink": INK,
    }
    scheme = "".join(f'<a:{k}><a:srgbClr val="{v}"/></a:{k}>' for k, v in colors.items())
    fills = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3
    lines = '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>' * 3
    effects = "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
    return (
        f'{XML}<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="أوراق"><a:themeElements>'
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


CLR_MAP = (
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
    'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
)
BACKGROUND = (
    f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{WHITE}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
)
MASTER = (
    f"{XML}<p:sldMaster {NS}><p:cSld>{BACKGROUND}<p:spTree>{GROUP}</p:spTree></p:cSld>{CLR_MAP}"
    "<p:sldLayoutIdLst>"
    + "".join(f'<p:sldLayoutId id="{2147483648 + i}" r:id="rId{i}"/>' for i in LAYOUTS)
    + "</p:sldLayoutIdLst></p:sldMaster>"
)


def _layout(name: str) -> str:
    return (
        f'{XML}<p:sldLayout {NS} preserve="1" userDrawn="1"><p:cSld name="{name}"><p:spTree>{GROUP}</p:spTree></p:cSld>'
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )


NOTES_MASTER = (
    f"{XML}<p:notesMaster {NS}><p:cSld>{BACKGROUND}<p:spTree>{GROUP}<p:sp><p:nvSpPr>"
    '<p:cNvPr id="2" name="ملاحظات"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/>'
    '</p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="685800" y="4400550"/><a:ext cx="5486400" cy="3600450"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr rtlCol="1"/><a:lstStyle/>'
    f'<a:p><a:pPr algn="r" rtl="1"/><a:endParaRPr lang="ar-SA"/></a:p></p:txBody></p:sp></p:spTree></p:cSld>{CLR_MAP}'
    "</p:notesMaster>"
)


def build_period_pptx(deck: PeriodDeck) -> bytes:
    """ملف PPTX للحصة: شريحة لكل شريحة في النموذج بترتيبه، ولكل شريحة صفحة ملاحظات بجانب المعلم."""
    lockup = LOCKUP.read_bytes()
    n = len(deck.slides)
    present = {s.phase for s in deck.slides}
    phases = tuple(p for p in STAGE_SHORT if p in present)  # مراحل هذا العرض بترتيبها
    canvases = [_render(s, lockup, k, n, phases) for k, s in enumerate(deck.slides, start=1)]
    overrides = [
        ("/ppt/presentation.xml", CT_PML + "presentation.main+xml"),
        ("/ppt/slideMasters/slideMaster1.xml", CT_PML + "slideMaster+xml"),
        *((f"/ppt/slideLayouts/slideLayout{i}.xml", CT_PML + "slideLayout+xml") for i in LAYOUTS),
        ("/ppt/notesMasters/notesMaster1.xml", CT_PML + "notesMaster+xml"),
        ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        ("/ppt/theme/theme2.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        *((f"/ppt/slides/slide{k}.xml", CT_PML + "slide+xml") for k in range(1, n + 1)),
        *((f"/ppt/notesSlides/notesSlide{k}.xml", CT_PML + "notesSlide+xml") for k in range(1, n + 1)),
        ("/docProps/core.xml", "application/vnd.openxmlformats-package.core-properties+xml"),
    ]
    content_types = (
        f'{XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
        + "".join(f'<Override PartName="{p}" ContentType="{t}"/>' for p, t in overrides)
        + "</Types>"
    )
    title = f"{deck.lesson} · {deck.k}/{deck.n}"
    core = (
        f'{XML}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>أوراق</dc:creator>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created></cp:coreProperties>'
    )
    notes_rid = f"rId{n + 2}"
    presentation = (
        f'{XML}<p:presentation {NS} rtl="1" saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
        f'</p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="{notes_rid}"/></p:notesMasterIdLst><p:sldIdLst>'
        + "".join(f'<p:sldId id="{255 + k}" r:id="rId{k + 1}"/>' for k in range(1, n + 1))
        + f'</p:sldIdLst><p:sldSz cx="{WIDTH}" cy="{HEIGHT}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    )
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
        "ppt/_rels/presentation.xml.rels": _rels(
            [("rId1", f"{REL}/slideMaster", "slideMasters/slideMaster1.xml")]
            + [(f"rId{k + 1}", f"{REL}/slide", f"slides/slide{k}.xml") for k in range(1, n + 1)]
            + [(notes_rid, f"{REL}/notesMaster", "notesMasters/notesMaster1.xml")]
            + [(f"rId{n + 3}", f"{REL}/theme", "theme/theme1.xml")]
        ),
        "ppt/slideMasters/slideMaster1.xml": MASTER,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _rels(
            [(f"rId{i}", f"{REL}/slideLayout", f"../slideLayouts/slideLayout{i}.xml") for i in LAYOUTS]
            + [(f"rId{len(LAYOUTS) + 1}", f"{REL}/theme", "../theme/theme1.xml")]
        ),
        **{f"ppt/slideLayouts/slideLayout{i}.xml": _layout(name) for i, name in LAYOUTS.items()},
        **{
            f"ppt/slideLayouts/_rels/slideLayout{i}.xml.rels": _rels(
                [("rId1", f"{REL}/slideMaster", "../slideMasters/slideMaster1.xml")]
            )
            for i in LAYOUTS
        },
        "ppt/notesMasters/notesMaster1.xml": NOTES_MASTER,
        "ppt/notesMasters/_rels/notesMaster1.xml.rels": _rels(
            [("rId1", f"{REL}/theme", "../theme/theme2.xml")]
        ),
        "ppt/theme/theme1.xml": _theme(),
        "ppt/theme/theme2.xml": _theme(),
    }
    for k, (c, slide) in enumerate(zip(canvases, deck.slides, strict=True), start=1):
        parts[f"ppt/slides/slide{k}.xml"] = c.xml()
        parts[f"ppt/slides/_rels/slide{k}.xml.rels"] = _rels(
            [("rId1", f"{REL}/slideLayout", f"../slideLayouts/slideLayout{c.layout}.xml")]
            + [
                (f"rId{j + 2}", f"{REL}/image", f"../media/slide{k}_{name}")
                for j, (name, _) in enumerate(c.media)
            ]
            + [(f"rId{len(c.media) + 2}", f"{REL}/notesSlide", f"../notesSlides/notesSlide{k}.xml")]
        )
        parts[f"ppt/notesSlides/notesSlide{k}.xml"] = _notes(k, slide.notes)
        parts[f"ppt/notesSlides/_rels/notesSlide{k}.xml.rels"] = _rels(
            [
                ("rId1", f"{REL}/notesMaster", "../notesMasters/notesMaster1.xml"),
                ("rId2", f"{REL}/slide", f"../slides/slide{k}.xml"),
            ]
        )
    for k, c in enumerate(canvases, start=1):
        for name, data in c.media:
            parts[f"ppt/media/slide{k}_{name}"] = data

    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():  # [Content_Types].xml أولًا كما تشترط OPC عادةً
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data.encode("utf-8") if isinstance(data, str) else data)
    return out.getvalue()
