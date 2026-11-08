import { afterEach, describe, expect, it, vi } from "vitest";
import { api, API_BASE, ApiError } from "./client";

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("عميل الواجهة البرمجية", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("يسبق كل مسار بإصدار الواجهة ويطلب JSON بجلسة الأصل نفسه", async () => {
    const fetchMock = mockFetch(200, { ok: true });
    await api.get("/ping");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${API_BASE}/ping`);
    expect(init.credentials).toBe("same-origin");
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBeUndefined();
  });

  it("يرسل رمز CSRF من الكوكي مع غير GET", async () => {
    document.cookie = "csrftoken=abc123";
    const fetchMock = mockFetch(204, undefined);
    await api.post("/auth/logout");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBe("abc123");
  });

  it("يرمي ApiError برسالة الخادم العربية عند الفشل", async () => {
    mockFetch(409, { detail: "تعذر توليد مسائل مختلفة" });
    await expect(api.get("/papers/exam")).rejects.toMatchObject({ status: 409, detail: "تعذر توليد مسائل مختلفة" });
    await expect(api.get("/papers/exam")).rejects.toBeInstanceOf(ApiError);
  });
});
