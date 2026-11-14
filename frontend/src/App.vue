<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "@/components/AppIcon.vue";
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

async function logout() {
  usePapersStore().$reset(); // لا تبقى ورقة المستخدم السابق في الذاكرة
  await auth.logout().catch(() => undefined);
  await router.replace({ name: "login" });
}
</script>

<template>
  <SplashScreen v-if="!auth.checked" class="no-print" />
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
        <RouterLink v-if="auth.canGenerate" class="nav-link" to="/saved">أوراقي</RouterLink>
        <RouterLink class="nav-link" to="/about">عن المنصة</RouterLink>
        <a v-if="auth.user?.admin_url" class="nav-link" :href="auth.user.admin_url">الإدارة</a>
        <button v-if="auth.user" type="button" class="nav-link nav-user" :title="auth.user.username" @click="logout">
          <AppIcon name="teacher" />خروج
        </button>
        <RouterLink v-else class="nav-link" to="/login">دخول</RouterLink>
      </nav>
      <ThemeToggle />
    </div>
  </header>
  <main class="container page">
    <RouterView />
  </main>
  <footer class="site-footer no-print">
    <div class="container">مسائل أصلية تُولَّد بالمعاملات ويُتحقق من أجوبتها برمجيًا، للاستعمال الصفي.</div>
  </footer>
</template>
