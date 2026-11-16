import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

// Lazy loading لكل صفحة (قاعدة الواجهة). الصفحات غير العامة تحتاج جلسة.
export const router = createRouter({
  history: createWebHistory("/"),
  routes: [
    { path: "/", name: "home", component: () => import("@/pages/HomePage.vue"), meta: { title: "توليد الأوراق" } },
    { path: "/saved", name: "saved", component: () => import("@/pages/SavedPage.vue"), meta: { title: "أوراقي" } },
    { path: "/decks", name: "decks", component: () => import("@/pages/DecksPage.vue"), meta: { title: "عروض الدروس" } },
    {
      path: "/copilot",
      name: "copilot-automation",
      component: () => import("@/pages/CopilotAutomationPage.vue"),
      meta: { title: "أتمتة المعاون" },
    },
    {
      path: "/copilot/flow",
      name: "copilot-flow",
      component: () => import("@/pages/CopilotFlowPage.vue"),
      meta: { title: "مخطط التدفق الحي" },
    },
    {
      path: "/welcome",
      name: "landing",
      component: () => import("@/pages/LandingPage.vue"),
      meta: { public: true, bleed: true, title: "مولّد أوراق الرياضيات" },
    },
    {
      path: "/about",
      name: "about",
      component: () => import("@/pages/AboutPage.vue"),
      meta: { public: true, title: "عن المنصة" },
    },
    {
      // للمتصفح الخادمي فقط: الرمز الموقّع في المسار هو الإذن، فلا جلسة ولا تنقل.
      path: "/print/:token",
      name: "print",
      component: () => import("@/pages/PrintPage.vue"),
      meta: { public: true, title: "طباعة" },
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/LoginPage.vue"),
      meta: { public: true, title: "تسجيل الدخول" },
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/pages/NotFoundPage.vue"),
      meta: { public: true, title: "الصفحة غير موجودة" },
    },
  ],
});

// يقبل مسارًا داخليًا فقط، فلا يصبح next وسيلة لإعادة توجيه مفتوحة.
export function safeNext(value: unknown): string {
  return typeof value === "string" && /^\/(?![/\\])/.test(value) ? value : "/";
}

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.checked) await auth.loadMe().catch(() => undefined);
  // من له جلسة لا يرى بطاقة الدخول: يعود إلى وجهته أو الرئيسية.
  if (to.name === "login" && auth.user) return safeNext(to.query.next);
  if (to.meta.public) return true;
  // الزائر الذي يفتح الجذر يرى الصفحة الافتتاحية لا بطاقة الدخول؛ باقي الصفحات المحمية تحوّله إلى الدخول.
  if (!auth.user && to.name === "home") return { name: "landing" };
  if (!auth.user) return { name: "login", query: { next: to.fullPath } };
  return true;
});

router.afterEach((to) => {
  const site = document.getElementById("app")?.dataset.siteTitle ?? "";
  const title = typeof to.meta.title === "string" ? to.meta.title : "";
  document.title = title && site ? `${title} | ${site}` : title || site;
});
