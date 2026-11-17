import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";

const calls = { get: vi.fn(), post: vi.fn() };
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: { get: (...a: unknown[]) => calls.get(...a), post: (...a: unknown[]) => calls.post(...a) },
  };
});

const { useDecksStore, POLL_MS, MAX_POLLS } = await import("@/stores/decks");

const out = (status: string, detail = "") => ({ status, detail, filename: "g10-s1-lesson-2.6.pptx" });

describe("decks store", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setActivePinia(createPinia());
    Object.values(calls).forEach((fn) => fn.mockReset());
  });
  afterEach(() => vi.useRealTimers());

  it("الطلب الجاهز فورًا يعطي رابط التنزيل بالدرس والزمن", async () => {
    calls.post.mockResolvedValue(out("ready"));
    const store = useDecksStore();
    store.select("2.6", 50);
    await store.request();
    expect(calls.post).toHaveBeenCalledWith("/decks/", { course: "g10-s1", lesson: "2.6", period_minutes: 50 });
    expect(store.status).toBe("ready");
    expect(store.url).toBe("/api/v1/decks/download?course=g10-s1&lesson=2.6&period_minutes=50");
  });

  it("المعلّق يُستطلع كل بضع ثوانٍ حتى يجهز ثم يتوقف الاستطلاع", async () => {
    calls.post.mockResolvedValue(out("pending"));
    calls.get.mockResolvedValueOnce(out("pending")).mockResolvedValueOnce(out("ready"));
    const store = useDecksStore();
    store.select("2.6", 45);
    await store.request();
    expect(store.busy).toBe(true);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(store.status).toBe("pending");
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(store.status).toBe("ready");
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    expect(calls.get).toHaveBeenCalledTimes(2);
  });

  it("الفشل يحمل سبب الخادم، وتغيير الدرس يلغي الحالة والاستطلاع", async () => {
    calls.post.mockResolvedValue(out("pending"));
    calls.get.mockResolvedValue(out("failed", "مقطع تالف"));
    const store = useDecksStore();
    store.select("2.6", 45);
    await store.request();
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(store.status).toBe("failed");
    expect(store.detail).toBe("مقطع تالف");
    store.select("2.7", 45);
    expect(store.status).toBe("idle");
    expect(store.url).toBe("");
  });

  it("رفض 422 يظهر رسالته العربية ولا يبقى معلقًا", async () => {
    calls.post.mockRejectedValue(new ApiError(422, "زمن الحصة بين 30 و90 دقيقة"));
    const store = useDecksStore();
    store.select("2.6", 5);
    await store.request();
    expect(store.status).toBe("idle");
    expect(store.error).toBe("زمن الحصة بين 30 و90 دقيقة");
  });

  it("الاستطلاع يتوقف بعد الحد الأقصى برسالة إعادة الطلب", async () => {
    calls.post.mockResolvedValue(out("pending"));
    calls.get.mockResolvedValue(out("pending"));
    const store = useDecksStore();
    store.select("2.6", 45);
    await store.request();
    await vi.advanceTimersByTimeAsync(POLL_MS * (MAX_POLLS + 2));
    expect(store.status).toBe("idle");
    expect(store.error).toContain("أعد الطلب");
  });
});
