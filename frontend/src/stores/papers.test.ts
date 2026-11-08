import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import type { Paper, Part } from "@/stores/papers";

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } };
});

const { usePapersStore } = await import("@/stores/papers");

function part(fingerprint: string, overrides: Partial<Part> = {}): Part {
  return {
    label: "",
    lesson: "1.2",
    lesson_title: "حساب النهايات",
    marks: 0,
    level: "A",
    stem: `س ${fingerprint}`,
    options: [],
    answer: "1",
    answer_index: -1,
    steps: [],
    graph: null,
    option_graphs: [],
    variant: "v",
    fingerprint,
    slot: { kind: "essay", level: "", needs_graph: false },
    ...overrides,
  };
}

function paper(): Paper {
  return {
    kind: "worksheet",
    form: "A",
    generator_version: "g",
    blueprint: "",
    lesson_code: "1.2",
    title: "ورقة عمل",
    seed: 42,
    total_marks: 0,
    is_forecast: false,
    level_marks: {},
    level_counts: {},
    level: "",
    questions: [
      { number: 1, kind: "essay", marks: 0, parts: [part("aaa")] },
      { number: 2, kind: "essay", marks: 0, parts: [part("bbb")] },
    ],
  };
}

describe("papers store: الوصفة والاستبدال", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    post.mockReset();
  });

  it("التوليد يسجّل وصفة بالبذرة ويصفّر الحفظ", async () => {
    get.mockResolvedValue(paper());
    const store = usePapersStore();
    store.savedId = 9;
    await store.generateWorksheet("1.2", 2, null, "A");
    expect(store.recipe).toEqual({
      kind: "worksheet",
      form: "A",
      blueprint: "",
      lesson_code: "1.2",
      count: 2,
      level: "A",
      purpose: "",
      seed: 42,
      replacements: [],
    });
    expect(store.savedId).toBeNull();
    expect(store.modified).toBe(false);
  });

  it("الورقة العلاجية ترسل الغرض بلا مستوى، والوصفة تحفظه", async () => {
    get.mockResolvedValue(paper());
    const store = usePapersStore();
    await store.generateWorksheet("1.2", 6, null, "A", false, "remedial");
    expect(get.mock.calls[0][0]).toBe("/papers/worksheet?lesson=1.2&count=6&purpose=remedial");
    expect(store.recipe).toMatchObject({ kind: "worksheet", level: "", purpose: "remedial" });
  });

  it("الاختبار القصير يرسل الدروس مفصولة بفاصلة بلا تكرار ويدوّنها في الوصفة", async () => {
    get.mockResolvedValueOnce({ ...paper(), kind: "quiz" }).mockResolvedValueOnce({ ...paper(), kind: "quiz", form: "B" });
    const store = usePapersStore();
    await store.generateQuiz(["1.1", "", "1.2", "1.1"], 5, true);
    expect(get.mock.calls[0][0]).toBe("/papers/quiz?lessons=1.1%2C1.2&seed=5");
    expect(get.mock.calls[1][0]).toBe("/papers/quiz?lessons=1.1%2C1.2&seed=5&seed=42&form=B");
    expect(store.recipe).toMatchObject({ kind: "quiz", lesson_code: "1.1,1.2", count: 0, purpose: "" });
    expect(store.twin?.form).toBe("B");
  });

  it("الاستبدال يرسل الخانة وكل البصمات، ويبدّل الجزء ويدوّن الاستبدال", async () => {
    get.mockResolvedValue(paper());
    post.mockResolvedValue({ ...part("ccc", { stem: "جديد" }), seed: 7 });
    const store = usePapersStore();
    await store.generateWorksheet("1.2", 2, null, "");
    await store.replacePart(2, "");
    expect(post).toHaveBeenCalledWith("/papers/replace-part", {
      lesson: "1.2",
      label: "",
      marks: 0,
      slot: { kind: "essay", level: "", needs_graph: false },
      exclude: ["aaa", "bbb"],
    });
    expect(store.paper?.questions[1].parts[0].stem).toBe("جديد");
    expect(store.paper?.questions[1].parts[0]).not.toHaveProperty("seed");
    expect(store.recipe?.replacements).toEqual([{ question: 2, label: "", seed: 7, fingerprint: "ccc" }]);
    expect(store.modified).toBe(true);
    expect(store.replacing).toBe("");
  });

  it("طلب النموذج ب يأخذ بذرة أ ويخزّنه توأمًا، والتوليد التالي بلا توأم يمسحه", async () => {
    get.mockResolvedValueOnce(paper()).mockResolvedValueOnce({ ...paper(), form: "B" });
    const store = usePapersStore();
    await store.generateWorksheet("1.2", 2, null, "", true);
    expect(get.mock.calls[1][0]).toBe("/papers/worksheet?lesson=1.2&count=2&seed=42&form=B");
    expect(store.twin?.form).toBe("B");
    get.mockResolvedValueOnce(paper());
    await store.generateWorksheet("1.2", 2, null, "");
    expect(store.twin).toBeNull();
  });

  it("409 من الخادم يظهر رسالته ولا يغيّر الورقة", async () => {
    get.mockResolvedValue(paper());
    post.mockRejectedValue(new ApiError(409, "لا بديل"));
    const store = usePapersStore();
    await store.generateWorksheet("1.2", 2, null, "");
    await store.replacePart(1, "");
    expect(store.error).toBe("لا بديل");
    expect(store.paper?.questions[0].parts[0].fingerprint).toBe("aaa");
    expect(store.modified).toBe(false);
  });

  it("فتح ورقة محفوظة يحمّل اللقطة والوصفة ورقم الحفظ", () => {
    const store = usePapersStore();
    const snapshot = paper();
    store.openSaved({
      id: 5,
      title: "ورقتي",
      paper: snapshot,
      recipe: {
        kind: "worksheet",
        form: "A",
        blueprint: "",
        lesson_code: "1.2",
        count: 2,
        level: "",
        purpose: "",
        seed: 42,
        replacements: [],
      },
    });
    expect(store.paper).toEqual(snapshot);
    expect(store.savedId).toBe(5);
    expect(store.savedTitle).toBe("ورقتي");
  });
});
