"""مرحلة student_clips: هندسة نقل الصندوق والبحث بمطابِق تحليلي مختلق (بلا OpenCV)، ثم المطابِق الحقيقي والمرحلة كلها على
ملفَي PDF اصطناعيين حين تتوفر pymupdf وOpenCV (بيئة guide_extract)؛ لا صفحة كتاب حقيقية."""

import json
import math

import pytest
import yaml

from tools.extraction import publish, stamps, student_clips
from tools.extraction.__main__ import main, run_stage
from tools.extraction.config import Book

from .conftest import TOY_PAGES, make_book

SEARCH = student_clips.DEFAULTS["search"]
PAGE = (600.0, 800.0)


# ───── نقل الصندوق ─────
def test_transfer_box_maps_panel_onto_student_page():
    panel = (20.0, 30.0, 335.0, 390.0)
    page = (0.0, 0.0, 630.0, 720.0)  # ضعف اللوحة في المحورين
    assert student_clips.transfer_box(panel, panel, page) == page
    assert student_clips.transfer_box((50.0, 60.0, 120.0, 100.0), panel, page) == (60.0, 60.0, 200.0, 140.0)


def test_transfer_box_scales_each_axis_and_round_trips():
    src, dst = (10.0, 10.0, 110.0, 60.0), (5.0, 0.0, 305.0, 200.0)  # ×3 أفقيًا و×4 رأسيًا
    box = (35.0, 20.0, 60.0, 45.0)
    moved = student_clips.transfer_box(box, src, dst)
    assert moved == (80.0, 40.0, 155.0, 140.0)
    assert student_clips.transfer_box(moved, dst, src) == pytest.approx(box)
    with pytest.raises(ValueError, match="فارغ"):
        student_clips.transfer_box(box, (0.0, 0.0, 0.0, 5.0), dst)


def test_panel_rect_keeps_wide_left_images_and_fixes_width():
    cfg = {"min_width": 900, "max_x0": 100, "width": 315}
    rects = [
        (22.0, 40.0, 263.0, 200.0, 1004),
        (20.0, 200.0, 261.0, 390.0, 1004),
        (400.0, 10.0, 700.0, 500.0, 1200),  # عمود الدليل الأيمن: خارج اللوحة
        (30.0, 5.0, 60.0, 20.0, 120),  # أيقونة
    ]
    assert student_clips.panel_rect(rects, cfg) == (20.0, 40.0, 335.0, 390.0)
    assert student_clips.panel_rect(rects, {**cfg, "width": None}) == (20.0, 40.0, 263.0, 390.0)
    assert student_clips.panel_rect(rects[2:], cfg) is None


def test_pixel_box_snaps_outward_and_stays_inside_the_scan():
    bbox, size = (0.0, 0.0, 600.0, 800.0), (2500, 3333)  # 300 بكسل لكل بوصة
    assert student_clips.pixel_box((72.0, 144.0, 144.0, 216.0), bbox, size) == (300, 599, 600, 900)
    assert student_clips.pixel_box((-10.0, 790.0, 30.1, 900.0), bbox, size) == (0, 3291, 126, 3333)
    assert round(student_clips.native_dpi(bbox, size)) == 300
    with pytest.raises(ValueError, match="خارج"):
        student_clips.pixel_box((700.0, 0.0, 720.0, 10.0), bbox, size)


def test_scan_image_needs_cover_and_upright_placement():
    full = {
        "xref": 7,
        "bbox": (0, 0, 600, 800),
        "width": 2500,
        "height": 3333,
        "transform": (600, 0, 0, 800, 0, 0),
    }
    figure = {"xref": 8, "bbox": (100, 100, 300, 300), "width": 800, "height": 800}
    assert student_clips.scan_image([figure, full], PAGE, 0.85) is full
    assert student_clips.scan_image([figure], PAGE, 0.85) is None  # صفحة متجهية فيها رسم نقطي
    rotated = {**full, "transform": (0, 800, -600, 0, 600, 0)}
    assert student_clips.scan_image([rotated], PAGE, 0.85) is None
    assert student_clips.scan_image([{**full, "xref": 0}], PAGE, 0.85) is None


# ───── المطابقة (مطابِق تحليلي: الدرجة تهبط بالبعد عن الموضع والمقياس الحقيقيين) ─────
def analytic(true_box, base, calls=None, ceiling=1.0):
    """مطابِق مختلق: يعيد موضع الصندوق الحقيقي إن وقع في النافذة (وإلا أقرب موضع فيها) بدرجة تهبط بخطأ المقياس والموضع."""
    tx, ty, true_w = true_box[0], true_box[1], true_box[2] - true_box[0]

    def match(dpi, size, window):
        if calls is not None:
            calls.append((dpi, size, window))
        x0, y0, x1, y1 = window or (0.0, 0.0, *PAGE)
        if x1 - x0 < size[0] or y1 - y0 < size[1]:
            return (-1.0, 0.0, 0.0)
        x = min(max(tx, x0), x1 - size[0])
        y = min(max(ty, y0), y1 - size[1])
        miss = math.hypot(x - tx, y - ty) / 50
        scale_error = abs(size[0] / base[0] - true_w / base[0]) * 5
        return (ceiling - miss - scale_error, x, y)

    return match


def test_refine_corrects_offset_and_scale_within_the_window():
    predicted = (100.0, 200.0, 300.0, 350.0)  # 200×150
    true = (130.0, 180.0, 130.0 + 200 * 1.07, 180.0 + 150 * 1.07)
    calls = []
    box, score, widened = student_clips.refine(
        analytic(true, (200.0, 150.0), calls), predicted, PAGE, SEARCH, 0.8
    )
    assert not widened and score > 0.95
    assert box == pytest.approx(true, abs=0.01 * 200 + 0.01)  # المقياس إلى ربع الخطوة
    assert {c[0] for c in calls} == {SEARCH["dpi"], SEARCH["fine_dpi"]}
    assert all(c[2] is not None for c in calls)  # لم يحتج إلى الصفحة كلها


def test_refine_widens_to_the_whole_page_when_the_window_misses():
    predicted = (50.0, 50.0, 250.0, 200.0)
    true = (350.0, 600.0, 550.0, 750.0)  # خارج نافذة 15% حول المنقول
    calls = []
    box, score, widened = student_clips.refine(
        analytic(true, (200.0, 150.0), calls), predicted, PAGE, SEARCH, 0.8
    )
    assert widened and score > 0.95
    assert box == pytest.approx(true, abs=0.5)
    assert any(c[2] is None for c in calls)


def test_refine_reports_a_weak_match_without_inventing_a_score():
    predicted = (100.0, 200.0, 300.0, 350.0)
    box, score, widened = student_clips.refine(
        analytic(predicted, (200.0, 150.0), ceiling=0.6), predicted, PAGE, SEARCH, 0.8
    )
    assert widened and score == pytest.approx(0.6)
    assert student_clips.status_of(score, "1.1_m1_p28.png", 0.8, []) == "review"
    assert student_clips.status_of(score, "1.1_m1_p28.png", 0.8, ["1.1_m1_p28.png"]) == "approved"
    assert student_clips.status_of(0.8, "1.1_m1_p28.png", 0.8, []) == "ok"


def test_refine_survives_a_template_larger_than_the_page():
    def never(dpi, size, window):
        return (-1.0, 0.0, 0.0)

    box, score, widened = student_clips.refine(never, (0.0, 0.0, 900.0, 900.0), PAGE, SEARCH, 0.8)
    assert score == -1.0 and widened and box == (0.0, 0.0, *PAGE)


def test_refine_corrects_each_axis_scale_when_the_panel_aspect_is_off():
    # اللوحة المقدَّرة أعرض من صفحة الطالب: المقياس الحقيقي 1.03 أفقيًا و0.98 رأسيًا، ولا مقياس موحَّد يطابقهما
    predicted = (100.0, 200.0, 300.0, 500.0)  # 200×300
    true = (104.0, 197.0, 104.0 + 200 * 1.03, 197.0 + 300 * 0.98)

    def match(dpi, size, window):
        x0, y0, x1, y1 = window or (0.0, 0.0, *PAGE)
        if x1 - x0 < size[0] or y1 - y0 < size[1]:
            return (-1.0, 0.0, 0.0)
        x = min(max(true[0], x0), x1 - size[0])
        y = min(max(true[1], y0), y1 - size[1])
        miss = math.hypot(x - true[0], y - true[1]) / 50
        stretch = abs(size[0] / 200 - 1.03) + abs(size[1] / 300 - 0.98)
        return (1.0 - miss - stretch * 5, x, y)

    box, score, _ = student_clips.refine(match, predicted, PAGE, SEARCH, 0.8)
    assert score > 0.95
    assert box == pytest.approx(true, abs=0.005 * 300 + 0.01)
    # بلا تصحيح المحورين يبقى خطأ النسبة في الدرجة والصندوق
    _, flat, _ = student_clips.refine(match, predicted, PAGE, {**SEARCH, "aspect": 0}, 0.8)
    assert flat < score - 0.08


def test_refine_finds_a_scale_outside_the_window_range_on_the_whole_page():
    # لوحة صفحة الطالب في الدليل أصغر من المقدَّر (أول صفحة في الدرس): المقياس الحقيقي 1.4 خارج scales [0.85, 1.15]
    predicted = (40.0, 300.0, 240.0, 450.0)  # 200×150
    true = (2.0, 420.0, 2.0 + 200 * 1.4, 420.0 + 150 * 1.4)
    trace = {}
    box, score, widened = student_clips.refine(
        analytic(true, (200.0, 150.0)), predicted, PAGE, SEARCH, 0.8, trace
    )
    assert widened and score > 0.95
    assert box == pytest.approx(true, abs=0.01 * 200 + 0.01)
    # أرقام التشخيص: درجة النافذة قبل التوسيع والمقياس المعتمد
    assert trace["near_score"] < 0.8 and trace["scale"] == pytest.approx([1.4, 1.4], abs=0.011)
    # بمدى النافذة وحده يقف المقياس عند حدّه الأعلى وتبقى الدرجة دون العتبة
    narrow_box, narrow, _ = student_clips.refine(
        analytic(true, (200.0, 150.0)), predicted, PAGE, {**SEARCH, "wide_scales": None}, 0.8
    )
    assert narrow < 0.8 and narrow_box[2] - narrow_box[0] < 200 * 1.25


def test_pick_shift_keeps_the_offset_page_unless_a_neighbor_is_proven():
    def pick(scores, margin=0.15):
        return student_clips.pick_shift(scores.get, range(-2, 3), 0.8, margin)

    assert pick({0: 0.9, 1: 0.99}) == 0  # صفحة الإزاحة بلغت العتبة: لا تُجرَّب جارة
    # أعلى درجة بين درجات كلها دون العتبة ضجيج: لا تُختار به صفحة جارة
    assert pick({-2: 0.28, -1: 0.25, 0: 0.2, 1: 0.31, 2: 0.3}) == 0
    assert pick({0: 0.3, 2: 0.92}) == 2  # جارة بلغت العتبة وعلت صفحة الإزاحة بالهامش
    assert pick({0: 0.72, 1: 0.82}) == 0  # بلغت العتبة ولم تتميّز عن صفحة الإزاحة
    assert pick({0: 0.3, -1: 0.9, 1: 0.95, 2: 0.99}) == -1  # الأقرب فالأقرب، والسالب أولًا عند التساوي
    assert pick({1: 0.4, 2: 0.6}) == 2  # صفحة الإزاحة خارج الملف: أعلى الجارات (تبقى للمراجعة)
    assert pick({1: 0.85}) == 1
    assert pick({}) is None


def test_pinned_edges_name_the_page_borders_a_box_touches():
    assert student_clips.pinned_edges((1.0, 48.0, 410.0, 130.0), PAGE) == []
    assert student_clips.pinned_edges((0.0, 0.0, 304.3, 140.9), PAGE) == ["left", "top"]
    assert student_clips.pinned_edges((6.0, 49.5, 600.0, 800.0), PAGE) == ["right", "bottom"]


# ───── إطار صفحة الطالب في الدليل ─────
# أرقام من تقرير قصّ العاشر (2026-11-20): (صندوق الدليل، اللوحة، الصندوق في صفحة الطالب) لعشرة مقاطع بلغت العتبة
STUDENT = (595.3, 783.1)
MEASURED = [
    ((37.4, 137.5, 246.6, 445.3), (30.1, 108.3, 345.1, 511.5), (2.0, 48.0, 417.9, 663.8)),
    ((56.9, 136.8, 261.5, 278.3), (49.8, 107.5, 364.8, 510.7), (3.5, 48.0, 408.5, 331.0)),
    ((56.9, 288.7, 261.5, 477.7), (49.8, 107.5, 364.8, 510.7), (1.0, 352.0, 409.9, 730.1)),
    ((36.7, 137.5, 245.7, 458.1), (29.8, 108.3, 344.8, 511.5), (2.0, 48.0, 417.5, 689.3)),
    ((36.7, 137.5, 241.4, 305.8), (30.1, 108.3, 345.1, 511.5), (1.0, 48.0, 409.9, 384.7)),
    ((36.7, 313.2, 241.4, 455.8), (30.1, 108.3, 345.1, 511.5), (1.0, 399.5, 409.9, 684.7)),
    ((37.4, 184.3, 246.6, 484.0), (30.1, 108.3, 345.1, 511.5), (4.0, 141.5, 417.9, 741.1)),
    ((56.9, 136.8, 261.5, 438.7), (49.8, 107.5, 364.8, 510.7), (2.0, 48.0, 408.9, 651.9)),
    ((55.4, 136.8, 259.2, 469.3), (48.5, 107.6, 363.5, 510.8), (5.0, 48.0, 408.2, 713.1)),
    ((37.4, 172.8, 246.6, 423.0), (30.1, 108.3, 345.1, 511.5), (2.0, 118.5, 417.9, 619.0)),
]


def measured_fit():
    return student_clips.fit_frame([(g, p, b, STUDENT) for g, p, b in MEASURED], 8, SEARCH["step"])


def test_fit_frame_measures_one_scale_and_the_panel_margins():
    fit = measured_fit()
    # الصفحة مصغَّرة إلى النصف بنسبتها، وصورة اللوحة تزيد عليها هامشًا عند كل حافة: النقل من اللوحة كلها يخطئ بهما
    assert fit.scale == pytest.approx(2.0, abs=0.01) and fit.clips == 10
    assert (fit.left, fit.top, fit.bottom) == pytest.approx((6.1, 5.2, 6.5), abs=0.4)
    assert 2.0 <= fit.tolerance <= 5.0 and fit.stretch == SEARCH["step"]
    assert student_clips.fit_frame([(g, p, b, STUDENT) for g, p, b in MEASURED[:7]], 8, 0.02) is None
    # لوحة شاذة (صور أخرى تحت صفحة الطالب) لا تزيح الوسيط
    odd = ((37.4, 137.5, 246.6, 445.3), (30.1, 108.3, 345.1, 696.2), (2.0, 48.0, 417.9, 663.8), STUDENT)
    skewed = student_clips.fit_frame([(g, p, b, STUDENT) for g, p, b in MEASURED] + [odd], 8, 0.02)
    assert skewed.bottom == pytest.approx(fit.bottom, abs=0.1)


def test_frame_candidates_anchor_the_page_to_the_top_and_to_the_bottom_of_the_panel():
    fit = measured_fit()
    height = STUDENT[1] / fit.scale
    # لوحة بمقاس الصفحة وهامشيها: المرشّحان واحد
    assert len(student_clips.frame_candidates([], (30.1, 108.3, 345.1, 511.5), STUDENT, fit)) == 1
    # أول صفحة في الدرس: الصفحة مقصوصة من أعلاها فاللوحة أقصر، والإطار الصحيح المثبَّت بحافتها السفلى يبدأ فوقها
    short = (47.4, 100.4, 362.4, 389.8)
    top, bottom = student_clips.frame_candidates([], short, STUDENT, fit)
    assert top[1] == pytest.approx(100.4 + fit.top) and bottom[3] == pytest.approx(389.8 - fit.bottom)
    assert bottom[1] < 0 and bottom[3] - bottom[1] == pytest.approx(height)
    _, predicted = student_clips.frame_target((54.0, 144.7, 258.1, 324.2), bottom, STUDENT)
    assert (predicted[1], predicted[3]) == pytest.approx(
        (304.5, 663.8), abs=3.0
    )  # ما استقر عليه البحث الموسَّع رأسيًا
    assert predicted[2] - predicted[0] == pytest.approx(2 * 204.1, abs=3.0)  # وعرضه ضعف عرض الدليل لا 0.8 منه
    # صور اللوحة نفسها مرشّحات أيضًا: صورة أخرى تحت صفحة الطالب لا تُفسد التثبيت السفلي
    images = [(30.1, 108.3, 331.0, 511.5, 1004), (20.9, 511.5, 335.9, 696.2, 1200)]
    frames = student_clips.frame_candidates(images, (20.9, 108.3, 335.9, 696.2), STUDENT, fit)
    assert len(frames) == 4  # أعلى اللوحة وأعلى صورتها الأولى مرشّح واحد
    assert any(
        f[0] == pytest.approx(30.1 + fit.left) and f[1] == pytest.approx(108.3 + fit.top) for f in frames
    )


def test_frame_target_keeps_only_the_part_of_the_clip_inside_the_student_page():
    fit = measured_fit()
    (frame,) = student_clips.frame_candidates([], (30.1, 108.3, 345.1, 512.5), STUDENT, fit)
    # تتمة تبدأ فوق صفحة الطالب (هامش الصورة وحافة اللوحة): يُقطع ما فوقها والمنقول يبدأ عند حافة الصفحة العليا
    cont = (36.7, 106.6, 246.4, 381.2)
    part, predicted = student_clips.frame_target(cont, frame, STUDENT)
    assert part[1] == pytest.approx(frame[1]) and part[1] - cont[1] == pytest.approx(6.9, abs=0.3)
    assert predicted[1] == 0.0 and (part[0], part[2], part[3]) == (cont[0], cont[2], cont[3])
    # مقطع ينتهي تحت صفحة الطالب: يُقطع ما تحتها والمنقول ينتهي عند حافتها السفلى، وأعلاه عند 48 كسائر الصفحات
    (frame,) = student_clips.frame_candidates([], (29.8, 108.3, 344.8, 511.5), STUDENT, fit)
    part, predicted = student_clips.frame_target((36.7, 137.5, 241.2, 509.8), frame, STUDENT)
    assert part[3] == pytest.approx(frame[3]) and predicted[3] == pytest.approx(STUDENT[1])
    assert predicted[1] == pytest.approx(48.0, abs=1.0)
    # مقطع خارج الإطار كله أو جلّه لا يُطابَق
    assert student_clips.frame_target((36.7, 600.0, 241.2, 700.0), frame, STUDENT) is None
    assert student_clips.frame_target((36.7, 300.0, 241.2, 900.0), frame, STUDENT, min_part=0.5) is None
    assert student_clips.intersect((0.0, 0.0, 5.0, 5.0), (5.0, 0.0, 9.0, 5.0)) is None
    assert student_clips.deviation((0.0, 0.0, 5.0, 5.0), (1.0, -3.0, 5.0, 7.0)) == 3.0


FIT = student_clips.FrameFit(scale=2.0, left=6.0, top=5.0, bottom=7.0, tolerance=3.0, stretch=0.02, clips=10)
FRAME_SEARCH = student_clips.frame_search(SEARCH, student_clips.DEFAULTS["frame"])
WHOLE = (0.0, 0.0, *PAGE)


def stretched(true, ceiling=1.0):
    """مطابِق مختلق بمقياس لكل محور: الدرجة تهبط بخطأ الموضع (محصورًا في الصفحة: القالب لا يخرج عنها) وخطأ كل مقياس."""

    def match(dpi, size, window):
        x0, y0, x1, y1 = window or WHOLE
        if x1 - x0 < size[0] or y1 - y0 < size[1]:
            return (-1.0, 0.0, 0.0)
        x = min(max(true[0], x0), x1 - size[0])
        y = min(max(true[1], y0), y1 - size[1])
        miss = math.hypot(x - true[0], y - true[1]) / 50
        stretch = abs(size[0] / (true[2] - true[0]) - 1) + abs(size[1] / (true[3] - true[1]) - 1)
        return (ceiling - miss - stretch * 5, x, y)

    return match


def in_frames(guide_box, panel, true_frame, floor=None, ceiling=1.0, shift=0.0, images=()):
    """مطابقة بالإطار بمطابِق مختلق: كل جزء من المقطع موضعه الحقيقي نقله من الإطار الحقيقي (مزاحًا أفقيًا بـ `shift`)."""

    def matcher_for(part):
        x0, y0, x1, y1 = student_clips.transfer_box(part, true_frame, WHOLE)
        return stretched((x0 + shift, y0, x1 + shift, y1), ceiling)

    frames = student_clips.frame_candidates(images, panel, PAGE, FIT)
    return student_clips.refine_in_frames(
        matcher_for, guide_box, frames, PAGE, FRAME_SEARCH, 0.8, FIT, floor, 0.25
    )


def whole_clip(guide_box, panel, true_frame):
    """المطابقة السابقة: المقطع كله قالبًا، منقولًا من اللوحة كلها."""
    true = student_clips.transfer_box(guide_box, true_frame, WHOLE)
    predicted = student_clips.transfer_box(guide_box, panel, WHOLE)
    return student_clips.refine(stretched(true), predicted, PAGE, SEARCH, 0.8)


def test_clip_starting_above_the_student_page_is_matched_by_its_inner_part():
    panel, frame = (30.0, 100.0, 345.0, 512.0), (36.0, 105.0, 336.0, 505.0)
    cont = (40.0, 98.0, 250.0, 200.0)  # 7 نقاط منه فوق صفحة الطالب
    _, before, _ = whole_clip(cont, panel, frame)
    assert before < 0.8  # ما فوق الصفحة يمنع القالب من موضعه: المحتوى مزاح 14 نقطة
    found = in_frames(cont, panel, frame)
    assert found["evidence"] == "score" and found["score"] > 0.95 and not found["widened"]
    assert found["template"] == (40.0, 105.0, 250.0, 200.0)
    assert found["box"] == pytest.approx((8.0, 0.0, 428.0, 190.0), abs=1.0)
    assert student_clips.pinned_edges(found["box"], PAGE) == ["top"]


def test_clip_ending_below_the_student_page_is_matched_by_its_inner_part():
    panel, frame = (30.0, 100.0, 345.0, 512.0), (36.0, 105.0, 336.0, 505.0)
    clip_box = (40.0, 300.0, 250.0, 513.0)  # 8 نقاط منه تحت صفحة الطالب
    _, before, _ = whole_clip(clip_box, panel, frame)
    assert before < 0.8
    found = in_frames(clip_box, panel, frame)
    assert found["evidence"] == "score" and found["score"] > 0.95
    assert found["template"] == (40.0, 300.0, 250.0, 505.0)
    assert found["box"] == pytest.approx((8.0, 390.0, 428.0, 800.0), abs=1.0)
    assert student_clips.pinned_edges(found["box"], PAGE) == ["bottom"]


def test_predicted_inside_the_page_but_far_is_fixed_by_the_frame_anchor():
    # لوحة أطول من الصفحة (صورة أخرى تحتها): مقياس النقل الرأسي من ارتفاعها يخطئ بأكثر مما يصحّحه البحث
    tall, frame = (30.0, 100.0, 345.0, 640.0), (36.0, 105.0, 336.0, 505.0)
    clip_box = (40.0, 300.0, 250.0, 460.0)
    _, before, _ = whole_clip(clip_box, tall, frame)
    assert before < 0.8
    found = in_frames(clip_box, tall, frame)
    assert found["evidence"] == "score" and found["frame"] == pytest.approx(frame)
    assert found["box"] == pytest.approx((8.0, 390.0, 428.0, 710.0), abs=1.0) and not found["widened"]
    # أول صفحة في الدرس: لوحة أقصر (الصفحة مقصوصة من أعلاها)، والإطار الصحيح مثبَّت بحافتها السفلى
    short, frame = (47.0, 100.0, 362.0, 390.0), (53.0, -17.0, 353.0, 383.0)
    clip_box = (54.0, 145.0, 258.0, 324.0)
    _, before, _ = whole_clip(clip_box, short, frame)
    assert before < 0.8
    found = in_frames(clip_box, short, frame, floor=0.5, ceiling=0.7)
    assert found["frame"] == pytest.approx(frame) and found["evidence"] == "geometry"
    assert found["box"] == pytest.approx((2.0, 324.0, 410.0, 682.0), abs=1.0)


def test_geometric_evidence_needs_position_scale_and_a_measured_floor():
    panel, frame = (30.0, 100.0, 345.0, 512.0), (36.0, 105.0, 336.0, 505.0)
    clip_box = (40.0, 150.0, 250.0, 300.0)
    weak = in_frames(clip_box, panel, frame, floor=0.59, ceiling=0.7)
    # الموضع الصحيح بدرجة دون العتبة: بحث النافذة استقر على المتوقع من الإطار والمقياس 1 والدرجة فوق مستوى الصفحات الخاطئة
    assert weak["evidence"] == "geometry" and weak["score"] == pytest.approx(0.7)
    assert weak["deviation"] <= FIT.tolerance and not weak["widened"]
    assert student_clips.status_of(weak["score"], "1.1_m1_p28.png", 0.8, [], weak["evidence"]) == "ok"
    assert student_clips.status_of(0.7, "1.1_m1_p28.png", 0.8, []) == "review"  # العتبة نفسها لم تُخفض
    assert (
        in_frames(clip_box, panel, frame, floor=None, ceiling=0.7)["evidence"] is None
    )  # بلا درجة دنيا مقيسة
    assert in_frames(clip_box, panel, frame, floor=0.75, ceiling=0.7)["evidence"] is None  # دون الدرجة الدنيا
    # الموضع يبعد عن المتوقع بأكثر من انحراف المعايرة: لا دليل
    assert in_frames(clip_box, panel, frame, floor=0.59, ceiling=0.7, shift=10.0)["evidence"] is None
    # والمقياس خارج مداها كذلك
    off = {**weak, "scale": [1.0, 1.035]}
    assert not student_clips.geometric(off, FIT, 0.59) and student_clips.geometric(weak, FIT, 0.59)
    assert not student_clips.geometric({**weak, "widened": True}, FIT, 0.59)  # الصفحة كلها ليست دليل موضع
    assert student_clips.score_floor({"blur": {"hit": 0.68, "miss": 0.39}}, "blur", 0.2) == pytest.approx(
        0.59
    )
    assert student_clips.score_floor({}, "blur", 0.2) is None


def test_refine_without_widening_stays_in_the_window():
    predicted = (50.0, 50.0, 250.0, 200.0)
    true = (350.0, 600.0, 550.0, 750.0)
    calls = []
    _, score, widened = student_clips.refine(
        analytic(true, (200.0, 150.0), calls), predicted, PAGE, SEARCH, 0.8, widen=False
    )
    assert not widened and score < 0.8 and all(c[2] is not None for c in calls)


def test_steps_are_inclusive_and_exact():
    assert student_clips.steps(0.85, 1.15, 0.02)[:2] == [0.85, 0.87]
    assert student_clips.steps(0.85, 1.15, 0.02)[-1] == 1.15
    assert len(student_clips.steps(0.85, 1.15, 0.02)) == 16


# ───── الإزاحة والأسماء والتقرير ─────
def clip(name):
    return student_clips.parse(name)


def test_parse_names():
    assert clip("2.10_m3_p189_cont.png") == student_clips.ClipName(
        "2.10_m3_p189_cont.png", "2.10", 3, 189, True
    )
    assert clip("1.1_m1_p28.png").cont is False
    assert clip("index.json") is None and clip("1.1_m1_p28_thumb.png") is None


def test_estimate_offset_takes_the_best_mean_and_rejects_weak_or_absent():
    samples = [clip("1.1_m1_p28.png"), clip("3.5_m2_p274.png")]

    def score_at(c, offset):
        if offset > 12:
            return None  # صفحة خارج الملف
        return 0.95 if offset == 9 else 0.3

    assert student_clips.estimate_offset(score_at, samples, range(0, 41), 0.8) == (9, pytest.approx(0.95))
    with pytest.raises(student_clips.StudentClipsError, match="page_offset"):
        student_clips.estimate_offset(lambda c, o: 0.4, samples, range(0, 5), 0.8)
    with pytest.raises(student_clips.StudentClipsError, match="لا مرشّح"):
        student_clips.estimate_offset(lambda c, o: None, samples, range(0, 5), 0.8)


def test_estimate_offset_accepts_a_distinct_peak_below_the_threshold():
    samples = [clip("1.1_m1_p28.png"), clip("3.5_m2_p274.png")]

    def weak_peak(c, offset):  # الصفحة الصحيحة 0.55 والبقية 0.3: دون العتبة لكنها قمة منفردة
        return 0.55 if offset == 8 else 0.3

    with pytest.raises(student_clips.StudentClipsError, match="أفضل متوسط 0.55 عند 8"):
        student_clips.estimate_offset(weak_peak, samples, range(-20, 61), 0.8)
    assert student_clips.estimate_offset(weak_peak, samples, range(-20, 61), 0.8, 0.15) == (
        8,
        pytest.approx(0.55),
    )
    with pytest.raises(student_clips.StudentClipsError, match="page_offset"):  # قمتان متقاربتان: لا تميّز
        student_clips.estimate_offset(
            lambda c, o: 0.55 if o in (8, 9) else 0.3, samples, range(0, 41), 0.8, 0.15
        )
    with pytest.raises(student_clips.StudentClipsError, match="page_offset"):  # مرشّح وحيد لا يُقارَن بغيره
        student_clips.estimate_offset(weak_peak, samples, range(8, 9), 0.8, 0.15)


def test_pick_mode_takes_the_first_sound_representation_that_reaches_the_threshold():
    samples = [clip("1.1_m1_p28.png"), clip("3.5_m2_p274.png")]
    scores = {
        "gray": (0.5, 0.2),  # يفصل الصفحة الصحيحة عن جاراتها لكنه دون العتبة
        "blur": (0.9, 0.85),  # يبلغ العتبة في كل صفحة: لا يميّز
        "binary": (0.86, 0.3),
        "edges": (0.95, 0.3),
    }

    def score_at(mode, c, shift):
        if shift == 2:
            return None  # صفحة خارج الملف
        return scores[mode][0 if shift == 0 else 1]

    modes = list(scores)
    mode, table = student_clips.pick_mode(score_at, modes, samples, range(-2, 3), 0.8, 0.2)
    assert mode == "binary"  # أول سليم يبلغ العتبة، لا الأعلى درجة
    assert table["blur"] == {"hit": 0.9, "miss": 0.85} and table["gray"] == {"hit": 0.5, "miss": 0.2}
    assert student_clips.pick_mode(score_at, ["gray", "blur"], samples, range(-2, 3), 0.8, 0.2)[0] == "gray"
    assert student_clips.pick_mode(score_at, ["blur"], samples, range(-2, 3), 0.8, 0.2)[0] == "blur"
    with pytest.raises(student_clips.StudentClipsError, match="معايرة"):
        student_clips.pick_mode(lambda m, c, s: None, modes, samples, range(-2, 3), 0.8, 0.2)


def test_neighbor_pages_fill_only_between_consecutive_neighbors():
    table = {176: 97, 178: 99, 224: 125, 227: 128, 240: 140, 242: 150}
    filled = student_clips.neighbor_pages(table, [177, 178, 225, 226, 241, 20, 300])
    # 241 بين جارتين غير متتابعتين، و20 و300 بلا جارة من جهة: تبقى غائبة
    assert filled == {177: 98, 225: 126, 226: 127}


def test_pick_samples_spreads_over_main_clips():
    names = [f"1.{i}_m1_p{20 + i}.png" for i in range(1, 8)] + ["1.2_m1_p23_cont.png"]
    clips = [clip(n) for n in sorted(names)]
    picked = student_clips.pick_samples(clips, 3)
    assert [c.file for c in picked] == ["1.1_m1_p21.png", "1.4_m1_p24.png", "1.7_m1_p27.png"]
    assert not any(c.cont for c in picked)
    assert student_clips.pick_samples(clips[:2], 3) == [c for c in clips[:2] if not c.cont]


def test_summary_counts_and_unreviewed():
    result = {
        "page_offset": 9,
        "mode": "edges",
        "unmatched": ["x.png"],
        "clips": [
            {
                "file": "a.png",
                "lesson": "1.1",
                "page_shift": 0,
                "status": "ok",
                "score": 0.97,
                "kind": "vector",
                "dpi": 600,
            },
            {
                "file": "b.png",
                "lesson": "2.10",
                "page_shift": 1,
                "status": "approved",
                "score": 0.71,
                "kind": "scan",
                "dpi": 300,
            },
            {"file": "c.png", "lesson": "2.3", "page_shift": -2, "status": "review", "score": 0.42},
            {
                "file": "e.png",
                "lesson": "1.1",
                "page_shift": 0,
                "status": "ok",
                "score": 0.66,
                "evidence": "geometry",
                "kind": "vector",
                "dpi": 600,
            },
            {"file": "d.png", "lesson": "3.1", "status": "missing"},
        ],
    }
    assert student_clips.summarize(result) == {
        "clips": 5,
        "written": 3,
        "review": ["c.png", "d.png"],
        "min_score": 0.42,
        "min_dpi": 300,
        "geometry": 1,
        "kinds": {"vector": 2, "scan": 1},
        "page_offset": 9,
        "mode": "edges",
        "shifts": {"1": {"0": 2}, "2": {"1": 1}},  # المكتوب وحده: انزياح المطابقة الضعيفة لا يُعدّ
        "unmatched_names": 1,
    }
    assert student_clips.unreviewed(result) == ["c.png", "d.png"]


# ───── الإعداد والأختام وسطر الأوامر ─────
def toy(tmp_path, **over):
    dirs = {"examples_hires": "hires", "examples_student": "student"}
    over.setdefault("student_pdf", {"dir": "books", "pattern": "student*.pdf"})
    book = make_book(tmp_path, TOY_PAGES, dirs=dirs, **over)
    (tmp_path / "hires").mkdir(exist_ok=True)
    (tmp_path / "books").mkdir(exist_ok=True)
    (tmp_path / "guide.pdf").write_bytes(b"guide")
    (tmp_path / "books" / "student.pdf").write_bytes(b"student")
    (tmp_path / "printed_pages.json").write_text(json.dumps({"3": 13}), encoding="utf-8")
    return book


def test_config_errors():
    assert student_clips.errors({}) == []
    assert student_clips.errors({"student_pdf": {"dir": "d", "pattern": "*.pdf"}, "student_clips": {}}) == []
    errs = student_clips.errors(
        {
            "student_pdf": {"dir": "d"},
            "student_clips": {
                "threshold": 1.5,
                "page_offset": "9",
                "offsets": [5, 1],
                "modes": ["gray", "sepia"],
                "approved": "x",
            },
        }
    )
    assert len(errs) == 6
    assert student_clips.errors({"student_clips": 3}) == ["student_clips يجب أن يكون خريطة"]


def test_book_with_bad_student_clips_config_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="threshold"):
        make_book(tmp_path, TOY_PAGES, student_clips={"threshold": 0})


def test_settings_merge_nested_defaults(tmp_path):
    book = toy(
        tmp_path, student_clips={"search": {"margin": 0.3}, "panel": {"width": None}, "page_offset": 9}
    )
    cfg = student_clips.settings(book)
    assert cfg["search"]["margin"] == 0.3 and cfg["search"]["step"] == SEARCH["step"]
    assert cfg["panel"] == {"min_width": 900, "max_x0": 100, "width": None}
    assert cfg["frame"] == student_clips.DEFAULTS["frame"]
    assert (cfg["page_offset"], cfg["threshold"], cfg["vector_dpi"]) == (9, 0.8, 600)


def test_student_pdf_is_resolved_and_missing_is_explicit(tmp_path):
    book = toy(tmp_path)
    assert student_clips.student_pdf(book) == tmp_path / "books" / "student.pdf"
    (tmp_path / "books" / "student.pdf").unlink()
    with pytest.raises(student_clips.StudentClipsError, match="لا ملف يطابق"):
        student_clips.student_pdf(book)
    cfg = yaml.safe_load((tmp_path / "book.yaml").read_text(encoding="utf-8"))
    del cfg["student_pdf"]
    (tmp_path / "book.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(student_clips.StudentClipsError, match="student_pdf"):
        student_clips.student_pdf(Book.load(tmp_path))


def fake_run(scores):
    def run(book, table):
        clips = [
            {
                "file": name,
                "status": student_clips.status_of(score, name, 0.8, student_clips.settings(book)["approved"]),
                "score": score,
                "kind": "vector",
                "dpi": 600,
            }
            for name, score in scores.items()
        ]
        return {"page_offset": 9, "offset_score": None, "threshold": 0.8, "clips": clips, "unmatched": []}

    return run


def test_stage_writes_report_stamps_and_follows_its_inputs(tmp_path, monkeypatch, capsys):
    book = toy(tmp_path)
    monkeypatch.setattr(student_clips, "run", fake_run({"1.1_m1_p3.png": 0.93}))
    assert main([str(tmp_path), "student_clips"]) == 0
    assert '"written": 1' in capsys.readouterr().out
    report = json.loads((tmp_path / "student_clips.json").read_text(encoding="utf-8"))
    assert report["clips"][0]["score"] == 0.93 and report["clips"][0]["dpi"] == 600
    assert run_stage(book, "student_clips") is False  # مختومة
    (tmp_path / "books" / "student.pdf").write_bytes(b"student v2")  # كتاب الطالب مدخل
    assert run_stage(book, "student_clips") is True
    (tmp_path / "hires" / "1.1_m2_p4.png").write_bytes(b"png")  # والمقاطع الحالية
    assert run_stage(book, "student_clips") is True
    (tmp_path / "printed_pages.json").write_text(json.dumps({"3": 14}), encoding="utf-8")  # والجدول
    assert run_stage(book, "student_clips") is True
    assert run_stage(book, "student_clips") is False


def test_weak_match_without_review_exits_seven_and_leaves_no_stamp(tmp_path, monkeypatch, capsys):
    toy(tmp_path)
    monkeypatch.setattr(student_clips, "run", fake_run({"1.1_m1_p3.png": 0.93, "1.1_m2_p4.png": 0.55}))
    assert main([str(tmp_path), "student_clips"]) == 7
    assert "1.1_m2_p4.png" in capsys.readouterr().err
    assert (tmp_path / "student_clips.json").exists()  # التقرير مكتوب ليُراجَع
    stamp_file = tmp_path / ".stamps.json"
    assert not stamp_file.exists() or "student_clips" not in json.loads(
        stamp_file.read_text(encoding="utf-8")
    )
    # اعتماد المالك للمطابقة الضعيفة يمرّرها
    toy(tmp_path, student_clips={"approved": ["1.1_m2_p4.png"]})
    assert main([str(tmp_path), "student_clips"]) == 0


def test_missing_student_pdf_or_table_exits_seven(tmp_path, monkeypatch, capsys):
    toy(tmp_path)
    (tmp_path / "printed_pages.json").unlink()
    assert main([str(tmp_path), "student_clips"]) == 7
    assert "printed_pages" in capsys.readouterr().err
    (tmp_path / "books" / "student.pdf").unlink()
    assert main([str(tmp_path), "student_clips"]) == 7
    assert "لا ملف يطابق" in capsys.readouterr().err


def test_student_decks_runs_on_a_throwaway_database_and_storage(tmp_path, monkeypatch, capsys):
    toy(tmp_path, student_clips={"course": "g10-s1"})
    (tmp_path / "student").mkdir()
    (tmp_path / "student_clips.json").write_text("{}", encoding="utf-8")
    calls = []

    def run(book, args, env=None):
        calls.append((args, env))
        return "g10-s1: جديد 1" if args[0] == "publish_assets" else "ناجح 48 فاشل 0"

    monkeypatch.setattr(publish, "run_manage", run)
    assert main([str(tmp_path), "student_decks"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "ناجح 48 فاشل 0"
    assert [c[0][0] for c in calls] == ["migrate", "load_course", "publish_assets", "build_period_decks"]
    assert calls[2][0] == ["publish_assets", "g10-s1", "--source", str(tmp_path / "student")]
    envs = [c[1] for c in calls]
    assert all(e == envs[0] for e in envs)
    assert envs[0]["DATABASE_URL"].startswith("sqlite:///") and envs[0]["ASSETS_STORAGE"] == "local"
    assert str(tmp_path) not in envs[0]["ASSETS_LOCAL_ROOT"]  # خارج مجلد الكتاب: مؤقت يُحذف
    assert (
        json.loads((tmp_path / "student_decks.json").read_text(encoding="utf-8"))["decks"] == "ناجح 48 فاشل 0"
    )


def test_student_decks_failures_exit_five(tmp_path, monkeypatch, capsys):
    toy(tmp_path)
    assert main([str(tmp_path), "student_decks"]) == 5  # بلا course
    assert "student_clips.course" in capsys.readouterr().err
    toy(tmp_path, student_clips={"course": "g10-s1"})
    assert main([str(tmp_path), "student_decks"]) == 5  # بلا مجلد مقاطع
    (tmp_path / "student").mkdir()

    def failing(book, args, env=None):
        if args[0] == "build_period_decks":
            raise publish.PublishError("فشل build_period_decks: ناجح 40 فاشل 8")
        return "تم"

    monkeypatch.setattr(publish, "run_manage", failing)
    assert main([str(tmp_path), "student_decks"]) == 5
    assert "ناجح 40 فاشل 8" in capsys.readouterr().err
    assert not (tmp_path / "student_decks.json").exists()


def test_other_stage_stamps_do_not_depend_on_the_student_book(tmp_path):
    book = toy(tmp_path)
    before = stamps.digest(book, "printed_pages")
    (tmp_path / "books" / "student.pdf").write_bytes(b"changed")
    assert stamps.digest(book, "printed_pages") == before


# ───── المطابِق الحقيقي والمرحلة كلها (بيئة guide_extract: pymupdf وOpenCV) ─────
def _texture(np, width, height, seed):
    """صورة رمادية بتفاصيل غير دورية: مستطيلات عشوائية على بياض."""
    rng = np.random.default_rng(seed)
    image = np.full((height, width), 255, dtype=np.uint8)
    for _ in range(120):
        x, y = int(rng.integers(0, width - 20)), int(rng.integers(0, height - 20))
        w, h = int(rng.integers(4, 60)), int(rng.integers(4, 40))
        image[y : y + h, x : x + w] = int(rng.integers(0, 200))
    return image


def test_cv_matcher_finds_a_scaled_shifted_crop():
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    page_px = _texture(np, 1200, 1600, seed=1)  # الصفحة 600×800 نقطة بدقة 144

    def page_image(dpi):
        k = dpi / 144
        return cv2.resize(page_px, (round(1200 * k), round(1600 * k)), interpolation=cv2.INTER_AREA)

    true = (150.0, 260.0, 390.0, 440.0)
    crop = page_px[520:880, 300:780]
    template = cv2.resize(crop, (700, 525), interpolation=cv2.INTER_CUBIC)  # المقطع الحالي بمقياس آخر
    predicted = (120.0, 300.0, 120.0 + 240 / 1.08, 300.0 + 180 / 1.08)  # منقول بإزاحة ومقياس خاطئين
    match = student_clips.cv_matcher(page_image, template)
    box, score, widened = student_clips.refine(match, predicted, PAGE, SEARCH, 0.8)
    assert score > 0.9 and not widened
    assert box == pytest.approx(true, abs=3.0)
    other = student_clips.cv_matcher(page_image, _texture(np, 700, 525, seed=99))
    assert student_clips.refine(other, predicted, PAGE, SEARCH, 0.8)[1] < 0.5  # محتوى آخر لا يطابق


def _page_image(cv2, page_px):
    def page_image(dpi):
        k = dpi / 144
        size = (round(page_px.shape[1] * k), round(page_px.shape[0] * k))
        return cv2.resize(page_px, size, interpolation=cv2.INTER_AREA)

    return page_image


def test_cv_matcher_recovers_a_crop_stretched_on_one_axis():
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    page_px = _texture(np, 1200, 1600, seed=3)
    true = (150.0, 260.0, 390.0, 440.0)  # 240×180 نقطة
    template = cv2.resize(page_px[520:880, 300:780], (700, 525), interpolation=cv2.INTER_CUBIC)
    # المنقول أضيق 4% وأطول 3% من الحقيقي: نسبة اللوحة المقدَّرة تخالف صفحة الطالب
    predicted = (145.0, 255.0, 145.0 + 240 / 1.04, 255.0 + 180 / 0.97)
    match = student_clips.cv_matcher(_page_image(cv2, page_px), template)
    box, score, _ = student_clips.refine(match, predicted, PAGE, SEARCH, 0.8)
    assert score > 0.9
    assert box == pytest.approx(true, abs=2.0)
    flat, _, _ = student_clips.refine(match, predicted, PAGE, {**SEARCH, "aspect": 0}, 0.8)
    assert abs((flat[3] - flat[1]) - 180.0) > 4.0  # المقياس الموحَّد يترك خطأ النسبة في الصندوق


def test_part_matcher_matches_only_the_part_of_the_clip_inside_the_page():
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    page_px = _texture(np, 1200, 1600, seed=9)  # 600×800 نقطة بدقة 144
    page_image = _page_image(cv2, page_px)
    panel, frame = (30.0, 100.0, 345.0, 512.0), (36.0, 105.0, 336.0, 505.0)
    cont = (40.0, 98.0, 250.0, 200.0)  # 7 نقاط دليل فوق صفحة الطالب، ثم أعلى الصفحة (8, 0)-(428, 190)
    above = _texture(np, 840, 28, seed=10)  # ما فوق الصفحة في الدليل: ليس في صفحة الطالب
    clip_px = np.vstack([above, page_px[0:380, 16:856]])  # 4 بكسلات لكل نقطة دليل
    frames = student_clips.frame_candidates([], panel, PAGE, FIT)
    assert frames == [pytest.approx(frame)]
    found = student_clips.refine_in_frames(
        student_clips.part_matcher(page_image, clip_px, cont),
        cont,
        frames,
        PAGE,
        FRAME_SEARCH,
        0.8,
        FIT,
        None,
    )
    assert found["evidence"] == "score" and found["score"] > 0.9
    assert found["box"] == pytest.approx((8.0, 0.0, 428.0, 190.0), abs=3.0)
    # المقطع كله قالبًا لا يبلغ درجة جزئه الداخلي: ما فوق الصفحة لا مقابل له فيها
    predicted = student_clips.transfer_box(cont, panel, WHOLE)
    whole = student_clips.refine(student_clips.cv_matcher(page_image, clip_px), predicted, PAGE, SEARCH, 0.8)
    assert whole[1] < found["score"]


def test_cv_matcher_representations_survive_tone_and_polarity_differences():
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    page_px = _texture(np, 1200, 1600, seed=4)
    page_image = _page_image(cv2, page_px)
    crop = cv2.resize(page_px[520:880, 300:780], (700, 525), interpolation=cv2.INTER_CUBIC)
    size, window = (240.0, 180.0), (130.0, 240.0, 410.0, 460.0)

    def score(template, mode):
        found = student_clips.cv_matcher(page_image, template, mode)(144, size, window)
        assert found[0] < 0.5 or (found[1], found[2]) == pytest.approx((150.0, 260.0), abs=1.0)
        return found[0]

    inverted = 255 - crop  # قطبية معكوسة: الرمادي ينقلب والحواف تبقى
    assert score(inverted, "gray") < 0.3 and score(inverted, "edges") > 0.8
    # تدرّج آخر: كل مستوى رمادي (لون في الأصل) يُحوَّل إلى مستوى مختلف، والحبر يبقى حبرًا والورق ورقًا
    levels = np.random.default_rng(6).integers(0, 150, 256).astype(np.uint8)
    levels[230:] = 255
    recolored = levels[crop]
    assert score(recolored, "binary") > score(recolored, "gray") and score(recolored, "binary") > 0.8
    assert score(crop, "blur") > 0.9 and score(crop, "gray") > 0.9
    other = _texture(np, 700, 525, seed=77)
    assert max(score(other, mode) for mode in student_clips.MODES) < 0.5  # محتوى آخر لا يطابق بأي تمثيل
    with pytest.raises(student_clips.StudentClipsError, match="تمثيل"):
        student_clips.cv_matcher(page_image, crop, "sepia")(144, size, window)


def test_stage_end_to_end_on_synthetic_pdfs(tmp_path):
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    pymupdf = pytest.importorskip("pymupdf")

    def png(array):
        return cv2.imencode(".png", array)[1].tobytes()

    # كتاب الطالب: صفحتا تمهيد ثم صفحة ممسوحة (مطبوعها 1) وصفحة متجهية (مطبوعها 2): الإزاحة 2
    scan = _texture(np, 1250, 1667, seed=5)  # 150 بكسل لكل بوصة على 600×800 نقطة
    student = pymupdf.open()
    for _ in range(2):
        student.new_page(width=600, height=800)
    page = student.new_page(width=600, height=800)
    page.insert_image(page.rect, stream=png(scan))
    page = student.new_page(width=600, height=800)
    rng = np.random.default_rng(8)
    for _ in range(90):
        x, y = float(rng.uniform(20, 520)), float(rng.uniform(20, 740))
        rect = pymupdf.Rect(x, y, x + float(rng.uniform(5, 60)), y + float(rng.uniform(5, 40)))
        shade = float(rng.uniform(0, 0.7))
        page.draw_rect(rect, color=None, fill=(shade, shade, shade))
    (tmp_path / "books").mkdir()
    student.save(tmp_path / "books" / "student.pdf")

    # الدليل: كل صفحة طالب مصغَّرة إلى النصف في لوحة يسار الصفحة (صورة مضمَّنة عريضة)
    panel = pymupdf.Rect(20, 40, 320, 440)
    guide = pymupdf.open()
    for number in (3, 4):
        pix = student[number - 1].get_pixmap(dpi=150, alpha=False)
        page = guide.new_page(width=800, height=600)
        page.insert_image(panel, stream=pix.tobytes("png"))
    guide.save(tmp_path / "guide.pdf")

    make_book(
        tmp_path,
        {1: "x", 2: "y"},
        dirs={"examples_hires": "hires", "examples_student": "student"},
        pdf={"dir": ".", "pattern": "guide.pdf"},
        student_pdf={"dir": "books", "pattern": "student.pdf"},
        student_clips={"panel": {"min_width": 900, "max_x0": 100, "width": None}, "offsets": [0, 2]},
    )
    # صفحة الدليل 2 بلا رقم مطبوع في الجدول: يُقدَّر من جارتيها 1 و3
    (tmp_path / "printed_pages.json").write_text(json.dumps({"1": 1, "3": 3}), encoding="utf-8")
    hires = tmp_path / "hires"
    hires.mkdir()
    guide = pymupdf.open(tmp_path / "guide.pdf")
    boxes = {"1.1_m1_p1.png": (1, (60, 90, 240, 210)), "1.1_m2_p2.png": (2, (80, 200, 290, 360))}
    for name, (number, rect) in boxes.items():
        pix = guide[number - 1].get_pixmap(dpi=400, clip=pymupdf.Rect(*rect), alpha=False)
        (hires / name).write_bytes(pix.tobytes("png"))
    guide.close()

    assert main([str(tmp_path), "student_clips"]) == 0
    report = json.loads((tmp_path / "student_clips.json").read_text(encoding="utf-8"))
    assert report["page_offset"] == 2
    assert report["mode"] == "gray" and report["calibration"]["gray"]["hit"] > 0.95
    first, second = report["clips"]
    assert "page_source" not in first
    assert (second["printed_page"], second["page_source"], second["status"]) == (2, "neighbors", "ok")
    assert (first["kind"], first["dpi"], first["student_page"]) == ("scan", 150, 3)
    assert (second["kind"], second["dpi"], second["student_page"]) == ("vector", 600, 4)
    assert min(first["score"], second["score"]) >= 0.8 and first["guide_score"] > 0.95
    # أرقام التشخيص: صفحة الإزاحة وحدها جُرِّبت، والمقياس واللوحة والمنقول في التقرير
    assert first["page_shift"] == 0 and first["pages"] == {"0": first["score"]}
    assert first["panel"] == pytest.approx(list(panel), abs=0.1) and first["pinned"] == []
    assert first["scale"] == pytest.approx([1.0, 1.0], abs=0.07) and len(first["predicted"]) == 4
    # الصندوق في صفحة الطالب ضعف صندوق الدليل بعد طرح أصل اللوحة
    for entry, (_, rect) in zip(report["clips"], boxes.values(), strict=True):
        expected = student_clips.transfer_box(tuple(map(float, rect)), tuple(panel), (0.0, 0.0, 600.0, 800.0))
        assert entry["box"] == pytest.approx(expected, abs=4.0)
    # الممسوح بكسلات الأصل نفسها بلا استيفاء، والمتجهي بـ600 بكسل لكل بوصة
    data = np.frombuffer((tmp_path / "student" / "1.1_m1_p1.png").read_bytes(), dtype=np.uint8)
    cropped = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    left, top, right, bottom = student_clips.pixel_box(
        tuple(first["box"]), (0.0, 0.0, 600.0, 800.0), (1250, 1667)
    )
    assert cropped.shape == (bottom - top, right - left) == (first["height"], first["width"])
    assert (cropped == scan[top:bottom, left:right]).all()
    assert second["width"] == pytest.approx((second["box"][2] - second["box"][0]) * 600 / 72, abs=2)
