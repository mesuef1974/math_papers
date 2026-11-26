import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/api/client";
import AutomationPage from "./AutomationPage.vue";

const board = {
  received_at: new Date().toISOString(),
  board: {
    stages: ["في الطابور", "البرمجة", "الدمج والنشر"],
    cards: [{ id: "20261126-abc123", title: "بطاقة تعمل", group: "running", at_stage: 1, age: "2 د", url: "", note: "" }],
    pulse: { text: "آخر نبض", warn: false },
  },
};

afterEach(() => vi.restoreAllMocks());

describe("صفحة البث الحي", () => {
  it("تعرض البطاقة في مرحلتها بلا تحذير انقطاع", async () => {
    vi.spyOn(api, "get").mockResolvedValue(board);
    const wrapper = mount(AutomationPage);
    await flushPromises();
    expect(wrapper.findAll(".column")[1].text()).toContain("بطاقة تعمل");
    expect(wrapper.text()).not.toContain("انقطع البث");
    wrapper.unmount();
  });

  it("تنبّه حين يقدم عمر اللقطة", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ ...board, received_at: "2020-01-01T00:00:00Z" });
    const wrapper = mount(AutomationPage);
    await flushPromises();
    expect(wrapper.text()).toContain("انقطع البث");
    wrapper.unmount();
  });

  it("ترفض غير المشرف العام", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new ApiError(403, ""));
    const wrapper = mount(AutomationPage);
    await flushPromises();
    expect(wrapper.text()).toContain("للمشرف العام فقط");
    wrapper.unmount();
  });
});
