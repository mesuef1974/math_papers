<script setup lang="ts">
import { computed } from "vue";
import PaperHeader from "@/components/PaperHeader.vue";
import type { Paper } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";

// ورقة تظليل للأسئلة الموضوعية في صفحة واحدة: صف لكل سؤال ودائرة لكل خيار. answers=true تُظهر مفتاحها مظلَّلًا.
const props = withDefaults(defineProps<{ paper: Paper; header: PaperHeaderData; answers?: boolean }>(), {
  answers: false,
});
const LABELS = ["A", "B", "C", "D"];
const DOTS = "....................";

const rows = computed(() =>
  props.paper.questions
    .filter((q) => q.kind === "mcq")
    .map((q) => ({ number: q.number, correct: q.parts[0]?.answer_index ?? -1 })),
);
const title = computed(() => `${props.answers ? "مفتاح ورقة الإجابة" : "ورقة الإجابة"}: ${props.header.title}`);
</script>

<template>
  <article v-if="rows.length" class="sheet answer-sheet" :class="{ key: answers }">
    <PaperHeader :header="{ ...header, title, instructions: '' }" compact />
    <div v-if="!answers" class="student">
      <span class="grow">اسم الطالب: {{ DOTS }}{{ DOTS }}</span>
      <span>الشعبة: {{ header.section || DOTS }}</span>
      <span>الرقم: {{ DOTS }}</span>
    </div>
    <p class="note">
      {{
        answers
          ? "الدوائر المظلَّلة هي الإجابات الصحيحة لهذا النموذج."
          : "ظلّل دائرة واحدة فقط لكل سؤال بقلم أزرق أو أسود. التظليل في أكثر من دائرة يُلغي الإجابة."
      }}
    </p>
    <ol class="grid" :style="{ columnCount: rows.length > 12 ? 2 : 1 }">
      <li v-for="row in rows" :key="row.number" class="row">
        <span class="num">{{ row.number }}</span>
        <span
          v-for="(label, index) in LABELS"
          :key="label"
          class="bubble"
          :class="{ filled: answers && index === row.correct }"
          :aria-label="`${row.number} ${label}`"
        >
          {{ label }}
        </span>
      </li>
    </ol>
    <footer class="sheet-foot">
      <span>{{ rows.length }} سؤالًا موضوعيًا</span>
      <span>رقم النموذج {{ paper.seed }}</span>
    </footer>
  </article>
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
.student {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-6);
  margin-block-end: var(--space-3);
}
.grow {
  flex: 1 1 auto;
}
.note {
  margin: 0 0 var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
.grid {
  list-style: none;
  margin: 0;
  padding: 0;
  column-gap: var(--space-8);
}
.row {
  direction: ltr; /* الرقم ثم A B C D من اليسار إلى اليمين */
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-block: var(--space-2);
  border-block-end: 1px dotted var(--color-line);
  break-inside: avoid;
}
.num {
  inline-size: 2.2em;
  font-weight: var(--weight-bold);
  font-family: var(--font-math);
}
.bubble {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  inline-size: 24px;
  block-size: 24px;
  border: 1.5px solid var(--color-ink);
  border-radius: 50%;
  font-size: var(--text-xs);
  color: var(--color-ink-soft);
}
.filled {
  background: var(--color-ink);
  color: var(--color-on-brand);
}
.sheet-foot {
  display: flex;
  justify-content: space-between;
  color: var(--color-ink-soft);
  font-size: var(--text-xs);
  margin-block-start: var(--space-4);
  padding-block-start: var(--space-2);
  border-block-start: 1px solid var(--color-line);
}
@media print {
  .sheet {
    border: 0;
    box-shadow: none;
    padding: 0;
    margin: 0;
    break-before: page;
  }
  .filled {
    print-color-adjust: exact;
  }
}
</style>
