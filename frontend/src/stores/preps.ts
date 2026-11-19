import { defineStore } from "pinia";
import { api, API_BASE } from "@/api/client";
import { accessMessage } from "@/stores/papers";

// تحضير الحصة: حصص الدروس بترتيب الخطة الفصلية، وتحضير الحصة المختارة بمعاييره، وتنزيله في Word بنموذج الوزارة.
export const PREP_COURSE = "g10-s1";

export type CheckStatus = "pass" | "fail" | "pending";

export interface PrepPeriod {
  lesson: string;
  title: string;
  unit: number;
  k: number;
  n: number;
  week: number;
  status: CheckStatus;
}

// مراجعة المعلم لأهداف حصته: المعتمد من ملف الوحدة، ونسخته الشخصية (الشرط والمعيار)، وآخر اقتراح له.
export interface SharedObjective {
  behavior: string;
  condition: string;
  criterion: string;
}

export interface MyObjective {
  condition: string;
  criterion: string;
}

export type SuggestionStatus = "pending" | "accepted" | "rejected" | "applied";

export interface ObjectiveSuggestion {
  status: SuggestionStatus;
  condition: string;
  criterion: string;
  note: string;
  created_at: string;
}

export interface PrepReview {
  reviewed_at: string;
  stale: boolean;
}

export interface PrepObjective {
  example: number | null;
  text: string;
  pending: boolean;
  shared?: SharedObjective | null;
  mine?: MyObjective | null;
  stale?: boolean;
  editable?: boolean;
  suggestion?: ObjectiveSuggestion | null;
  teach_activity: string;
  teach_assessment: string;
  teach_minutes: number;
  check_activity: string;
  check_assessment: string;
  check_minutes: number;
}

export interface PrepStage {
  name: string;
  label: string;
  minutes: number;
  strategy: string;
}

export interface PrepCheck {
  code: string;
  title: string;
  status: CheckStatus;
  kind: "blocking" | "warning" | "manual";
  details: string[];
}

export interface PrepSheet {
  course: string;
  lesson: string;
  lesson_title: string;
  unit: number;
  k: number;
  n: number;
  week: number;
  minutes: number;
  year: string;
  semester: string;
  grade: string;
  day_date: string;
  outcomes: string;
  main_sources: string;
  support_sources: string;
  warmup: string;
  warmup_minutes: number;
  objectives: PrepObjective[];
  closing: string;
  closing_minutes: number;
  homework: string;
  basic: string;
  advanced: string;
  quiz: string;
  stages: PrepStage[];
  checks: PrepCheck[];
  pending: boolean;
  review?: PrepReview | null;
}

export function prepPath(lesson: string, k: number): string {
  return `/preps/${PREP_COURSE}/${encodeURIComponent(lesson)}/${k}`;
}

export const periodKey = (p: { lesson: string; k: number }) => `${p.lesson}/${p.k}`;

export function wordUrl(lesson: string, k: number): string {
  return `${API_BASE}${prepPath(lesson, k)}/word`;
}

export const usePrepsStore = defineStore("preps", {
  state: () => ({
    periods: [] as PrepPeriod[],
    loaded: false,
    loading: false,
    sheet: null as PrepSheet | null,
    opening: false,
    error: "",
  }),
  getters: {
    url: (state) => (state.sheet ? wordUrl(state.sheet.lesson, state.sheet.k) : ""),
  },
  actions: {
    async load() {
      this.loading = true;
      this.error = "";
      try {
        this.periods = await api.get<PrepPeriod[]>(`/preps/${PREP_COURSE}`);
        this.loaded = true;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل حصص الخطة.";
      } finally {
        this.loading = false;
      }
    },
    async open(lesson: string, k: number) {
      this.opening = true;
      this.error = "";
      try {
        this.sheet = await api.get<PrepSheet>(prepPath(lesson, k));
      } catch (error) {
        this.sheet = null;
        this.error = accessMessage(error) ?? "تعذر فتح تحضير الحصة.";
      } finally {
        this.opening = false;
      }
    },
  },
});
