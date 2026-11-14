import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { router } from "@/router";
import { useAuthStore } from "@/stores/auth";
import LandingPage from "./LandingPage.vue";

describe("الصفحة الافتتاحية (screens/landing من دليل الهوية)", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("تعرض العنوان وزرَّي الفعل والبطاقات الثلاث بنص الدليل", async () => {
    await router.push("/welcome");
    const wrapper = mount(LandingPage, { global: { plugins: [router] } });
    expect(wrapper.get("h1").text()).toBe("ورقتك من منهجك، بثلاثة مستويات");
    expect(wrapper.findAll(".landing-card-title").map((el) => el.text())).toEqual(["دقيقة", "هادئة", "واضحة"]);
    const links = wrapper.findAll("a.btn").map((el) => el.attributes("href"));
    expect(links).toEqual(["/login?next=/", "/about"]);
    expect(wrapper.find(".landing-tile svg").exists()).toBe(true);
  });

  it("الزائر الذي يفتح الجذر يصل إلى الافتتاحية، والمسجَّل إلى التوليد", async () => {
    const auth = useAuthStore();
    auth.checked = true;
    auth.user = null;
    await router.push("/");
    expect(router.currentRoute.value.name).toBe("landing");
    auth.user = { id: 1, username: "t", is_staff: false, admin_url: "", permissions: [] };
    await router.push("/");
    expect(router.currentRoute.value.name).toBe("home");
  });
});
