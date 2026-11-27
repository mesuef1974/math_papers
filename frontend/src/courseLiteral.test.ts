import { describe, expect, it } from "vitest";

// حارس: رمز المقرر يأتي من متجر المقررات وحده، فلا تُثبَّت صفحة على صف.
const sources = import.meta.glob(["./**/*.{ts,vue}", "!./**/*.test.ts"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("رموز المقررات", () => {
  it("لا يثبّت ملف في الواجهة رمز مقرر", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20);
    const fixed = Object.entries(sources)
      .filter(([, code]) => /["'`]g\d{1,2}-(?:[a-z]+-)?s[12]["'`]/.test(code))
      .map(([path]) => path);
    expect(fixed).toEqual([]);
  });
});
