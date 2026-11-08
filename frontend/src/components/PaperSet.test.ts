import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Paper, Part } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import AnswerSheet from "./AnswerSheet.vue";
import PaperSet from "./PaperSet.vue";

function part(overrides: Partial<Part> = {}): Part {
  return {
    label: "",
    lesson: "1.2",
    lesson_title: "حساب النهايات",
    marks: 1,
    level: "A",
    stem: "س",
    options: ["$1$", "$2$", "$3$", "$4$"],
    answer: "$2$",
    answer_index: 1,
    steps: [],
    graph: null,
    option_graphs: [],
    variant: "v",
    fingerprint: "f",
    slot: { kind: "mcq", level: "", needs_graph: false },
    ...overrides,
  };
}

function paper(form: "A" | "B"): Paper {
  return {
    kind: "exam",
    form,
    generator_version: "g",
    blueprint: "bp",
    lesson_code: "",
    title: "اختبار",
    seed: 9,
    total_marks: 3,
    is_forecast: false,
    level_marks: {},
    level_counts: {},
    level: "",
    questions: [
      { number: 1, kind: "mcq", marks: 1, parts: [part({ fingerprint: `${form}1` })] },
      { number: 2, kind: "mcq", marks: 1, parts: [part({ fingerprint: `${form}2`, answer_index: 3 })] },
      {
        number: 3,
        kind: "essay",
        marks: 1,
        parts: [part({ fingerprint: `${form}3`, options: [], answer_index: -1, slot: { kind: "essay", level: "", needs_graph: false } })],
      },
    ],
  };
}

const header = (p: Paper): PaperHeaderData => ({
  school: "",
  teacher: "",
  subject: "الرياضيات",
  grade: "",
  title: p.title,
  minutes: 150,
  date: "",
  section: "",
  totalMarks: p.total_marks,
  instructions: "",
  seed: p.seed,
});

describe("AnswerSheet", () => {
  it("صف لكل سؤال موضوعي بأربع دوائر، والمفتاح يظلّل الصحيحة فقط", () => {
    const blank = mount(AnswerSheet, { props: { paper: paper("A"), header: header(paper("A")) } });
    expect(blank.findAll(".row")).toHaveLength(2);
    expect(blank.findAll(".bubble")).toHaveLength(8);
    expect(blank.findAll(".filled")).toHaveLength(0);
    expect(blank.text()).toContain("ورقة الإجابة: اختبار");
    const key = mount(AnswerSheet, { props: { paper: paper("A"), header: header(paper("A")), answers: true } });
    expect(key.findAll(".filled").map((b) => b.text())).toEqual(["ب", "د"]);
    expect(key.text()).toContain("مفتاح ورقة الإجابة");
  });

  it("لا تُعرض لورقة بلا أسئلة موضوعية", () => {
    const essayOnly: Paper = { ...paper("A"), questions: [paper("A").questions[2]] };
    const wrapper = mount(AnswerSheet, { props: { paper: essayOnly, header: header(essayOnly) } });
    expect(wrapper.find(".answer-sheet").exists()).toBe(false);
  });
});

describe("PaperSet", () => {
  it("نموذج واحد بلا تظليل: ورقة ثم مفتاحها، بلا وسم النموذج", () => {
    const wrapper = mount(PaperSet, { props: { papers: [paper("A")], header, showKey: true } });
    expect(wrapper.findAll(".sheet:not(.answer-key):not(.answer-sheet)")).toHaveLength(1);
    expect(wrapper.findAll(".answer-key")).toHaveLength(1);
    expect(wrapper.findAll(".answer-sheet")).toHaveLength(0);
    expect(wrapper.findAll(".paper-header dt").map((d) => d.text())).not.toContain("النموذج");
  });

  it("نموذجان مع تظليل ومفاتيح: أ، تظليل أ، ب، تظليل ب، ثم مفتاح أ ومفتاحه المظلَّل، ثم ب", () => {
    const wrapper = mount(PaperSet, {
      props: { papers: [paper("A"), paper("B")], header, showKey: true, bubble: true, replaceable: true },
    });
    const order = wrapper
      .findAll("article")
      .map((a) => a.classes().filter((c) => c !== "sheet" && c !== "booklet").join("|") || "sheet");
    expect(order).toEqual([
      "sheet",
      "answer-sheet",
      "sheet",
      "answer-sheet",
      "answer-key",
      "answer-sheet|key",
      "answer-key",
      "answer-sheet|key",
    ]);
    expect(wrapper.findAll(".paper-header dt").map((d) => d.text())).toContain("النموذج");
    expect(wrapper.findAll(".part-tools")).toHaveLength(3); // الاستبدال على أ فقط
    expect(wrapper.findAll(".paper-header").filter((h) => h.text().includes("ب")).length).toBeGreaterThan(0);
  });
});
