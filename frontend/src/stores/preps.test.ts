import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";

const calls = { get: vi.fn(), put: vi.fn(), del: vi.fn() };
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: {
      get: (...a: unknown[]) => calls.get(...a),
      put: (...a: unknown[]) => calls.put(...a),
      del: (...a: unknown[]) => calls.del(...a),
    },
  };
});

const { usePrepsStore, wordUrl } = await import("@/stores/preps");

describe("preps store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    calls.get.mockReset();
    calls.put.mockReset();
    calls.del.mockReset();
  });

  it("يحمّل حصص الخطة من مقرر العاشر", async () => {
    calls.get.mockResolvedValue([
      {
        lesson: "1.1",
        title: "",
        unit: 1,
        k: 1,
        n: 3,
        week: 1,
        status: "pending",
      },
    ]);
    const store = usePrepsStore();
    await store.load();
    expect(calls.get).toHaveBeenCalledWith("/preps/g10-s1");
    expect(store.periods).toHaveLength(1);
    expect(store.loaded).toBe(true);
  });

  it("يفتح تحضير الحصة ويعطي رابط Word بالدرس ورقم الحصة", async () => {
    calls.get.mockResolvedValue({ lesson: "2.6", k: 2 });
    const store = usePrepsStore();
    await store.open("2.6", 2);
    expect(calls.get).toHaveBeenCalledWith("/preps/g10-s1/2.6/2");
    expect(store.url).toBe("/api/v1/preps/g10-s1/2.6/2/word");
    expect(wordUrl("1.1", 1)).toBe("/api/v1/preps/g10-s1/1.1/1/word");
  });

  it("الحصة غير الموجودة تُفرغ التحضير وتعرض رسالة", async () => {
    calls.get.mockRejectedValue(new ApiError(404, "لا حصة"));
    const store = usePrepsStore();
    await store.open("9.9", 1);
    expect(store.sheet).toBeNull();
    expect(store.url).toBe("");
    expect(store.error).toBe("تعذر فتح تحضير الحصة.");
  });

  it("يحفظ تعديل الحصة المفتوحة ويسترجع المشترك، ويعرض رفض الخادم برسالته", async () => {
    const store = usePrepsStore();
    calls.get
      .mockResolvedValueOnce({ lesson: "1.1", k: 2 })
      .mockResolvedValue([]);
    await store.open("1.1", 2);
    calls.put.mockResolvedValue({
      lesson: "1.1",
      k: 2,
      edit: { state: "active" },
    });
    expect(
      await store.saveOverride({
        strategies: { warmup: "opening-predict" },
        removed: [],
      }),
    ).toBe(true);
    expect(calls.put).toHaveBeenCalledWith("/preps/g10-s1/1.1/2/override", {
      strategies: { warmup: "opening-predict" },
      removed: [],
    });
    expect(calls.get).toHaveBeenLastCalledWith("/preps/g10-s1");
    calls.del.mockResolvedValue({
      lesson: "1.1",
      k: 2,
      edit: { state: "none" },
    });
    expect(await store.saveOverride(null)).toBe(true);
    expect(calls.del).toHaveBeenCalledWith("/preps/g10-s1/1.1/2/override");
    calls.put.mockRejectedValue(
      new ApiError(422, "التعديل يُفشل معيارًا حاجبًا فلم يُحفظ"),
    );
    expect(await store.saveOverride({ strategies: {}, removed: [7] })).toBe(
      false,
    );
    expect(store.editError).toBe("التعديل يُفشل معيارًا حاجبًا فلم يُحفظ");
    expect(store.sheet?.k).toBe(2);
  });
});
