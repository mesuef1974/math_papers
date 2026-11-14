import { readFileSync } from "node:fs";
import { join } from "node:path";

// حارس بيان التبنّي: token_map في brand/math_papers/identity/ADOPTION.yaml (مولَّد من سِمة) هو المرجع،
// وكل متغير فيه بقيمة نهارية أو ليلية يجب أن يطابق tokens.css نفسه. فتغيير لون في أحد الطرفين دون الآخر يُكتشف.
const ROOT = join(process.cwd(), "..");
const adoption = readFileSync(join(ROOT, "brand", "math_papers", "identity", "ADOPTION.yaml"), "utf-8");
const tokens = readFileSync(join(process.cwd(), "src", "styles", "tokens.css"), "utf-8");

interface Row {
  appVar: string;
  light?: string;
  dark?: string;
}

function parseTokenMap(text: string): Row[] {
  const lines = text.split(/\r?\n/);
  const start = lines.findIndex((line) => line.startsWith("token_map:"));
  const end = lines.findIndex((line, i) => i > start && /^[a-z_]+:/.test(line));
  const rows: Row[] = [];
  let mode: "light" | "dark" | null = null;
  for (const line of lines.slice(start + 1, end < 0 ? undefined : end)) {
    const head = line.match(/^- app_var:\s*(--[a-z0-9-]+)/);
    if (head) {
      rows.push({ appVar: head[1] });
      mode = null;
      continue;
    }
    const row = rows[rows.length - 1];
    if (!row) continue;
    if (/^ {2}light:/.test(line)) mode = "light";
    else if (/^ {2}dark:/.test(line)) mode = "dark";
    const value = line.match(/^ {4}value:\s*'?([^'\s]+)'?\s*$/);
    if (value && mode) row[mode] = value[1].toLowerCase();
  }
  return rows;
}

function block(open: string): string {
  const from = tokens.indexOf(open);
  if (from < 0) throw new Error(`لا كتلة ${open}`);
  return tokens.slice(from, tokens.indexOf("}", from));
}
function vars(body: string): Record<string, string> {
  return Object.fromEntries([...body.matchAll(/(--[a-z0-9-]+):\s*([^;]+?);/g)].map((m) => [m[1], m[2].toLowerCase()]));
}
const light = vars(block(":root {"));
const dark = { ...light, ...vars(block(':root:not([data-theme="light"]) {')) };
const rows = parseTokenMap(adoption);

describe("تطابق رموز التطبيق مع ADOPTION.yaml", () => {
  it("يقرأ كل صفوف token_map (32 متغيرًا)", () => {
    expect(rows).toHaveLength(32);
  });

  it.each(rows)("$appVar مطابق نهارًا وليلًا", (row) => {
    if (row.light) expect(light[row.appVar]).toBe(row.light);
    if (row.dark) expect(dark[row.appVar]).toBe(row.dark);
  });

  it("الكتلتان الليليتان في tokens.css متطابقتان", () => {
    expect(vars(block(':root[data-theme="dark"] {'))).toEqual(vars(block(':root:not([data-theme="light"]) {')));
  });

  it("نسخة motion.css في الواجهة مطابقة لنسخة الهوية المولَّدة", () => {
    const a = readFileSync(join(ROOT, "brand", "math_papers", "identity", "motion.css"), "utf-8");
    const b = readFileSync(join(process.cwd(), "src", "styles", "motion.css"), "utf-8");
    expect(b).toBe(a);
  });
});
