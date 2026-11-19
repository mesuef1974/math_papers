import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Paper, Part } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import AnswerKey from "./AnswerKey.vue";

function part(overrides: Partial<Part> = {}): Part {
  return {
    label: "",
    lesson: "1.1",
    lesson_title: "الدرس",
    marks: 2,
    level: "K",
    stem: "س",
    options: [],
    answer: "$2$",
    answer_index: -1,
    steps: ["خطوة"],
    marking: [
      { steps: ["خطوة"], marks: 1, final: false },
      { steps: [], marks: 1, final: true },
    ],
    graph: null,
    option_graphs: [],
    variant: "v",
    fingerprint: "fp",
    slot: { kind: "essay", level: "K", needs_graph: false },
    ...overrides,
  };
}

function paper(parts: Part[]): Paper {
  return {
    kind: "exam",
    form: "A",
    generator_version: "v1",
    blueprint: "bp",
    lesson_code: "",
    title: "اختبار",
    seed: 7,
    total_marks: 4,
    is_forecast: false,
    level_counts: {},
    level_marks: {},
    level: "",
    questions: parts.map((p, index) => ({ number: index + 1, kind: "essay", marks: p.marks, parts: [p] })),
  };
}

const header: PaperHeaderData = {
  school: "مدرسة",
  teacher: "",
  subject: "الرياضيات",
  grade: "",
  title: "اختبار",
  minutes: 60,
  date: "",
  section: "",
  totalMarks: 4,
  instructions: "",
  seed: 7,
};

const heads = (wrapper: ReturnType<typeof mount>) => wrapper.findAll(".key thead th").map((th) => th.text());

describe("AnswerKey", () => {
  it("المستوى بعمق المعرفة DOK، وعمود الخطوات وحده غير موسَّط (قرار المالك 2026-11-18)", () => {
    const wrapper = mount(AnswerKey, {
      props: { paper: paper([part({ level: "K" }), part({ level: "A", fingerprint: "b" }), part({ level: "R", fingerprint: "c" })]), header },
    });
    expect(wrapper.findAll(".badge").map((b) => b.text())).toEqual(["DOK 1", "DOK 2", "DOK 3"]);
    const rows = wrapper.findAll(".key tbody tr");
    expect(rows.every((row) => row.findAll(".steps-cell").length === 1)).toBe(true);
  });

  it("أعمدة «الصفحة» و«المثال» و«التدريب» بعد الدرس بخلايا الخادم، تمتد على صفوف بنود الجزء، و«—» للمجهول", () => {
    const withSource = part({
      fingerprint: "a",
      source: { kind: "example", number: 1, page: 5, exercises: [14, 15, 16] },
      source_label: "ص 5، مثال 1، تدريب 14–16",
      source_page: "5",
      source_example: "1",
      source_exercises: "14–16",
    });
    const wrapper = mount(AnswerKey, { props: { paper: paper([withSource, part({ fingerprint: "b" })]), header } });
    expect(heads(wrapper)).toEqual(["السؤال", "الإجابة والخطوات", "الدرجة", "الدرس", "الصفحة", "المثال", "التدريب", "المستوى", "المجموع"]);
    const cells = wrapper.findAll("td.source");
    expect(cells.map((td) => td.text().replace(/[⁦-⁩]/g, ""))).toEqual(["5", "1", "14–16", "—", "—", "—"]);
    expect(cells[0].attributes("rowspan")).toBe("2");
    const firstRow = wrapper.findAll(".key tbody tr")[0].findAll("th, td");
    expect(firstRow.slice(4, 7).every((td) => td.classes().includes("source"))).toBe(true);
  });

  it("لا عمود مصدر حين لا يُعرف مصدر أي جزء (الثاني عشر والأوراق المحفوظة قبله)", () => {
    const wrapper = mount(AnswerKey, { props: { paper: paper([part()]), header } });
    expect(heads(wrapper)).not.toContain("الصفحة");
    expect(wrapper.find("td.source").exists()).toBe(false);
  });
});
