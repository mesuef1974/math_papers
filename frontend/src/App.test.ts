import { readFileSync } from "node:fs";
import { join } from "node:path";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it, vi } from "vitest";
import { GENERATE_PERMISSION, useAuthStore } from "@/stores/auth";

vi.mock("vue-router", () => ({
  useRoute: () => ({ meta: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: vi.fn().mockResolvedValue({}) } };
});

const App = (await import("./App.vue")).default;
const css = readFileSync(join(process.cwd(), "src", "styles", "layout.css"), "utf-8");

describe("الشريط السفلي", () => {
  it("يعرض كل روابط المعلم", () => {
    setActivePinia(createPinia());
    const auth = useAuthStore();
    auth.checked = true;
    auth.user = { id: 1, username: "t", permissions: [GENERATE_PERMISSION] } as unknown as typeof auth.user;
    const wrapper = mount(App, {
      global: {
        stubs: {
          RouterLink: { props: ["to"], template: '<a :href="to"><slot /></a>' },
          RouterView: true,
          ThemeToggle: true,
        },
      },
    });
    expect(wrapper.findAll(".tabbar a").map((a) => a.attributes("href"))).toEqual([
      "/",
      "/saved",
      "/preps",
      "/decks",
      "/misconceptions",
      "/copilot",
      "/about",
    ]);
  });

  // jsdom لا يحسب التخطيط: نحرس قواعد النمط التي تمنع القصّ على 375
  it("لا يقصّ تبويبًا: يلتفّ ويتقاسم العرض", () => {
    const rule = (selector: string) => css.match(new RegExp(`\\n  \\${selector} \\{([^}]*)\\}`))?.[1] ?? "";
    expect(rule(".tabbar")).toContain("flex-wrap: wrap");
    expect(rule(".tab")).toContain("flex: 1 1 0");
    const minimum = Number(rule(".tab").match(/min-inline-size: ([\d.]+)rem/)?.[1]) * 16;
    expect(minimum * 7).toBeLessThanOrEqual(375);
  });
});
