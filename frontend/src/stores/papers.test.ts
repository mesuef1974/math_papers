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

  it("المقرر المختار يحدد الدروس والجداول ويُرسل مع كل توليد ويُدوَّن في الوصفة", async () => {
    const blueprints = [
      { slug: "g12", title: "ج12", total_marks: 40, is_forecast: true, course: "g12-sci-s1" },
      { slug: "g10", title: "ج10", total_marks: 50, is_forecast: false, course: "g10-s1" },
    ];
    get.mockResolvedValueOnce([]).mockResolvedValueOnce(blueprints);
    const store = usePapersStore();
    await store.loadOptions("g10-s1");
    expect(get.mock.calls[0][0]).toBe("/lessons?course=g10-s1");
    expect(store.blueprints.map((row) => row.slug)).toEqual(["g10"]);

    get.mockResolvedValue(paper());
    await store.generateWorksheet("1.2", 2, null, "");
    expect(get.mock.calls[2][0]).toBe("/papers/worksheet?lesson=1.2&count=2&course=g10-s1");
    expect(store.recipe?.course).toBe("g10-s1");
    await store.generateQuiz(["1.1"], 5);
    expect(get.mock.calls[3][0]).toBe("/papers/quiz?lessons=1.1&seed=5&course=g10-s1");

    // ورقة محفوظة من كتاب آخر تُستبدل مسائلها من كتابها لا من المختار الآن
    store.openSaved({ id: 3, title: "قديمة", paper: paper(), recipe: { ...store.recipe!, course: "g12-sci-s1" } });
    post.mockResolvedValue({ ...part("ccc"), seed: 7 });
    await store.replacePart(2, "");
    expect(post.mock.calls[0][1]).toMatchObject({ course: "g12-sci-s1" });
  });

  it("ردّ مقرر سابق يصل بعد تبديل أحدث لا يكتب فوقه", async () => {
    let releaseOld: (value: unknown) => void = () => {};
    const lesson = (code: string) => ({ code, title: code, unit: 1, examinable: true, has_generator: true, levels: [] });
    get
      .mockReturnValueOnce(new Promise((resolve) => (releaseOld = resolve)))
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([lesson("10.1")])
      .mockResolvedValueOnce([]);
    const store = usePapersStore();
    const old = store.loadOptions("g12-sci-s1");
    await store.loadOptions("g10-s1");
    releaseOld([lesson("12.1")]);
    await old;
    expect(store.course).toBe("g10-s1");
    expect(store.lessons.map((row) => row.code)).toEqual(["10.1"]);
    expect(store.optionsLoading).toBe(false);
  });

  it("بلا مقرر تبقى الطلبات كما كانت للمقرر الحالي في الخادم", async () => {
    get.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    const store = usePapersStore();
    await store.loadOptions();
    expect(get.mock.calls[0][0]).toBe("/lessons");
    expect(store.course).toBe("");
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
