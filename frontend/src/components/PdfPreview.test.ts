import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { PdfRequest } from "@/stores/pdf";

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) } };
});

const { usePdfStore, PREVIEW_MAX_AGE_MS } = await import("@/stores/pdf");
const { default: PdfPreview } = await import("./PdfPreview.vue");
const { default: PdfPageView } = await import("./PdfPageView.vue");

const request: PdfRequest = {
  papers: [],
  profile: {
    school: "",
    teacher_name: "",
    subject: "الرياضيات",
    grade: "",
    exam_minutes: 150,
    exam_instructions: "",
    worksheet_instructions: "",
  },
  date: "08/11/2026",
  section: "12/3",
  show_key: true,
  bubble: false,
};
const done = (id: string) => ({ id, status: "done", error: "", filename: "x.pdf" });

function viewer(enabled: boolean | undefined) {
  Object.defineProperty(navigator, "pdfViewerEnabled", { value: enabled, configurable: true });
}

describe("PdfPreview: صفحات ملف الخادم الحقيقي", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    post.mockReset();
    viewer(true);
  });
  afterEach(() => vi.useRealTimers());

  it("يطلب الملف عند فتح التبويب ويعرضه في إطار من مسار العرض داخل الصفحة", async () => {
    post.mockResolvedValue(done("j1"));
    const wrapper = mount(PdfPreview, { props: { request } });
    await nextTick();
    expect(wrapper.find("[role=status]").text()).toContain("المعاينة");
    await flushPromises();
    expect(post).toHaveBeenCalledWith("/pdf", request);
    const frame = wrapper.find("iframe");
    expect(frame.attributes("src")).toBe("/api/v1/pdf/j1/file?inline=1");
    expect(frame.attributes("title")).toBeTruthy();
    expect(wrapper.find("a.open").attributes("href")).toBe("/api/v1/pdf/j1/file?inline=1");
    expect(wrapper.classes()).toContain("no-print");
  });

  it("تغيّر الورقة أو إعداداتها يعلّم المعاينة قديمة ولا يطلب ملفًا حتى يضغط المعلم التحديث", async () => {
    post.mockResolvedValueOnce(done("j1")).mockResolvedValueOnce(done("j2"));
    const wrapper = mount(PdfPreview, { props: { request } });
    await flushPromises();
    expect(wrapper.text()).not.toContain("تحديث المعاينة");
    const changed = { ...request, show_key: false };
    await wrapper.setProps({ request: changed });
    expect(post).toHaveBeenCalledTimes(1);
    expect(wrapper.find("iframe").attributes("src")).toContain("j1");
    await wrapper.find(".notice button").trigger("click");
    await flushPromises();
    expect(post).toHaveBeenLastCalledWith("/pdf", changed);
    expect(wrapper.find("iframe").attributes("src")).toContain("j2");
    expect(wrapper.text()).not.toContain("تحديث المعاينة");
  });

  it("العودة إلى التبويب لا تعيد الطلب ما دامت المعاينة حديثة، وتعيده بعد انتهاء مهلة الملف", async () => {
    vi.useFakeTimers();
    post.mockResolvedValue(done("j1"));
    mount(PdfPreview, { props: { request } }).unmount();
    await flushPromises();
    mount(PdfPreview, { props: { request } }).unmount();
    expect(post).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(PREVIEW_MAX_AGE_MS);
    mount(PdfPreview, { props: { request } });
    expect(post).toHaveBeenCalledTimes(2);
  });

  it("متصفح لا يعرض PDF داخل الصفحة: رابط فتح الملف بلا إطار", async () => {
    viewer(false);
    post.mockResolvedValue(done("j1"));
    const wrapper = mount(PdfPreview, { props: { request } });
    await flushPromises();
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.text()).toContain("لا يعرض PDF داخل الصفحة");
    expect(wrapper.find("a.open").attributes("target")).toBe("_blank");
  });

  it("الخطأ يظهر برسالته وزر إعادة المحاولة يطلب من جديد", async () => {
    post.mockResolvedValueOnce({ id: "j1", status: "error", error: "تعذر توليد الملف.", filename: "" });
    post.mockResolvedValueOnce(done("j2"));
    const wrapper = mount(PdfPreview, { props: { request } });
    await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("تعذر توليد الملف");
    expect(wrapper.find("iframe").exists()).toBe(false);
    await wrapper.find("[role=alert] button").trigger("click");
    await flushPromises();
    expect(usePdfStore().previewStatus).toBe("done");
    expect(wrapper.find("iframe").attributes("src")).toContain("j2");
  });
});

describe("PdfPreview: تقليب الصفحات", () => {
  const withPages = (id: string, pages: number) => ({ ...done(id), pages });
  // الرسم الفعلي على canvas له اختبار مستقل (PdfPageView.test.ts)؛ هنا يُستبدل بمكوّن مبتور يعرض خصائصه
  const mountStubbed = () => mount(PdfPreview, { props: { request }, global: { stubs: { PdfPageView: true } } });
  const view = (wrapper: ReturnType<typeof mount>) => wrapper.findComponent(PdfPageView);
  const buttons = (wrapper: ReturnType<typeof mount>) => wrapper.findAll(".pager button");

  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    post.mockReset();
    viewer(true);
  });

  async function opened(pages = 3) {
    post.mockResolvedValue(withPages("j1", pages));
    const wrapper = mountStubbed();
    await flushPromises();
    return wrapper;
  }

  it("يعرض الصفحة الأولى وعدد الصفحات من الخادم وأزرار السابقة والتالية", async () => {
    const wrapper = await opened(3);
    expect(wrapper.find(".pager").exists()).toBe(true);
    expect(wrapper.find(".pager").text()).toContain("3");
    expect(view(wrapper).props()).toEqual({ url: "/api/v1/pdf/j1/file?inline=1", page: 1, pages: 3 });
    expect(wrapper.find("iframe").exists()).toBe(false);
    const [prev, next] = buttons(wrapper);
    expect(prev.attributes("disabled")).toBeDefined();
    expect(next.attributes("disabled")).toBeUndefined();
  });

  it("التالية والسابقة تبدّلان رقم الصفحة وحده ويتعطل الزر عند الطرفين دون طلب جديد", async () => {
    const wrapper = await opened(2);
    const [prev, next] = buttons(wrapper);
    const before = view(wrapper).element;
    await next.trigger("click");
    expect(view(wrapper).props("page")).toBe(2);
    expect(view(wrapper).element).toBe(before); // المكوّن نفسه لا يُعاد بناؤه: لا وميض
    expect(next.attributes("disabled")).toBeDefined();
    await prev.trigger("click");
    expect(view(wrapper).props("page")).toBe(1);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("رقم الصفحة المكتوب يُقيَّد بين الأولى والأخيرة", async () => {
    const wrapper = await opened(5);
    const input = wrapper.find(".pager input");
    await input.setValue("4");
    await input.trigger("change");
    expect(view(wrapper).props("page")).toBe(4);
    await input.setValue("99");
    await input.trigger("change");
    expect(view(wrapper).props("page")).toBe(5);
    expect((input.element as HTMLInputElement).value).toBe("5");
    await input.setValue("0");
    await input.trigger("change");
    expect(view(wrapper).props("page")).toBe(1);
  });

  it("لوحة المفاتيح: الأيسر تالية والأيمن سابقة وHome وEnd", async () => {
    const wrapper = await opened(4);
    const section = wrapper.find(".flipper");
    await section.trigger("keydown", { key: "ArrowLeft" });
    expect(view(wrapper).props("page")).toBe(2);
    await section.trigger("keydown", { key: "PageDown" });
    expect(view(wrapper).props("page")).toBe(3);
    await section.trigger("keydown", { key: "ArrowRight" });
    expect(view(wrapper).props("page")).toBe(2);
    await section.trigger("keydown", { key: "End" });
    expect(view(wrapper).props("page")).toBe(4);
    await section.trigger("keydown", { key: "Home" });
    expect(view(wrapper).props("page")).toBe(1);
    await section.trigger("keydown", { key: "a" });
    expect(view(wrapper).props("page")).toBe(1);
  });

  it("تحديث المعاينة يعيد التقليب إلى الصفحة الأولى بعدد الصفحات الجديد", async () => {
    post.mockResolvedValueOnce(withPages("j1", 3)).mockResolvedValueOnce(withPages("j2", 6));
    const wrapper = mountStubbed();
    await flushPromises();
    await buttons(wrapper)[1].trigger("click");
    expect(view(wrapper).props("page")).toBe(2);
    await wrapper.setProps({ request: { ...request, show_key: false } });
    await wrapper.find(".notice button").trigger("click");
    await flushPromises();
    expect(view(wrapper).props()).toEqual({ url: "/api/v1/pdf/j2/file?inline=1", page: 1, pages: 6 });
    expect(wrapper.find(".pager").text()).toContain("6");
  });

  it("عدد الصفحات معروف: التقليب يعمل ولو لم يعلن المتصفح عارض PDF داخليًا (الرسم على canvas)", async () => {
    viewer(false);
    post.mockResolvedValue(withPages("j3", 4));
    const wrapper = mountStubbed();
    await flushPromises();
    expect(wrapper.find(".pager").exists()).toBe(true);
    expect(view(wrapper).exists()).toBe(true);
    expect(wrapper.text()).not.toContain("لا يعرض PDF داخل الصفحة");
  });

  it("بلا عدد صفحات: عارض المتصفح وحده بلا أزرار ولا مكوّن رسم", async () => {
    post.mockResolvedValue({ ...done("j1"), pages: 0 });
    const wrapper = mountStubbed();
    await flushPromises();
    expect(wrapper.find(".pager").exists()).toBe(false);
    expect(view(wrapper).exists()).toBe(false);
    expect(wrapper.find("iframe").attributes("src")).toBe("/api/v1/pdf/j1/file?inline=1");
  });
});
