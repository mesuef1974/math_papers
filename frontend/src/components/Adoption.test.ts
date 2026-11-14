import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { playMarkIntro, resetMarkIntro } from "@/utils/markIntro";
import SlideFrame from "./SlideFrame.vue";
import SplashScreen from "./SplashScreen.vue";

describe("ظهور الرمز", () => {
  beforeEach(() => {
    resetMarkIntro();
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it("يضيف الصنف ويرقّم الأجزاء مرة واحدة فقط", () => {
    const wrapper = mount(SplashScreen);
    vi.advanceTimersByTime(160);
    const svg = wrapper.find("svg").element;
    expect(svg.classList.contains("sima-mark-intro")).toBe(true);
    const parts = Array.from(svg.children) as SVGElement[];
    expect(parts.map((p) => p.style.getPropertyValue("--i"))).toEqual(parts.map((_, i) => String(i)));
    const other = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    playMarkIntro(other);
    expect(other.classList.contains("sima-mark-intro")).toBe(false);
  });
});

describe("شاشة الافتتاح", () => {
  it("حالة تحميل مقروءة للقارئ الآلي، وتتأخر 150ms في الظهور", async () => {
    vi.useFakeTimers();
    const wrapper = mount(SplashScreen);
    expect(wrapper.classes()).not.toContain("ready");
    vi.advanceTimersByTime(160);
    await wrapper.vm.$nextTick();
    expect(wrapper.classes()).toContain("ready");
    vi.useRealTimers();
    expect(wrapper.attributes("role")).toBe("status");
    expect(wrapper.text()).toContain("جارٍ التحميل");
  });
});

describe("إطار الشرائح", () => {
  it("شريحة العنوان بعنوان وعنوان فرعي وقفل", () => {
    const wrapper = mount(SlideFrame, { props: { layout: "title", title: "مولّد أوراق الرياضيات", subtitle: "من المنهج إلى الورقة" } });
    expect(wrapper.find("h2").text()).toBe("مولّد أوراق الرياضيات");
    expect(wrapper.find(".slide-subtitle").text()).toBe("من المنهج إلى الورقة");
    expect(wrapper.find(".brand-lockup").exists()).toBe(true);
  });

  it("شريحة المحتوى بعرض البنود ورقم الشريحة", () => {
    const wrapper = mount(SlideFrame, {
      props: { title: "عنوان الشريحة", page: 3 },
      slots: { default: "<ul><li>بند أول</li><li>بند ثان</li></ul>" },
    });
    expect(wrapper.findAll("li")).toHaveLength(2);
    expect(wrapper.find(".page-no").text()).toBe("3");
    expect(wrapper.find(".brand-mark").exists()).toBe(true);
  });
});
