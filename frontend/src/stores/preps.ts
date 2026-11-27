import { defineStore } from "pinia";
import { api, API_BASE, ApiError } from "@/api/client";
import { useCoursesStore } from "@/stores/courses";
import { accessMessage } from "@/stores/papers";
import type { PaperLink } from "@/utils/paperLink";

// تحضير الحصة: حصص الدروس بترتيب الخطة الفصلية، وتحضير الحصة المختارة بمعاييره، وتنزيله في Word بنموذج الوزارة.
export type CheckStatus = "pass" | "fail" | "pending";

// حصة الدرس أو نوع حصة غير الدرس (مفتاحها في `lesson`، مثل «quiz-u1»)
export type PeriodKind = "lesson" | "orientation" | "quiz" | "review" | "exam" | "project" | "support";

export interface PrepPeriod {
  lesson: string;
  title: string;
  unit: number;
  k: number;
  n: number;
  week: number;
  status: CheckStatus;
  // للمعلم تعديل محفوظ على حصص هذا الدرس
  customized?: boolean;
  kind?: PeriodKind;
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

// تعديل المعلم لحصته (له وحده): توزيع أمثلة الدرس على حصصه، واستراتيجية كل مرحلة، والتمارين المحذوفة.
export interface StrategyOption {
  slug: string;
  title: string;
}

export interface StageEdit {
  name: string;
  current: string;
  chosen: string | null;
  options: StrategyOption[];
}

export interface PrepEdit {
  state: "none" | "active" | "invalid";
  allocation: number[][];
  default_allocation: number[][];
  stages: StageEdit[];
  exercises: number[];
  removed: number[];
  example_pages?: Record<number, number>;
}

export interface PeriodOverride {
  allocation?: number[][];
  strategies: Record<string, string>;
  removed: number[];
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
  // حصة غير الدرس مشتركة بلا تعديل
  edit?: PrepEdit | null;
  kind?: PeriodKind;
  papers?: PaperLink[];
  scope?: string[];
}

export function prepPath(course: string, lesson: string, k: number): string {
  return `/preps/${course}/${encodeURIComponent(lesson)}/${k}`;
}

export const periodKey = (p: { lesson: string; k: number }) =>
  `${p.lesson}/${p.k}`;

export function wordUrl(course: string, lesson: string, k: number): string {
  return `${API_BASE}${prepPath(course, lesson, k)}/word`;
}

export const usePrepsStore = defineStore("preps", {
  state: () => ({
    periods: [] as PrepPeriod[],
    loaded: false,
    loading: false,
    sheet: null as PrepSheet | null,
    opening: false,
    saving: false,
    error: "",
    editError: "",
  }),
  getters: {
    url: (state) =>
      state.sheet ? wordUrl(state.sheet.course, state.sheet.lesson, state.sheet.k) : "",
  },
  actions: {
    async load() {
      this.loading = true;
      this.error = "";
      const course = useCoursesStore().selected;
      try {
        const periods = await api.get<PrepPeriod[]>(`/preps/${course}`);
        if (course !== useCoursesStore().selected) return; // ردّ متأخر لمقرر تُرك
        this.periods = periods;
        this.loaded = true;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل حصص الخطة.";
      } finally {
        this.loading = false;
      }
    },
    // يحفظ تعديل الحصة المفتوحة (أو يسترجع التحضير المشترك للدرس) ويعرض ورقتها بعده؛ الرفض 422 برسالته العربية.
    async saveOverride(change: PeriodOverride | null): Promise<boolean> {
      const sheet = this.sheet;
      if (!sheet) return false;
      this.saving = true;
      this.editError = "";
      const path = `${prepPath(sheet.course, sheet.lesson, sheet.k)}/override`;
      try {
        this.sheet = change
          ? await api.put<PrepSheet>(path, change)
          : await api.del<PrepSheet>(path);
        await this.load();
        return true;
      } catch (error) {
        this.editError =
          error instanceof ApiError && error.status === 422 && error.detail
            ? error.detail
            : (accessMessage(error) ?? "تعذر حفظ تعديل الحصة.");
        return false;
      } finally {
        this.saving = false;
      }
    },
    // تغيير المقرر: لا تبقى حصص المقرر السابق ولا ورقته.
    reset() {
      this.$reset();
    },
    async open(lesson: string, k: number) {
      this.opening = true;
      this.error = "";
      try {
        const course = useCoursesStore().selected;
        this.sheet = await api.get<PrepSheet>(prepPath(course, lesson, k));
      } catch (error) {
        this.sheet = null;
        this.error = accessMessage(error) ?? "تعذر فتح تحضير الحصة.";
      } finally {
        this.opening = false;
      }
    },
  },
});
