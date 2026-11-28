import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/api/client";
import LessonPackagePanel from "./LessonPackagePanel.vue";

const out = (status: string) => ({
  status,
  detail: "",
  sheets: ["ورقة الواجب"],
  notes: ["بطاقة الخروج: لا بنود لها"],
});
const props = { course: "g10-s1", lesson: "1.1", k: 2 };

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => vi.restoreAllMocks());

describe("LessonPackagePanel", () => {
  it("shows the index, builds, then offers the download", async () => {
    vi.spyOn(api, "get").mockResolvedValue(out("idle") as never);
    const post = vi.spyOn(api, "post").mockResolvedValue(out("ready") as never);
    const wrapper = mount(LessonPackagePanel, { props });
    await flushPromises();
    expect(wrapper.find('[data-test="package-sheets"]').text()).toBe("ورقة الواجب");
    expect(wrapper.find("a[download]").exists()).toBe(false);

    await wrapper.find('[data-test="package-build"]').trigger("click");
    await flushPromises();
    expect(post).toHaveBeenCalledWith("/preps/g10-s1/1.1/2/package", {});
    expect(wrapper.find("a[download]").attributes("href")).toContain("/package/download");
  });

  it("disables the button when there is no worker", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new ApiError(503, "غير متاحة الآن"));
    const wrapper = mount(LessonPackagePanel, { props });
    await flushPromises();
    expect(wrapper.find('[data-test="package-build"]').attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("غير متاحة الآن");
  });
});
