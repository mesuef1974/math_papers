import { defineStore } from "pinia";
import { api } from "@/api/client";
import { accessMessage, type Paper } from "@/stores/papers";
import { todayLabel } from "@/utils/duration";

// ترويسة المعلم الدائمة (تُحفظ في الخادم) وحقول كل طباعة (التاريخ والشعبة، لا تُحفظ).
export interface PrintProfile {
  school: string;
  teacher_name: string;
  subject: string;
  grade: string;
  exam_minutes: number;
  exam_instructions: string;
  worksheet_instructions: string;
}

export interface PaperHeaderData {
  school: string;
  teacher: string;
  subject: string;
  grade: string;
  title: string;
  minutes: number | null;
  date: string;
  section: string;
  totalMarks: number;
  instructions: string;
  seed: number;
  form?: string; // «أ» أو «ب» عند طباعة نموذجين
}

// الاختبار القصير بزمن ثابت كأوراق الحصة؛ ويأخذ تعليمات الاختبار لا ورقة العمل.
export const QUIZ_MINUTES = 20;

function minutesFor(paper: Paper, profile: PrintProfile): number | null {
  if (paper.kind === "exam") return profile.exam_minutes;
  if (paper.kind === "quiz") return QUIZ_MINUTES;
  return null;
}

const EMPTY: PrintProfile = {
  school: "",
  teacher_name: "",
  subject: "الرياضيات",
  grade: "",
  exam_minutes: 150,
  exam_instructions: "",
  worksheet_instructions: "",
};

export const usePrintStore = defineStore("print", {
  state: () => ({
    profile: { ...EMPTY } as PrintProfile,
    loaded: false,
    saving: false,
    saved: false,
    error: "",
    date: todayLabel(),
    section: "",
    showKey: false,
    bubble: false, // ورقة تظليل للأسئلة الموضوعية
  }),
  getters: {
    header:
      (state) =>
      (paper: Paper): PaperHeaderData => ({
        school: state.profile.school,
        teacher: state.profile.teacher_name,
        subject: state.profile.subject,
        grade: paper.grade || state.profile.grade,
        title: paper.title,
        minutes: minutesFor(paper, state.profile),
        date: state.date,
        section: state.section,
        totalMarks: paper.total_marks,
        instructions: paper.kind === "worksheet" ? state.profile.worksheet_instructions : state.profile.exam_instructions,
        seed: paper.seed,
      }),
  },
  actions: {
    async load() {
      if (this.loaded) return;
      try {
        this.profile = await api.get<PrintProfile>("/print-profile");
        this.loaded = true;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل إعدادات الطباعة.";
      }
    },
    async save() {
      this.saving = true;
      this.saved = false;
      this.error = "";
      try {
        this.profile = await api.put<PrintProfile>("/print-profile", this.profile);
        this.saved = true;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر حفظ الإعدادات. تحقق من الحقول وحاول مرة أخرى.";
      } finally {
        this.saving = false;
      }
    },
  },
});
