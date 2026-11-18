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
  it("عمود «المصدر في الكتاب» بعد الدرس بنص الخادم، خلية واحدة للجزء تمتد على صفوف بنوده، و«—» لجزء بلا مصدر", () => {
    const withSource = part({
      fingerprint: "a",
      source: { kind: "example", number: 1, page: 5 },
      source_label: "ص 5، مثال 1",
    });
    const wrapper = mount(AnswerKey, { props: { paper: paper([withSource, part({ fingerprint: "b" })]), header } });
    expect(heads(wrapper)).toEqual(["السؤال", "الإجابة والخطوات", "الدرجة", "الدرس", "المصدر في الكتاب", "المستوى", "المجموع"]);
    const cells = wrapper.findAll("td.source");
    expect(cells.map((td) => td.text())).toEqual(["ص 5، مثال 1", "—"]);
    expect(cells[0].attributes("rowspan")).toBe("2");
    const firstRow = wrapper.findAll(".key tbody tr")[0].findAll("th, td");
    expect(firstRow[4].classes()).toContain("source");
  });

  it("لا عمود مصدر حين لا يُعرف مصدر أي جزء (الثاني عشر والأوراق المحفوظة قبله)", () => {
    const wrapper = mount(AnswerKey, { props: { paper: paper([part()]), header } });
    expect(heads(wrapper)).not.toContain("المصدر في الكتاب");
    expect(wrapper.find("td.source").exists()).toBe(false);
  });
});
