<script setup lang="ts">
import { computed } from "vue";
import katex from "katex";
import "katex/dist/katex.min.css";

const props = defineProps<{ text: string }>();

// النص يتناوب بين عربي ورياضيات تفصلها علامة $، فالمقاطع الفردية رياضيات.
const segments = computed(() =>
  props.text.split("$").map((value, index) =>
    index % 2 === 1
      ? { math: true, value: katex.renderToString(value, { throwOnError: false }) }
      : { math: false, value },
  ),
);
</script>

<template>
  <span class="math-text">
    <template v-for="(segment, index) in segments" :key="index">
      <bdi v-if="segment.math" class="math" dir="ltr" v-html="segment.value" />
      <template v-else>{{ segment.value }}</template>
    </template>
  </span>
</template>

<style scoped>
.math {
  unicode-bidi: isolate;
}
</style>
