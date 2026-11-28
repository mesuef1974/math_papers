import { defineStore } from "pinia";
import { api, API_BASE, ApiError } from "@/api/client";
import { accessMessage } from "@/stores/papers";
import { prepPath } from "@/stores/preps";

// باقة الحصة: فهرسها قبل التنزيل، وبناء ملفها مهمة خلفية تُستطلع حالتها ثم يُنزَّل من التطبيق.
export const POLL_MS = 2000;
export const MAX_POLLS = 300; // عشر دقائق: ملف لكل ورقة

export type PackageStatus = "idle" | "pending" | "ready" | "stale" | "failed";

export interface PackageOut {
  status: PackageStatus;
  detail: string;
  sheets: string[];
  notes: string[];
}

// رقم الحصة المختارة: رد متأخر لاختيار سابق يُهمل.
let ticket = 0;
let timer: ReturnType<typeof setTimeout> | null = null;

function stop() {
  if (timer !== null) clearTimeout(timer);
  timer = null;
}

export const useLessonPackageStore = defineStore("lessonPackage", {
  state: () => ({
    path: "",
    status: "idle" as PackageStatus,
    detail: "",
    sheets: [] as string[],
    notes: [] as string[],
    error: "",
    unavailable: "", // سبب تعطيل الزر (503)
    sending: false,
    polls: 0,
  }),
  getters: {
    busy: (state) => state.sending || state.status === "pending",
    url: (state) =>
      state.path && (state.status === "ready" || state.status === "stale")
        ? `${API_BASE}${state.path}/download`
        : "",
  },
  actions: {
    reset() {
      ticket += 1;
      stop();
      this.$reset();
    },
    async select(course: string, lesson: string, k: number) {
      this.reset();
      this.path = `${prepPath(course, lesson, k)}/package`;
      await this.poll();
    },
    async request() {
      if (!this.path || this.busy || this.unavailable) return;
      const mine = ++ticket;
      stop();
      this.sending = true;
      this.status = "idle";
      this.error = "";
      this.polls = 0;
      try {
        const out = await api.post<PackageOut>(this.path, {});
        if (mine === ticket) this.apply(out);
      } catch (error) {
        if (mine === ticket) this.fail(error, "تعذر طلب باقة الحصة.");
      } finally {
        if (mine === ticket) this.sending = false;
      }
    },
    apply(out: PackageOut) {
      stop();
      this.status = out.status;
      this.detail = out.detail;
      this.sheets = out.sheets ?? [];
      this.notes = out.notes ?? [];
      if (out.status === "pending")
        timer = setTimeout(() => void this.poll(), POLL_MS);
    },
    async poll() {
      if (!this.path) return;
      const mine = ticket;
      timer = null;
      this.polls += 1;
      if (this.polls > MAX_POLLS) {
        this.status = "idle";
        this.error = "استغرق البناء أطول من المتوقع. أعد الطلب بعد قليل.";
        return;
      }
      try {
        const out = await api.get<PackageOut>(this.path);
        if (mine === ticket) this.apply(out);
      } catch (error) {
        if (mine === ticket) this.fail(error, "تعذر قراءة حالة باقة الحصة.");
      }
    },
    fail(error: unknown, fallback: string) {
      this.status = "idle";
      if (error instanceof ApiError && error.status === 503 && error.detail)
        this.unavailable = error.detail;
      else this.error = accessMessage(error) ?? fallback;
    },
  },
});
