import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

// حارس الهوية: الألوان تُعرَّف في tokens.css وحدها، وكل متغير مستعمل معرَّف هناك.
const SRC = join(process.cwd(), "src"); // vitest يعمل من مجلد frontend
const STYLES = join(SRC, "styles");

function files(dir: string, ext: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path, ext);
    return path.endsWith(ext) ? [path] : [];
  });
}

const tokens = readFileSync(join(STYLES, "tokens.css"), "utf-8");
const defined = new Set([...tokens.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
const sheets = [...files(SRC, ".vue"), ...files(STYLES, ".css").filter((path) => !path.endsWith("tokens.css"))];
// متغيرات محلية يضبطها العنصر نفسه لا الهوية: --i رقم الجزء في ظهور الرمز (motion.css المولَّد، وله قيمة احتياطية 0)،
// و--ratio نسبة صفحة PDF يضبطها PdfPageView من الملف نفسه
const LOCAL_VARS = new Set(["--i", "--ratio"]);
const RAW_COLOR = /#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(/i;

describe("الهوية البصرية", () => {
  it.each(sheets.filter((path) => !path.endsWith("print.css")))("لا ألوان خام في %s", (path) => {
    const css = readFileSync(path, "utf-8").split("<style")[path.endsWith(".vue") ? 1 : 0] ?? "";
    expect(css.match(RAW_COLOR)).toBeNull();
  });

  it.each(sheets)("كل متغير في %s معرَّف في tokens.css", (path) => {
    const used = [...readFileSync(path, "utf-8").matchAll(/var\((--[a-z0-9-]+)/g)].map((m) => m[1]);
    expect(used.filter((name) => !defined.has(name) && !LOCAL_VARS.has(name))).toEqual([]);
  });
});
