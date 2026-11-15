import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const drawImage = vi.fn();
const pageCalls: number[] = [];
const prefetch = vi.fn();
const destroy = vi.fn();
const resize = vi.fn();
let openFails = false;
let pageGate: Promise<void> | null = null;

class FakeRenderer {
  constructor(
    public doc: unknown,
    public width: number,
    public density: number,
  ) {}
  async ratio() {
    return 0.7;
  }
  async page(n: number) {
    pageCalls.push(n);
    if (n === 2 && pageGate) await pageGate;
    const canvas = document.createElement("canvas");
    canvas.width = 100 + n;
    canvas.height = 140;
    return canvas;
  }
  prefetch = prefetch;
  destroy = destroy;
  resize = resize;
}
vi.mock("@/utils/pdfPages", () => ({
  PageRenderer: FakeRenderer,
  openPdf: vi.fn(async () => {
    if (openFails) throw new Error("x");
    return {};
  }),
}));

const { default: PdfPageView } = await import("./PdfPageView.vue");

function mountView(props = { url: "/a.pdf", page: 1, pages: 3 }) {
  return mount(PdfPageView, { props, attachTo: document.body });
}

describe("PdfPageView: صفحة على canvas بلا وميض", () => {
  beforeEach(() => {
    pageCalls.length = 0;
    drawImage.mockReset();
    prefetch.mockReset();
    destroy.mockReset();
    resize.mockReset();
    openFails = false;
    pageGate = null;
    HTMLCanvasElement.prototype.getContext = (() => ({ drawImage })) as never;
    // jsdom بلا تخطيط: عرض الحاوية 600 ليبدأ الرسم
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { value: 600, configurable: true });
  });

  it("يرسم الصفحة الأولى بنسبة الملف ثم يحمّل الجارتين مسبقًا", async () => {
    const wrapper = mountView();
    expect(wrapper.find("[role=status]").exists()).toBe(true);
    await flushPromises();
    expect(pageCalls).toEqual([1]);
    expect(drawImage).toHaveBeenCalledTimes(1);
    expect(wrapper.find("[role=status]").exists()).toBe(false);
    expect(wrapper.find("canvas").attributes("style") ?? "").not.toContain("display: none");
    expect(wrapper.find(".page-box").attributes("style")).toContain("--ratio: 0.7");
    expect(wrapper.find("canvas").attributes("aria-label")).toBe("الصفحة 1 من 3");
    expect(prefetch).toHaveBeenCalledWith(1, 3);
  });

  it("التقليب يُبقي الصفحة القديمة حتى تجهز الجديدة ثم تُنسخ دفعة واحدة", async () => {
    const wrapper = mountView();
    await flushPromises();
    let open!: () => void;
    pageGate = new Promise<void>((resolve) => (open = resolve));
    await wrapper.setProps({ page: 2 });
    await nextTick();
    // الجديدة لم تجهز: لا رسم جديد ولا اختفاء للوحة ولا رسالة «جارٍ الرسم»
    expect(drawImage).toHaveBeenCalledTimes(1);
    expect(wrapper.find("canvas").attributes("style") ?? "").not.toContain("display: none");
    expect(wrapper.find("[role=status]").exists()).toBe(false);
    expect(wrapper.find(".page-box").attributes("aria-busy")).toBe("true");
    open();
    await flushPromises();
    expect(drawImage).toHaveBeenCalledTimes(2);
    expect(wrapper.find(".page-box").attributes("aria-busy")).toBe("false");
  });

  it("طلب أحدث يُهمل نتيجة أقدم تأخرت", async () => {
    const wrapper = mountView();
    await flushPromises();
    let open!: () => void;
    pageGate = new Promise<void>((resolve) => (open = resolve));
    await wrapper.setProps({ page: 2 });
    await wrapper.setProps({ page: 3 });
    await flushPromises();
    expect(drawImage).toHaveBeenCalledTimes(2); // الأولى والثالثة
    open();
    await flushPromises();
    expect(drawImage).toHaveBeenCalledTimes(2); // الثانية المتأخرة لم تُرسم فوق الثالثة
    expect((wrapper.find("canvas").element as HTMLCanvasElement).width).toBe(103);
  });

  it("ملف جديد يعيد البناء ويُتلف السابق", async () => {
    const wrapper = mountView();
    await flushPromises();
    await wrapper.setProps({ url: "/b.pdf" });
    await flushPromises();
    expect(destroy).toHaveBeenCalledTimes(1);
    expect(pageCalls).toEqual([1, 1]);
  });

  it("الفشل يظهر برسالة وزر إعادة المحاولة ينجح بعد زوال السبب", async () => {
    openFails = true;
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("تعذر عرض الصفحة");
    openFails = false;
    await wrapper.find("[role=alert] button").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
    expect(pageCalls).toEqual([1]);
  });

  it("الإزالة تُتلف الرسّام", async () => {
    const wrapper = mountView();
    await flushPromises();
    wrapper.unmount();
    expect(destroy).toHaveBeenCalled();
  });
});
