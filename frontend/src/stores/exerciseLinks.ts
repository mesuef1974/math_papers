import { defineStore } from "pinia";
import { api, ApiError } from "@/api/client";

export type LinkKind = "try" | "practice";

export interface LinkLesson {
  code: string;
  title: string;
  total: number;
  pending: number;
}

export interface LinkExample {
  number: number;
  page: number | null;
  skill: string;
}

export interface LinkExercise {
  kind: LinkKind;
  number: number;
  page?: number | null;
  examples: number[];
  provenance: string;
  reviewed: boolean;
}

export interface LessonLinks {
  examples: LinkExample[];
  exercises: LinkExercise[];
}

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "هذه الصفحة للمشرف العام فقط.";
    if (error.detail) return error.detail;
  }
  return "تعذّر الاتصال بالخادم. أعد المحاولة.";
}

// مراجعة ربط تمارين الكتاب بأمثلتها: دروس المقرر، ثم تمارين الدرس المختار. كل اعتماد يعيد الدرس من الخادم.
export const useExerciseLinksStore = defineStore("exerciseLinks", {
  state: () => ({
    course: "",
    lesson: "",
    lessons: [] as LinkLesson[],
    links: null as LessonLinks | null,
    busy: false,
    error: "",
  }),
  actions: {
    async run(work: () => Promise<void>): Promise<void> {
      this.busy = true;
      this.error = "";
      try {
        await work();
      } catch (error) {
        this.error = message(error);
      } finally {
        this.busy = false;
      }
    },
    async loadLessons(course: string): Promise<void> {
      this.course = course;
      this.lesson = "";
      this.lessons = [];
      this.links = null;
      if (!course) return;
      await this.run(async () => {
        this.lessons = await api.get<LinkLesson[]>(`/exercise-links/${course}`);
      });
    },
    async open(lesson: string): Promise<void> {
      this.lesson = lesson;
      this.links = null;
      if (!lesson) return;
      await this.run(async () => {
        this.links = await api.get<LessonLinks>(this.path());
      });
    },
    path(): string {
      return `/exercise-links/${this.course}/${this.lesson}`;
    },
    async apply(change: () => Promise<LessonLinks>): Promise<void> {
      await this.run(async () => {
        this.links = await change();
        this.lessons = await api.get<LinkLesson[]>(`/exercise-links/${this.course}`);
      });
    },
    async review(exercise: LinkExercise, examples: number[]): Promise<void> {
      await this.apply(() =>
        api.put<LessonLinks>(`${this.path()}/${exercise.kind}/${exercise.number}`, { examples }),
      );
    },
    async approveLesson(): Promise<void> {
      await this.apply(() => api.post<LessonLinks>(`${this.path()}/approve`));
    },
  },
});
