<script setup lang="ts">
// نمط الهوية (identity/patterns/motif-soft.svg): همزتان في بلاطة 200×200 تتكرّران بتباعد واسع؛ الأولى بلون النمط والثانية بلون التمييز الخفيف.
// زخرفة فقط: لا يحمل نصًا ولا يُوضع خلف مسألة أو مفتاح إجابة، ولا يجاور الشعار. الألوان من متغيرات السمة فيتبدّل ليلًا مع الواجهة.
// المعرّف فريد لكل نسخة لأن عدة أنماط قد تظهر في صفحة واحدة.
import { useId } from "vue";

withDefaults(defineProps<{ tile?: number }>(), { tile: 240 });
const id = `motif-${useId()}`;
</script>

<template>
  <svg class="brand-pattern" aria-hidden="true" focusable="false" preserveAspectRatio="none">
    <defs>
      <pattern :id="id" patternUnits="userSpaceOnUse" :width="tile" :height="tile" viewBox="0 0 200 200">
        <path
          class="motif"
          d="M 79 24 C 62 28 47.5 42 39 59.5 L 53.5 63.5 L 34 84.5 L 74 64.5 L 80 52.5 L 61 48.5 C 65.5 42 75.5 38 79 24 Z"
        />
        <path
          class="motif accent"
          d="M 179 124 C 162 128 147.5 142 139 159.5 L 153.5 163.5 L 134 184.5 L 174 164.5 L 180 152.5 L 161 148.5 C 165.5 142 175.5 138 179 124 Z"
        />
      </pattern>
    </defs>
    <rect width="100%" height="100%" :fill="`url(#${id})`" />
  </svg>
</template>

<style scoped>
.brand-pattern {
  display: block;
  inline-size: 100%;
  block-size: 100%;
  pointer-events: none;
}
.motif {
  fill: var(--color-brand-soft);
}
.accent {
  fill: var(--color-sand-soft);
}
</style>
