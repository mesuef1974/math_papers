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
  answer_index: number; // موضع الخيار الصحيح، -1 للمقالي
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

export type Form = "A" | "B";
export type PaperKind = "exam" | "worksheet" | "quiz";
// غرض ورقة العمل: العلاجية تحصر المسائل في السهل، والإثرائية في مهارات العليا.
export type Purpose = "" | "remedial" | "enrichment";
export const PURPOSE_NAMES: Record<Purpose, string> = { "": "عادية", remedial: "علاجية (سهل)", enrichment: "إثرائية (مهارات عليا)" };
export const PURPOSE_LEVEL: Record<Exclude<Purpose, "">, Level> = { remedial: "K", enrichment: "R" };
export const QUIZ_MAX_LESSONS = 2;

export interface Paper {
  kind: PaperKind;
  form: Form;
  generator_version: string;
  blueprint: string;
  lesson_code: string;
  title: string;
  seed: number;
  total_marks: number;
  is_forecast: boolean;
  level_marks: Partial<Record<Level, number>>;
  level_counts: Partial<Record<Level, number>>;
  questions: Question[];
  level: Level | "";
}

export interface Replacement {
  question: number;
  label: string;
  seed: number;
  fingerprint: string;
}

// كيف وُلّدت الورقة وما استُبدل فيها: تُحفظ مع اللقطة وهي هوية الورقة المحفوظة.
export interface Recipe {
  kind: PaperKind;
  form: Form;
  blueprint: string;
  lesson_code: string; // للاختبار القصير «1.1,1.2»
  count: number;
  level: Level | "";
  purpose: Purpose;
  seed: number;
  replacements: Replacement[];
}

export interface BundleEntry {
  lesson: string;
  title: string;
  count: number;
  levels: Partial<Record<Level, number>>;
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
    twin: null as Paper | null, // النموذج ب، يُعاد حتميًا من رقم النموذج
    recipe: null as Recipe | null,
    savedId: null as number | null,
    savedTitle: "",
    replacing: "", // بصمة الجزء الذي يُستبدل الآن
    bundle: null as Paper[] | null,
    bundlePlan: [] as BundleEntry[],
    bundleSeed: 0,
    bundleDone: 0,
    loading: false,
    optionsLoading: false,
    error: "",
  }),
  getters: {
    worksheetLessons: (state) => state.lessons.filter((lesson) => lesson.has_generator),
    // بعد استبدال، رقم النموذج وحده لا يعيد الورقة؛ اللقطة المحفوظة هي المرجع.
    modified: (state) => (state.recipe?.replacements.length ?? 0) > 0,
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
    async fetchPaper(path: string, base: Omit<Recipe, "seed" | "replacements" | "form">, twin = false) {
      this.loading = true;
      this.error = "";
      try {
        // النموذج ب بالتوازي؛ بلا بذرة يُطلب بعد أ ليأخذ بذرته.
        const first = await api.get<Paper>(path);
        this.paper = first;
        this.twin = twin ? await api.get<Paper>(`${path}&${query({ seed: first.seed, form: "B" })}`) : null;
        this.recipe = { ...base, form: "A", seed: first.seed, replacements: [] };
        this.savedId = null;
        this.savedTitle = "";
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر توليد الورقة. تحقق من رقم النموذج وحاول مرة أخرى.";
      } finally {
        this.loading = false;
      }
    },
    generateExam(blueprint: string, seed: number | null, twin = false) {
      return this.fetchPaper(
        `/papers/exam?${query({ blueprint, seed })}`,
        { kind: "exam", blueprint, lesson_code: "", count: 0, level: "", purpose: "" },
        twin,
      );
    },
    generateWorksheet(
      lesson: string,
      count: number,
      seed: number | null,
      level: Level | "" = "",
      twin = false,
      purpose: Purpose = "",
    ) {
      // الغرض يحدد المستوى في الخادم؛ لا يُرسل مستوى معه حتى لا يتعارضا.
      const effectiveLevel = purpose ? "" : level;
      return this.fetchPaper(
        `/papers/worksheet?${query({ lesson, count, seed, level: effectiveLevel, purpose })}`,
        { kind: "worksheet", blueprint: "", lesson_code: lesson, count, level: effectiveLevel, purpose },
        twin,
      );
    },
    // اختبار قصير من 10 لدرس أو درسين؛ البنية ثابتة والخانات تتناوب على الدروس.
    generateQuiz(lessons: string[], seed: number | null, twin = false) {
      const codes = [...new Set(lessons.filter(Boolean))].slice(0, QUIZ_MAX_LESSONS);
      const lesson_code = codes.join(",");
      return this.fetchPaper(
        `/papers/quiz?${query({ lessons: lesson_code, seed })}`,
        { kind: "quiz", blueprint: "", lesson_code, count: 0, level: "", purpose: "" },
        twin,
      );
    },
    // استبدال جزء واحد بآخر من الخانة نفسها، مع تفادي كل بصمات الورقة. يُدوَّن في الوصفة.
    async replacePart(questionNumber: number, label: string) {
      const question = this.paper?.questions.find((q) => q.number === questionNumber);
      const index = question?.parts.findIndex((p) => p.label === label) ?? -1;
      if (!this.paper || !question || !this.recipe || index < 0 || this.replacing) return;
      const old = question.parts[index];
      this.replacing = old.fingerprint;
      this.error = "";
      try {
        const exclude = this.paper.questions.flatMap((q) => q.parts.map((p) => p.fingerprint));
        const { seed, ...part } = await api.post<Part & { seed: number }>("/papers/replace-part", {
          lesson: old.lesson,
          label: old.label,
          marks: old.marks,
          slot: old.slot,
          exclude,
        });
        question.parts.splice(index, 1, part);
        this.recipe.replacements.push({ question: questionNumber, label, seed, fingerprint: part.fingerprint });
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر استبدال المسألة. حاول مرة أخرى.";
      } finally {
        this.replacing = "";
      }
    },
    // فتح ورقة محفوظة: اللقطة كما حُفظت، ووصفتها، ورقمها ليُحدَّث الحفظ لا يُكرَّر.
    openSaved(saved: { id: number; title: string; paper: Paper; recipe: Recipe }) {
      this.bundle = null;
      this.twin = null;
      this.paper = saved.paper;
      this.recipe = saved.recipe;
      this.savedId = saved.id;
      this.savedTitle = saved.title;
      this.error = "";
    },
    // الحزمة: خطة من الخادم ثم ورقة لكل درس بالتوازي (كل واحدة بضع عشرات المللي ثانية ومخزنة في الكاش).
    async generateBundle(blueprint: string, seed: number | null) {
      this.loading = true;
      this.error = "";
      this.bundle = null;
      this.bundleDone = 0;
      try {
        this.bundlePlan = await api.get<BundleEntry[]>(`/papers/bundle-plan?${query({ blueprint })}`);
        this.bundleSeed = seed ?? Math.floor(Math.random() * 2_000_000_000);
        const papers = await Promise.all(
          this.bundlePlan.map(async (entry) => {
            const paper = await api.get<Paper>(
              `/papers/bundle-item?${query({ blueprint, lesson: entry.lesson, seed: this.bundleSeed })}`,
            );
            this.bundleDone += 1;
            return paper;
          }),
        );
        this.bundle = papers;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر توليد الحزمة. حاول مرة أخرى.";
      } finally {
        this.loading = false;
      }
    },
  },
});
