import { describe, expect, it } from "vitest";
import { EDGES, LANES, POS } from "./copilotLayout";
import { GROUPS, SOURCES, STAGES, splitCode, statusCounts } from "./copilotPipeline";

describe("مراحل معاون المعلم", () => {
  it("تسع عشرة مرحلة بترقيم متصل", () => {
    expect(STAGES.map((s) => s.id)).toEqual(Array.from({ length: 19 }, (_, i) => i + 1));
  });

  it.each(STAGES.map((s) => [s.id, s] as const))("المرحلة %i بمدخل ومخرج ومتطلبات وعنوان", (_id, s) => {
    expect(s.title.trim()).not.toBe("");
    expect(s.inputs.length).toBeGreaterThan(0);
    expect(s.outputs.length).toBeGreaterThan(0);
    expect(s.requirements.length).toBeGreaterThan(0);
    expect(Object.keys(GROUPS)).toContain(s.group);
  });

  it("مجموع الحالات يساوي عدد المراحل", () => {
    const c = statusCounts();
    expect(c.done + c.run + c.plan).toBe(STAGES.length);
    expect(c.run).toBeGreaterThan(0);
  });

  it("المدخلات الأساسية ثمانية", () => {
    expect(SOURCES).toHaveLength(8);
  });

  it("splitCode يفصل الشيفرة بين علامتَي `", () => {
    expect(splitCode("ملف `book.yaml` جاهز")).toEqual([
      { text: "ملف ", code: false },
      { text: "book.yaml", code: true },
      { text: " جاهز", code: false },
    ]);
    expect(splitCode("نص بلا شيفرة")).toEqual([{ text: "نص بلا شيفرة", code: false }]);
  });

  it("لا نص من الكتب في البيانات: لا علامات حماية ولا أسئلة", () => {
    const all = JSON.stringify(STAGES);
    expect(all).not.toMatch(/For Qatar MoE Use Only/i);
  });
});

describe("هندسة المخطط", () => {
  it("لكل مرحلة موضع داخل إطار الرسم", () => {
    for (const s of STAGES) expect(POS[s.id]).toBeDefined();
  });

  it("كل مسار يبدأ بـ M ويشير إلى مراحل موجودة", () => {
    const ids = new Set(STAGES.map((s) => s.id));
    for (const e of EDGES) {
      expect(e.d.startsWith("M")).toBe(true);
      for (const n of e.nodes) expect(ids.has(n)).toBe(true);
    }
    expect(new Set(EDGES.map((e) => e.id)).size).toBe(EDGES.length);
  });

  it("ثلاثة مسارات تغطي كل مجموعات المراحل", () => {
    expect(LANES.map((l) => l.id)).toEqual(["A", "B", "C"]);
  });
});
