import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import PrintFooter from "@/components/PrintFooter.vue";
import { COPYRIGHT_NAME, COPYRIGHT_PHONE } from "@/utils/brand";

describe("تذييل الورق", () => {
  it("سطر الحقوق: العلامة والاسم ورمز الجوال والرقم، والعنوان الجاري سطر مستقل", () => {
    const wrapper = mount(PrintFooter);
    const copy = wrapper.get(".pf-copy");
    expect(copy.text()).toContain(`©\u00a0${COPYRIGHT_NAME}`);
    expect(copy.text()).toContain(COPYRIGHT_PHONE);
    expect(copy.find("svg.pf-phone").exists()).toBe(true);
    expect(wrapper.find(".pf-title").exists()).toBe(true);
    expect(wrapper.get(".pf-logo").attributes("aria-label")).toBe("أوراق");
  });

  it("ملف الشعار في الواجهة نسخة طبق الأصل من الشعار المقفل المعتمد", () => {
    const brand = readFileSync(resolve(__dirname, "../../../brand/math_papers/math_papers-lockup.svg"), "utf8");
    const copy = readFileSync(resolve(__dirname, "../assets/brand/lockup.svg"), "utf8");
    expect(copy).toBe(brand);
  });
});
