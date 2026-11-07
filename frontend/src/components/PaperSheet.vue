<script setup lang="ts">
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import { LEVEL_NAMES, type Level, type Paper } from "@/stores/papers";

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
      <h2>{{ paper.title }}</h2>
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
          <span class="lesson-tag">الدرس {{ part.lesson }}، {{ LEVEL_NAMES[part.level as Level] }}</span>
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
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 24px;
  margin-block-start: 20px;
}
.sheet-head {
  border-block-end: 2px solid var(--ink);
  padding-block-end: 8px;
  margin-block-end: 12px;
}
.sheet-head h2 {
  font-size: 20px;
  margin-block: 0 8px;
}
.fields {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}
.question {
  break-inside: avoid;
  margin-block-end: 14px;
}
.question-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.marks {
  color: var(--muted);
  font-size: 15px;
}
.part {
  overflow-y: hidden;
  overflow-x: auto;
}
.stem {
  margin-block: 6px;
}
.part-label {
  display: inline-block;
  font-weight: 700;
  margin-inline-end: 8px;
}
.options {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
}
.graph-option {
  display: flex;
  align-items: start;
  gap: 4px;
  break-inside: avoid;
}
.option-label {
  margin-inline-end: 6px;
}
.work-space {
  border-block-end: 1px dashed var(--line);
}
.steps {
  margin-block: 4px;
  padding-inline-start: 24px;
  color: var(--muted);
}
.lesson-tag {
  color: var(--muted);
  font-size: 14px;
  margin-inline-start: 10px;
}
.sheet-foot {
  color: var(--muted);
  font-size: 14px;
  margin-block-start: 12px;
}
@media (max-width: 560px) {
  .sheet {
    padding: 16px;
  }
  .options {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media print {
  .sheet {
    border: 0;
    padding: 0;
    margin: 0;
    background: #fff;
    color: #000;
  }
  .answer-key {
    break-before: page;
  }
  .marks,
  .steps,
  .sheet-foot,
  .lesson-tag {
    color: #000;
  }
}
</style>
