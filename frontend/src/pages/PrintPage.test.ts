import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import type { Paper } from "@/stores/papers";

const get = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: (...a: unknown[]) => get(...a) } };
});
vi.mock("vue-router", () => ({ useRoute: () => ({ params: { token: "tok.en" } }) }));

const PrintPage = (await import("./PrintPage.vue")).default;

const paper: Paper = {
  kind: "exam",
  form: "A",
  generator_version: "v1",
  blueprint: "bp",
  lesson_code: "",
  title: "اختبار تدريبي للطباعة",
  seed: 7,
  total_marks: 40,
  is_forecast: false,
  level_counts: {},
  level_marks: {},
  level: "",
  questions: [
    {
      number: 1,
      kind: "mcq",
      marks: 1,
      parts: [
        {
          label: "",
          lesson: "1.1",
          lesson_title: "مفهوم النهاية",
          marks: 1,
          level: "K",
          stem: "س؟",
          options: ["أ", "ب", "ج", "د"],
          answer: "أ",
          answer_index: 0,
          steps: [],
          graph: null,
          option_graphs: [],
          variant: "v",
          fingerprint: "f1",
          slot: { kind: "mcq", level: "K", needs_graph: false },
        },
      ],
    },
  ],
};

const payload = {
  papers: [paper],
  profile: {
    school: "مدرسة الطباعة",
    teacher_name: "أ. معلم",
    subject: "الرياضيات",
    grade: "الصف 12",
    exam_minutes: 150,
    exam_instructions: "أجب عن جميع الأسئلة.",
    worksheet_instructions: "",
  },
  date: "08/11/2026",
  section: "12/3",
  show_key: true,
  bubble: true,
};

describe("PrintPage: صفحة الطباعة للمتصفح الخادمي", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    delete document.documentElement.dataset.printReady;
  });

  it("تقرأ الحمولة بالرمز وتعرض الورقة والمفتاح والتظليل ثم تعلن الجاهزية", async () => {
    get.mockResolvedValue(payload);
    const wrapper = mount(PrintPage, { global: { stubs: { MathText: true, GraphPlot: true } } });
    await flushPromises();
    expect(get).toHaveBeenCalledWith("/pdf/print/tok.en");
    const text = wrapper.text();
    for (const expected of ["مدرسة الطباعة", "اختبار تدريبي للطباعة", "الشعبة: 12/3", "08/11/2026", "مفتاح"]) {
      expect(text).toContain(expected);
    }
    expect(wrapper.findAll(".bubble").length).toBeGreaterThan(0);
    expect(document.documentElement.dataset.printReady).toBe("1");
  });

  it("رمز غير صالح: رسالة وإشارة خطأ حتى لا ينتظر الخادم المهلة كاملة", async () => {
    get.mockRejectedValue(new ApiError(404, "صفحة الطباعة غير متاحة"));
    const wrapper = mount(PrintPage);
    await flushPromises();
    expect(wrapper.text()).toContain("غير متاحة");
    expect(document.documentElement.dataset.printReady).toBe("error");
  });
});
