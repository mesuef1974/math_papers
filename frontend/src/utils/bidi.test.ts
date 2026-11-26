import { isolateNumberRanges } from "./bidi";

const isolated = (range: string) => `⁦${range}⁩`;

describe("isolateNumberRanges", () => {
  it("يعزل مدى السنوات", () => {
    expect(isolateNumberRanges("الفصل الأول، 2026-2027")).toBe(`الفصل الأول، ${isolated("2026-2027")}`);
  });
  it("لا يمس الأرقام المفردة", () => {
    expect(isolateNumberRanges("السؤال 12")).toBe("السؤال 12");
  });
  it.each([
    "(8 - 4 x)",
    "x² - 6 x + 8",
    "2 - 3x",
    "x - 8 - 4",
    "y = 2 - 3",
    "(5 - 2)²",
    "2(3 - 1)",
    "3 - 1.5x",
    "-2 - 3",
    "x^2 - 6",
    "‎8 - 4‏",
  ])("لا يعزل داخل تعبير رياضي: %s", (text) => {
    expect(isolateNumberRanges(text)).toBe(text);
  });
  it.each([
    ["2026-2027", "2026-2027"],
    ["الصفحات 10 - 12", "10 - 12"],
    ["العام (2026-2027)", "2026-2027"],
    ["العاشر، 2026-2027 – 10", "2026-2027 – 10"],
    ["أ) 2-3", "2-3"],
    ["DOK 2-3", "2-3"],
  ])("يبقي عزل المدى في النص: %s", (text, range) => {
    expect(isolateNumberRanges(text)).toBe(text.replace(range, isolated(range)));
  });
});
