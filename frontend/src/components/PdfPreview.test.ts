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
