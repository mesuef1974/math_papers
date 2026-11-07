<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
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
    <div class="inner">
      <RouterLink class="brand" to="/">{{ store.siteTitle }}</RouterLink>
      <nav>
        <RouterLink to="/">الرئيسية</RouterLink>
        <RouterLink to="/about">عن المنصة</RouterLink>
        <button v-if="auth.user" type="button" class="nav-button" :title="auth.user.username" @click="logout">
          خروج
        </button>
        <RouterLink v-else to="/login">دخول</RouterLink>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <RouterView />
  </main>
</template>
