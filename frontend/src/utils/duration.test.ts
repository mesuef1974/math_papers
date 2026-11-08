import { describe, expect, it } from "vitest";
import { durationLabel, todayLabel } from "./duration";

describe("durationLabel", () => {
  it("يسمّي الأزمنة الشائعة كما في أغلفة الوزارة", () => {
    expect(durationLabel(150)).toBe("ساعتان ونصف");
    expect(durationLabel(120)).toBe("ساعتان");
    expect(durationLabel(90)).toBe("ساعة ونصف");
    expect(durationLabel(75)).toBe("75 دقيقة");
    expect(durationLabel(null)).toBe("");
  });
});

describe("todayLabel", () => {
  it("يوم/شهر/سنة بأرقام لاتينية", () => {
    expect(todayLabel(new Date(2026, 10, 8))).toBe("08/11/2026");
  });
});
