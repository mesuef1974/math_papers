import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { Paper, Part } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import AnswerKey from "./AnswerKey.vue";
import PaperPart from "./PaperPart.vue";

const part: Part = {
  label: "",
  lesson: "1.1",
  lesson_title: "الدرس",
  marks: 0,
  level: "R",
  stem: "حدّد الخطوة الخاطئة",
  options: [],
  answer: "الجواب الصحيح",
  answer_index: -1,
  steps: [],
  marking: [],
  graph: null,
  option_graphs: [],
  variant: "v",
  fingerprint: "fp",
  slot: { kind: "essay", level: "", needs_graph: false },
  spotting: {
    steps: ["أولى", "ثانية خاطئة", "ثالثة"],
    wrong_step: 2,
    error_kind: "sign",
    correct_step: "ثانية مصححة",
    diagnosis: "عكس إشارة",
  },
};

const paper = {
  kind: "worksheet",
  seed: 1,
  questions: [{ number: 1, kind: "essay", marks: 0, parts: [part] }],
} as unknown as Paper;

describe("اكتشف الخطأ", () => {
  it("shows the numbered steps in the sheet without revealing the diagnosis", () => {
    const wrapper = mount(PaperPart, { props: { part, number: 1, booklet: false } });
    expect(wrapper.findAll("ol.spotting-steps li").map((li) => li.text())).toEqual(part.spotting!.steps);
    expect(wrapper.text()).not.toContain("عكس إشارة");
    expect(wrapper.find(".work-space").exists()).toBe(true);
  });

  it("names the wrong step, its kind, the correction, the answer and DOK 3 in the key", () => {
    const wrapper = mount(AnswerKey, { props: { paper, header: { title: "ورقة" } as PaperHeaderData } });
    const rows = wrapper.findAll(".spotting-key div").map((row) => `${row.find("dt").text()} ${row.find("dd").text()}`);
    expect(rows).toEqual([
      "الخطوة الخاطئة: 2",
      "نوع الخطأ: عكس إشارة",
      "الخطوة الصحيحة: ثانية مصححة",
      "الجواب: الجواب الصحيح",
    ]);
    expect(wrapper.text()).toContain("DOK 3");
  });
});
