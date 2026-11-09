import { defineStore } from "pinia";

export type ThemeMode = "auto" | "light" | "dark";
export const THEME_KEY = "math_papers_theme";
const MODES: ThemeMode[] = ["auto", "light", "dark"];

function stored(): ThemeMode {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return MODES.includes(value as ThemeMode) ? (value as ThemeMode) : "auto";
  } catch {
    return "auto"; // التخزين محجوب (نافذة خاصة): تبقى السمة تلقائية بلا خطأ
  }
}

// تفضيل السمة وحده يُحفظ في المتصفح (ليس سرًّا)؛ «تلقائي» يتبع نظام التشغيل بلا data-theme.
export function applyTheme(mode: ThemeMode, root: HTMLElement = document.documentElement): void {
  if (mode === "auto") delete root.dataset.theme;
  else root.dataset.theme = mode;
}

export const useThemeStore = defineStore("theme", {
  state: () => ({ mode: stored() as ThemeMode }),
  actions: {
    init() {
      applyTheme(this.mode);
    },
    set(mode: ThemeMode) {
      this.mode = mode;
      applyTheme(mode);
      try {
        if (mode === "auto") localStorage.removeItem(THEME_KEY);
        else localStorage.setItem(THEME_KEY, mode);
      } catch {
        // التفضيل يسري في هذه الجلسة فقط
      }
    },
    cycle() {
      this.set(MODES[(MODES.indexOf(this.mode) + 1) % MODES.length]);
    },
  },
});
