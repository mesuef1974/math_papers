import { defineStore } from "pinia";
import { api, ApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

export interface Lesson {
  code: string;
  title: string;
  unit: number;
  examinable: boolean;
  has_generator: boolean;
  levels: Level[];
}

export type Level = "K" | "A" | "R";

// أسماء المستويات كما يراها المعلم؛ الرموز للخادم فقط.
export const LEVEL_NAMES: Record<Level, string> = { K: "سهل", A: "متوسط", R: "مهارات عليا" };

export interface Blueprint {
  slug: string;
  title: string;
  total_marks: number;
  is_forecast: boolean;
}

export interface Graph {
  window: [number, number, number, number];
  label: string;
  curves: number[][][];
  dots: [number, number, boolean][];
  asymptotes: number[];
  lines: number[][][];
}

export type QuestionKind = "mcq" | "essay";

// قيود الخانة كما وُلِّدت؛ تلزم الاستبدال ونموذج B.
export interface Slot {
  kind: QuestionKind;
  level: Level | "";
  needs_graph: boolean;
}

export interface Part {
  label: string;
  lesson: string;
  lesson_title: string;
  marks: number;
  level: Level;
  stem: string;
  options: string[];
  answer: string;
  steps: string[];
  graph: Graph | null;
  option_graphs: Graph[];
  variant: string;
  fingerprint: string;
  slot: Slot;
}

export interface Question {
  number: number;
  kind: QuestionKind;
  marks: number;
  parts: Part[];
}

export interface Paper {
  kind: "exam" | "worksheet";
  generator_version: string;
  blueprint: string;
  lesson_code: string;
  title: string;
  seed: number;
  total_marks: number;
  is_forecast: boolean;
  level_marks: Partial<Record<Level, number>>;
  questions: Question[];
  level: Level | "";
}

export function query(params: Record<string, string | number | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== "") search.set(key, String(value));
  }
  return search.toString();
}

// انتهاء الجلسة يُسقط المستخدم؛ التنقل إلى الدخول يقرره الحارس في App.vue، لا المخزن.
export function accessMessage(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  if (error.status === 401) {
    useAuthStore().expire();
    return "انتهت الجلسة. سجّل الدخول من جديد.";
  }
  if (error.status === 403) return error.detail || "حسابك لا يملك صلاحية توليد الأوراق.";
  if (error.status === 409 || error.status === 429) return error.detail;
  return null;
}

export const usePapersStore = defineStore("papers", {
  state: () => ({
    lessons: [] as Lesson[],
    blueprints: [] as Blueprint[],
    paper: null as Paper | null,
    loading: false,
    optionsLoading: false,
    error: "",
  }),
  getters: {
    worksheetLessons: (state) => state.lessons.filter((lesson) => lesson.has_generator),
  },
  actions: {
    async loadOptions() {
      this.optionsLoading = true;
      try {
        [this.lessons, this.blueprints] = await Promise.all([
          api.get<Lesson[]>("/lessons"),
          api.get<Blueprint[]>("/blueprints"),
        ]);
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل الدروس. أعد تحميل الصفحة.";
      } finally {
        this.optionsLoading = false;
      }
    },
    async fetchPaper(path: string) {
      this.loading = true;
      this.error = "";
      try {
        this.paper = await api.get<Paper>(path);
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر توليد الورقة. تحقق من رقم النموذج وحاول مرة أخرى.";
      } finally {
        this.loading = false;
      }
    },
    generateExam(blueprint: string, seed: number | null) {
      return this.fetchPaper(`/papers/exam?${query({ blueprint, seed })}`);
    },
    generateWorksheet(lesson: string, count: number, seed: number | null, level: Level | "" = "") {
      return this.fetchPaper(`/papers/worksheet?${query({ lesson, count, seed, level })}`);
    },
  },
});
