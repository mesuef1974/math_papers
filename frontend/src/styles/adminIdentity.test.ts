import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// لوحة الإدارة على الهوية الحالية: قفل الإدارة نسخة من BrandLockup.vue (مولَّد من سِمة) فلا يتخلف عنه عند إصدار جديد،
// والترويسة بسطح الورقة لا شريطًا عنابيًا، وبلا شبكة الدفتر القديمة.
const ROOT = join(process.cwd(), "..");
const lockupTemplate = readFileSync(join(ROOT, "templates", "admin", "_lockup.html"), "utf-8");
const lockupComponent = readFileSync(join(process.cwd(), "src", "components", "BrandLockup.vue"), "utf-8");
const css = readFileSync(join(process.cwd(), "src", "styles", "admin.css"), "utf-8");

const inner = (svg: string) => svg.replace(/^[\s\S]*?<svg[^>]*>/, "").replace(/<\/svg>[\s\S]*$/, "").replace(/\s+/g, " ").trim();

describe("لوحة الإدارة على هوية v8", () => {
  it("قفل الإدارة مطابق لمكوّن BrandLockup رسمًا وإطارًا", () => {
    expect(inner(lockupTemplate)).toBe(inner(lockupComponent.match(/<template>([\s\S]*)<\/template>/)![1]));
    expect(lockupTemplate).toContain('viewBox="0 0 618.75 256"');
  });

  it("الترويسة بسطح الورقة وبلا شبكة الدفتر", () => {
    expect(css).toMatch(/--header-bg:\s*var\(--color-surface\)/);
    expect(css).not.toMatch(/--color-grid|--grid-size|linear-gradient/);
  });
});
