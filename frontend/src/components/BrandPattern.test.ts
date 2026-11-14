import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import BookletCover from "./BookletCover.vue";
import BrandPattern from "./BrandPattern.vue";
import EmptyState from "./EmptyState.vue";
import SplashScreen from "./SplashScreen.vue";

// النمط من identity/patterns: زخرفة فقط، بمعرّف فريد لكل نسخة، وفي المواضع التي يحددها الدليل (الغلاف والحالة الفارغة والافتتاح).
describe("نمط الهوية", () => {
  it("يرسم همزتين في بلاطة وبمعرّف فريد لكل نسخة، ومخفي عن قارئ الشاشة", () => {
    // useId يرقّم داخل التطبيق الواحد، فتُركَّب النسختان معًا في أب واحد كما في الصفحة الحقيقية
    const both = mount({ components: { BrandPattern }, template: "<div><BrandPattern /><BrandPattern /></div>" });
    const [a, b] = both.findAllComponents(BrandPattern);
    expect(a.findAll("pattern path")).toHaveLength(2);
    expect(a.find("path.accent").exists()).toBe(true);
    expect(a.get("svg").attributes("aria-hidden")).toBe("true");
    expect(a.get("pattern").attributes("id")).not.toBe(b.get("pattern").attributes("id"));
    expect(a.get("rect").attributes("fill")).toBe(`url(#${a.get("pattern").attributes("id")})`);
  });

  it("الحالة الفارغة: الشريط فوق الرسالة لا خلفها", () => {
    const wrapper = mount(EmptyState, { slots: { default: "لا أوراق" } });
    const children = Array.from(wrapper.get(".empty-state").element.children);
    expect(children[0].classList.contains("band")).toBe(true);
    expect(children[1].textContent).toBe("لا أوراق");
    expect(wrapper.get(".band").find("svg").exists()).toBe(true);
  });

  it("شاشة الافتتاح تحمل النمط بعد الرمز، فيبقى أول svg هو الرمز", () => {
    const wrapper = mount(SplashScreen);
    expect(wrapper.find(".splash-pattern svg").exists()).toBe(true);
    expect(wrapper.find("svg").classes()).toContain("brand-mark");
  });

  it("غلاف الكراسة يحمل شريط النمط قبل الشعار", () => {
    const wrapper = mount(BookletCover, {
      props: {
        header: { title: "ت", subject: "الرياضيات", grade: "", form: "", totalMarks: 10, minutes: 0, school: "", teacher: "", date: "", section: "", instructions: "" },
        paper: { questions: [], is_forecast: false },
      } as never,
    });
    const first = wrapper.get(".cover").element.firstElementChild;
    expect(first?.classList.contains("cover-pattern")).toBe(true);
  });
});
