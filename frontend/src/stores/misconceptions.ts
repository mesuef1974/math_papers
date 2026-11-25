import { defineStore } from "pinia";
import { api, ApiError } from "@/api/client";
import { accessMessage, type Lesson } from "@/stores/papers";

// لوحة سوء الفهم: لكل نوع خطأ طلاب شعبة المعلم الذين وقعوا فيه في درس. قراءة فقط؛ إدخال النتائج في `resultsEntry.ts`.
export interface BoardStudent {
  enrollment_no: string;
  first_name: string;
  last_name: string;
  examples: number[];
}

export interface BoardKind {
  kind: string;
  label: string;
  count: number;
  examples: number[];
  students: BoardStudent[];
}

export interface Board {
  course: string;
  lesson: string;
  section: string;
  students: number;
  entered: number;
  correct: number;
  missing: number;
  kinds: BoardKind[];
}

function message(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 404 && error.detail)
    return error.detail;
  return accessMessage(error) ?? fallback;
}

// رقم آخر طلب: تبديل الاختيار سريعًا لا يترك ردًّا متأخرًا لاختيار سابق.
let lessonsTicket = 0;
let boardTicket = 0;

export const useMisconceptionsStore = defineStore("misconceptions", {
  state: () => ({
    // آخر مقرر ودرس وشعبة أُدخلت نتائجها: تفتح اللوحة عليها بعد الحفظ (في الذاكرة وحدها، وبلا أي بيان طالب).
    last: null as { course: string; lesson: string; section: string } | null,
    sections: [] as string[],
    sectionsLoaded: false,
    lessons: [] as Lesson[],
    board: null as Board | null,
    loading: false,
    error: "",
  }),
  actions: {
    async loadSections() {
      this.error = "";
      try {
        this.sections = await api.get<string[]>("/results/sections");
        this.sectionsLoaded = true;
      } catch (error) {
        this.error = message(error, "تعذر تحميل شعبك. أعد تحميل الصفحة.");
      }
    },
    async loadLessons(course: string) {
      const ticket = ++lessonsTicket;
      this.lessons = [];
      if (!course) return;
      try {
        const lessons = await api.get<Lesson[]>(
          `/lessons?${new URLSearchParams({ course })}`,
        );
        if (ticket === lessonsTicket) this.lessons = lessons;
      } catch (error) {
        if (ticket === lessonsTicket)
          this.error = message(error, "تعذر تحميل الدروس. أعد تحميل الصفحة.");
      }
    },
    clear() {
      boardTicket += 1;
      this.board = null;
      this.loading = false;
    },
    async load(course: string, lesson: string, section: string) {
      const ticket = ++boardTicket;
      this.board = null;
      this.error = "";
      this.loading = true;
      try {
        const board = await api.get<Board>(
          `/misconceptions/${encodeURIComponent(course)}/${encodeURIComponent(lesson)}?${new URLSearchParams({ section })}`,
        );
        if (ticket === boardTicket) this.board = board;
      } catch (error) {
        if (ticket === boardTicket)
          this.error = message(error, "تعذر تحميل لوحة سوء الفهم.");
      } finally {
        if (ticket === boardTicket) this.loading = false;
      }
    },
  },
});
