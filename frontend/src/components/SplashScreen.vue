<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import BrandMark from "@/components/BrandMark.vue";
import BrandPattern from "@/components/BrandPattern.vue";
import { playMarkIntro } from "@/utils/markIntro";

// شاشة الافتتاح (identity/applications/app-splash): الرمز وحده في وسط الصفحة بخلفية الورق، مع ظهور الرمز بالحركة.
// تُعرض ما دامت الجلسة لم تُفحص بعد؛ وتتأخر 150ms في الظهور فلا تومض في التحميل السريع.
const DELAY_MS = 150;
const holder = ref<HTMLElement | null>(null);
const ready = ref(false);
let timer: ReturnType<typeof setTimeout> | undefined;
onMounted(() => {
  timer = setTimeout(() => {
    ready.value = true;
    playMarkIntro(holder.value?.querySelector("svg"));
  }, DELAY_MS);
});
onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
  <div class="splash" :class="{ ready }" role="status" aria-live="polite">
    <div ref="holder" class="splash-mark">
      <BrandMark :size="132" />
    </div>
    <div class="splash-pattern" aria-hidden="true"><BrandPattern :tile="100" /></div>
    <span class="visually-hidden">جارٍ التحميل</span>
  </div>
</template>

<style scoped>
.splash {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  background: var(--color-paper);
  visibility: hidden;
}
.splash.ready {
  visibility: visible;
}
/* شريط النمط في أسفل الشاشة كما في app-splash: بعيد عن الرمز، ولا نص فوقه */
.splash-pattern {
  position: absolute;
  inset-inline: 0;
  inset-block-end: 0;
  block-size: 160px;
}
</style>
