import { isolateNumberRanges } from "./bidi";

describe("isolateNumberRanges", () => {
  it("يعزل مدى السنوات", () => {
    expect(isolateNumberRanges("الفصل الأول، 2026-2027")).toBe("الفصل الأول، ⁦2026-2027⁩");
  });
  it("لا يمس الأرقام المفردة", () => {
    expect(isolateNumberRanges("السؤال 12")).toBe("السؤال 12");
  });
});
