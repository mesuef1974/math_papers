import { defineStore } from "pinia";
import { api } from "@/api/client";
import { accessMessage } from "@/stores/papers";

export interface Course {
  slug: string;
  title: string;
  grade: number;
  track: string;
  semester: number;
  academic_year: string;
  edition: string;
  language: string;
  is_current: boolean;
  lesson_count: number;
  has_generators: boolean;
}

export const COURSE_KEY = "math_papers_course";

// المقرر المختار تفضيل عرض لا سر، فيُحفظ في المتصفح كالسمة؛ التخزين المحجوب لا يمنع الاختيار في الجلسة.
function stored(): string {
  try {
    return localStorage.getItem(COURSE_KEY) ?? "";
  } catch {
    return "";
  }
}

function remember(slug: string): void {
  try {
    localStorage.setItem(COURSE_KEY, slug);
  } catch {
    // يسري الاختيار في هذه الجلسة فقط
  }
}

// الاختيار الافتراضي: المحفوظ إن بقي له مولّدات، ثم المقرر الحالي، ثم أول مقرر له مولّدات.
export function defaultCourse(courses: Course[], remembered: string): string {
  const usable = courses.filter((course) => course.has_generators);
  return (
    usable.find((course) => course.slug === remembered)?.slug ??
    usable.find((course) => course.is_current)?.slug ??
    usable[0]?.slug ??
    ""
  );
}

export const useCoursesStore = defineStore("courses", {
  state: () => ({
    courses: [] as Course[],
    selected: "",
    loading: false,
    error: "",
  }),
  getters: {
    current: (state) => state.courses.find((course) => course.slug === state.selected) ?? null,
  },
  actions: {
    async load() {
      this.loading = true;
      this.error = "";
      try {
        this.courses = await api.get<Course[]>("/courses");
        this.selected = defaultCourse(this.courses, this.selected || stored());
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل المقررات. أعد تحميل الصفحة.";
      } finally {
        this.loading = false;
      }
    },
    // لصفحات تحتاج المقرر قبل أول طلب: يحمّل المقررات إن لزم، ثم يختار `wanted` (من الرابط) إن صح.
    async ensure(wanted = "") {
      if (!this.courses.length) await this.load();
      if (wanted) this.select(wanted);
    },
    select(slug: string) {
      if (!this.courses.some((course) => course.slug === slug && course.has_generators)) return;
      this.selected = slug;
      remember(slug);
    },
  },
});
