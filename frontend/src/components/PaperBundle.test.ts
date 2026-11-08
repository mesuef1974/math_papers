import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { BundleEntry, Paper } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import PaperBundle from "./PaperBundle.vue";

function paper(code: string, n: number): Paper {
  return {
    kind: "worksheet",
    generator_version: "v",
    blueprint: "bp",
    lesson_code: code,
    title: `ورقة عمل: ${code}`,
    seed: 1,
    total_marks: 0,
    is_forecast: false,
    level_marks: {},
    level_counts: { K: 1, A: n - 1 },
    level: "",
    questions: Array.from({ length: n }, (_, i) => ({
      number: i + 1,
      kind: "essay" as const,
      marks: 0,
      parts: [
        {
          label: "",
          lesson: code,
          lesson_title: "",
          marks: 0,
          level: (i ? "A" : "K") as "A" | "K",
          stem: `س $x_{${i}}$`,
          options: [],
          answer: "$1$",
          steps: [],
          graph: null,
          option_graphs: [],
          variant: "v",
          fingerprint: `${code}-${i}`,
          slot: { kind: "essay", level: "", needs_graph: false },
        },
      ],
    })),
  };
}

const plan: BundleEntry[] = [
  { lesson: "1.1", title: "النهايات", count: 2, levels: { K: 1, A: 1 } },
  { lesson: "1.2", title: "حساب النهايات", count: 3, levels: { K: 1, A: 2 } },
];
const header = (p: Paper): PaperHeaderData => ({
  school: "مدرسة",
  teacher: "",
  subject: "الرياضيات",
  grade: "",
  title: p.title,
  minutes: null,
  date: "",
  section: "",
  totalMarks: 0,
  instructions: "",
  seed: p.seed,
});

describe("PaperBundle", () => {
  it("غلاف بفهرس ومجموع المسائل، ثم ورقة لكل درس، بلا مفاتيح افتراضيًا", () => {
    const wrapper = mount(PaperBundle, {
      props: { papers: [paper("1.1", 2), paper("1.2", 3)], plan, seed: 42, header, showKey: false },
    });
    expect(wrapper.text()).toContain("2 ورقة عمل، 5 مسألة");
    expect(wrapper.findAll(".index li")).toHaveLength(2);
    expect(wrapper.text()).toContain("سهل 1، متوسط 2");
    expect(wrapper.findAll(".bundle-sheet")).toHaveLength(2);
    expect(wrapper.findAll(".answer-key")).toHaveLength(0);
    expect(wrapper.text()).toContain("رقم الحزمة 42");
  });

  it("المفاتيح كلها بعد الأوراق كلها", () => {
    const wrapper = mount(PaperBundle, {
      props: { papers: [paper("1.1", 2), paper("1.2", 3)], plan, seed: 42, header, showKey: true },
    });
    const blocks = wrapper.findAll(".bundle-sheet");
    expect(blocks).toHaveLength(4);
    expect(blocks[1].find(".answer-key").exists()).toBe(false);
    expect(blocks[2].find(".answer-key").exists()).toBe(true);
    expect(blocks[2].find(".sheet:not(.answer-key)").exists()).toBe(false);
  });
});
