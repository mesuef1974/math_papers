<script setup lang="ts">
import { computed } from "vue";
import MathText from "@/components/MathText.vue";
import PaperHeader from "@/components/PaperHeader.vue";
import { KEY_LEVELS, type Paper, type Part } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { isolateNumberRanges } from "@/utils/bidi";
import { OPTION_LABELS } from "@/utils/options";

// مفتاح الحل (دليل تقدير الدرجات في الاختبار): جدول رموز الإجابات الموضوعية، ثم جدول الحلول بتوزيع درجاتها.
const props = withDefaults(defineProps<{ paper: Paper; header: PaperHeaderData; modified?: boolean }>(), {
  modified: false,
});

const keyTitle = computed(() => (props.paper.kind === "exam" ? "دليل تقدير الدرجات" : "مفتاح الحل"));

// جدول الإجابات الموضوعية: رقم كل سؤال وحرف إجابته.
const mcqAnswers = computed(() =>
  props.paper.questions
    .filter((q) => q.kind === "mcq" && (q.parts[0]?.answer_index ?? -1) >= 0)
    .map((q) => ({ number: q.number, letter: OPTION_LABELS[q.parts[0].answer_index] })),
);
// أوراق العمل بلا درجات، فلا يُعرض لها عمود درجة فارغ.
const hasMarks = computed(() => props.paper.questions.some((q) => q.parts.some((p) => p.marks > 0)));
// أعمدة مصدر الفكرة في كتاب الطالب («الصفحة» و«المثال» و«التدريب»، كما في Word) تظهر متى عُرف مصدر جزء واحد؛
// الخانة المجهولة «—».
const hasSources = computed(() => props.paper.questions.some((q) => q.parts.some((p) => p.source)));
const sourceCells = (part: Part) => [part.source_page, part.source_example, part.source_exercises];

// صفوف المفتاح لكل جزء: المقالي ذو الدرجة صف لكل بند من توزيعه (خطوات الطريقة ثم الجواب النهائي) بدرجته،
// وغيره صف واحد فيه الإجابة وخطواتها. ترقيم الخطوات متصل عبر صفوف الجزء.
interface KeyRow {
  steps: string[];
  start: number;
  marks: number;
  final: boolean;
  plain: boolean;
}
function keyRows(part: Part): KeyRow[] {
  const items = part.marking ?? [];
  if (!items.length) return [{ steps: part.steps, start: 1, marks: part.marks, final: false, plain: true }];
  let start = 1;
  return items.map((item) => {
    const row = { steps: item.steps, start, marks: item.marks, final: item.final, plain: false };
    start += item.steps.length;
    return row;
  });
}
const keyParts = computed(() =>
  props.paper.questions.flatMap((question) =>
    question.parts.map((part) => ({
      id: `${question.number}${part.label ? ` ${part.label}` : ""}`,
      part,
      rows: keyRows(part),
    })),
  ),
);
</script>

<template>
  <article class="sheet answer-key">
    <PaperHeader :header="{ ...header, title: `${keyTitle}: ${header.title}` }" compact />
    <div v-if="mcqAnswers.length" class="table-scroll">
      <table class="key mcq-key">
        <caption>إجابات الأسئلة الموضوعية</caption>
        <thead>
          <tr>
            <th scope="col">رقم السؤال</th>
            <th scope="col">رمز الإجابة</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in mcqAnswers" :key="row.number">
            <th scope="row">{{ row.number }}</th>
            <td><bdi dir="ltr">{{ row.letter }}</bdi></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="table-scroll">
      <table class="key">
        <caption v-if="mcqAnswers.length">{{ hasMarks ? "الحلول والخطوات بدرجاتها" : "الحلول والخطوات" }}</caption>
        <thead>
          <tr>
            <th scope="col">السؤال</th>
            <th scope="col">الإجابة والخطوات</th>
            <th v-if="hasMarks" scope="col">الدرجة</th>
            <th scope="col">الدرس</th>
            <template v-if="hasSources">
              <th scope="col">الصفحة</th>
              <th scope="col">المثال</th>
              <th scope="col">التدريب</th>
            </template>
            <th scope="col">المستوى</th>
            <th v-if="hasMarks" scope="col">المجموع</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="{ id, part, rows } in keyParts" :key="part.fingerprint">
            <tr v-for="(row, index) in rows" :key="index" :class="{ 'final-row': row.final }">
              <th v-if="index === 0" scope="row" :rowspan="rows.length">
                <bdi>{{ id }}</bdi>
              </th>
              <td class="steps-cell">
                <p v-if="row.plain || row.final" class="answer">
                  <span v-if="row.final" class="final-label">الجواب النهائي: </span><MathText :text="part.answer" />
                </p>
                <ol v-if="row.steps.length" class="steps" :class="{ marked: !row.plain }" :start="row.start">
                  <li v-for="step in row.steps" :key="step"><MathText :text="step" /></li>
                </ol>
              </td>
              <td v-if="hasMarks" class="num step-mark"><bdi dir="ltr">{{ row.marks || "" }}</bdi></td>
              <td v-if="index === 0" class="lesson" :rowspan="rows.length">{{ part.lesson }}</td>
              <template v-if="hasSources && index === 0">
                <td v-for="(cell, c) in sourceCells(part)" :key="c" class="source" :rowspan="rows.length">
                  {{ isolateNumberRanges(cell || "—") }}
                </td>
              </template>
              <td v-if="index === 0" :rowspan="rows.length">
                <span class="badge" :class="`badge-${part.level.toLowerCase()}`"><bdi dir="ltr">{{ KEY_LEVELS[part.level] }}</bdi></span>
              </td>
              <td v-if="hasMarks && index === 0" class="num part-total" :rowspan="rows.length">{{ part.marks || "" }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <footer class="sheet-foot"><span>رقم النموذج {{ paper.seed }}{{ modified ? " (معدّل)" : "" }}</span></footer>
  </article>
</template>

<style scoped>
.key {
  inline-size: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  margin-block-end: var(--space-4);
}
.key caption {
  caption-side: top;
  text-align: start;
  font-weight: var(--weight-bold);
  padding-block: var(--space-2);
}
.key th,
.key td {
  border: 1px solid var(--color-line);
  padding: var(--space-2) var(--space-3);
  text-align: start;
  vertical-align: top;
}
.key thead th {
  background: var(--color-brand);
  color: var(--color-on-brand);
  border-color: var(--color-brand);
  font-weight: var(--weight-bold);
}
.key tbody tr {
  break-inside: avoid;
}
/* كل الأعمدة في الوسط أفقيًا ورأسيًا عدا الإجابة والخطوات (قرار المالك 2026-11-18)، كما في Word */
.key thead th,
.key tbody th,
.key tbody td {
  text-align: center;
  vertical-align: middle;
}
.key tbody .steps-cell {
  text-align: start;
  vertical-align: top;
}
.key tbody th {
  white-space: nowrap;
  color: var(--color-brand-strong);
}
.mcq-key {
  inline-size: auto;
  min-inline-size: 40%;
}
.mcq-key td {
  text-align: center;
  font-weight: var(--weight-bold);
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
/* ترقيم الخطوات «1- 2- 3-» كما في Word؛ عدّاد list-item يحترم start في الصفوف المتتالية */
.steps li::marker {
  /* RLM حول الشرطة يُبقيها يسار الرقم («1-» لا «-1»)، كما في Word */
  content: "\200F" counter(list-item) "\200F-\200F ";
}
.steps.marked {
  margin-block: 0;
  color: var(--color-ink);
}
.final-label {
  font-weight: var(--weight-bold);
  color: var(--color-brand-strong);
}
.source {
  text-align: center;
}
.lesson,
.num {
  white-space: nowrap;
}
.num {
  text-align: center;
}
.key .step-mark,
.key .part-total {
  vertical-align: middle;
}
.part-total {
  font-weight: var(--weight-bold);
}
/* خط الختام بلون الفواصل */
.sheet-foot {
  border-block-start-color: var(--color-line-strong);
}
@media print {
  .answer-key {
    break-before: page;
  }
  /* تذييل الورقة لا ينفرد في صفحة وحده */
  .sheet-foot {
    break-before: avoid;
  }
}
</style>
