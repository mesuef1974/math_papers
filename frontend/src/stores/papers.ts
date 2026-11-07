import { defineStore } from "pinia";
import { api, ApiError } from "@/api/client";
import { router } from "@/router";
import { useAuthStore } from "@/stores/auth";

export interface Lesson {
  code: string;
  title: string;
  unit: number;
  examinable: boolean;
  has_generator: boolean;
}

export interface Blueprint {
  slug: string;
  title: string;
  total_marks: number;
  is_forecast: boolean;
}

export interface Part {
  label: string;
  lesson: string;
  lesson_title: string;
  marks: number;
  level: string;
  stem: string;
  options: string[];
  answer: string;
  steps: string[];
}

export interface Question {
  number: number;
  kind: "mcq" | "essay";
  marks: number;
  parts: Part[];
}

export interface Paper {
  title: string;
  seed: number;
  total_marks: number;
  is_forecast: boolean;
  level_marks: Record<string, number>;
  questions: Question[];
}

function query(params: Record<string, string | number | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== "") search.set(key, String(value));
  }
  return search.toString();
}

// انتهاء الجلسة يعيد إلى الدخول ثم إلى الصفحة نفسها؛ غياب الصلاحية رسالة واضحة.
function accessMessage(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  if (error.status === 401) {
    useAuthStore().expire();
    void router.replace({ name: "login", query: { next: router.currentRoute.value.fullPath } });
    return "انتهت الجلسة. سجّل الدخول من جديد.";
  }
  if (error.status === 403) return error.detail || "حسابك لا يملك صلاحية توليد الأوراق.";
  return null;
}

export const usePapersStore = defineStore("papers", {
  state: () => ({
    lessons: [] as Lesson[],
    blueprints: [] as Blueprint[],
    paper: null as Paper | null,
    loading: false,
    error: "",
  }),
  getters: {
    worksheetLessons: (state) => state.lessons.filter((lesson) => lesson.has_generator),
  },
  actions: {
    async loadOptions() {
      try {
        [this.lessons, this.blueprints] = await Promise.all([
          api.get<Lesson[]>("/api/lessons"),
          api.get<Blueprint[]>("/api/blueprints"),
        ]);
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل الدروس. أعد تحميل الصفحة.";
      }
    },
    async fetchPaper(url: string) {
      this.loading = true;
      this.error = "";
      try {
        this.paper = await api.get<Paper>(url);
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر توليد الورقة. تحقق من رقم النموذج وحاول مرة أخرى.";
      } finally {
        this.loading = false;
      }
    },
    generateExam(blueprint: string, seed: number | null) {
      return this.fetchPaper(`/api/papers/exam?${query({ blueprint, seed })}`);
    },
    generateWorksheet(lesson: string, count: number, seed: number | null) {
      return this.fetchPaper(`/api/papers/worksheet?${query({ lesson, count, seed })}`);
    },
  },
});
