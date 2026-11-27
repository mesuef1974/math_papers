import { defineStore } from "pinia";
import { api, API_BASE, ApiError } from "@/api/client";
import { useCoursesStore } from "@/stores/courses";
import { accessMessage } from "@/stores/papers";
import type { PrepPeriod } from "@/stores/preps";

// عروض الحصص: عرض لكل حصة من تحضيرها، والبناء مهمة خلفية في الخادم، والواجهة تطلبه ثم تستطلع حالته حتى يجهز أو يفشل.
export const POLL_MS = 2000;
export const MAX_POLLS = 90; // ثلاث دقائق، وبعدها يُترك الطلب للمعلم يعيده

// حصة الدروس بحالة معايير تحضيرها، و`clips` صادقة حين نُشر مقطع لكل مثال فيها.
export interface DeckPeriod extends PrepPeriod {
  examples: number;
  clips: boolean;
  // آخر عرض طلبته للحصة بُني من تحضير عدّلتَه بعده
  stale: boolean;
}

export function periodQuery(course: string, lesson: string, k: number): URLSearchParams {
  return new URLSearchParams({ course, lesson, k: String(k) });
}

export type DeckStatus = "idle" | "pending" | "ready" | "failed";

interface DeckOut {
  status: "pending" | "ready" | "failed";
  detail: string;
  filename: string;
}

function message(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 422 && error.detail)
    return error.detail;
  return accessMessage(error) ?? fallback;
}

export function downloadUrl(course: string, lesson: string, k: number): string {
  return `${API_BASE}/decks/download?${periodQuery(course, lesson, k)}`;
}

export const useDecksStore = defineStore("decks", {
  state: () => ({
    periods: [] as DeckPeriod[],
    loaded: false,
    loading: false,
    status: "idle" as DeckStatus,
    detail: "",
    error: "",
    course: "",
    lesson: "",
    k: 0,
    timer: null as ReturnType<typeof setTimeout> | null,
    polls: 0,
  }),
  getters: {
    busy: (state) => state.status === "pending",
    url: (state) =>
      state.status === "ready" ? downloadUrl(state.course, state.lesson, state.k) : "",
  },
  actions: {
    async load() {
      this.loading = true;
      this.error = "";
      const course = useCoursesStore().selected;
      try {
        const periods = await api.get<DeckPeriod[]>(
          `/decks/periods?course=${course}`,
        );
        if (course !== useCoursesStore().selected) return; // ردّ متأخر لمقرر تُرك
        this.periods = periods;
        this.loaded = true;
      } catch (error) {
        this.error = message(error, "تعذر تحميل قائمة الحصص.");
      } finally {
        this.loading = false;
      }
    },
    stop() {
      if (this.timer !== null) clearTimeout(this.timer);
      this.timer = null;
    },
    // تغيير المقرر: يقف الاستطلاع ولا تبقى حصص المقرر السابق ولا رابطه.
    reset() {
      this.stop();
      this.$reset();
    },
    // اختيار حصة جديدة يلغي ما قبله، فلا يبقى رابط تنزيل لعرض غير المختار.
    select(lesson: string, k: number) {
      this.stop();
      this.course = useCoursesStore().selected;
      this.lesson = lesson;
      this.k = k;
      this.status = "idle";
      this.detail = "";
      this.error = "";
    },
    async request() {
      this.stop();
      this.error = "";
      this.detail = "";
      this.polls = 0;
      try {
        const out = await api.post<DeckOut>("/decks/", {
          course: this.course,
          lesson: this.lesson,
          k: this.k,
        });
        // الخادم سجّل هذا الطلب آخرَ عرض للحصة، فلم يعد قديمًا
        const period = this.periods.find(
          (p) => p.lesson === this.lesson && p.k === this.k,
        );
        if (period) period.stale = false;
        this.apply(out);
      } catch (error) {
        this.status = "idle";
        this.error = message(error, "تعذر طلب العرض.");
      }
    },
    apply(out: DeckOut) {
      this.status = out.status;
      this.detail = out.detail;
      if (out.status === "pending") this.schedule();
    },
    schedule() {
      this.timer = setTimeout(() => void this.poll(), POLL_MS);
    },
    async poll() {
      this.timer = null;
      this.polls += 1;
      if (this.polls > MAX_POLLS) {
        this.status = "idle";
        this.error = "استغرق البناء أطول من المتوقع. أعد الطلب بعد قليل.";
        return;
      }
      try {
        this.apply(
          await api.get<DeckOut>(
            `/decks/status?${periodQuery(this.course, this.lesson, this.k)}`,
          ),
        );
      } catch (error) {
        this.status = "idle";
        this.error = message(error, "تعذر قراءة حالة العرض.");
      }
    },
  },
});
