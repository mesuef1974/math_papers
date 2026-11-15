// رسم صفحات ملف PDF الحقيقي على canvas بدقة الشاشة. عارض المتصفح المضمَّن يُعاد بناؤه مع كل صفحة فيومض
// وجودته بحجم إطاره؛ هنا تُرسم الصفحة مرة بدقة (عرض الحاوية × devicePixelRatio) وتبقى في مخزن قصير،
// فينتقل التقليب بين صفحات جاهزة ويُحمَّل الجاران مسبقًا.
import type { PDFDocumentProxy } from "pdfjs-dist";

type PdfJs = typeof import("pdfjs-dist");

/** أقصى عرض بكسلات للوحة الرسم: فوقه لا ترى العين فرقًا وتتضخم الذاكرة */
export const MAX_BACKING_WIDTH = 3000;
/** صفحات تبقى مرسومة: الحالية وجارتاها */
export const CACHE_SIZE = 3;

let library: Promise<PdfJs> | null = null;

/** تحميل كسول للمكتبة وعاملها من الأصل نفسه (CSP تسمح بـ 'self' وحده)؛ الفشل لا يُحفظ فتنجح إعادة المحاولة. */
export function loadPdfjs(): Promise<PdfJs> {
  library ??= (async () => {
    const [pdfjs, worker] = await Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?url")]);
    pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
    return pdfjs;
  })().catch((error: unknown) => {
    library = null;
    throw error;
  });
  return library;
}

export async function openPdf(url: string): Promise<PDFDocumentProxy> {
  const pdfjs = await loadPdfjs();
  // الإصدار 6 بلا eval فتناسب CSP؛ الملف من الأصل نفسه فتُرسَل معه الجلسة
  return pdfjs.getDocument({ url, withCredentials: true }).promise;
}

/** مقياس الرسم: بكسلات اللوحة = عرض الحاوية × كثافة الشاشة، بسقف MAX_BACKING_WIDTH */
export function renderScale(cssWidth: number, density: number, pageWidth: number): number {
  const target = Math.min(Math.max(cssWidth, 1) * Math.max(density, 1), MAX_BACKING_WIDTH);
  return target / pageWidth;
}

export class PageRenderer {
  private cache = new Map<number, HTMLCanvasElement>();
  private pending = new Map<number, Promise<HTMLCanvasElement>>();
  private generation = 0;

  constructor(
    private doc: PDFDocumentProxy,
    private width: number,
    private density: number,
  ) {}

  /** نسبة عرض الصفحة إلى ارتفاعها (من الصفحة الأولى؛ ملف الخادم كله بمقاس واحد) */
  async ratio(): Promise<number> {
    const page = await this.doc.getPage(1);
    const view = page.getViewport({ scale: 1 });
    return view.width / view.height;
  }

  /** تغيّر العرض أو الكثافة يبطل المرسوم كله؛ ما كان قيد الرسم يُهمَل نتيجته */
  resize(width: number, density: number): void {
    if (width === this.width && density === this.density) return;
    this.width = width;
    this.density = density;
    this.generation += 1;
    this.cache.clear();
    this.pending.clear();
  }

  /** الصفحة مرسومة على لوحة جاهزة للنسخ؛ المتزامن من الطلبات يشترك في رسم واحد */
  page(number: number): Promise<HTMLCanvasElement> {
    const cached = this.cache.get(number);
    if (cached) {
      this.cache.delete(number); // تُجدَّد مكانتها: الأحدث استعمالًا آخر الخريطة
      this.cache.set(number, cached);
      return Promise.resolve(cached);
    }
    const running = this.pending.get(number);
    if (running) return running;
    const generation = this.generation;
    const job = this.draw(number, this.width, this.density).then((canvas) => {
      if (generation === this.generation) {
        this.pending.delete(number);
        this.cache.set(number, canvas);
        this.evict(number);
      }
      return canvas;
    });
    this.pending.set(number, job);
    job.catch(() => {
      if (generation === this.generation) this.pending.delete(number);
    });
    return job;
  }

  /** تحميل مسبق للجارتين دون انتظار ولا إظهار خطأ؛ الفشل يظهر حين تُطلب الصفحة فعلًا */
  prefetch(number: number, pages: number): void {
    for (const next of [number + 1, number - 1]) {
      if (next >= 1 && next <= pages) void this.page(next).catch(() => undefined);
    }
  }

  destroy(): void {
    this.generation += 1;
    this.cache.clear();
    this.pending.clear();
    void this.doc.loadingTask.destroy();
  }

  // المقاس يُلتقط عند بدء الرسم: تغيّر الحاوية أثناءه لا يخلط مقاسين في لوحة واحدة
  private async draw(number: number, width: number, density: number): Promise<HTMLCanvasElement> {
    const page = await this.doc.getPage(number);
    const base = page.getViewport({ scale: 1 });
    const viewport = page.getViewport({ scale: renderScale(width, density, base.width) });
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    await page.render({ canvas, viewport }).promise;
    return canvas;
  }

  private evict(keep: number): void {
    while (this.cache.size > CACHE_SIZE) {
      const oldest = [...this.cache.keys()].find((key) => key !== keep);
      if (oldest === undefined) return;
      this.cache.delete(oldest);
    }
  }
}
