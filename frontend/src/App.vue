<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon, { type IconName } from "@/components/AppIcon.vue";
import BrandLockup from "@/components/BrandLockup.vue";
import SplashScreen from "@/components/SplashScreen.vue";
import ThemeToggle from "@/components/ThemeToggle.vue";
import { useAppStore } from "@/stores/app";
import { useAuthStore } from "@/stores/auth";
import { usePapersStore } from "@/stores/papers";

const store = useAppStore();
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
onMounted(() => store.loadPing());

// سقوط الجلسة (401 من أي طلب، أو خروج) على صفحة محمية يعيد إلى الدخول ثم إلى الصفحة نفسها.
watch(
  () => auth.user,
  (user, previous) => {
    if (previous && !user && !route.meta.public) {
      void router.replace({ name: "login", query: { next: route.fullPath } });
    }
  },
);

// عناصر التنقل المشتركة بين الشريط الجانبي والتبويب السفلي؛ المعاون وأوراقي لمن يملك صلاحية التوليد.
const navItems = computed(() => {
  const items: { to: string; label: string; icon: IconName }[] = [{ to: "/", label: "توليد الأوراق", icon: "generate" }];
  if (auth.canGenerate) {
    items.push({ to: "/saved", label: "أوراقي", icon: "worksheet" });
    items.push({ to: "/preps", label: "التحضير", icon: "answer-key" });
    items.push({ to: "/decks", label: "العروض", icon: "test" });
    items.push({ to: "/copilot", label: "المعاون", icon: "curriculum" });
  }
  items.push({ to: "/about", label: "عن المنصة", icon: "teacher" });
  return items;
});

async function logout() {
  usePapersStore().$reset(); // لا تبقى ورقة المستخدم السابق في الذاكرة
  await auth.logout().catch(() => undefined);
  await router.replace({ name: "login" });
}
</script>

<template>
  <SplashScreen v-if="!auth.checked" class="no-print" />
  <!-- المسجَّل: هيكل التطبيق من screens/app-light وmobile في دليل الهوية (شريط جانبي، وتبويب سفلي في الجوال) -->
  <div v-if="auth.user" class="shell">
    <aside class="sidebar no-print">
      <RouterLink class="sidebar-brand" to="/" :aria-label="store.siteTitle">
        <BrandLockup :height="36" />
      </RouterLink>
      <nav class="side-nav" aria-label="التنقل الرئيسي">
        <RouterLink v-for="item in navItems" :key="item.to" class="side-link" :to="item.to">
          <AppIcon :name="item.icon" />{{ item.label }}
        </RouterLink>
        <a v-if="auth.user.admin_url" class="side-link" :href="auth.user.admin_url">
          <AppIcon name="answer-key" />الإدارة
        </a>
      </nav>
      <div class="side-user">
        <span class="avatar" aria-hidden="true"></span>
        <div class="side-user-text">
          <strong>{{ auth.user.username }}</strong>
          <small>{{ store.siteTitle }}</small>
        </div>
        <button type="button" class="side-logout" @click="logout">خروج</button>
      </div>
      <ThemeToggle />
    </aside>
    <div class="shell-main">
      <header class="mobilebar no-print">
        <RouterLink class="brand" to="/" :aria-label="store.siteTitle"><BrandLockup :height="30" /></RouterLink>
        <ThemeToggle />
        <button type="button" class="nav-link" :title="auth.user.username" @click="logout">خروج</button>
      </header>
      <main class="container page">
        <RouterView />
      </main>
      <footer class="site-footer no-print">
        <div class="container">مسائل أصلية تُولَّد بالمعاملات ويُتحقق من أجوبتها برمجيًا، للاستعمال الصفي.</div>
      </footer>
    </div>
    <nav class="tabbar no-print" aria-label="التنقل السفلي">
      <RouterLink v-for="item in navItems" :key="item.to" class="tab" :to="item.to">
        <AppIcon :name="item.icon" />{{ item.label }}
      </RouterLink>
    </nav>
  </div>
  <!-- الزائر: ترويسة علوية والصفحة الافتتاحية بعرض كامل -->
  <template v-else>
    <header class="topbar no-print">
      <div class="container topbar-inner">
        <RouterLink class="brand" to="/" :aria-label="store.siteTitle">
          <BrandLockup :height="40" />
          <span class="brand-name">
            <strong class="visually-hidden">{{ store.siteTitle }}</strong>
            <small v-if="store.subtitle">{{ store.subtitle }}</small>
          </span>
        </RouterLink>
        <nav class="nav" aria-label="التنقل الرئيسي">
          <RouterLink class="nav-link" to="/">الرئيسية</RouterLink>
          <RouterLink class="nav-link" to="/about">عن المنصة</RouterLink>
          <RouterLink class="btn btn-secondary btn-small" to="/login">تسجيل الدخول</RouterLink>
        </nav>
        <ThemeToggle />
      </div>
    </header>
    <main :class="route.meta.bleed ? 'page-bleed' : 'container page'">
      <RouterView />
    </main>
    <footer class="site-footer no-print">
      <div class="container">مسائل أصلية تُولَّد بالمعاملات ويُتحقق من أجوبتها برمجيًا، للاستعمال الصفي.</div>
    </footer>
  </template>
</template>
