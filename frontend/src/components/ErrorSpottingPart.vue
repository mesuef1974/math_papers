<script setup lang="ts">
import MathText from "@/components/MathText.vue";

// حل «اكتشف الخطأ» المعروض بخطواته المرقّمة (شاشة وطباعة وPDF). لا يدل على الخطوة الخاطئة: تشخيصها في المفتاح وحده.
defineProps<{ steps: string[] }>();
</script>

<template>
  <ol class="spotting-steps">
    <li v-for="(step, index) in steps" :key="index"><MathText :text="step" /></li>
  </ol>
</template>

<style scoped>
.spotting-steps {
  margin-block: var(--space-2);
  padding-inline-start: var(--space-8);
}
.spotting-steps li {
  margin-block-end: var(--space-1);
}
/* ترقيم «1- 2- 3-» كما في المفتاح وWord؛ RLM حول الشرطة يُبقيها يسار الرقم */
.spotting-steps li::marker {
  content: "\200F" counter(list-item) "\200F-\200F ";
}
</style>
