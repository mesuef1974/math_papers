<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiError } from "@/api/client";
import { safeNext } from "@/router";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const username = ref("");
const password = ref("");
const busy = ref(false);
const error = ref("");

async function submit() {
  busy.value = true;
  error.value = "";
  try {
    await auth.login(username.value.trim(), password.value);
    password.value = "";
    await router.replace(safeNext(route.query.next));
  } catch (err) {
    error.value =
      err instanceof ApiError && err.detail ? err.detail : "تعذر تسجيل الدخول. تحقق من الاتصال وحاول مرة أخرى.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="container-narrow login">
    <header class="page-head">
      <span class="eyebrow">للمعلمين</span>
      <h1>تسجيل الدخول</h1>
      <p class="lead">المولّد للمعلمين المسجّلين، ويُنشئ المشرف حسابك.</p>
    </header>
    <form class="panel stack" @submit.prevent="submit">
      <label class="field">
        اسم المستخدم
        <input v-model="username" class="input" autocomplete="username" dir="ltr" required maxlength="150" />
      </label>
      <label class="field">
        كلمة المرور
        <input v-model="password" class="input" type="password" autocomplete="current-password" dir="ltr" required />
      </label>
      <button type="submit" class="btn btn-primary btn-block" :disabled="busy || !username || !password">
        {{ busy ? "جارٍ الدخول" : "دخول" }}
      </button>
      <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<style scoped>
.login {
  padding-block-start: var(--space-6);
}
.stack {
  display: grid;
  gap: var(--space-4);
}
</style>
