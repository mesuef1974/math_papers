<script setup lang="ts">
// شعار المنصة: مربع عنابي فيه محوران ومنحنى بنقطة قصوى، أي «ورقة المربعات» في رمز واحد.
// النسخة نفسها في public/favicon.svg؛ أي تعديل هنا يُنقل إليها.
withDefaults(defineProps<{ size?: number }>(), { size: 36 });
</script>

<template>
  <svg class="brand-mark" :width="size" :height="size" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
    <rect width="40" height="40" rx="10" class="tile" />
    <path d="M9 30.5H32M12 33V8" class="axes" />
    <path d="M10 27C15 27 16 12 21.5 12S28 22 32 24" class="curve" />
    <circle cx="21.5" cy="12" r="2.4" class="dot" />
  </svg>
</template>

<style scoped>
.brand-mark {
  flex: none;
  display: block;
}
.tile {
  fill: var(--color-mark-tile);
}
.axes {
  fill: none;
  stroke: var(--color-mark-ink);
  stroke-opacity: 0.55;
  stroke-width: 1.6;
  stroke-linecap: round;
}
.curve {
  fill: none;
  stroke: var(--color-mark-ink);
  stroke-width: 2.6;
  stroke-linecap: round;
}
.dot {
  fill: var(--color-mark-dot);
}
</style>
