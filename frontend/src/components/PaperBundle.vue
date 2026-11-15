<script setup lang="ts">
import { computed, watchEffect } from "vue";
import PaperHeader from "@/components/PaperHeader.vue";
import PaperSheet from "@/components/PaperSheet.vue";
import PrintFrame from "@/components/PrintFrame.vue";
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

const BUNDLE_TITLE = "حزمة أوراق العمل: كل دروس الفصل الأول";
const total = computed(() => props.plan.reduce((sum, entry) => sum + entry.count, 0));
const coverHeader = computed<PaperHeaderData>(() => ({
  ...props.header(props.papers[0]),
  title: BUNDLE_TITLE,
  minutes: null,
  totalMarks: 0,
  instructions: "",
  seed: props.seed,
}));

// تذييل الحزمة الجاري واحد لكل صفحاتها؛ أوراقها لا تضبطه (runningFooter=false).
watchEffect(() => {
  if (typeof document === "undefined") return;
  document.documentElement.style.setProperty("--print-footer", JSON.stringify(BUNDLE_TITLE));
});

function levelsLabel(levels: BundleEntry["levels"]): string {
  return (Object.keys(LEVEL_NAMES) as Level[])
    .filter((code) => levels[code])
    .map((code) => `${LEVEL_NAMES[code]} ${levels[code]}`)
    .join("، ");
}
</script>

<template>
  <div class="bundle">
    <PrintFrame>
      <article class="sheet cover">
        <PaperHeader :header="coverHeader" compact />
        <p class="summary">{{ plan.length }} ورقة عمل، {{ total }} مسألة، مرتبة من السهل إلى مهارات التفكير العليا.</p>
        <div class="table-scroll">
          <table class="index">
            <caption>الفهرس</caption>
            <thead>
              <tr>
                <th scope="col">الدرس</th>
                <th scope="col">العنوان</th>
                <th scope="col">المسائل</th>
                <th scope="col">المستويات</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in plan" :key="entry.lesson">
                <th scope="row" class="code">{{ entry.lesson }}</th>
                <td class="name">{{ entry.title }}</td>
                <td class="num">{{ entry.count }}</td>
                <td class="count">{{ levelsLabel(entry.levels) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <footer class="foot">رقم الحزمة {{ seed }}</footer>
      </article>

      <div v-for="paper in papers" :key="paper.lesson_code" class="bundle-sheet">
        <PaperSheet :paper="paper" :header="header(paper)" :show-key="false" :running-footer="false" />
      </div>

      <template v-if="showKey">
        <div v-for="paper in papers" :key="`key-${paper.lesson_code}`" class="bundle-sheet">
    <PaperSheet :paper="paper" :header="header(paper)" :show-key="true" hide-sheet :running-footer="false" />
        </div>
      </template>
    </PrintFrame>
  </div>
</template>

<style scoped>
.summary {
  color: var(--color-ink-soft);
}
.index {
  inline-size: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.index caption {
  text-align: start;
  color: var(--color-brand-strong);
  font-weight: var(--weight-bold);
  font-size: var(--text-md);
  padding-block-end: var(--space-2);
}
.index th,
.index td {
  border: 1px solid var(--color-line-strong);
  padding: var(--space-1) var(--space-3);
  text-align: start;
}
.index thead th {
  background: var(--color-brand);
  color: var(--color-on-brand);
  border-color: var(--color-brand);
}
.index .num,
.code {
  text-align: center;
  white-space: nowrap;
}
.code {
  font-weight: var(--weight-bold);
  font-family: var(--font-math);
  color: var(--color-brand-strong);
}
.count {
  color: var(--color-ink-soft);
}
.foot {
  color: var(--color-ink-soft);
  font-size: var(--text-xs);
  margin-block-start: var(--space-6);
}
@media print {
  .bundle-sheet {
    break-before: page;
  }
}
</style>
