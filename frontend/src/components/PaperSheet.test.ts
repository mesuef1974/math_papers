import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Paper, Part } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { marksLabel } from "@/utils/marks";
import PaperSheet from "./PaperSheet.vue";

function part(overrides: Partial<Part> = {}): Part {
  return {
    label: "",
    lesson: "2.4",
    lesson_title: "قواعد الاشتقاق",
    marks: 2,
    level: "A",
    stem: "أوجد $f'(x)$",
    options: [],
    answer: "$2x$",
    answer_index: -1,
    steps: ["اشتق كل حد"],
    graph: null,
    option_graphs: [],
    variant: "power_rule",
    fingerprint: "fp-demo-0001",
    slot: { kind: "essay", level: "A", needs_graph: false },
    ...overrides,
  };
}

const paper: Paper = {
  kind: "exam",
  form: "A",
  generator_version: "v1",
  blueprint: "bp",
  lesson_code: "",
  title: "اختبار تدريبي 2026-2027",
  seed: 7,
  total_marks: 40,
  is_forecast: true,
  level_counts: { A: 1 },
  level_marks: { A: 40 },
  level: "",
  questions: [
    {
      number: 1,
      kind: "mcq",
      marks: 1,
      parts: [part({ marks: 1, options: ["$1$", "$2$", "$3$", "$4$"], answer: "$2$", answer_index: 1, fingerprint: "q1" })],
    },
    {
      number: 2,
      kind: "mcq",
      marks: 1,
      parts: [part({ marks: 1, options: ["$1$", "$2$", "$3$", "$4$"], answer: "$3$", answer_index: 2, fingerprint: "q2" })],
    },
    { number: 3, kind: "essay", marks: 12, parts: [part({ marks: 12, fingerprint: "q3" })] },
  ],
};

const header: PaperHeaderData = {
  school: "مدرسة",
  teacher: "",
  subject: "الرياضيات",
  grade: "",
  title: paper.title,
  minutes: 150,
  date: "",
  section: "",
  totalMarks: 40,
  instructions: "",
  seed: 7,
};

describe("PaperSheet", () => {
  it("الاختبار كراسة: غلاف وتعليمات ثنائية ومربع رقم وخيارات ومربعات وصندوق حل بدرجته وجدول رصد، ويخفي المفتاح افتراضيًا", () => {
    const wrapper = mount(PaperSheet, { props: { paper, header, showKey: false } });
    expect(wrapper.find(".sheet").classes()).toContain("booklet");
    expect(wrapper.find(".cover").text()).toContain("اختبار الرياضيات (تدريبي)");
    expect(wrapper.find(".cover").text()).toContain("ساعتان ونصف");
    expect(wrapper.find(".instructions").text()).toContain("General instructions");
    expect(wrapper.find(".instructions").text()).toContain("2 موضوعية و1 مقالية");
    const notes = wrapper.findAll(".section-note").map((n) => n.text());
    expect(notes).toHaveLength(2);
    expect(notes[0]).toContain("من 1 إلى 2");
    expect(notes[0]).toContain("questions 1 through 2");
    expect(notes[1]).toContain("السؤال 3");
    expect(wrapper.findAll(".question-head .number").map((n) => n.text())).toEqual(["1", "2", "3"]);
    expect(wrapper.findAll(".options li .box")).toHaveLength(8);
    expect(wrapper.find(".work-space").exists()).toBe(false);
    expect(wrapper.find(".work-box").attributes("style")).toContain("min-block-size: 300px");
    expect(wrapper.find(".part-marks").text()).toBe("12");
    expect(wrapper.find(".essay .marks").text()).toBe("12 درجة /");
    expect(wrapper.find(".essay .score-cell").exists()).toBe(true);
    expect(wrapper.findAll(".section-end").map((n) => n.findAll("span").map((s) => s.text()))).toEqual([
      ["انتهت الأسئلة الموضوعية", "End of multiple-choice questions"],
      ["انتهت جميع الأسئلة", "End of all questions"],
    ]);
    const score = wrapper.find(".score-page");
    expect(score.text()).toContain("لا تكتب على هذه الصفحة");
    expect(score.findAll("tbody tr").map((r) => `${r.find("th").text()} ${r.find("td").text()}`)).toEqual(["1 – 2 2", "3 12", "المجموع 14"]);
    expect(wrapper.find(".answer-key").exists()).toBe(false);
    expect(wrapper.text()).toContain("رقم النموذج 7");
    expect(document.documentElement.style.getPropertyValue("--print-footer")).toBe('"الرياضيات – اختبار تدريبي 2026-2027"');
  });

  it("ورقة العمل تبقى ورقة بترويسة ومساحة حل متدرجة بلا غلاف", () => {
    const sheet: Paper = { ...paper, kind: "worksheet" };
    const wrapper = mount(PaperSheet, { props: { paper: sheet, header, showKey: false } });
    expect(wrapper.find(".sheet").classes()).not.toContain("booklet");
    expect(wrapper.find(".cover").exists()).toBe(false);
    expect(wrapper.find(".paper-header").exists()).toBe(true);
    expect(wrapper.find(".question-head strong").text()).toBe("السؤال 1");
    expect(wrapper.find(".work-space").attributes("data-lines")).toBe("6");
    expect(wrapper.findAll(".section-end")).toHaveLength(0);
    expect(wrapper.find(".score-page").exists()).toBe(false);
    expect(document.documentElement.style.getPropertyValue("--print-footer")).toBe('""');
  });

  it("المفتاح: جدول الإجابات الموضوعية ثم جدول بصف لكل جزء مع المستوى والدرس والخطوات، وعنوانه دليل التقدير للاختبار", () => {
    const wrapper = mount(PaperSheet, { props: { paper, header, showKey: true } });
    const key = wrapper.find(".answer-key");
    expect(key.exists()).toBe(true);
    expect(key.findAll(".mcq-key tbody tr").map((r) => `${r.find("th").text()} ${r.find("td").text()}`)).toEqual(["1 B", "2 C"]);
    expect(key.findAll("table:not(.mcq-key) tbody tr")).toHaveLength(3);
    expect(key.findAll(".badge-a")).toHaveLength(3);
    expect(key.text()).toContain("اشتق كل حد");
    expect(key.text()).toContain("دليل تقدير الدرجات");
    const sheet = mount(PaperSheet, { props: { paper: { ...paper, kind: "worksheet" }, header, showKey: true } });
    expect(sheet.find(".answer-key").text()).toContain("مفتاح الحل");
  });

  it("ورقة بنوع واحد لا تحمل تعليمات أقسام", () => {
    const sheet: Paper = { ...paper, kind: "worksheet", questions: [paper.questions[2]] };
    const wrapper = mount(PaperSheet, { props: { paper: sheet, header, showKey: false } });
    expect(wrapper.findAll(".section-note")).toHaveLength(0);
  });

  it("زر الاستبدال يظهر عند الطلب فقط، ويبعث رقم السؤال وتسمية الجزء، ويعطّل أثناء الاستبدال", async () => {
    const plain = mount(PaperSheet, { props: { paper, header, showKey: false } });
    expect(plain.findAll(".part-tools")).toHaveLength(0);
    const wrapper = mount(PaperSheet, { props: { paper, header, showKey: false, replaceable: true, modified: true } });
    const buttons = wrapper.findAll(".part-tools button");
    expect(buttons).toHaveLength(3);
    expect(buttons[0].classes()).toContain("btn-small");
    expect(wrapper.find(".part-tools").classes()).toContain("no-print");
    await buttons[2].trigger("click");
    expect(wrapper.emitted("replace")).toEqual([[3, ""]]);
    expect(wrapper.text()).toContain("رقم النموذج 7 (معدّل)");
    await wrapper.setProps({ replacing: "q2" });
    expect(wrapper.findAll(".part-tools button")[1].text()).toBe("جارٍ الاستبدال");
    expect(wrapper.findAll(".part-tools button")[0].attributes("disabled")).toBeDefined();
  });

  it("يجمع الدرجات بالعربية الصحيحة", () => {
    expect(marksLabel(1)).toBe("درجة واحدة");
    expect(marksLabel(2)).toBe("درجتان");
    expect(marksLabel(3)).toBe("3 درجات");
    expect(marksLabel(10)).toBe("10 درجات");
    expect(marksLabel(12)).toBe("12 درجة");
  });
});
