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
    expect(print).toContain("border-top: 0.9pt solid #842447");
    expect(print).toContain("print-color-adjust: exact");
  });
});
