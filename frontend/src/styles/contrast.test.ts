import { readFileSync } from "node:fs";
import { join } from "node:path";

// حارس التباين: كل نص على خلفيته 4.5:1 فأكثر (WCAG AA)، وحدود الحقول والتركيز 3:1 فأكثر، في الوضعين.
// يقرأ tokens.css نفسه، فأي لون يُغيَّر يُفحص تلقائيًا ولا تُحفظ الأرقام في مكان ثانٍ.
const css = readFileSync(join(process.cwd(), "src", "styles", "tokens.css"), "utf-8");

function block(open: string): string {
  const start = css.indexOf(open);
  if (start < 0) throw new Error(`لا كتلة ${open}`);
  const end = css.indexOf("}", start);
  return css.slice(start, end);
}
function vars(body: string): Record<string, string> {
  return Object.fromEntries([...body.matchAll(/(--[a-z0-9-]+):\s*(#[0-9a-f]{6})\b/gi)].map((m) => [m[1], m[2].toLowerCase()]));
}
const light = vars(block(":root {"));
const darkAuto = vars(block(':root:not([data-theme="light"]) {'));
const darkManual = vars(block(':root[data-theme="dark"] {'));
const dark = { ...light, ...darkAuto };

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const TEXT: [string, string][] = [
  ["--color-ink", "--color-paper"],
  ["--color-ink", "--color-surface"],
  ["--color-ink", "--color-surface-sunken"],
  ["--color-ink", "--color-sheet"],
  ["--color-ink", "--color-field"],
  ["--color-ink-soft", "--color-paper"],
  ["--color-ink-soft", "--color-surface"],
  ["--color-ink-soft", "--color-surface-sunken"],
  ["--color-ink-soft", "--color-sheet"],
  ["--color-brand", "--color-paper"],
  ["--color-brand", "--color-surface"],
  ["--color-brand", "--color-field"],
  ["--color-brand", "--color-brand-soft"],
  ["--color-brand-strong", "--color-brand-soft"],
  ["--color-ink", "--color-brand-soft"],
  ["--color-on-brand", "--color-brand"],
  ["--color-on-brand", "--color-brand-strong"],
  ["--color-danger", "--color-danger-soft"],
  ["--color-danger", "--color-paper"],
  ["--color-danger", "--color-surface"],
  ["--color-success", "--color-success-soft"],
  ["--color-success", "--color-paper"],
  ["--color-info", "--color-info-soft"],
  ["--color-info", "--color-paper"],
  ["--color-ink", "--color-info-soft"],
  ["--color-level-k", "--color-level-k-soft"],
  ["--color-level-a", "--color-level-a-soft"],
  ["--color-level-r", "--color-level-r-soft"],
  ["--color-sand", "--color-paper"],
  ["--color-sand", "--color-surface"],
  ["--color-sand", "--color-sand-soft"],
  ["--color-ink", "--color-sand-soft"],
];
const NON_TEXT: [string, string][] = [
  ["--color-line-strong", "--color-field"],
  ["--color-line-strong", "--color-surface"],
  ["--color-focus", "--color-paper"],
  ["--color-focus", "--color-surface"],
  ["--color-brand", "--color-paper"],
];

describe.each([
  ["النهاري", light],
  ["الليلي", dark],
])("التباين في الوضع %s", (_name, theme) => {
  it.each(TEXT)("نص %s على %s فوق 4.5:1", (fg, bg) => {
    expect(ratio(theme[fg], theme[bg])).toBeGreaterThanOrEqual(4.5);
  });
  it.each(NON_TEXT)("عنصر %s على %s فوق 3:1", (fg, bg) => {
    expect(ratio(theme[fg], theme[bg])).toBeGreaterThanOrEqual(3);
  });
});

describe("السمة", () => {
  it("كتلتا الوضع الليلي (تلقائي ويدوي) متطابقتان", () => {
    expect(darkManual).toEqual(darkAuto);
    expect(Object.keys(darkAuto).length).toBeGreaterThan(20);
  });
  it("كل متغير لوني نهاري له مقابل ليلي إلا الثابت", () => {
    const fixed = new Set(["--color-mark-accent", "--color-focus-fixed"]);
    const missing = Object.keys(light).filter((name) => !(name in darkAuto) && !fixed.has(name));
    expect(missing).toEqual([]);
  });
});
