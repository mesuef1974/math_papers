import { defineStore } from "pinia";
import { api, ApiError } from "@/api/client";

export interface Me {
  id: number;
  username: string;
  is_staff: boolean;
  admin_url: string;
  permissions: string[];
}

export const GENERATE_PERMISSION = "curriculum.generate_paper";

// الحالة في الذاكرة فقط؛ الجلسة نفسها كوكي HttpOnly لا يقرؤه JavaScript.
export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null as Me | null,
    checked: false,
  }),
  getters: {
    canGenerate: (state) => state.user?.permissions.includes(GENERATE_PERMISSION) ?? false,
  },
  actions: {
    async loadMe() {
      try {
        this.user = await api.get<Me>("/me");
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) throw error;
        this.user = null;
      } finally {
        this.checked = true;
      }
    },
    async login(username: string, password: string) {
      this.user = await api.post<Me>("/auth/login", { username, password });
      this.checked = true;
    },
    async logout() {
      try {
        await api.post<void>("/auth/logout");
      } finally {
        this.user = null;
      }
    },
    expire() {
      this.user = null;
    },
  },
});
