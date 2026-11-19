import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GENERATE_PERMISSION, useAuthStore } from "@/stores/auth";

// حصص الدروس كما يرسلها الخادم: الأولى مقاطعها منشورة، والثانية بلا مقاطع، والثالثة تحضيرها فاشل.
const periods = [
  { lesson: "1.1", title: "الدوال الرئيسة", unit: 1, k: 1, n: 2, week: 1, status: "pass", examples: 2, clips: true },
  { lesson: "1.1", title: "الدوال الرئيسة", unit: 1, k: 2, n: 2, week: 1, status: "pass", examples: 2, clips: false },
  { lesson: "1.2", title: "صيغة الرأس", unit: 1, k: 1, n: 3, week: 2, status: "fail", examples: 3, clips: true },
];

const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: { ...actual.api, get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a) },
  };
});

const DecksPage = (await import("./DecksPage.vue")).default;

describe("DecksPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset().mockResolvedValue(periods);
    post.mockReset();
    useAuthStore().user = { id: 1, username: "t", is_staff: false, admin_url: "", permissions: [GENERATE_PERMISSION] };
  });

  it("يجمع الحصص تحت دروسها ويعطّل ما لا يُبنى عرضه", async () => {
    const wrapper = mount(DecksPage);
    await flushPromises();
    expect(get).toHaveBeenCalledWith("/decks/periods?course=g10-s1");
    const groups = wrapper.findAll("optgroup");
    expect(groups.map((g) => g.attributes("label"))).toEqual(["1.1 — الدوال الرئيسة", "1.2 — صيغة الرأس"]);
    const options = wrapper.findAll("optgroup option");
    expect(options.map((o) => o.attributes("disabled") !== undefined)).toEqual([false, true, true]);
    expect(options[1].text()).toContain("مقاطعها لم تُنشر");
    expect(options[2].text()).toContain("تحضيرها لم يجتز معاييره");
  });

  it("يطلب عرض الحصة المختارة برقمها ويعرض رابط التنزيل", async () => {
    post.mockResolvedValue({ status: "ready", detail: "", filename: "g10-s1-lesson-1.1-k1of2.pptx" });
    const wrapper = mount(DecksPage);
    await flushPromises();
    await wrapper.find("select").setValue("1.1|1");
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(post).toHaveBeenCalledWith("/decks/", { course: "g10-s1", lesson: "1.1", k: 1 });
    expect(wrapper.text()).toContain("الحصة 1 من 2");
    expect(wrapper.find("a[download]").attributes("href")).toBe("/api/v1/decks/download?course=g10-s1&lesson=1.1&k=1");
  });

  it("بلا حصة منشورة المقاطع تظهر الحالة الفارغة", async () => {
    get.mockResolvedValue(periods.map((p) => ({ ...p, clips: false })));
    const wrapper = mount(DecksPage);
    await flushPromises();
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.text()).toContain("لم تُنشر مقاطع أمثلة أي حصة بعد");
  });
});
