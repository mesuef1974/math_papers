<script setup lang="ts">
// شعار مولّد أوراق الرياضيات: كلمة «أوراق» بالكوفي الحديث (Reem Kufi 700) على سطر سميك، وإلى يمينها رزمة ثلاث أوراق متراجعة، الورقة الأمامية مطوية الزاوية.
// مُولَّد بأداة سِمة (المفهوم w1)؛ النسخة نفسها في public/favicon.svg. أي تعديل يُنقل إليها.
withDefaults(defineProps<{ size?: number }>(), { size: 36 });
</script>

<template>
  <svg class="brand-mark" :width="size" :height="size" aria-hidden="true" focusable="false" viewBox="0 0 256 256"><path fill="var(--color-mark-ink, #842447)" d="M144.0 96.0V240.0H32.0V136.0L72.0 96.0ZM72.0 56.0H184.0V200.0H158.0V82.0H72.0Z" /><path fill="var(--color-mark-accent, #E3AB3C)" d="M112.0 16.0H224.0V160.0H198.0V42.0H112.0Z" /></svg>
</template>

<style scoped>
.brand-mark {
  flex: none;
  display: block;
}
</style>
