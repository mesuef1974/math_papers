import { describe, expect, it, vi } from "vitest";

vi.mock("@/stores/auth", () => ({ useAuthStore: () => ({}) }));
const { safeNext } = await import("@/router");

describe("safeNext", () => {
  it("يقبل المسارات الداخلية", () => {
    expect(safeNext("/about?x=1")).toBe("/about?x=1");
  });
  it("يرفض العناوين الخارجية والقيم الغريبة", () => {
    for (const value of ["https://evil.example", "//evil.example", "javascript:alert(1)", undefined, ["/a"]]) {
      expect(safeNext(value)).toBe("/");
    }
  });
});
