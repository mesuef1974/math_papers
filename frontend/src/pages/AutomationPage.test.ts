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
    const station = wrapper.find('[data-station="build"]');
    expect(station.classes()).toContain("run");
    expect(station.text()).toContain("بطاقة تعمل");
    expect(wrapper.text()).not.toContain("انقطع البث");
    wrapper.unmount();
  });

  it("تحرّك البطاقة حين تنتقل محطتها فقط", async () => {
    vi.useFakeTimers();
    const moved = { ...board, board: { ...board.board, cards: [{ ...board.board.cards[0], at_stage: 2 }] } };
    const get = vi.spyOn(api, "get").mockResolvedValue(board);
    const wrapper = mount(AutomationPage);
    await vi.advanceTimersByTimeAsync(0);
    expect(wrapper.find("[data-token]").exists()).toBe(false);
    get.mockResolvedValue(moved);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(wrapper.find("[data-token]").attributes("data-token")).toBe("20261126-abc123");
    await vi.advanceTimersByTimeAsync(10_000);
    expect(wrapper.find("[data-token]").exists()).toBe(false);
    wrapper.unmount();
    vi.useRealTimers();
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
