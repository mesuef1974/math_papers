import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import type { Paper, Recipe } from "@/stores/papers";

const calls = { get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn() };
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: {
      get: (...a: unknown[]) => calls.get(...a),
      post: (...a: unknown[]) => calls.post(...a),
      patch: (...a: unknown[]) => calls.patch(...a),
      del: (...a: unknown[]) => calls.del(...a),
    },
  };
});

const { useSavedStore } = await import("@/stores/saved");

const paper = { kind: "worksheet", title: "ورقة", seed: 1, questions: [] } as unknown as Paper;
const recipe: Recipe = {
  kind: "worksheet",
  form: "A",
  blueprint: "",
  lesson_code: "1.1",
  count: 0,
  level: "",
  purpose: "",
  seed: 1,
  replacements: [],
};
const summary = {
  id: 3,
  title: "ورقة",
  kind: "worksheet" as const,
  blueprint: "",
  lesson_code: "1.1",
  seed: 1,
  total_marks: 0,
  question_count: 0,
  replacement_count: 0,
  generator_version: "g",
  created_at: "2026-11-08T07:00:00Z",
  updated_at: "2026-11-08T07:00:00Z",
};

describe("saved store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    Object.values(calls).forEach((fn) => fn.mockReset());
  });

  it("الحفظ يرسل الاسم بلا فراغات ويضيف الملخص أول القائمة بلا لقطة", async () => {
    calls.post.mockResolvedValue({ ...summary, paper, recipe });
    const store = useSavedStore();
    const row = await store.save("  ورقة ", paper, recipe);
    expect(calls.post).toHaveBeenCalledWith("/saved", { title: "ورقة", paper, recipe });
    expect(row?.id).toBe(3);
    expect(store.items).toEqual([summary]);
  });

  it("التحديث يستبدل الملخص في مكانه، والحذف يزيله", async () => {
    calls.get.mockResolvedValue([summary, { ...summary, id: 4 }]);
    calls.patch.mockResolvedValue({ ...summary, title: "جديد", paper, recipe });
    calls.del.mockResolvedValue(undefined);
    const store = useSavedStore();
    await store.load();
    await store.update(3, { title: "جديد" });
    expect(store.items.map((i) => i.title)).toEqual(["جديد", "ورقة"]);
    expect(await store.remove(4)).toBe(true);
    expect(store.items.map((i) => i.id)).toEqual([3]);
  });

  it("الفتح يعيد null مع رسالة عند 404", async () => {
    calls.get.mockRejectedValue(new ApiError(404, "الورقة غير موجودة"));
    const store = useSavedStore();
    expect(await store.open(99)).toBeNull();
    expect(store.error).toBe("الورقة غير موجودة.");
  });
});
