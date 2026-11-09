import { createPinia, setActivePinia } from "pinia";
import { THEME_KEY, applyTheme, useThemeStore } from "./theme";

beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("سمة الواجهة", () => {
  it("تبدأ تلقائية بلا data-theme", () => {
    const theme = useThemeStore();
    theme.init();
    expect(theme.mode).toBe("auto");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("الاختيار اليدوي يُطبَّق ويُحفظ، والتلقائي يمسحهما", () => {
    const theme = useThemeStore();
    theme.set("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    theme.set("auto");
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it("يقرأ التفضيل المحفوظ ويتجاهل أي قيمة غريبة", () => {
    localStorage.setItem(THEME_KEY, "light");
    setActivePinia(createPinia());
    expect(useThemeStore().mode).toBe("light");
    localStorage.setItem(THEME_KEY, "<script>");
    setActivePinia(createPinia());
    expect(useThemeStore().mode).toBe("auto");
  });

  it("التبديل الدوري يمرّ بالأوضاع الثلاثة", () => {
    const theme = useThemeStore();
    theme.cycle();
    expect(theme.mode).toBe("light");
    theme.cycle();
    expect(theme.mode).toBe("dark");
    theme.cycle();
    expect(theme.mode).toBe("auto");
  });

  it("applyTheme يعمل على أي عنصر جذر", () => {
    const el = document.createElement("html");
    applyTheme("dark", el);
    expect(el.dataset.theme).toBe("dark");
    applyTheme("auto", el);
    expect(el.dataset.theme).toBeUndefined();
  });
});
