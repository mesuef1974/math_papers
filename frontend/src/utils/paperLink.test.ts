import { describe, expect, it } from "vitest";
import { paperPrefill, paperRoute, type PaperLink } from "@/utils/paperLink";

const link = (over: Partial<PaperLink>): PaperLink => ({
  kind: "worksheet",
  label: "",
  lessons: [],
  level: "",
  blueprint: "",
  ...over,
});

describe("رابط ورقة حصة غير الدرس", () => {
  it("يعيد مدخلات الاختبار القصير بدرسيه كما هي", () => {
    const route = paperRoute("g10-s1", link({ kind: "quiz", lessons: ["1.2", "1.3"] }));
    expect(route).toEqual({ name: "home", query: { course: "g10-s1", mode: "quiz", lesson: "1.2", second: "1.3" } });
    const query = (route as { query: Record<string, string> }).query;
    expect(paperPrefill(query)).toEqual({
      course: "g10-s1",
      mode: "quiz",
      lesson: "1.2",
      second: "1.3",
      level: "",
      blueprint: "",
    });
  });

  it("يحمل مستوى ورقة الدعم وجدول الحزمة", () => {
    const support = paperRoute("g10-s1", link({ lessons: ["2.1"], level: "K" }));
    expect((support as { query: Record<string, string> }).query.level).toBe("K");
    const bundle = paperRoute("g10-s1", link({ kind: "bundle", blueprint: "g10-final" }));
    expect(paperPrefill((bundle as { query: Record<string, string> }).query)?.blueprint).toBe("g10-final");
  });

  it("يرفض رابطًا بلا مقرر أو بنوع أو مستوى غير معروف", () => {
    expect(paperPrefill({ mode: "quiz" })).toBeNull();
    expect(paperPrefill({ course: "g10-s1", mode: "essay" })).toBeNull();
    expect(paperPrefill({ course: "g10-s1", mode: "worksheet", level: "Z" })?.level).toBe("");
  });
});
