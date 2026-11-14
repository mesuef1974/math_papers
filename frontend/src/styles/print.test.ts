import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { PAGE_WIDTH_MM } from "@/composables/usePaperFit";

// الورق يتبع الهوية: print.css يثبّت متغيرات الألوان على نطاق الورقة (.sheet) بقيم الوضع النهاري في tokens.css،
// على الشاشة والورق معًا، فلا يعود الورق أبيض وأسود ولا يتسرب إليه الوضع الداكن، وما يُعرض هو ما يُطبع.
const STYLES = join(process.cwd(), "src", "styles"); // vitest يعمل من مجلد frontend
const COMPONENTS = join(STYLES, "..", "components");
const print = readFileSync(join(STYLES, "print.css"), "utf-8");
const tokens = readFileSync(join(STYLES, "tokens.css"), "utf-8");

// كتلة قاعدة يبدأ محدِّدها في أول السطر (القواعد داخل كتلة الطباعة مزاحة فلا تطابق).
function rule(css: string, selector: string): string {
  const start = css.indexOf(`\n${selector} {`);
  if (start < 0) throw new Error(`لا قاعدة ${selector}`);
  return css.slice(start, css.indexOf("\n}", start));
}
const sheet = rule(print, ".sheet");
const printMedia = print.slice(print.indexOf("\n@media print {"));

function vars(block: string): Map<string, string> {
  return new Map([...block.matchAll(/(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim().toLowerCase()]));
}

const light = vars(tokens.slice(tokens.indexOf(":root"), tokens.indexOf("}", tokens.indexOf(":root"))));
const paper = vars(sheet);

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

  it("اللوحة على نطاق الورقة وحده، غير مشروطة بالطباعة ولا مكررة على الجذر", () => {
    expect(print.indexOf("\n.sheet {")).toBeLessThan(print.indexOf("\n@media print {"));
    expect(printMedia).not.toMatch(/--color-[a-z0-9-]+\s*:/);
    expect(printMedia).not.toContain(":root");
    // ما يُعرَّف على الجذر بمتغيرات اللوحة يُعاد تعريفه في النطاق، وإلا ورث قيمة الوضع الداكن محسوبة
    for (const name of ["--border", "--focus-ring", "--color-focus"]) expect(sheet).toContain(`  ${name}: `);
    expect(sheet).toContain("color-scheme: light");
    expect(sheet).toContain("color: var(--color-ink)");
    expect(sheet).toContain("background: var(--color-sheet)");
  });

  it("التذييل الجاري بلون العلامة، والخلفيات الملوّنة تُطبع كما هي", () => {
    expect(print).toContain("border-top: 0.9pt solid #8e2433");
    expect(print).toContain("print-color-adjust: exact");
  });
});

describe("الورقة على الشاشة بقواعد الورق", () => {
  const token = (name: string) => new RegExp(`${name}:\\s*([^;]+);`).exec(tokens)?.[1].trim() ?? "";

  it("مقاس الصفحة وهوامشها في المتغيرات تساوي قاعدة الصفحة", () => {
    const page = print.slice(print.indexOf("@page {"), print.indexOf("@bottom-right"));
    expect(page).toContain("size: A4");
    expect(token("--page-width")).toBe(`${PAGE_WIDTH_MM}mm`);
    expect(token("--page-height")).toBe("297mm");
    const margin = [token("--page-margin-block-start"), token("--page-margin-inline"), token("--page-margin-block-end")];
    expect(/margin:\s*([^;]+);/.exec(page)?.[1]).toBe(margin.join(" "));
  });

  it("الورقة بعرض الصفحة وحشوها هوامشها، وخطها وحجمه وارتفاع سطره كالمطبوع", () => {
    expect(sheet).toContain("inline-size: var(--page-width)");
    expect(sheet).toContain(
      "padding: var(--page-margin-block-start) var(--page-margin-inline) var(--page-margin-block-end)",
    );
    expect(sheet).toContain("zoom: var(--paper-zoom)");
    // الإطار لا يأكل من عرض الصفحة: خط خارجي لا حدّ
    expect(sheet).not.toMatch(/^ {2}border:/m);
    expect(sheet).toContain("font-family: var(--font-print)");
    expect(sheet).toContain("font-size: var(--print-body)");
    expect(sheet).toContain("--leading-body: 1.6");
    expect(sheet).toContain("line-height: var(--leading-body)");
    expect(token("--paper-zoom")).toBe("1");
  });

  it("على الورق بلا إطار ولا حشو ولا تصغير: الصفحة من قاعدة الصفحة", () => {
    const printed = printMedia.slice(printMedia.indexOf("  .sheet {"), printMedia.indexOf("\n  }"));
    for (const declaration of ["inline-size: auto", "padding: 0", "margin: 0", "zoom: 1", "outline: 0", "box-shadow: none"]) {
      expect(printed).toContain(declaration);
    }
  });

  // مكوّنات الورقة لا تعيد تدفقها بعرض الشاشة: التصغير يتولّى الشاشات الضيقة، فيبقى المعروض مطابقًا للمطبوع.
  const paperComponents = readdirSync(COMPONENTS).filter(
    (name) => /^(Paper|AnswerKey|AnswerSheet|BookletCover|ScoreTable|GraphPlot|MathText)/.test(name) && name.endsWith(".vue"),
  );
  it.each(paperComponents)("لا استعلام عرض شاشة في %s، ولا إطار ورقة خاص به", (name) => {
    const style = readFileSync(join(COMPONENTS, name), "utf-8").split("<style")[1] ?? "";
    expect(style).not.toMatch(/@media[^{]*(?:width|screen)/);
    expect(style).not.toMatch(/^\.sheet \{[^}]*(?:padding|border|background):/m);
  });

  it("زر الاستبدال خارج مجرى المحتوى في هامش الصفحة، فلا يغيّر ارتفاع الجزء", () => {
    const part = readFileSync(join(COMPONENTS, "PaperPart.vue"), "utf-8").split("<style")[1];
    const tools = part.slice(part.indexOf(".part-tools {"), part.indexOf("}", part.indexOf(".part-tools {")));
    expect(tools).toContain("position: absolute");
    expect(tools).toContain("var(--page-margin-inline)");
    expect(tools).toContain("zoom: calc(1 / var(--paper-zoom))");
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

describe("تبويب صفحات PDF", () => {
  const home = readFileSync(join(STYLES, "..", "pages", "HomePage.vue"), "utf-8");

  it("الورقة خلف التبويب تغيب عن الشاشة وحدها، فتطبعها نافذة طباعة المتصفح", () => {
    const [template, style] = home.split("<style");
    expect(template).toMatch(/class="sheet-focus"\s+:class="\{ 'behind-pdf': view === 'pdf' \}"/);
    expect(template).not.toMatch(/v-if="[^"]*view === 'sheet'/);
    expect(style).toMatch(/@media screen \{\s*\.behind-pdf \{\s*display: none;\s*\}\s*\}/);
    expect(style.replace(/@media screen \{[^}]*\}\s*\}/, "")).not.toContain(".behind-pdf");
  });
});
