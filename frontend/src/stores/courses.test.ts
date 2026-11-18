import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Course } from "@/stores/courses";

const get = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: (...a: unknown[]) => get(...a) } };
});

const { COURSE_KEY, defaultCourse, useCoursesStore } = await import("@/stores/courses");

function course(slug: string, overrides: Partial<Course> = {}): Course {
  return {
    slug,
    title: `مقرر ${slug}`,
    grade: 10,
    track: "",
    semester: 1,
    academic_year: "2026-2027",
    edition: "",
    language: "ar",
    is_current: false,
    lesson_count: 3,
    has_generators: true,
    ...overrides,
  };
}

const ROWS = [
  course("g10-s1"),
  course("g11-sci-s1", { has_generators: false }),
  course("g12-sci-s1", { is_current: true }),
];

describe("defaultCourse", () => {
  it("يفضّل المحفوظ ثم الحالي ثم أول مقرر له مولّدات", () => {
    expect(defaultCourse(ROWS, "g10-s1")).toBe("g10-s1");
    expect(defaultCourse(ROWS, "")).toBe("g12-sci-s1");
    expect(defaultCourse(ROWS, "g11-sci-s1")).toBe("g12-sci-s1"); // المحفوظ بلا مولّدات لا يُختار
    expect(defaultCourse(ROWS, "gone")).toBe("g12-sci-s1"); // مقرر حُذف بعد حفظه
    expect(defaultCourse([course("a", { has_generators: false }), course("b")], "")).toBe("b");
    expect(defaultCourse([course("a", { has_generators: false })], "")).toBe("");
  });
});

describe("courses store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    localStorage.clear();
  });

  it("يحمّل المقررات ويختار الافتراضي ويحفظ اختيار المعلم", async () => {
    get.mockResolvedValueOnce(ROWS);
    const store = useCoursesStore();
    await store.load();
    expect(get).toHaveBeenCalledWith("/courses");
    expect(store.selected).toBe("g12-sci-s1");
    expect(store.current?.title).toBe("مقرر g12-sci-s1");

    store.select("g10-s1");
    expect(store.selected).toBe("g10-s1");
    expect(localStorage.getItem(COURSE_KEY)).toBe("g10-s1");

    store.select("g11-sci-s1"); // بلا مولّدات: لا يُختار
    store.select("nope");
    expect(store.selected).toBe("g10-s1");
  });

  it("يبدأ من الاختيار المحفوظ في المتصفح", async () => {
    localStorage.setItem(COURSE_KEY, "g10-s1");
    get.mockResolvedValueOnce(ROWS);
    const store = useCoursesStore();
    await store.load();
    expect(store.selected).toBe("g10-s1");
  });

  it("يعرض رسالة عند تعذر التحميل ولا يختار مقررًا", async () => {
    get.mockRejectedValueOnce(new Error("network"));
    const store = useCoursesStore();
    await store.load();
    expect(store.selected).toBe("");
    expect(store.error).toContain("تعذر تحميل المقررات");
    expect(store.loading).toBe(false);
  });
});
