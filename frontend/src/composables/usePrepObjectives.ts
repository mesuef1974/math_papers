import { ref } from "vue";
import { api, ApiError } from "@/api/client";
import { accessMessage } from "@/stores/papers";
import { prepPath, usePrepsStore, type PrepObjective, type PrepSheet } from "@/stores/preps";

// مراجعة المعلم لأهداف حصته (docs/teacher_objective_review_plan.md): نسخته الشخصية من الشرط والمعيار، واسترجاع المعتمد،
// واقتراح تعديله للنسخة المعتمدة، وعلامة «راجعتُ أهداف الحصة». كل مسار يرجع الورقة كاملة فتُستبدل بها ورقة المخزن.
export const TEXT_MIN = 3;
export const TEXT_MAX = 240;
export const NOTE_MAX = 240;

export interface ObjectiveDraft {
  condition: string;
  criterion: string;
  suggest: boolean;
  note: string;
}

type Busy = number | "review" | null;

function failure(error: unknown, fallback: string): string {
  const message = accessMessage(error);
  if (message) return message;
  if (error instanceof ApiError && error.status === 422 && error.detail) return error.detail;
  return fallback;
}

export function usePrepObjectives() {
  const preps = usePrepsStore();
  const busy = ref<Busy>(null);
  const error = ref("");

  async function run(key: Exclude<Busy, null>, call: (path: string) => Promise<PrepSheet>, fallback: string) {
    const sheet = preps.sheet;
    if (!sheet || busy.value !== null) return false;
    busy.value = key;
    error.value = "";
    try {
      preps.sheet = await call(prepPath(sheet.course, sheet.lesson, sheet.k));
      return true;
    } catch (caught) {
      error.value = failure(caught, fallback);
      return false;
    } finally {
      busy.value = null;
    }
  }

  const save = (example: number, draft: ObjectiveDraft) =>
    run(
      example,
      (path) =>
        api.put<PrepSheet>(`${path}/objectives/${example}`, {
          condition: draft.condition.trim(),
          criterion: draft.criterion.trim(),
          suggest: draft.suggest,
          note: draft.suggest && draft.note.trim() ? draft.note.trim() : null,
        }),
      "تعذر حفظ نسختك من الهدف.",
    );

  const reset = (example: number) =>
    run(example, (path) => api.del<PrepSheet>(`${path}/objectives/${example}`), "تعذر استرجاع النص المعتمد.");

  // إبقاء نسختي بعد تغيّر المعتمد: حفظها من جديد يحدّث بصمة المعتمد فيزول القِدم، بلا اقتراح.
  const keepMine = (objective: PrepObjective) =>
    objective.example !== null && objective.mine
      ? save(objective.example, { ...objective.mine, suggest: false, note: "" })
      : Promise.resolve(false);

  const markReviewed = () =>
    run("review", (path) => api.post<PrepSheet>(`${path}/review`), "تعذر تسجيل مراجعة أهداف الحصة.");

  return { busy, error, save, reset, keepMine, markReviewed };
}
