<script setup lang="ts">
defineProps<{ ok: boolean | null }>();
</script>

<template>
  <p class="status" :class="{ ok: ok === true, bad: ok === false }" role="status">
    <span v-if="ok === null">يتحقق من الخادم…</span>
    <span v-else-if="ok">الخادم يعمل</span>
    <span v-else>الخادم لا يستجيب</span>
  </p>
</template>
