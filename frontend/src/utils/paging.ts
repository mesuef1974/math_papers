// تقسيم ورقة الشاشة إلى صفحات للتقليب. الورقة على الشاشة عمود واحد متصل بعرض A4 وتخطيطها يطابق المطبوع
// (يقيس ذلك الحارس البصري)، فتُقسَّم بنوافذ بارتفاع محتوى الصفحة تبدأ عند حدود العناصر لا في وسطها.
// الحدود تقديرية: فواصل الطباعة الحقيقية (‎break-*‎) في «صفحات PDF».

export interface SheetSpan {
  top: number;
  bottom: number;
  /** رؤوس العناصر التي يجوز أن تبدأ صفحة (أبناء الورقة والأسئلة والأجزاء)، إحداثيات مطلقة في المنصة */
  cuts: number[];
}

const EPSILON = 0.5;

export interface PageWindow {
  start: number;
  end: number;
}

/** نوافذ الصفحات لكل ورقة (بداية ونهاية بإحداثيات المنصة)؛ ما تجاوز ارتفاع الصفحة من عنصر واحد يُقطع عند الارتفاع.
 *  نهاية كل صفحة هي بداية التالية في الورقة نفسها، فلا يتكرر في صفحة ما ظهر في سابقتها. */
export function planPages(sheets: SheetSpan[], height: number): PageWindow[] {
  const windows: PageWindow[] = [];
  if (!(height > 0)) return windows;
  for (const sheet of sheets) {
    const cuts = [...sheet.cuts].sort((a, b) => a - b);
    let start = sheet.top;
    for (;;) {
      if (sheet.bottom - start <= height + EPSILON) {
        windows.push({ start, end: sheet.bottom });
        break;
      }
      const limit = start + height + EPSILON;
      let next = start + height;
      for (const cut of cuts) {
        if (cut > start + EPSILON && cut <= limit) next = cut;
      }
      windows.push({ start, end: next });
      start = next;
    }
  }
  return windows;
}
