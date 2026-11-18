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
  pages?: number; // صفحات PDF الجاهز (0 أو غائب: غير معروف)
}

export interface PdfRequest {
  papers: Paper[];
  profile: PrintProfile;
  date: string;
  section: string;
  show_key: boolean;
  bubble: boolean;
  bundle?: { plan: BundleEntry[]; seed: number } | null; // حزمة كل أوراق العمل: غلاف بفهرس ثم الأوراق
  template?: "awraq" | "school"; // قالب Word: «school» قالب المدرسة للاختبار وورقة العمل والحزمة؛ لا أثر له في PDF
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

/** الملف نفسه معروضًا في عارض المتصفح داخل الصفحة (تبويب «صفحات PDF») بدل تنزيله. */
export function inlineUrl(id: string): string {
  return `${fileUrl(id)}?inline=1`;
}

// الملف يبقى في كاش الخادم عشر دقائق؛ معاينة أقدم من هذا تُطلب من جديد قبل أن يُعرض إطار بملف منتهٍ.
export const PREVIEW_MAX_AGE_MS = 8 * 60 * 1000;

const PREVIEW_TEXT: Record<PdfStatus, string> = {
  idle: "",
  queued: "في انتظار دور المعاينة",
  running: "جارٍ تجهيز صفحات PDF في الخادم",
  done: "",
  error: "",
};

/** بصمة الطلب: المعاينة قديمة حين تختلف بصمتها عن بصمة الورقة المعروضة وإعدادات طباعتها. */
export function requestKey(request: PdfRequest): string {
  return JSON.stringify(request);
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

/** ينشئ المهمة ويستطلعها حتى تنتهي (done أو error)، ويبلّغ كل حالة وسيطة. */
async function runJob(
  request: PdfRequest,
  format: "pdf" | "docx",
  onStatus: (status: "queued" | "running", id: string) => void,
): Promise<PdfJob> {
  let job = await api.post<PdfJob>(`/${format}`, request);
  for (let tick = 0; job.status === "queued" || job.status === "running"; tick += 1) {
    if (tick >= POLL_LIMIT) throw new PollTimeout();
    onStatus(job.status, job.id);
    await sleep(POLL_MS);
    job = await api.get<PdfJob>(`/pdf/${job.id}`);
  }
  return job;
}

export const usePdfStore = defineStore("pdf", {
  state: () => ({
    status: "idle" as PdfStatus,
    error: "",
    jobId: "",
    // معاينة «صفحات PDF»: مهمة مستقلة عن التنزيل، فلا يحجب أحدهما الآخر.
    previewStatus: "idle" as PdfStatus,
    previewError: "",
    previewUrl: "",
    previewPages: 0,
    previewKey: "",
    previewAt: 0,
  }),
  getters: {
    busy: (state) => state.status === "queued" || state.status === "running",
    statusText: (state) => STATUS_TEXT[state.status],
    previewBusy: (state) => state.previewStatus === "queued" || state.previewStatus === "running",
    previewText: (state) => PREVIEW_TEXT[state.previewStatus],
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
        const job = await runJob(request, format, (status, id) => {
          this.status = status;
          this.jobId = id;
        });
        this.jobId = job.id;
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
    /** يطلب ملف PDF الحقيقي للمعاينة؛ عند نجاحه previewUrl رابط العرض داخل الصفحة وpreviewKey بصمة طلبه. */
    async preview(request: PdfRequest) {
      if (this.previewBusy) return;
      this.previewError = "";
      this.previewUrl = "";
      this.previewPages = 0;
      this.previewKey = requestKey(request);
      this.previewStatus = "queued";
      try {
        const job = await runJob(request, "pdf", (status) => {
          this.previewStatus = status;
        });
        if (job.status === "error") {
          this.previewStatus = "error";
          this.previewError = job.error || "تعذر توليد الملف.";
          return;
        }
        this.previewUrl = inlineUrl(job.id);
        this.previewPages = job.pages ?? 0;
        this.previewAt = Date.now();
        this.previewStatus = "done";
      } catch (error) {
        this.previewStatus = "error";
        this.previewError = failureText(error);
      }
    },
    /** هل المعاينة الجاهزة لهذا الطلب نفسه وما زال ملفها في الخادم؟ */
    previewFresh(request: PdfRequest): boolean {
      return (
        this.previewStatus === "done" &&
        this.previewKey === requestKey(request) &&
        Date.now() - this.previewAt < PREVIEW_MAX_AGE_MS
      );
    },
    reset() {
      this.status = "idle";
      this.error = "";
      this.jobId = "";
    },
  },
});
