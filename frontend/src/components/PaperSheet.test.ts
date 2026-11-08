import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Paper, Part } from "@/stores/papers";
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
  level_marks: { A: 40 },
  level: "",
  questions: [
    {
      number: 1,
      kind: "mcq",
      marks: 1,
      parts: [part({ marks: 1, options: ["$1$", "$2$", "$3$", "$4$"], answer: "$2$", fingerprint: "q1" })],
    },
    { number: 2, kind: "essay", marks: 12, parts: [part({ marks: 12, fingerprint: "q2" })] },
  ],
};

describe("PaperSheet", () => {
  it("يعرض الأسئلة والخيارات ومكان الحل، ويخفي المفتاح افتراضيًا", () => {
    const wrapper = mount(PaperSheet, { props: { paper, showKey: false } });
    expect(wrapper.findAll("section.question")).toHaveLength(2);
    expect(wrapper.findAll(".options li")).toHaveLength(4);
    expect(wrapper.find(".work-space").exists()).toBe(true);
    expect(wrapper.find(".answer-key").exists()).toBe(false);
    expect(wrapper.text()).toContain("رقم النموذج 7");
  });

  it("يعرض المفتاح بشارة المستوى والخطوات عند الطلب", () => {
    const wrapper = mount(PaperSheet, { props: { paper, showKey: true } });
    const key = wrapper.find(".answer-key");
    expect(key.exists()).toBe(true);
    expect(key.findAll(".badge-a")).toHaveLength(2);
    expect(key.text()).toContain("اشتق كل حد");
  });

  it("يجمع الدرجات بالعربية الصحيحة", () => {
    expect(marksLabel(1)).toBe("درجة واحدة");
    expect(marksLabel(2)).toBe("درجتان");
    expect(marksLabel(3)).toBe("3 درجات");
    expect(marksLabel(10)).toBe("10 درجات");
    expect(marksLabel(12)).toBe("12 درجة");
  });
});
