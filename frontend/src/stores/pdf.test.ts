import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } };
});

const { usePdfStore, requestKey, POLL_MS, POLL_LIMIT, PREVIEW_MAX_AGE_MS } = await import("@/stores/pdf");

const request = {
  papers: [],
  profile: {
    school: "",
    teacher_name: "",
    subject: "الرياضيات",
    grade: "",
    exam_minutes: 150,
    exam_instructions: "",
    worksheet_instructions: "",
  },
  date: "08/11/2026",
  section: "12/3",
  show_key: true,
  bubble: false,
};

describe("pdf store: مهمة خلفية واستطلاع ثم تنزيل", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    post.mockReset();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it("يطلب Word من مسار docx ويستطلع المسار نفسه", async () => {
    post.mockResolvedValue({ id: "d1", status: "done", error: "", filename: "x.docx" });
    const open = vi.fn();
    const store = usePdfStore();
    await store.download(request, open, "docx");
    expect(post).toHaveBeenCalledWith("/docx", request);
    expect(open).toHaveBeenCalledWith("/api/v1/pdf/d1/file");
  });

  it("يستطلع حتى تنتهي المهمة ثم يفتح رابط الملف", async () => {
    post.mockResolvedValue({ id: "a1", status: "queued", error: "", filename: "x.pdf" });
    get.mockResolvedValueOnce({ id: "a1", status: "running", error: "", filename: "x.pdf" }).mockResolvedValueOnce({
      id: "a1",
      status: "done",
      error: "",
      filename: "x.pdf",
    });
    const open = vi.fn();
    const store = usePdfStore();
    const run = store.download(request, open);
    expect(post).toHaveBeenCalledWith("/pdf", request);
    await vi.advanceTimersByTimeAsync(POLL_MS * 2);
    await run;
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith("/pdf/a1");
    expect(open).toHaveBeenCalledWith("/api/v1/pdf/a1/file");
    expect(store.status).toBe("done");
    expect(store.statusText).toContain("جاهز");
  });

  it("خطأ المهمة من الخادم يظهر نصه، ولا يُفتح شيء", async () => {
    post.mockResolvedValue({ id: "b2", status: "error", error: "تعذر توليد الملف. حاول مرة أخرى.", filename: "" });
    const open = vi.fn();
    const store = usePdfStore();
    await store.download(request, open);
    expect(open).not.toHaveBeenCalled();
    expect(store.status).toBe("error");
    expect(store.error).toContain("تعذر توليد الملف");
  });

  it("503 (غير مفعّل) يعرض رسالة الخادم، وطول الانتظار يُقطع برسالة", async () => {
    post.mockRejectedValue(new ApiError(503, "توليد PDF في الخادم غير مفعّل هنا."));
    const store = usePdfStore();
    await store.download(request, vi.fn());
    expect(store.error).toContain("غير مفعّل");

    post.mockResolvedValue({ id: "c3", status: "queued", error: "", filename: "" });
    get.mockResolvedValue({ id: "c3", status: "running", error: "", filename: "" });
    const open = vi.fn();
    const run = store.download(request, open);
    await vi.advanceTimersByTimeAsync(POLL_MS * (POLL_LIMIT + 1));
    await run;
    expect(open).not.toHaveBeenCalled();
    expect(store.error).toContain("طال انتظار الملف");
  });

  it("لا يبدأ طلبًا ثانيًا ما دام الأول جاريًا", async () => {
    post.mockResolvedValue({ id: "d4", status: "queued", error: "", filename: "" });
    get.mockResolvedValue({ id: "d4", status: "done", error: "", filename: "" });
    const store = usePdfStore();
    const first = store.download(request, vi.fn());
    await store.download(request, vi.fn());
    expect(post).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    await first;
  });
});

describe("pdf store: معاينة «صفحات PDF»", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    post.mockReset();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it("تطلب ملف PDF وتستطلعه ثم تعطي رابط العرض داخل الصفحة، دون مسّ حالة التنزيل", async () => {
    post.mockResolvedValue({ id: "p1", status: "queued", error: "", filename: "x.pdf" });
    get.mockResolvedValue({ id: "p1", status: "done", error: "", filename: "x.pdf" });
    const store = usePdfStore();
    const run = store.preview(request);
    expect(post).toHaveBeenCalledWith("/pdf", request);
    expect(store.previewBusy).toBe(true);
    expect(store.previewText).toContain("المعاينة");
    await vi.advanceTimersByTimeAsync(POLL_MS);
    await run;
    expect(store.previewStatus).toBe("done");
    expect(store.previewUrl).toBe("/api/v1/pdf/p1/file?inline=1");
    expect(store.status).toBe("idle");
    expect(store.busy).toBe(false);
  });

  it("المعاينة حديثة لطلبها وحده، وتقدُم بتغيّر الطلب أو بانتهاء مهلة ملفها", async () => {
    post.mockResolvedValue({ id: "p2", status: "done", error: "", filename: "x.pdf" });
    const store = usePdfStore();
    expect(store.previewFresh(request)).toBe(false);
    await store.preview(request);
    expect(store.previewFresh(request)).toBe(true);
    expect(store.previewFresh({ ...request, show_key: false })).toBe(false);
    expect(store.previewKey).toBe(requestKey(request));
    vi.advanceTimersByTime(PREVIEW_MAX_AGE_MS);
    expect(store.previewFresh(request)).toBe(false);
  });

  it("خطأ المهمة ورفض الخادم يظهران في حالة المعاينة بلا رابط", async () => {
    post.mockResolvedValue({ id: "p3", status: "error", error: "تعذر توليد الملف. حاول مرة أخرى.", filename: "" });
    const store = usePdfStore();
    await store.preview(request);
    expect(store.previewStatus).toBe("error");
    expect(store.previewError).toContain("تعذر توليد الملف");
    expect(store.previewUrl).toBe("");

    post.mockRejectedValue(new ApiError(429, "الخادم مشغول بتوليد ملفات أخرى. حاول بعد قليل."));
    await store.preview(request);
    expect(store.previewError).toContain("مشغول");
    expect(store.error).toBe("");
  });

  it("لا تبدأ معاينة ثانية ما دامت الأولى جارية، والتنزيل لا يحجبها", async () => {
    post.mockResolvedValue({ id: "p4", status: "queued", error: "", filename: "" });
    get.mockResolvedValue({ id: "p4", status: "done", error: "", filename: "" });
    const store = usePdfStore();
    const download = store.download(request, vi.fn());
    const first = store.preview(request);
    await store.preview(request);
    expect(post).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    await Promise.all([download, first]);
    expect(store.previewStatus).toBe("done");
  });
});
