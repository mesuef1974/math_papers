import { defineStore } from "pinia";
import { api } from "@/api/client";

interface PingOut {
  ok: boolean;
  site: string;
  subtitle: string;
}

// العنوان الأولي من القشرة المحقونة (قبل أول طلب)، ثم يحدّثه الخادم مع العنوان الفرعي للسنة والصف.
export const useAppStore = defineStore("app", {
  state: () => ({
    siteTitle: document.getElementById("app")?.dataset.siteTitle ?? "",
    subtitle: "",
  }),
  actions: {
    async loadPing() {
      try {
        const data = await api.get<PingOut>("/ping");
        if (data.site) this.siteTitle = data.site;
        this.subtitle = data.subtitle;
      } catch {
        // الشريط يعمل بالعنوان المحقون؛ تعذر الاتصال يظهر عند أول فعل للمستخدم
      }
    },
  },
});
