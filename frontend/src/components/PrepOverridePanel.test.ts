import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import PrepOverridePanel from "./PrepOverridePanel.vue";
import type { PrepEdit } from "@/stores/preps";

function edit(extra: Partial<PrepEdit> = {}): PrepEdit {
  return {
    state: "none",
    allocation: [[1, 2, 3], [4, 5], []],
    default_allocation: [[1, 2, 3], [4, 5], []],
    stages: [
      {
        name: "warmup",
        current: "opening-warmup-question",
        chosen: null,
        options: [
          { slug: "opening-warmup-question", title: "سؤال تهيئة" },
          { slug: "opening-predict", title: "توقّع" },
        ],
      },
      {
        name: "guided",
        current: "explore-pairs",
        chosen: null,
        options: [{ slug: "explore-pairs", title: "أزواج" }],
      },
    ],
    exercises: [7, 8, 9],
    removed: [],
    ...extra,
  };
}

const labels = { warmup: "التهيئة", guided: "الممارسة الموجهة" };

function panel(
  props: Partial<{ edit: PrepEdit; k: number; n: number; error: string }> = {},
) {
  return mount(PrepOverridePanel, {
    props: {
      edit: edit(),
      k: 1,
      n: 3,
      labels,
      saving: false,
      error: "",
      ...props,
    },
  });
}

const buttons = (w: ReturnType<typeof panel>) => w.findAll("button");
const byText = (w: ReturnType<typeof panel>, text: string) =>
  buttons(w).find((b) => b.text().includes(text))!;

describe("PrepOverridePanel", () => {
  it("يحفظ بلا تغيير قائمة فارغة: لا توزيع ولا استراتيجية ولا حذف", async () => {
    const w = panel();
    await byText(w, "احفظ التعديل").trigger("click");
    expect(w.emitted("save")![0][0]).toEqual({ strategies: {}, removed: [] });
  });

  it("ينقل آخر مثال إلى الحصة التالية ويرسل التوزيع كاملًا", async () => {
    const w = panel();
    expect(w.text()).not.toContain("إلى الحصة 0");
    await byText(w, "انقل المثال 3 إلى الحصة 2").trigger("click");
    expect(w.text()).toContain("الحصة 2: 3 و4 و5");
    await byText(w, "احفظ التعديل").trigger("click");
    expect(w.emitted("save")![0][0]).toMatchObject({
      allocation: [[1, 2], [3, 4, 5], []],
    });
  });

  it("لا ينقل إلى حصة بلغت ثلاثة أمثلة ولا إلى الحصة الأخيرة", () => {
    const back = panel({ k: 2 });
    expect(
      byText(back, "انقل المثال 4 إلى الحصة 1").attributes("disabled"),
    ).toBeDefined();
    expect(back.text()).not.toContain("إلى الحصة 3");
  });

  it("الحصة الأخيرة بلا قسم أمثلة", () => {
    expect(panel({ k: 3 }).text()).not.toContain("أمثلة الحصة");
  });

  it("يعرض المراحل ذات البدائل وحدها ويرسل الاستراتيجية المختارة", async () => {
    const w = panel();
    const selects = w.findAll("select");
    expect(selects).toHaveLength(1);
    expect(w.text()).toContain("التهيئة");
    await selects[0].setValue("opening-predict");
    await byText(w, "احفظ التعديل").trigger("click");
    expect(w.emitted("save")![0][0]).toMatchObject({
      strategies: { warmup: "opening-predict" },
    });
  });

  it("إزالة علامة تمرين تحذفه، والمحذوف المحفوظ يبدأ بلا علامة", async () => {
    const w = panel({ edit: edit({ state: "active", removed: [9] }) });
    const boxes = w.findAll('input[type="checkbox"]');
    expect(boxes.map((b) => (b.element as HTMLInputElement).checked)).toEqual([
      true,
      true,
      false,
    ]);
    await boxes[0].setValue(false);
    await byText(w, "احفظ التعديل").trigger("click");
    expect(w.emitted("save")![0][0]).toMatchObject({ removed: [7, 9] });
  });

  it("الاسترجاع يظهر للتعديل المحفوظ، ورسالة الخادم والتعديل المهمل يظهران", async () => {
    expect(panel().text()).not.toContain("استرجع التحضير المشترك");
    const w = panel({
      edit: edit({ state: "invalid" }),
      error: "التعديل يُفشل معيارًا حاجبًا",
    });
    expect(w.text()).toContain("لم يعد يطابق أمثلته");
    expect(w.get('[role="alert"]').text()).toContain("معيارًا حاجبًا");
    await byText(w, "استرجع التحضير المشترك").trigger("click");
    expect(w.emitted("reset")).toHaveLength(1);
  });
});
