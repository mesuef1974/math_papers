import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import PagedSheet from "./PagedSheet.vue";

describe("PagedSheet: الورقة صفحة بصفحة", () => {
  it("مفعَّلًا: بطاقة صفحة وشريط تقليب حول المحتوى", () => {
    const wrapper = mount(PagedSheet, { props: { enabled: true }, slots: { default: '<div class="sheet">ورقة</div>' } });
    expect(wrapper.find(".paged-card").exists()).toBe(true);
    expect(wrapper.find(".paged-card .sheet").text()).toBe("ورقة");
    expect(wrapper.find(".pager").exists()).toBe(true);
  });

  it("معطَّلًا: المحتوى كما هو بلا بطاقة ولا شريط", () => {
    const wrapper = mount(PagedSheet, { props: { enabled: false }, slots: { default: '<div class="sheet">ورقة</div>' } });
    expect(wrapper.find(".paged-card").exists()).toBe(false);
    expect(wrapper.find(".pager").exists()).toBe(false);
    expect(wrapper.find(".sheet").text()).toBe("ورقة");
  });
});
