import { describe, expect, it, vi } from "vitest";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { CACHE_SIZE, MAX_BACKING_WIDTH, PageRenderer, renderScale } from "./pdfPages";

// ملف مزيّف بمقاس A4 بالنقاط؛ كل رسم يُحصى ويمكن تأخيره لاختبار السباقات
function fakeDoc(pages = 10) {
  const renders: number[] = [];
  const gates = new Map<number, Promise<void>>();
  const doc = {
    numPages: pages,
    loadingTask: { destroy: vi.fn().mockResolvedValue(undefined) },
    getPage: vi.fn(async (n: number) => ({
      getViewport: ({ scale }: { scale: number }) => ({ width: 595 * scale, height: 842 * scale }),
      render: () => ({
        promise: (async () => {
          await gates.get(n);
          renders.push(n);
        })(),
      }),
    })),
  };
  return { doc: doc as unknown as PDFDocumentProxy, raw: doc, renders, gates };
}

describe("renderScale: دقة الرسم", () => {
  it("عرض الحاوية × كثافة الشاشة على عرض الصفحة", () => {
    expect(renderScale(595, 2, 595)).toBe(2);
    expect(renderScale(800, 1, 595)).toBeCloseTo(800 / 595);
  });
  it("كثافة أقل من 1 تُرفع إلى 1 ولا تتجاوز اللوحة السقف", () => {
    expect(renderScale(600, 0.5, 600)).toBe(1);
    expect(renderScale(2000, 3, 600)).toBeCloseTo(MAX_BACKING_WIDTH / 600);
  });
});

describe("PageRenderer: صفحات جاهزة للتقليب", () => {
  it("نسبة الصفحة من الصفحة الأولى", async () => {
    const { doc } = fakeDoc();
    expect(await new PageRenderer(doc, 600, 1).ratio()).toBeCloseTo(595 / 842);
  });

  it("لوحة بدقة الشاشة، والطلبان المتزامنان لصفحة واحدة رسمٌ واحد", async () => {
    const { doc, renders } = fakeDoc();
    const renderer = new PageRenderer(doc, 600, 2);
    const [a, b] = await Promise.all([renderer.page(3), renderer.page(3)]);
    expect(a).toBe(b);
    expect(a.width).toBe(1200);
    expect(a.height).toBe(Math.ceil(842 * (1200 / 595)));
    expect(renders).toEqual([3]);
  });

  it("العودة إلى صفحة مرسومة لا تعيد رسمها", async () => {
    const { doc, renders } = fakeDoc();
    const renderer = new PageRenderer(doc, 600, 1);
    await renderer.page(1);
    await renderer.page(2);
    await renderer.page(1);
    expect(renders).toEqual([1, 2]);
  });

  it("المخزن لا يتجاوز الحد ويُبقي الأحدث استعمالًا", async () => {
    const { doc, renders } = fakeDoc();
    const renderer = new PageRenderer(doc, 600, 1);
    for (const n of [1, 2, 3, 4]) await renderer.page(n);
    expect(renders).toHaveLength(4);
    await renderer.page(4); // مخزنة
    await renderer.page(3); // مخزنة
    expect(renders).toHaveLength(4);
    await renderer.page(1); // أُخرجت: تُرسم من جديد
    expect(renders).toHaveLength(5);
    expect(CACHE_SIZE).toBe(3);
  });

  it("التحميل المسبق للجارتين داخل حدود الملف فقط", async () => {
    const { doc, renders } = fakeDoc(3);
    const renderer = new PageRenderer(doc, 600, 1);
    renderer.prefetch(1, 3);
    await vi.waitFor(() => expect(renders).toEqual([2]));
    renderer.prefetch(3, 3);
    await vi.waitFor(() => expect(renders).toEqual([2]));
  });

  it("تغيّر العرض يبطل المرسوم، ولا يُحفظ رسم بدأ بالمقاس القديم", async () => {
    const { doc, renders, gates } = fakeDoc();
    let open!: () => void;
    gates.set(5, new Promise<void>((resolve) => (open = resolve)));
    const renderer = new PageRenderer(doc, 600, 1);
    await renderer.page(1);
    const slow = renderer.page(5);
    renderer.resize(900, 1);
    open();
    const stale = await slow;
    expect(stale.width).toBe(600);
    const fresh = await renderer.page(5);
    expect(fresh.width).toBe(900);
    expect(renders.filter((n) => n === 5)).toHaveLength(2);
    renderer.resize(900, 1); // لا تغيّر فلا إبطال
    await renderer.page(5);
    expect(renders.filter((n) => n === 5)).toHaveLength(2);
  });

  it("فشل الرسم يُرفض ولا يعلق في الانتظار فتنجح إعادة الطلب", async () => {
    const { doc, raw } = fakeDoc();
    raw.getPage.mockRejectedValueOnce(new Error("x"));
    const renderer = new PageRenderer(doc, 600, 1);
    await expect(renderer.page(2)).rejects.toThrow("x");
    await expect(renderer.page(2)).resolves.toBeInstanceOf(HTMLCanvasElement);
  });

  it("الإتلاف يغلق الملف", () => {
    const { doc, raw } = fakeDoc();
    new PageRenderer(doc, 600, 1).destroy();
    expect(raw.loadingTask.destroy).toHaveBeenCalled();
  });
});
