import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useCoursesStore } from "@/stores/courses";
import ExerciseLinksPage from "./ExerciseLinksPage.vue";

const lessons = [{ code: "1.1", title: "درس", total: 1, pending: 1 }];
const links = {
  examples: [
    { number: 1, page: 10, skill: "" },
    { number: 2, page: 11, skill: "" },
  ],
  exercises: [{ kind: "practice", number: 8, page: 12, examples: [1], provenance: "ai_unreviewed", reviewed: false }],
};

beforeEach(() => setActivePinia(createPinia()));
afterEach(() => vi.restoreAllMocks());

describe("صفحة ربط التمارين", () => {
  it("تصحّح مثال التمرين وتعتمده", async () => {
    useAuthStore().user = { is_superuser: true } as never;
    const courses = useCoursesStore();
    courses.courses = [{ slug: "c1", title: "مقرر" }] as never;
    vi.spyOn(api, "get").mockImplementation(async (path: string) =>
      (path.endsWith("/1.1") ? links : lessons) as never,
    );
    const put = vi.spyOn(api, "put").mockResolvedValue(links);
    const wrapper = mount(ExerciseLinksPage);
    await flushPromises();
    await wrapper.find('select[name="lesson"]').setValue("1.1");
    await flushPromises();

    const row = wrapper.find('[data-exercise="practice-8"]');
    expect(row.text()).toContain("آلي لم يُراجَع");
    const boxes = row.findAll('input[type="checkbox"]');
    await boxes[0].setValue(false);
    expect(wrapper.find("tbody th").text()).toBe("التمرين 8 (ص 12)");
    await boxes[1].setValue(true);
    await row.find("button").trigger("click");
    await flushPromises();
    expect(put).toHaveBeenCalledWith("/exercise-links/c1/1.1/practice/8", { examples: [2] });
  });

  it("تمنع غير المشرف", () => {
    useAuthStore().user = { is_superuser: false } as never;
    const get = vi.spyOn(api, "get");
    expect(mount(ExerciseLinksPage).text()).toContain("للمشرف العام فقط");
    expect(get).not.toHaveBeenCalled();
  });
});
