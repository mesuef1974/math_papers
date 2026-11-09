<script setup lang="ts">
import { computed } from "vue";
import PaperHeader from "@/components/PaperHeader.vue";
import PaperSheet from "@/components/PaperSheet.vue";
import { LEVEL_NAMES, type BundleEntry, type Level, type Paper } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";

// حزمة كل أوراق العمل: غلاف بفهرس، ثم كل ورقة في صفحة جديدة، ثم المفاتيح كلها في آخر الحزمة إن طُلبت.
const props = defineProps<{
  papers: Paper[];
  plan: BundleEntry[];
  seed: number;
  header: (paper: Paper) => PaperHeaderData;
  showKey: boolean;
}>();

const total = computed(() => props.plan.reduce((sum, entry) => sum + entry.count, 0));
const coverHeader = computed<PaperHeaderData>(() => ({
  ...props.header(props.papers[0]),
  title: "حزمة أوراق العمل: كل دروس الفصل الأول",
  minutes: null,
  totalMarks: 0,
  instructions: "",
  seed: props.seed,
}));

function levelsLabel(levels: BundleEntry["levels"]): string {
  return (Object.keys(LEVEL_NAMES) as Level[])
    .filter((code) => levels[code])
    .map((code) => `${LEVEL_NAMES[code]} ${levels[code]}`)
    .join("، ");
}
</script>

<template>
  <div class="bundle">
    <article class="sheet cover">
      <PaperHeader :header="coverHeader" compact />
      <p class="summary">{{ plan.length }} ورقة عمل، {{ total }} مسألة، مرتبة من السهل إلى مهارات التفكير العليا.</p>
      <h3>الفهرس</h3>
      <ol class="index">
        <li v-for="entry in plan" :key="entry.lesson">
          <span class="code">{{ entry.lesson }}</span>
          <span class="name">{{ entry.title }}</span>
          <span class="count">{{ entry.count }} مسائل: {{ levelsLabel(entry.levels) }}</span>
        </li>
      </ol>
      <footer class="foot">رقم الحزمة {{ seed }}</footer>
    </article>

    <div v-for="paper in papers" :key="paper.lesson_code" class="bundle-sheet">
      <PaperSheet :paper="paper" :header="header(paper)" :show-key="false" />
    </div>

    <template v-if="showKey">
      <div v-for="paper in papers" :key="`key-${paper.lesson_code}`" class="bundle-sheet">
        <PaperSheet :paper="paper" :header="header(paper)" :show-key="true" hide-sheet />
      </div>
    </template>
  </div>
</template>

<style scoped>
.sheet {
  background: var(--color-sheet);
  border: var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  padding: var(--space-8);
  margin-block-start: var(--space-6);
}
.summary {
  color: var(--color-ink-soft);
}
.index {
  margin: 0;
  padding-inline-start: var(--space-6);
  display: grid;
  gap: var(--space-2);
}
.index li {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: var(--space-3);
  align-items: baseline;
  border-block-end: 1px dotted var(--color-line);
  padding-block-end: var(--space-1);
}
.code {
  font-weight: var(--weight-bold);
  font-family: var(--font-math);
}
.count {
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.foot {
  color: var(--color-ink-soft);
  font-size: var(--text-xs);
  margin-block-start: var(--space-6);
}
@media print {
  .sheet {
    border: 0;
    box-shadow: none;
    padding: 0;
    margin: 0;
  }
  .bundle-sheet {
    break-before: page;
  }
  .index li {
    grid-template-columns: auto 1fr;
  }
  .count {
    grid-column: 2;
  }
}
</style>
