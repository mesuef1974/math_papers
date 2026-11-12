<script setup lang="ts">
import { computed } from "vue";
import katex from "katex";
import "katex/dist/katex.min.css";
import { splitMath } from "@/utils/mathText";

const props = defineProps<{ text: string }>();

// صيغة غير صالحة تُعرض كنص بلون الخطر؛ لون الخطر من متغيرات الهوية (ومنها print.css على الورق)، لا أحمر KaTeX الافتراضي.
const segments = computed(() =>
  splitMath(props.text).map((segment) =>
    segment.math
      ? {
          ...segment,
          // السطري بحجم كامل (كسور ونهايات كما في الكتب)؛ المعروض كامل أصلًا، فلا نكرر.
          value: katex.renderToString(segment.display ? segment.value : `\\displaystyle ${segment.value}`, {
            throwOnError: false,
            displayMode: segment.display,
            errorColor: "var(--color-danger)",
          }),
        }
      : segment,
  ),
);
</script>

<template>
  <span class="math-text">
    <template v-for="(segment, index) in segments" :key="index">
      <bdi v-if="segment.math" class="math" :class="{ display: segment.display }" dir="ltr" v-html="segment.value" />
      <template v-else>{{ segment.value }}</template>
    </template>
  </span>
</template>

<style scoped>
.math {
  unicode-bidi: isolate;
}
.math.display {
  display: block;
  text-align: center;
  margin-block: var(--space-2);
}
</style>
