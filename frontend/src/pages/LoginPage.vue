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
  <section class="login">
    <h1>تسجيل الدخول</h1>
    <p class="lead">المولّد للمعلمين المسجّلين. يُنشئ المشرف حسابك.</p>
    <form class="panel" @submit.prevent="submit">
      <label class="field">
        اسم المستخدم
        <input v-model="username" autocomplete="username" dir="ltr" required maxlength="150" />
      </label>
      <label class="field">
        كلمة المرور
        <input v-model="password" type="password" autocomplete="current-password" dir="ltr" required />
      </label>
      <button type="submit" :disabled="busy || !username || !password">
        {{ busy ? "جارٍ الدخول" : "دخول" }}
      </button>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </form>
  </section>
</template>

<style scoped>
.login {
  max-inline-size: 420px;
  margin-inline: auto;
}
.panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
  display: grid;
  gap: 14px;
}
.field {
  display: grid;
  gap: 4px;
  color: var(--muted);
  font-size: 15px;
}
input {
  font: inherit;
  color: var(--ink);
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  inline-size: 100%;
}
button {
  font: inherit;
  font-weight: 600;
  background: var(--accent);
  color: var(--surface);
  border: 1px solid var(--accent);
  border-radius: 6px;
  padding: 8px 18px;
  cursor: pointer;
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.error {
  color: var(--risk);
  margin: 0;
}
</style>
