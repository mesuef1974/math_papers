import { defineStore } from "pinia";
import { api, API_BASE, ApiError } from "@/api/client";
import { accessMessage } from "@/stores/papers";

// الحزمة العلاجية لشعبة في درس: البناء مهمة خلفية، والواجهة تطلبه وتستطلع حالته ثم تعرض رابط التنزيل من التطبيق.
// لا أسماء ولا ملف في تخزين المتصفح.
export const POLL_MS = 2000;
export const MAX_POLLS = 150; // خمس دقائق: حد مهمة العامل

export type PackStatus = "idle" | "pending" | "ready" | "failed";

interface PackOut {
  status: PackStatus;
  detail: string;
}

interface Scope {
  course: string;
  lesson: string;
  section: string;
}

function path({ course, lesson }: Scope): string {
  return `/remedial-packs/${encodeURIComponent(course)}/${encodeURIComponent(lesson)}`;
}

const query = ({ section }: Scope) => new URLSearchParams({ section });

// رقم الاختيار الحالي: رد متأخر لاختيار سابق يُهمل.
let ticket = 0;
let timer: ReturnType<typeof setTimeout> | null = null;

function stop() {
  if (timer !== null) clearTimeout(timer);
  timer = null;
}

export const useRemedialStore = defineStore("remedial", {
  state: () => ({
    scope: null as Scope | null,
    status: "idle" as PackStatus,
    detail: "",
    error: "",
    unavailable: "", // سبب تعطيل الزر (503)
    sending: false,
    polls: 0,
  }),
  getters: {
    busy: (state) => state.sending || state.status === "pending",
    url: (state) =>
      state.status === "ready" && state.scope
        ? `${API_BASE}${path(state.scope)}/download?${query(state.scope)}`
        : "",
  },
  actions: {
    reset() {
      ticket += 1;
      stop();
      this.$reset();
    },
    // اختيار شعبة ودرس: تُقرأ الحالة فيظهر البناء الجاري أو تعطّل الخدمة
    async select(course: string, lesson: string, section: string) {
      this.reset();
      this.scope = { course, lesson, section };
      await this.poll();
    },
    async request() {
      const scope = this.scope;
      if (!scope || this.busy || this.unavailable) return;
      const mine = ++ticket;
      stop();
      this.sending = true;
      this.status = "idle";
      this.detail = "";
      this.error = "";
      this.polls = 0;
      try {
        const out = await api.post<PackOut>(path(scope), {
          section: scope.section,
        });
        if (mine === ticket) this.apply(out);
      } catch (error) {
        if (mine === ticket) this.fail(error, "تعذر طلب الأوراق العلاجية.");
      } finally {
        if (mine === ticket) this.sending = false;
      }
    },
    apply(out: PackOut) {
      stop();
      this.status = out.status;
      this.detail = out.detail;
      if (out.status === "pending")
        timer = setTimeout(() => void this.poll(), POLL_MS);
    },
    async poll() {
      const scope = this.scope;
      if (!scope) return;
      const mine = ticket;
      timer = null;
      this.polls += 1;
      if (this.polls > MAX_POLLS) {
        this.status = "idle";
        this.detail = "";
        this.error = "استغرق البناء أطول من المتوقع. أعد الطلب بعد قليل.";
        return;
      }
      try {
        const out = await api.get<PackOut>(`${path(scope)}?${query(scope)}`);
        if (mine === ticket) this.apply(out);
      } catch (error) {
        if (mine === ticket)
          this.fail(error, "تعذر قراءة حالة الأوراق العلاجية.");
      }
    },
    fail(error: unknown, fallback: string) {
      this.status = "idle";
      this.detail = "";
      if (error instanceof ApiError && error.status === 503 && error.detail)
        this.unavailable = error.detail;
      else this.error = accessMessage(error) ?? fallback;
    },
  },
});
