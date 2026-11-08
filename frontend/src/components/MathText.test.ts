import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import MathText from "./MathText.vue";

describe("MathText", () => {
  it("يعرض النص العربي ويحول ما بين علامتي الدولار إلى رياضيات باتجاه LTR", () => {
    const wrapper = mount(MathText, { props: { text: "أوجد $x^2$ الآن" } });
    expect(wrapper.text()).toContain("أوجد");
    expect(wrapper.text()).toContain("الآن");
    const math = wrapper.find("bdi.math");
    expect(math.attributes("dir")).toBe("ltr");
    expect(math.find(".katex").exists()).toBe(true);
  });

  it("لا يفسر الوسوم داخل النص العربي", () => {
    const wrapper = mount(MathText, { props: { text: "<b>نص</b>" } });
    expect(wrapper.find("b").exists()).toBe(false);
  });

  it("يعرض $$ كصيغة معروضة و\\$ كدولار حرفي", () => {
    const wrapper = mount(MathText, { props: { text: "ثمنه \\$3 و $$x$$" } });
    expect(wrapper.text()).toContain("ثمنه $3");
    expect(wrapper.find("bdi.math.display .katex-display").exists()).toBe(true);
  });

  it("الصيغة الخاطئة تُلوَّن بمتغير الخطر لا بلون خام", () => {
    const wrapper = mount(MathText, { props: { text: "$\\frac{$" } });
    expect(wrapper.html()).toContain("var(--color-danger)");
    expect(wrapper.html()).not.toContain("#cc0000");
  });
});
