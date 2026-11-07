<script setup lang="ts">
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import { LEVEL_NAMES, type Level, type Paper } from "@/stores/papers";
import { isolateNumberRanges } from "@/utils/bidi";

defineProps<{ paper: Paper; showKey: boolean }>();

const OPTION_LABELS = ["أ", "ب", "ج", "د"];

function marksLabel(marks: number): string {
  if (marks === 1) return "درجة واحدة";
  if (marks === 2) return "درجتان";
  return `${marks} درجات`;
}
</script>

<template>
  <article class="sheet">
    <header class="sheet-head">
      <h2>{{ isolateNumberRanges(paper.title) }}</h2>
      <div class="fields">
        <span>الاسم: ........................................</span>
        <span>الصف: ..............</span>
        <span v-if="paper.total_marks">الدرجة: ........ / {{ paper.total_marks }}</span>
      </div>
    </header>

    <section v-for="question in paper.questions" :key="question.number" class="question">
      <div class="question-head">
        <strong>السؤال {{ question.number }}</strong>
        <span v-if="question.marks" class="marks">{{ marksLabel(question.marks) }}</span>
      </div>
      <div v-for="part in question.parts" :key="part.label + part.stem" class="part">
        <p class="stem">
          <bdi v-if="part.label" class="part-label">{{ part.label }}.</bdi>
          <MathText :text="part.stem" />
          <span v-if="part.label" class="marks">({{ part.marks }})</span>
        </p>
        <GraphPlot v-if="part.graph" :graph="part.graph" />
        <ol v-if="part.options.length" class="options">
          <li v-for="(option, index) in part.options" :key="index" :class="{ 'graph-option': part.option_graphs.length }">
            <span class="option-label">{{ OPTION_LABELS[index] }})</span>
            <GraphPlot v-if="part.option_graphs[index]" :graph="part.option_graphs[index]" compact />
            <MathText v-else :text="option" />
          </li>
        </ol>
        <div v-else class="work-space" :style="{ minBlockSize: `${Math.max(part.marks, 2) * 34}px` }" />
      </div>
    </section>
    <footer class="sheet-foot">رقم النموذج {{ paper.seed }}</footer>
  </article>

  <article v-if="showKey" class="sheet answer-key">
    <header class="sheet-head"><h2>مفتاح الحل، نموذج {{ paper.seed }}</h2></header>
    <section v-for="question in paper.questions" :key="question.number" class="question">
      <div v-for="part in question.parts" :key="part.label + part.stem" class="part">
        <p class="stem">
          <strong><bdi>{{ question.number }}{{ part.label ? ` ${part.label}` : "" }}</bdi> :</strong>
          <MathText :text="part.answer" />
          <span class="lesson-tag">الدرس {{ part.lesson }}</span>
          <span class="badge" :class="`badge-${part.level.toLowerCase()}`">{{ LEVEL_NAMES[part.level as Level] }}</span>
        </p>
        <ol class="steps">
          <li v-for="step in part.steps" :key="step"><MathText :text="step" /></li>
        </ol>
      </div>
    </section>
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
.sheet-head {
  border-block-end: 2px solid var(--color-ink);
  padding-block-end: var(--space-3);
  margin-block-end: var(--space-2);
}
.sheet-head h2 {
  font-size: var(--text-xl);
  margin-block: 0 var(--space-2);
}
.fields {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-6);
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
.graph-option {
  display: flex;
  align-items: start;
  gap: var(--space-1);
  break-inside: avoid;
}
.option-label {
  font-weight: var(--weight-medium);
  margin-inline-end: var(--space-2);
}
.work-space {
  border-block-end: 1px dashed var(--color-line-strong);
}
.steps {
  margin-block: var(--space-1);
  padding-inline-start: var(--space-6);
  color: var(--color-ink-soft);
}
.lesson-tag {
  color: var(--color-ink-soft);
  font-size: var(--text-xs);
  margin-inline: var(--space-3) var(--space-2);
}
.sheet-foot {
  color: var(--color-ink-soft);
  font-size: var(--text-xs);
  margin-block-start: var(--space-4);
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
  .answer-key {
    break-before: page;
  }
}
</style>
