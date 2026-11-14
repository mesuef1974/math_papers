import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { STAGES } from "@/data/copilotPipeline";

const stubs = { RouterLink: { template: "<a><slot /></a>" } };
const Automation = (await import("./CopilotAutomationPage.vue")).default;
const Flow = (await import("./CopilotFlowPage.vue")).default;

describe("صفحة أتمتة المعاون", () => {
  it("تعرض كل المراحل بمدخلها ومخرجها ومتطلباتها", () => {
    const wrapper = mount(Automation, { global: { stubs } });
    expect(wrapper.findAll("article.stage")).toHaveLength(STAGES.length);
    expect(wrapper.findAll(".col-in")).toHaveLength(STAGES.length);
    expect(wrapper.findAll(".col-out")).toHaveLength(STAGES.length);
    expect(wrapper.findAll(".col-req")).toHaveLength(STAGES.length);
  });

  it("التصفية بالحالة تُبقي المراحل المطابقة وحدها", async () => {
    const wrapper = mount(Automation, { global: { stubs } });
    const run = wrapper.findAll('input[name="status"]').find((i) => (i.element as HTMLInputElement).value === "run");
    await run!.setValue();
    const expected = STAGES.filter((s) => s.status === "run").length;
    expect(wrapper.findAll("article.stage")).toHaveLength(expected);
  });

  it("الشيفرة تُعرض في عنصر code", () => {
    const wrapper = mount(Automation, { global: { stubs } });
    expect(wrapper.find("code").text()).not.toContain("`");
  });
});

describe("صفحة مخطط التدفق الحي", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("تعرض تسع عشرة عقدة قابلة للتركيز ونبضات متحركة", () => {
    const wrapper = mount(Flow, { global: { stubs } });
    const nodes = wrapper.findAll("g.node");
    expect(nodes).toHaveLength(STAGES.length);
    for (const n of nodes) expect(n.attributes("tabindex")).toBe("0");
    expect(wrapper.find("svg.flow").classes()).toContain("live");
    expect(wrapper.findAll("circle.packet").length).toBeGreaterThan(10);
    wrapper.unmount();
  });

  it("الجولة التلقائية تنتقل بين المراحل", async () => {
    const wrapper = mount(Flow, { global: { stubs } });
    const first = wrapper.find(".detail .num").text();
    vi.advanceTimersByTime(2000);
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".detail .num").text()).not.toBe(first);
    wrapper.unmount();
  });

  it("النقر يثبّت المرحلة ويوقف الجولة، والنقرة الثانية تفك التثبيت", async () => {
    const wrapper = mount(Flow, { global: { stubs } });
    const node = wrapper.findAll("g.node")[6];
    await node.trigger("click");
    expect(wrapper.find(".detail .num").text()).toBe("7");
    vi.advanceTimersByTime(6000);
    await wrapper.vm.$nextTick();
    expect(wrapper.find(".detail .num").text()).toBe("7");
    expect(node.attributes("aria-pressed")).toBe("true");
    await node.trigger("click");
    expect(node.attributes("aria-pressed")).toBe("false");
    wrapper.unmount();
  });

  it("زر إيقاف الحركة يزيل النبضات ويبقي التفاصيل", async () => {
    const wrapper = mount(Flow, { global: { stubs } });
    await wrapper.find("button").trigger("click");
    expect(wrapper.find("svg.flow").classes()).not.toContain("live");
    expect(wrapper.findAll("circle.packet")).toHaveLength(0);
    expect(wrapper.find(".detail h2").text()).not.toBe("");
    wrapper.unmount();
  });
});
