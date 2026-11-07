import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

// Lazy loading لكل صفحة (قاعدة الواجهة). الصفحات غير العامة تحتاج جلسة.
export const router = createRouter({
  history: createWebHistory("/"),
  routes: [
    { path: "/", name: "home", component: () => import("@/pages/HomePage.vue") },
    { path: "/about", name: "about", component: () => import("@/pages/AboutPage.vue"), meta: { public: true } },
    { path: "/login", name: "login", component: () => import("@/pages/LoginPage.vue"), meta: { public: true } },
  ],
});

// يقبل مسارًا داخليًا فقط، فلا يصبح next وسيلة لإعادة توجيه مفتوحة.
export function safeNext(value: unknown): string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.checked) await auth.loadMe().catch(() => undefined);
  // من له جلسة لا يرى بطاقة الدخول: يعود إلى وجهته أو الرئيسية.
  if (to.name === "login" && auth.user) return safeNext(to.query.next);
  if (to.meta.public) return true;
  if (!auth.user) return { name: "login", query: { next: to.fullPath } };
  return true;
});
