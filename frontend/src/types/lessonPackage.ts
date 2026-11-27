// حمولة طباعة باقة الحصة (`PackagePrintOut` في papers/api.py).
import type { Graph } from "@/stores/papers";

export interface PackageEntry {
  source: "book" | "generated" | "item";
  example: number | null;
  number: number | null;
  page: number | null;
  dok: number | null;
  stem: string;
  graph: Graph | null;
  options: string[];
  answer: string;
  answer_index: number;
  steps: string[];
}

export interface PackageSheet {
  kind: string;
  title: string;
  per_page: number;
  objectives: [number, string][];
  example_pages?: Record<number, number>;
  entries: PackageEntry[];
}

export interface LessonPackage {
  lesson: string;
  lesson_title: string;
  grade: string;
  k: number;
  sheets: PackageSheet[];
}
