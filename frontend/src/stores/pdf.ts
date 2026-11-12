import { defineStore } from "pinia";
import { API_BASE, ApiError, api } from "@/api/client";
import { accessMessage, type BundleEntry, type Paper } from "@/stores/papers";
import type { PrintProfile } from "@/stores/print";

// PDF من الخادم: Chromium في الخادم يطبع صفحة الطباعة نفسها، فترقيم الصفحات مضمون في كل متصفح.
// الطلب يُنشئ مهمة خلفية، والواجهة تستطلع حالتها ثم تنزّل الملف.
export type PdfStatus = "idle" | "queued" | "running" | "done" | "error";

export interface PdfJob {
  id: string;
  status: Exclude<PdfStatus, "idle">;
  error: string;
  filename: string;
}

export interface PdfRequest {
  papers: Paper[];
  profile: PrintProfile;
  date: string;
  section: string;
  show_key: boolean;
  bubble: boolean;
  bundle?: { plan: BundleEntry[]; seed: number } | null; // حزمة كل أوراق العمل: غلاف بفهرس ثم الأوراق
}

export const POLL_MS = 1000;
export const POLL_LIMIT = 90; // استطلاعات (ثوانٍ) قبل اليأس من مهمة لا تنتهي

const STATUS_TEXT: Record<PdfStatus, string> = {
  idle: "",
  queued: "في انتظار دور الملف",
  running: "جارٍ تجهيز الملف في الخادم",
  done: "جاهز، بدأ التنزيل",
  error: "",
};

export function fileUrl(id: string): string {
  return `${API_BASE}/pdf/${id}/file`;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

class PollTimeout extends Error {}

// رسالة الخادم (503 غير مفعّل، 429 مشغول) أولى من رسالتنا العامة.
function failureText(error: unknown): string {
  if (error instanceof PollTimeout) return "طال انتظار الملف. حاول مرة أخرى أو اطبع من المتصفح.";
  const access = accessMessage(error);
  if (access) return access;
  if (error instanceof ApiError && error.detail) return error.detail;
  return "تعذر طلب الملف من الخادم. اطبع من المتصفح.";
}

export const usePdfStore = defineStore("pdf", {
  state: () => ({
    status: "idle" as PdfStatus,
    error: "",
    jobId: "",
  }),
  getters: {
    busy: (state) => state.status === "queued" || state.status === "running",
    statusText: (state) => STATUS_TEXT[state.status],
  },
  actions: {
    async download(
      request: PdfRequest,
      open: (url: string) => void = (url) => window.location.assign(url),
      format: "pdf" | "docx" = "pdf",
    ) {
      if (this.busy) return;
      this.error = "";
      this.status = "queued";
      try {
        let job = await api.post<PdfJob>(`/${format}`, request);
        this.jobId = job.id;
        for (let tick = 0; job.status === "queued" || job.status === "running"; tick += 1) {
          if (tick >= POLL_LIMIT) throw new PollTimeout();
          this.status = job.status;
          await sleep(POLL_MS);
          job = await api.get<PdfJob>(`/pdf/${job.id}`);
        }
        if (job.status === "error") {
          this.status = "error";
          this.error = job.error || "تعذر توليد الملف.";
          return;
        }
        this.status = "done";
        open(fileUrl(job.id));
      } catch (error) {
        this.status = "error";
        this.error = failureText(error);
      }
    },
    reset() {
      this.status = "idle";
      this.error = "";
      this.jobId = "";
    },
  },
});
