import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ObjectiveEditor from "./ObjectiveEditor.vue";
import type { PrepObjective } from "@/stores/preps";

const shared = { behavior: "يحسب قيمة الدالة", condition: "عند قيمة معطاة", criterion: "بلا خطأ" };

function objective(extra: Partial<PrepObjective> = {}): PrepObjective {
  return {
    example: 1,
    text: "يحسب قيمة الدالة عند قيمة معطاة بلا خطأ",
    pending: false,
    shared,
    mine: null,
    stale: false,
    editable: true,
    suggestion: null,
    teach_activity: "",
    teach_assessment: "",
    teach_minutes: 8,
    check_activity: "",
    check_assessment: "",
    check_minutes: 3,
    ...extra,
  };
}

describe("ObjectiveEditor", () => {
  it("يبدأ بالمعتمد ويعرض السلوك للقراءة فقط ويحفظ الشرط والمعيار منظّفين", async () => {
    const wrapper = mount(ObjectiveEditor, { props: { objective: objective(), busy: false } });
    expect(wrapper.text()).toContain(shared.behavior);
    const [condition, criterion] = wrapper.findAll("textarea");
    expect((condition.element as HTMLTextAreaElement).value).toBe(shared.condition);
    await criterion.setValue("  في أقل من   دقيقتين ");
    expect(wrapper.text()).toContain("17 / 240");
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("save")?.[0]).toEqual([
      { condition: shared.condition, criterion: "في أقل من دقيقتين", suggest: false, note: "" },
    ]);
  });

  it("يبدأ بنسخة المعلم إن وُجدت ويعرض «استرجاع المعتمد»", async () => {
    const mine = { condition: "من جدول قيم", criterion: "بدقة تامة" };
    const wrapper = mount(ObjectiveEditor, { props: { objective: objective({ mine }), busy: false } });
    expect((wrapper.findAll("textarea")[0].element as HTMLTextAreaElement).value).toBe(mine.condition);
    const reset = wrapper.findAll("button").find((b) => b.text() === "استرجاع المعتمد");
    await reset!.trigger("click");
    expect(wrapper.emitted("reset")).toHaveLength(1);
  });

  it("لا استرجاع بلا نسخة، والإلغاء يُبلَّغ", async () => {
    const wrapper = mount(ObjectiveEditor, { props: { objective: objective(), busy: false } });
    expect(wrapper.text()).not.toContain("استرجاع المعتمد");
    await wrapper.findAll("button").find((b) => b.text() === "إلغاء")!.trigger("click");
    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("يرفض نصًا أقصر من ثلاثة أحرف ولا يحفظ", async () => {
    const wrapper = mount(ObjectiveEditor, { props: { objective: objective(), busy: false } });
    await wrapper.findAll("textarea")[0].setValue("أ ");
    expect(wrapper.find("button[type=submit]").attributes("disabled")).toBeDefined();
    expect(wrapper.findAll("textarea")[0].attributes("aria-invalid")).toBe("true");
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("save")).toBeUndefined();
  });

  it("الاقتراح يفتح الملاحظة ويرسلها", async () => {
    const wrapper = mount(ObjectiveEditor, { props: { objective: objective(), busy: false } });
    expect(wrapper.find("input:not([type])").exists()).toBe(false);
    await wrapper.find("input[type=checkbox]").setValue(true);
    await wrapper.find("input:not([type])").setValue("أوضح للطلاب");
    await wrapper.find("form").trigger("submit");
    expect(wrapper.emitted("save")?.[0][0]).toMatchObject({ suggest: true, note: "أوضح للطلاب" });
  });

  it("أثناء الانشغال لا حفظ", () => {
    const wrapper = mount(ObjectiveEditor, { props: { objective: objective(), busy: true } });
    expect(wrapper.find("button[type=submit]").attributes("disabled")).toBeDefined();
  });
});
