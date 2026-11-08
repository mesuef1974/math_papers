import { describe, expect, it } from "vitest";
import { splitMath } from "./mathText";

describe("splitMath", () => {
  it("يفصل الرياضيات السطرية عن النص", () => {
    expect(splitMath("أوجد $x^2$ الآن")).toEqual([
      { math: false, display: false, value: "أوجد " },
      { math: true, display: false, value: "x^2" },
      { math: false, display: false, value: " الآن" },
    ]);
  });

  it("يميّز الرياضيات المعروضة بعلامتين", () => {
    expect(splitMath("حل $$\\int x\\,dx$$ ثم")).toEqual([
      { math: false, display: false, value: "حل " },
      { math: true, display: true, value: "\\int x\\,dx" },
      { math: false, display: false, value: " ثم" },
    ]);
  });

  it("يعامل \\$ علامة دولار حرفية", () => {
    expect(splitMath("السعر \\$5 و $x$")).toEqual([
      { math: false, display: false, value: "السعر $5 و " },
      { math: true, display: false, value: "x" },
    ]);
  });

  it("علامة غير مغلقة تبقى نصًا", () => {
    expect(splitMath("نص $ناقص")).toEqual([{ math: false, display: false, value: "نص $ناقص" }]);
  });
});
