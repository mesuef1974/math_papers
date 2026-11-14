// ظهور الرمز عند أول عرض له في الصفحة: الصنف sima-mark-intro من styles/motion.css (مولَّد من سِمة)،
// وعلى كل جزء من أجزاء الرمز المتغير --i لتتابع الظهور. مرة واحدة لكل تحميل، وتُلغيه الحركة المخفَّضة في CSS نفسه.
let played = false;

export function playMarkIntro(svg: Element | null | undefined): void {
  if (!svg || played) return;
  played = true;
  Array.from(svg.children).forEach((part, index) => (part as SVGElement).style.setProperty("--i", String(index)));
  svg.classList.add("sima-mark-intro");
}

/** للاختبارات فقط */
export function resetMarkIntro(): void {
  played = false;
}
