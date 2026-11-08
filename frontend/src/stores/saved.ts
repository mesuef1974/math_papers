import { defineStore } from "pinia";
import { api } from "@/api/client";
import { accessMessage, type Paper, type Recipe } from "@/stores/papers";

// أوراقي: لقطات محفوظة في الخادم مع وصفاتها. القائمة بلا لقطات، والفتح يجلب اللقطة.
export interface SavedSummary {
  id: number;
  title: string;
  kind: "exam" | "worksheet";
  blueprint: string;
  lesson_code: string;
  seed: number;
  total_marks: number;
  question_count: number;
  replacement_count: number;
  generator_version: string;
  created_at: string;
  updated_at: string;
}

export interface SavedPaper extends SavedSummary {
  paper: Paper;
  recipe: Recipe;
}

export interface SavedPatch {
  title?: string;
  paper?: Paper;
  recipe?: Recipe;
}

export const useSavedStore = defineStore("saved", {
  state: () => ({
    items: [] as SavedSummary[],
    loaded: false,
    loading: false,
    saving: false,
    error: "",
  }),
  actions: {
    async load() {
      this.loading = true;
      this.error = "";
      try {
        this.items = await api.get<SavedSummary[]>("/saved");
        this.loaded = true;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحميل أوراقك.";
      } finally {
        this.loading = false;
      }
    },
    async save(title: string, paper: Paper, recipe: Recipe): Promise<SavedPaper | null> {
      this.saving = true;
      this.error = "";
      try {
        const row = await api.post<SavedPaper>("/saved", { title: title.trim(), paper, recipe });
        this.upsert(row);
        return row;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر حفظ الورقة.";
        return null;
      } finally {
        this.saving = false;
      }
    },
    async update(id: number, patch: SavedPatch): Promise<SavedPaper | null> {
      this.saving = true;
      this.error = "";
      try {
        const row = await api.patch<SavedPaper>(`/saved/${id}`, patch);
        this.upsert(row);
        return row;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر تحديث الورقة.";
        return null;
      } finally {
        this.saving = false;
      }
    },
    async open(id: number): Promise<SavedPaper | null> {
      this.error = "";
      try {
        return await api.get<SavedPaper>(`/saved/${id}`);
      } catch (error) {
        this.error = accessMessage(error) ?? "الورقة غير موجودة.";
        return null;
      }
    },
    async remove(id: number): Promise<boolean> {
      this.error = "";
      try {
        await api.del<void>(`/saved/${id}`);
        this.items = this.items.filter((item) => item.id !== id);
        return true;
      } catch (error) {
        this.error = accessMessage(error) ?? "تعذر حذف الورقة.";
        return false;
      }
    },
    upsert(row: SavedPaper) {
      const { paper: _paper, recipe: _recipe, ...summary } = row;
      const index = this.items.findIndex((item) => item.id === row.id);
      if (index >= 0) this.items.splice(index, 1, summary);
      else this.items.unshift(summary);
    },
  },
});
