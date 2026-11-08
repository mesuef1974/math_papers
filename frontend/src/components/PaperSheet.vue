<script setup lang="ts">
import { computed } from "vue";
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import PaperHeader from "@/components/PaperHeader.vue";
import { LEVEL_NAMES, type Paper, type Question } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { marksLabel } from "@/utils/marks";

const props = defineProps<{ paper: Paper; header: PaperHeaderData; showKey: boolean }>();

const OPTION_LABELS = ["أ", "ب", "ج", "د"];

// تعليمات كل قسم كما في أوراق الوزارة: قبل أول سؤال موضوعي وقبل أول سؤال مقالي، بنطاق أرقامه.
const sectionNotes = computed(() => {
  const notes = new Map<number, string>();
  const kinds: Question["kind"][] = ["mcq", "essay"];
  for (const kind of kinds) {
    const group = props.paper.questions.filter((q) => q.kind === kind);
    if (!group.length || group.length === props.paper.questions.length) continue;
    const first = group[0].number;
    const last = group[group.length - 1].number;
    const range = first === last ? `السؤال ${first}` : `كل سؤال من ${first} إلى ${last}`;
    notes.set(
      first,
      kind === "mcq"
        ? `اختر الإجابة الصحيحة لـ${range} بوضع علامة × في المربع المجاور للإجابة الصحيحة.`
        : `أجب عن ${range} مبيّنًا خطوات الحل.`,
    );
  }
  return notes;
});
</script>

<template>
  <article class="sheet">
    <PaperHeader :header="header" />

    <section v-for="question in paper.questions" :key="question.number" class="question">
      <p v-if="sectionNotes.has(question.number)" class="section-note">{{ sectionNotes.get(question.number) }}</p>
      <div class="question-head">
        <strong>السؤال {{ question.number }}</strong>
        <span v-if="question.marks" class="marks">{{ marksLabel(question.marks) }}</span>
      </div>
      <div v-for="part in question.parts" :key="part.fingerprint" class="part">
        <p class="stem">
          <bdi v-if="part.label" class="part-label">{{ part.label }}.</bdi>
          <MathText :text="part.stem" />
          <span v-if="part.label" class="marks">({{ part.marks }})</span>
        </p>
        <GraphPlot v-if="part.graph" :graph="part.graph" />
        <ol v-if="part.options.length" class="options">
          <li v-for="(option, index) in part.options" :key="index" :class="{ 'graph-option': part.option_graphs.length }">
            <span class="box" aria-hidden="true" />
            <span class="option-label">{{ OPTION_LABELS[index] }})</span>
            <GraphPlot v-if="part.option_graphs[index]" :graph="part.option_graphs[index]" compact />
            <MathText v-else :text="option" />
          </li>
        </ol>
        <div v-else class="work-space" :data-lines="Math.min(Math.max(part.marks, 2), 6)" />
      </div>
    </section>
    <footer class="sheet-foot">
      <span>انتهت الأسئلة</span>
      <span>رقم النموذج {{ paper.seed }}</span>
    </footer>
  </article>

  <article v-if="showKey" class="sheet answer-key">
    <PaperHeader :header="{ ...header, title: `مفتاح الحل: ${header.title}` }" compact />
    <table class="key">
      <thead>
        <tr>
          <th scope="col">السؤال</th>
          <th scope="col">الإجابة والخطوات</th>
          <th scope="col">الدرس</th>
          <th scope="col">المستوى</th>
          <th scope="col">الدرجة</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="question in paper.questions" :key="question.number">
          <tr v-for="part in question.parts" :key="part.fingerprint">
            <th scope="row">
              <bdi>{{ question.number }}{{ part.label ? ` ${part.label}` : "" }}</bdi>
            </th>
            <td>
              <p class="answer"><MathText :text="part.answer" /></p>
              <ol v-if="part.steps.length" class="steps">
                <li v-for="step in part.steps" :key="step"><MathText :text="step" /></li>
              </ol>
            </td>
            <td class="lesson">{{ part.lesson }}</td>
            <td><span class="badge" :class="`badge-${part.level.toLowerCase()}`">{{ LEVEL_NAMES[part.level] }}</span></td>
            <td class="num">{{ part.marks || "" }}</td>
          </tr>
        </template>
      </tbody>
    </table>
    <footer class="sheet-foot"><span>رقم النموذج {{ paper.seed }}</span></footer>
  </article>
</template>

<style scoped>
.sheet {
  background: var(--color-surface);
  border: var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  padding: var(--space-8);
  margin-block-start: var(--space-6);
}
.section-note {
  margin-block: var(--space-2) var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-sunken);
  border-inline-start: 3px solid var(--color-ink);
  font-size: var(--text-sm);
}
.question {
  break-inside: avoid;
  padding-block: var(--space-3);
  border-block-end: 1px solid var(--color-line);
}
.question:last-of-type {
  border-block-end: 0;
}
.question-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-3);
}
.question-head strong {
  color: var(--color-brand);
}
.marks {
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.part {
  overflow-y: hidden;
  overflow-x: auto;
}
.stem {
  margin-block: var(--space-2);
}
.part-label {
  display: inline-block;
  font-weight: var(--weight-bold);
  margin-inline-end: var(--space-2);
}
.options {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2) var(--space-4);
}
.options li {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}
.graph-option {
  align-items: start;
  break-inside: avoid;
}
/* مربع التظليل كما في أوراق الوزارة: علامة × داخله */
.box {
  flex: none;
  inline-size: 14px;
  block-size: 14px;
  border: 1.5px solid var(--color-ink);
  border-radius: 2px;
  align-self: center;
}
.option-label {
  font-weight: var(--weight-medium);
}
/* مساحة الحل تتدرج مع الدرجات (سطر 34px لكل درجة، من 2 إلى 6) */
.work-space {
  min-block-size: 68px;
  border-block-end: 1px dashed var(--color-line-strong);
}
.work-space[data-lines="3"] {
  min-block-size: 102px;
}
.work-space[data-lines="4"] {
  min-block-size: 136px;
}
.work-space[data-lines="5"] {
  min-block-size: 170px;
}
.work-space[data-lines="6"] {
  min-block-size: 204px;
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
/* مفتاح الحل: جدول */
.key {
  inline-size: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.key th,
.key td {
  border: 1px solid var(--color-line);
  padding: var(--space-2) var(--space-3);
  text-align: start;
  vertical-align: top;
}
.key thead th {
  background: var(--color-surface-sunken);
  font-weight: var(--weight-bold);
}
.key tbody tr {
  break-inside: avoid;
}
.key tbody th {
  white-space: nowrap;
  color: var(--color-brand);
}
.answer {
  margin: 0;
  font-weight: var(--weight-medium);
}
.steps {
  margin-block: var(--space-1) 0;
  padding-inline-start: var(--space-5);
  color: var(--color-ink-soft);
}
.lesson,
.num {
  white-space: nowrap;
}
@media (max-width: 560px) {
  .sheet {
    padding: var(--space-4);
  }
  .options {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media print {
  .sheet {
    border: 0;
    box-shadow: none;
    padding: 0;
    margin: 0;
  }
  /* لا قصّ للصيغ الطويلة على الورق؛ التمرير للشاشة فقط */
  .part {
    overflow: visible;
  }
  .section-note {
    background: none;
    border-inline-start-color: var(--color-ink);
  }
  .answer-key {
    break-before: page;
  }
}
</style>
