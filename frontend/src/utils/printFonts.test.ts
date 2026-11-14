import { afterEach, describe, expect, it, vi } from "vitest";
import { ensurePrintFonts, PRINT_FONT_FACES } from "@/utils/printFonts";

describe("تحميل خط الورقة قبل الطباعة", () => {
  afterEach(() => {
    Reflect.deleteProperty(document, "fonts");
  });

  it("يطلب وزنَي خط الورقة وخط الرياضيات بنوعيه", async () => {
    const load = vi.fn().mockResolvedValue([]);
    Object.defineProperty(document, "fonts", { value: { load }, configurable: true });
    await ensurePrintFonts();
    expect(load.mock.calls).toEqual(PRINT_FONT_FACES.map((entry) => [...entry]));
    expect(PRINT_FONT_FACES.map(([face]) => face)).toEqual([
      '400 13pt "Noto Naskh Arabic"',
      '700 13pt "Noto Naskh Arabic"',
      '400 13pt "KaTeX_Main"',
      '700 13pt "KaTeX_Main"',
      'italic 400 13pt "KaTeX_Main"',
    ]);
  });

  it("فشل التحميل أو غياب واجهة الخطوط لا يعطّل الورقة", async () => {
    await expect(ensurePrintFonts()).resolves.toBeUndefined();
    const load = vi.fn().mockRejectedValue(new Error("offline"));
    Object.defineProperty(document, "fonts", { value: { load }, configurable: true });
    await expect(ensurePrintFonts()).resolves.toBeUndefined();
  });
});
