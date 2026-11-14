import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { PAGE_WIDTH_PX, fitZoom, usePaperFit } from "./usePaperFit";

describe("fitZoom", () => {
  it("صفحة A4 بعرض 210mm عند 96 نقطة للبوصة", () => {
    expect(PAGE_WIDTH_PX).toBeCloseTo(793.7, 1);
  });

  it("لا تصغير حين تتسع الحاوية للصفحة، ولا تكبير فوق الحجم الحقيقي", () => {
    expect(fitZoom(794)).toBe(1);
    expect(fitZoom(1200)).toBe(1);
  });

  it("تصغير بالنسبة حين تضيق الحاوية، مقرَّبًا إلى أسفل فلا تتجاوز الصفحة حاويتها", () => {
    for (const width of [343, 375, 600, 793]) {
      const zoom = fitZoom(width);
      expect(zoom).toBeLessThan(1);
      expect(zoom * PAGE_WIDTH_PX).toBeLessThanOrEqual(width);
      expect(zoom * PAGE_WIDTH_PX).toBeGreaterThan(width - 0.1);
    }
  });

  it("عرض غير معروف (قبل التخطيط) لا يصغّر", () => {
    expect(fitZoom(0)).toBe(1);
    expect(fitZoom(Number.NaN)).toBe(1);
  });
});

describe("usePaperFit", () => {
  afterEach(() => vi.unstubAllGlobals());

  function host(width: () => number) {
    return defineComponent({
      setup() {
        const box = ref<HTMLElement | null>(null);
        usePaperFit(box);
        return { box };
      },
      render() {
        return h("div", {
          class: "box",
          ref: (el) => {
            if (el) Object.defineProperty(el, "clientWidth", { get: width, configurable: true });
            this.box = el as HTMLElement | null;
          },
        });
      },
    });
  }

  it("يضبط نسبة التصغير على الحاوية ويحدّثها عند تغيّر عرضها، ويفكّ المراقبة عند زوالها", async () => {
    const observers: { callback: () => void; disconnected: boolean }[] = [];
    vi.stubGlobal(
      "ResizeObserver",
      class {
        entry: { callback: () => void; disconnected: boolean };
        constructor(callback: () => void) {
          this.entry = { callback, disconnected: false };
          observers.push(this.entry);
        }
        observe() {}
        disconnect() {
          this.entry.disconnected = true;
        }
      },
    );
    let width = 375;
    const wrapper = mount(host(() => width));
    await nextTick();
    const box = wrapper.find(".box").element as HTMLElement;
    expect(box.style.getPropertyValue("--paper-zoom")).toBe(String(fitZoom(375)));

    width = 1000;
    observers.at(-1)?.callback();
    expect(box.style.getPropertyValue("--paper-zoom")).toBe("1");

    wrapper.unmount();
    expect(observers.length).toBeGreaterThan(0);
    expect(observers.every((o) => o.disconnected)).toBe(true);
  });

  it("بلا ResizeObserver يضبط النسبة مرة واحدة ولا يرمي", async () => {
    vi.stubGlobal("ResizeObserver", undefined);
    const wrapper = mount(host(() => 600));
    await nextTick();
    const box = wrapper.find(".box").element as HTMLElement;
    expect(box.style.getPropertyValue("--paper-zoom")).toBe(String(fitZoom(600)));
  });
});
