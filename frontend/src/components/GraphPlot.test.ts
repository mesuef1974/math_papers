import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import GraphPlot from "./GraphPlot.vue";

const graph = {
  window: [-5, 5, -4, 4] as [number, number, number, number],
  label: "f",
  curves: [
    [
      [-5, -3],
      [0, 2],
    ],
  ],
  dots: [
    [0, 2, false],
    [0, -1, true],
  ] as [number, number, boolean][],
  asymptotes: [3],
  lines: [],
};

describe("GraphPlot", () => {
  it("يرسم المنحنى والنقاط المفتوحة والمغلقة وخط التقارب", () => {
    const wrapper = mount(GraphPlot, { props: { graph } });
    expect(wrapper.findAll("path.curve")).toHaveLength(1);
    expect(wrapper.findAll("circle.open")).toHaveLength(1);
    expect(wrapper.findAll("circle.closed")).toHaveLength(1);
    expect(wrapper.findAll("line.asymptote")).toHaveLength(1);
    expect(wrapper.find("figure").attributes("dir")).toBe("ltr");
  });

  it("يحوّل الإحداثيات بحيث يكون y للأعلى", () => {
    const wrapper = mount(GraphPlot, { props: { graph } });
    const [open, closed] = wrapper.findAll("circle");
    expect(Number(open.attributes("cy"))).toBeLessThan(Number(closed.attributes("cy")));
    expect(open.attributes("cx")).toBe(closed.attributes("cx"));
  });
});

describe("GraphPlot compact", () => {
  it("يصغّر الرسم ويخفي التسمية في خيارات الرسوم", () => {
    const full = mount(GraphPlot, { props: { graph } });
    const small = mount(GraphPlot, { props: { graph, compact: true } });
    expect(Number(small.find("svg").attributes("width"))).toBeLessThan(Number(full.find("svg").attributes("width")));
    expect(small.find("figcaption").exists()).toBe(false);
  });
});
