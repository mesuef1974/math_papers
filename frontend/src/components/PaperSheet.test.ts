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
    steps: ["اشتق كل حد"],
    graph: null,
    option_graphs: [],
    variant: "power_rule",
    fingerprint: "abc123def456",
    slot: { kind: "essay", level: "A", needs_graph: false },
    ...overrides,
  };
}

const paper: Paper = {
  kind: "exam",
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
      parts: [part({ marks: 1, options: ["$1$", "$2$", "$3$", "$4$"], answer: "$2$", fingerprint: "q1" })],
    },
    {
      number: 2,
      kind: "mcq",
      marks: 1,
      parts: [part({ marks: 1, options: ["$1$", "$2$", "$3$", "$4$"], answer: "$3$", fingerprint: "q2" })],
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
  it("يعرض الترويسة وتعليمات القسمين ومربعات الخيارات ومكان الحل، ويخفي المفتاح افتراضيًا", () => {
    const wrapper = mount(PaperSheet, { props: { paper, header, showKey: false } });
    expect(wrapper.text()).toContain("ساعتان ونصف");
    const notes = wrapper.findAll(".section-note").map((n) => n.text());
    expect(notes).toHaveLength(2);
    expect(notes[0]).toContain("من 1 إلى 2");
    expect(notes[1]).toContain("السؤال 3");
    expect(wrapper.findAll(".options li .box")).toHaveLength(8);
    expect(wrapper.find(".work-space").attributes("data-lines")).toBe("6");
    expect(wrapper.find(".answer-key").exists()).toBe(false);
    expect(wrapper.text()).toContain("رقم النموذج 7");
  });

  it("المفتاح جدول بصف لكل جزء مع المستوى والدرس والخطوات", () => {
    const wrapper = mount(PaperSheet, { props: { paper, header, showKey: true } });
    const key = wrapper.find(".answer-key");
    expect(key.exists()).toBe(true);
    expect(key.findAll("tbody tr")).toHaveLength(3);
    expect(key.findAll(".badge-a")).toHaveLength(3);
    expect(key.text()).toContain("اشتق كل حد");
    expect(key.text()).toContain("مفتاح الحل");
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
