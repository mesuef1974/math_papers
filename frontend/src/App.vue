<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import BrandMark from "@/components/BrandMark.vue";
import { useAppStore } from "@/stores/app";
import { useAuthStore } from "@/stores/auth";
import { usePapersStore } from "@/stores/papers";

const store = useAppStore();
const auth = useAuthStore();
const router = useRouter();
onMounted(() => store.loadPing());

async function logout() {
  await auth.logout().catch(() => undefined);
  usePapersStore().$reset(); // لا تبقى ورقة المستخدم السابق في الذاكرة
  await router.replace({ name: "login" });
}
</script>

<template>
  <header class="topbar no-print">
    <div class="container topbar-inner">
      <RouterLink class="brand" to="/" :aria-label="store.siteTitle">
        <BrandMark />
        <span class="brand-name">
          <strong>{{ store.siteTitle }}</strong>
          <small>12 علمي وتكنولوجي، الفصل الأول</small>
        </span>
      </RouterLink>
      <nav class="nav" aria-label="التنقل الرئيسي">
        <RouterLink class="nav-link" to="/">الرئيسية</RouterLink>
        <RouterLink class="nav-link" to="/about">عن المنصة</RouterLink>
        <a v-if="auth.user?.admin_url" class="nav-link" :href="auth.user.admin_url">الإدارة</a>
        <button v-if="auth.user" type="button" class="nav-link" :title="auth.user.username" @click="logout">
          خروج
        </button>
        <RouterLink v-else class="nav-link" to="/login">دخول</RouterLink>
      </nav>
    </div>
  </header>
  <main class="container page">
    <RouterView />
  </main>
  <footer class="site-footer no-print">
    <div class="container">مسائل أصلية تُولَّد بالمعاملات ويُتحقق من أجوبتها برمجيًا، للاستعمال الصفي.</div>
  </footer>
</template>
