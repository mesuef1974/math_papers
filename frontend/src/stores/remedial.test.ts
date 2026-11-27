import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
    },
  };
});

const { useRemedialStore, POLL_MS, MAX_POLLS } = await import("./remedial");
const { ApiError, API_BASE } = await import("@/api/client");

const idle = { status: "idle", detail: "" };
const pending = { status: "pending", detail: "الحزمة قيد البناء" };

async function selected() {
  const store = useRemedialStore();
  await store.select("g10-s1", "1.1", "10/3");
  return store;
}

describe("remedial store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setActivePinia(createPinia());
    get.mockReset().mockResolvedValue(idle);
    post.mockReset();
  });
  afterEach(() => {
    useRemedialStore().reset();
    vi.useRealTimers();
  });

  it("يطلب الحزمة ويستطلع حالتها حتى تجهز ثم يعطي رابط التنزيل", async () => {
    const store = await selected();
    expect(get).toHaveBeenCalledWith(
      "/remedial-packs/g10-s1/1.1?section=10%2F3",
    );
    post.mockResolvedValue(pending);
    await store.request();
    expect(post).toHaveBeenCalledWith("/remedial-packs/g10-s1/1.1", {
      section: "10/3",
    });
    expect(store.busy).toBe(true);
    expect(store.detail).toBe("الحزمة قيد البناء");
    expect(store.url).toBe("");
    get.mockResolvedValue({ status: "ready", detail: "" });
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(store.url).toBe(
      `${API_BASE}/remedial-packs/g10-s1/1.1/download?section=10%2F3`,
    );
  });

  it("503 يعطّل الطلب ويحفظ سببه", async () => {
    get.mockRejectedValue(new ApiError(503, "خدمة المهام غير مفعّلة"));
    const store = await selected();
    expect(store.unavailable).toBe("خدمة المهام غير مفعّلة");
    await store.request();
    expect(post).not.toHaveBeenCalled();
  });

  it("سبب الفشل من الخادم يبقى للمعلم، و403 رسالة", async () => {
    const store = await selected();
    post.mockResolvedValue({
      status: "failed",
      detail: "الحزمة تتسع لـ 40 طالبًا",
    });
    await store.request();
    expect(store.detail).toBe("الحزمة تتسع لـ 40 طالبًا");
    post.mockRejectedValue(new ApiError(403, "الشعبة ليست من شعبك"));
    await store.request();
    expect(store.error).toBe("الشعبة ليست من شعبك");
  });

  it("الاستطلاع محدود، وتغيير الاختيار يوقفه", async () => {
    const store = await selected();
    post.mockResolvedValue(pending);
    get.mockResolvedValue(pending);
    await store.request();
    await vi.advanceTimersByTimeAsync(POLL_MS * (MAX_POLLS + 2));
    expect(store.error).toContain("أطول من المتوقع");
    await store.request();
    store.reset();
    get.mockClear();
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    expect(get).not.toHaveBeenCalled();
  });
});
