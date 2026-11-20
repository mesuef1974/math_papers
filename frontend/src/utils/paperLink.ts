import type { LocationQuery, RouteLocationRaw } from "vue-router";
import type { Level } from "@/stores/papers";

// ورقة يولّدها «أوراق» لحصة غير درس (`non_lesson.PaperLink` في الخادم)، ورابطها إلى صفحة التوليد بمدخلاتها.
export type PaperMode = "quiz" | "worksheet" | "exam" | "bundle";

export interface PaperLink {
  kind: PaperMode;
  label: string;
  lessons: string[];
  level: string;
  blueprint: string;
}

export interface PaperPrefill {
  course: string;
  mode: PaperMode;
  lesson: string;
  second: string;
  level: Level | "";
  blueprint: string;
}

const MODES: readonly PaperMode[] = ["quiz", "worksheet", "exam", "bundle"];
const LEVELS: readonly string[] = ["K", "A", "R"];

export function paperRoute(course: string, link: PaperLink): RouteLocationRaw {
  const query: Record<string, string> = { course, mode: link.kind };
  if (link.lessons[0]) query.lesson = link.lessons[0];
  if (link.lessons[1]) query.second = link.lessons[1];
  if (link.level) query.level = link.level;
  if (link.blueprint) query.blueprint = link.blueprint;
  return { name: "home", query };
}

const text = (value: unknown) => (typeof value === "string" ? value : "");

// يقرأ الرابط ويرفض ما لا يعرفه: بلا مقرر أو بنوع غير معروف لا ملء.
export function paperPrefill(query: LocationQuery): PaperPrefill | null {
  const course = text(query.course);
  const mode = text(query.mode) as PaperMode;
  if (!course || !MODES.includes(mode)) return null;
  const level = text(query.level);
  return {
    course,
    mode,
    lesson: text(query.lesson),
    second: text(query.second),
    level: LEVELS.includes(level) ? (level as Level) : "",
    blueprint: text(query.blueprint),
  };
}
