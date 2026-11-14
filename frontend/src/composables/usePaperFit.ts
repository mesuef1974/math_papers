import { onBeforeUnmount, watch, type Ref } from "vue";

// الورقة على الشاشة بعرض A4 الحقيقي. حين تضيق حاويتها تُصغَّر كلها بالنسبة (‎--paper-zoom‎ في print.css)
// ولا يُعاد تدفق محتواها، فتبقى الأسطر والفواصل كما تُطبع.
const MM_PER_INCH = 25.4;
const CSS_DPI = 96;
export const PAGE_WIDTH_MM = 210; // يساوي ‎--page-width‎ في tokens.css (يفرضه print.test.ts)
export const PAGE_WIDTH_PX = (PAGE_WIDTH_MM * CSS_DPI) / MM_PER_INCH;

/** نسبة تصغير تُدخل صفحة A4 في العرض المتاح؛ لا تكبير فوق الحجم الحقيقي. */
export function fitZoom(available: number): number {
  if (!(available > 0)) return 1;
  return Math.min(1, Math.floor((available / PAGE_WIDTH_PX) * 10000) / 10000);
}

/** يضبط ‎--paper-zoom‎ على الحاوية ويحدّثه كلما تغيّر عرضها. */
export function usePaperFit(container: Ref<HTMLElement | null>): void {
  let observer: ResizeObserver | null = null;

  function apply(element: HTMLElement) {
    element.style.setProperty("--paper-zoom", String(fitZoom(element.clientWidth)));
  }
  function release() {
    observer?.disconnect();
    observer = null;
  }

  watch(
    container,
    (element) => {
      release();
      if (!element) return;
      apply(element);
      if (typeof ResizeObserver === "undefined") return;
      observer = new ResizeObserver(() => apply(element));
      observer.observe(element);
    },
    { immediate: true, flush: "post" },
  );
  onBeforeUnmount(release);
}
