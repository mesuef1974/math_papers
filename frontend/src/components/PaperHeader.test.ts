import { readFileSync } from "node:fs";
import { join } from "node:path";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { PaperHeaderData } from "@/stores/print";
import PaperHeader from "./PaperHeader.vue";

const header: PaperHeaderData = {
  school: "مدرسة قطر الثانوية",
  teacher: "أ. سعيد",
  subject: "الرياضيات",
  grade: "الصف 12: المسار العلمي / المسار التكنولوجي",
  title: "اختبار تدريبي: الفصل الأول 2026-2027",
  minutes: 150,
  date: "08/11/2026",
  section: "12/3",
  totalMarks: 40,
  instructions: "أجب عن جميع الأسئلة.",
  seed: 7,
};

describe("PaperHeader", () => {
  it("يعرض حقول غلاف الوزارة: المدرسة والمادة والصف والزمن بالاسم والدرجة والتاريخ والتعليمات", () => {
    const text = mount(PaperHeader, { props: { header } }).text();
    for (const expected of ["مدرسة قطر الثانوية", "المعلم: أ. سعيد", "الرياضيات", "ساعتان ونصف", "40 درجة", "08/11/2026", "الشعبة: 12/3", "تعليمات:"]) {
      expect(text).toContain(expected);
    }
  });

  it("شعار المنصة «أوراق» في رأس كل ورقة، والمضغوطة أيضًا", () => {
    for (const compact of [false, true]) {
      const logo = mount(PaperHeader, { props: { header, compact } }).find("svg.logo.brand-lockup");
      expect(logo.exists()).toBe(true);
      expect(logo.attributes("height")).toBe(compact ? "38" : "46");
    }
  });

  it("العنوان الطويل يلتف في عموده ولا يضغط عمود المدرسة: لا مسار auto للعنوان", () => {
    const source = readFileSync(join(process.cwd(), "src", "components", "PaperHeader.vue"), "utf-8");
    const top = source.slice(source.indexOf(".top {"), source.indexOf("}", source.indexOf(".top {")));
    expect(top).toContain("grid-template-columns: minmax(max-content, 1fr) minmax(0, 2.4fr) minmax(max-content, 1fr)");
    expect(source).toMatch(/\.org\s*{[^}]*max-inline-size:\s*16rem/);
  });

  it("ورقة العمل بلا زمن ولا درجة كلية، والمضغوطة بلا سطر الطالب", () => {
    const sheet = { ...header, minutes: null, totalMarks: 0, instructions: "" };
    const text = mount(PaperHeader, { props: { header: sheet } }).text();
    expect(text).not.toContain("زمن الاختبار");
    expect(text).not.toContain("الدرجة الكلية");
    expect(text).toContain("اسم الطالب");
    const compact = mount(PaperHeader, { props: { header, compact: true } }).text();
    expect(compact).not.toContain("اسم الطالب");
    expect(compact).not.toContain("تعليمات");
  });
});
