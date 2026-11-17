import { defineStore } from "pinia";
import { api, API_BASE, ApiError } from "@/api/client";
import { accessMessage } from "@/stores/papers";

// عروض الدروس: البناء مهمة خلفية في الخادم، والواجهة تطلبه ثم تستطلع حالته حتى يجهز أو يفشل.
export const DECK_COURSE = "g10-s1";
export const DEFAULT_PERIOD = 45;
export const POLL_MS = 2000;
export const MAX_POLLS = 90; // ثلاث دقائق، وبعدها يُترك الطلب للمعلم يعيده

export interface DeckLesson {
  lesson: string;
  title: string;
  examples: number;
  clips: number;
}

export type DeckStatus = "idle" | "pending" | "ready" | "failed";

interface DeckOut {
  status: "pending" | "ready" | "failed";
  detail: string;
  filename: string;
}

function message(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 422 && error.detail) return error.detail;
  return accessMessage(error) ?? fallback;
}

export function downloadUrl(lesson: string, period: number): string {
  const query = new URLSearchParams({ course: DECK_COURSE, lesson, period_minutes: String(period) });
  return `${API_BASE}/decks/download?${query}`;
}

export const useDecksStore = defineStore("decks", {
  state: () => ({
    lessons: [] as DeckLesson[],
    loaded: false,
    loading: false,
    status: "idle" as DeckStatus,
    detail: "",
    error: "",
    lesson: "",
    period: DEFAULT_PERIOD,
    timer: null as ReturnType<typeof setTimeout> | null,
    polls: 0,
  }),
  getters: {
    busy: (state) => state.status === "pending",
    url: (state) => (state.status === "ready" ? downloadUrl(state.lesson, state.period) : ""),
  },
  actions: {
    async load() {
      this.loading = true;
      this.error = "";
      try {
        this.lessons = await api.get<DeckLesson[]>(`/decks/lessons?course=${DECK_COURSE}`);
        this.loaded = true;
      } catch (error) {
        this.error = message(error, "تعذر تحميل قائمة الدروس.");
      } finally {
        this.loading = false;
      }
    },
    stop() {
      if (this.timer !== null) clearTimeout(this.timer);
      this.timer = null;
    },
    // اختيار درس أو زمن جديد يلغي ما قبله، فلا يبقى رابط تنزيل لعرض غير المختار.
    select(lesson: string, period: number) {
      this.stop();
      this.lesson = lesson;
      this.period = period;
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
          course: DECK_COURSE,
          lesson: this.lesson,
          period_minutes: this.period,
        });
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
      const query = new URLSearchParams({
        course: DECK_COURSE,
        lesson: this.lesson,
        period_minutes: String(this.period),
      });
      try {
        this.apply(await api.get<DeckOut>(`/decks/status?${query}`));
      } catch (error) {
        this.status = "idle";
        this.error = message(error, "تعذر قراءة حالة العرض.");
      }
    },
  },
});
