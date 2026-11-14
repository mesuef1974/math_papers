import { readFileSync } from "node:fs";
import { join } from "node:path";

// الورق يتبع الهوية: print.css يثبّت متغيرات الألوان على قيم الوضع النهاري في tokens.css،
// فلا يعود الورق أبيض وأسود ولا يتسرب إليه الوضع الداكن.
const STYLES = join(process.cwd(), "src", "styles"); // vitest يعمل من مجلد frontend
const print = readFileSync(join(STYLES, "print.css"), "utf-8");
const tokens = readFileSync(join(STYLES, "tokens.css"), "utf-8");

function vars(block: string): Map<string, string> {
  return new Map([...block.matchAll(/(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim().toLowerCase()]));
}

const light = vars(tokens.slice(tokens.indexOf(":root"), tokens.indexOf("}", tokens.indexOf(":root"))));
const paper = vars(print.slice(print.indexOf("@media print")));

describe("ألوان الورق المطبوع", () => {
  it.each([
    "--color-brand",
    "--color-brand-strong",
    "--color-brand-soft",
    "--color-on-brand",
    "--color-accent",
    "--color-mark-ink",
    "--color-mark-accent",
    "--color-level-k",
    "--color-level-a",
    "--color-level-r",
  ])("%s على الورق هو لون الهوية النهاري", (name) => {
    expect(paper.get(name)).toBe(light.get(name));
  });

  it("الورق أبيض ونصه حبر داكن مهما كانت سمة الشاشة", () => {
    expect(paper.get("--color-sheet")).toBe("#ffffff");
    expect(paper.get("--color-ink")).toBe(light.get("--color-ink"));
    // كل لون يعرّفه الوضع الليلي مثبَّت للورق، فلا يتسرب منه شيء
    const dark = vars(tokens.slice(tokens.indexOf("prefers-color-scheme: dark")));
    const missing = [...dark.keys()].filter((name) => !paper.has(name) && name !== "--color-focus");
    expect(missing).toEqual([]);
  });

  it("التذييل الجاري بلون العلامة، والخلفيات الملوّنة تُطبع كما هي", () => {
    expect(print).toContain("border-top: 0.9pt solid #8e2433");
    expect(print).toContain("print-color-adjust: exact");
  });
});

describe("خط الورقة", () => {
  const fonts = readFileSync(join(STYLES, "fonts.css"), "utf-8");
  const stack = /--font-print:\s*([^;]+);/.exec(tokens)?.[1] ?? "";

  it("أول خط للورقة هو الخط المضمَّن، ولا خط خاص بجهاز المعلم قبله", () => {
    expect(stack.startsWith('"Noto Naskh Arabic"')).toBe(true);
    expect(stack).not.toMatch(/Sakkal Majalla/);
    expect(print).toContain("font-family: var(--font-print)");
  });

  it("نصوص الرسوم بخط KaTeX المضمَّن قبل أي خط من الجهاز", () => {
    const math = /--font-math:\s*([^;]+);/.exec(tokens)?.[1] ?? "";
    expect(math.startsWith('"KaTeX_Main"')).toBe(true);
  });

  it("الخط معرَّف بوزنيه من ملفين موجودين ولا يُطبع ببديل قبل تحميله", () => {
    const faces = [...fonts.matchAll(/@font-face\s*\{([^}]+)\}/g)].map((m) => m[1]).filter((b) => b.includes('"Noto Naskh Arabic"'));
    expect(faces.map((b) => /font-weight:\s*(\d+)/.exec(b)?.[1])).toEqual(["400", "700"]);
    for (const block of faces) {
      const file = /url\("\.\.\/([^"]+)"\)/.exec(block)?.[1] ?? "";
      expect(readFileSync(join(STYLES, "..", file)).length).toBeGreaterThan(20000);
      expect(block).toContain("font-display: block");
    }
  });
});
