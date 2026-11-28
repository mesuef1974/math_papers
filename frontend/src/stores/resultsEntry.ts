import { defineStore } from "pinia";
import { api, ApiError } from "@/api/client";
import { accessMessage } from "@/stores/papers";

// إدخال نتائج الطلاب في بنود بطاقات الخروج. البنود (المثال والبذرة والنص) من الخادم وحده، ولا يُعرف الصحيح هنا.
// أسماء الطلاب في الذاكرة فقط: لا تُكتب في localStorage ولا sessionStorage.
export interface EntryItem {
  k: number;
  n: number;
  example: number;
  page?: number | null;
  seed: number;
  stem: string;
  options: string[];
}

export interface SavedChoice {
  example: number;
  seed: number;
  choice: number;
}

export interface SavedStudent {
  enrollment_no: string;
  first_name: string;
  last_name: string;
  results: SavedChoice[];
}

export interface ResultRow {
  enrollment_no: string;
  first_name: string;
  last_name: string;
  example: number;
  seed: number;
  choice: number;
}

export interface SavedSummary {
  students: number;
  results: number;
  created: number;
  updated: number;
}

// رسالة الخادم كما هي حين يرفض الإدخال (422) أو لا يجد الدرس (404)، ورسالة الصلاحية والجلسة من مصدرها المشترك.
function message(error: unknown, fallback: string): string {
  if (
    error instanceof ApiError &&
    (error.status === 422 || error.status === 404) &&
    error.detail
  )
    return error.detail;
  return accessMessage(error) ?? fallback;
}

const lessonPath = (course: string, lesson: string) =>
  `/results/${encodeURIComponent(course)}/${encodeURIComponent(lesson)}`;

// رقم آخر طلب: تبديل الاختيار سريعًا لا يترك ردًّا متأخرًا لاختيار سابق.
let ticket = 0;

export const useResultsEntryStore = defineStore("resultsEntry", {
  state: () => ({
    items: [] as EntryItem[],
    students: [] as SavedStudent[],
    loaded: false,
    loading: false,
    saving: false,
    error: "",
    saved: null as SavedSummary | null,
  }),
  actions: {
    clear() {
      ticket += 1;
      this.items = [];
      this.students = [];
      this.loaded = false;
      this.loading = false;
      this.error = "";
      this.saved = null;
    },
    // بنود الدرس، ومعها طلاب الشعبة واختياراتهم المحفوظة حين تكون الشعبة من شعب المعلم (غيرها يرفضه الخادم بـ 403).
    async load(course: string, lesson: string, section: string, owned: boolean) {
      this.clear();
      const mine = ticket;
      this.loading = true;
      try {
        const base = lessonPath(course, lesson);
        const [items, roster] = await Promise.all([
          api.get<{ items: EntryItem[] }>(`${base}/items`),
          owned
            ? api.get<{ students: SavedStudent[] }>(
                `${base}?${new URLSearchParams({ section })}`,
              )
            : Promise.resolve({ students: [] as SavedStudent[] }),
        ]);
        if (mine !== ticket) return;
        this.items = items.items;
        this.students = roster.students;
        this.loaded = true;
      } catch (error) {
        if (mine === ticket)
          this.error = message(error, "تعذر تحميل بنود الدرس. أعد المحاولة.");
      } finally {
        if (mine === ticket) this.loading = false;
      }
    },
    async save(
      course: string,
      lesson: string,
      section: string,
      results: ResultRow[],
    ): Promise<boolean> {
      this.error = "";
      this.saved = null;
      this.saving = true;
      try {
        this.saved = await api.post<SavedSummary>(lessonPath(course, lesson), {
          section,
          results,
        });
        return true;
      } catch (error) {
        this.error = message(error, "تعذر حفظ النتائج. أعد المحاولة.");
        return false;
      } finally {
        this.saving = false;
      }
    },
  },
});
