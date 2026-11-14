<script setup lang="ts">
import BrandPattern from "@/components/BrandPattern.vue";

// الحالة الفارغة بنمط الهوية: شريط النمط فوق الرسالة لا خلفها، فلا يقع نص عليه.
</script>

<template>
  <div class="empty-state">
    <div class="band" aria-hidden="true"><BrandPattern :tile="120" /></div>
    <p class="message"><slot /></p>
  </div>
</template>

<style scoped>
.empty-state {
  display: grid;
  gap: var(--space-3);
  justify-items: center;
  text-align: center;
  padding-block: var(--space-4);
}
.band {
  inline-size: 100%;
  block-size: 120px;
  overflow: hidden;
  border-radius: var(--radius-md);
}
.message {
  margin: 0;
  color: var(--color-ink-soft);
}
</style>
