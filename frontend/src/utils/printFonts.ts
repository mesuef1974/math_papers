// خط الورقة يُستعمل في وسيط الطباعة وحده، وخط الرياضيات في نصوص الرسوم قد لا يظهر على الشاشة قبل الطباعة،
// فلا يحمّلهما المتصفح مع عرض الشاشة. نطلبهما صراحةً عند ظهور ورقة، فيكونان جاهزين حين يفتح المعلم نافذة
// الطباعة وحين يطبع Chromium الخادم، ولا يُصفّ النص بخط بديل من الجهاز.
const ARABIC = "أبجد 123";
const LATIN = "xy 123";

export const PRINT_FONT_FACES: readonly (readonly [face: string, sample: string])[] = [
  ['400 13pt "Noto Naskh Arabic"', ARABIC],
  ['700 13pt "Noto Naskh Arabic"', ARABIC],
  ['400 13pt "KaTeX_Main"', LATIN],
  ['700 13pt "KaTeX_Main"', LATIN],
  ['italic 400 13pt "KaTeX_Main"', LATIN],
];

export async function ensurePrintFonts(): Promise<void> {
  const fonts = typeof document === "undefined" ? undefined : document.fonts;
  if (!fonts?.load) return; // بيئة بلا واجهة الخطوط (jsdom)
  await Promise.all(PRINT_FONT_FACES.map(([face, sample]) => fonts.load(face, sample))).catch(() => undefined);
}
