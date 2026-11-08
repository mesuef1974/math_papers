<script setup lang="ts">
import { computed, watchEffect } from "vue";
import BookletCover from "@/components/BookletCover.vue";
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import PaperHeader from "@/components/PaperHeader.vue";
import ScoreTable from "@/components/ScoreTable.vue";
import { LEVEL_NAMES, type Paper, type Question } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { marksLabel } from "@/utils/marks";

// hideSheet: في الحزمة تُطبع المفاتيح كلها في آخرها، فتُعرض الورقة في موضعها ومفتاحها لاحقًا.
// replaceable: زر استبدال لكل جزء (شاشة فقط)؛ replacing بصمة الجزء الجاري استبداله؛ modified بعد أي استبدال.
// الاختبار يُخرج كراسةً على نسق كراسات الوزارة (غلاف، تعليمات ثنائية، صناديق حل بدرجاتها، جدول رصد)،
// وورقة العمل والاختبار القصير يبقيان ورقة واحدة بترويسة.
const props = withDefaults(
  defineProps<{
    paper: Paper;
    header: PaperHeaderData;
    showKey: boolean;
    hideSheet?: boolean;
    replaceable?: boolean;
    replacing?: string;
    modified?: boolean;
  }>(),
  { hideSheet: false, replaceable: false, replacing: "", modified: false },
);
const emit = defineEmits<{ replace: [question: number, label: string] }>();

const OPTION_LABELS = ["أ", "ب", "ج", "د"];
const booklet = computed(() => props.paper.kind === "exam");
const keyTitle = computed(() => (booklet.value ? "دليل تقدير الدرجات" : "مفتاح الحل"));

// جدول الإجابات الموضوعية في المفتاح: رقم كل سؤال وحرف إجابته.
const mcqAnswers = computed(() =>
  props.paper.questions
    .filter((q) => q.kind === "mcq" && (q.parts[0]?.answer_index ?? -1) >= 0)
    .map((q) => ({ number: q.number, letter: OPTION_LABELS[q.parts[0].answer_index] })),
);
const lastMcq = computed(() => props.paper.questions.filter((q) => q.kind === "mcq").at(-1)?.number ?? 0);

// تعليمات كل قسم كما في كراسات الوزارة: قبل أول سؤال موضوعي وقبل أول سؤال مقالي، بنطاق أرقامه وبلغتين.
const sectionNotes = computed(() => {
  const notes = new Map<number, { ar: string; en: string }>();
  const kinds: Question["kind"][] = ["mcq", "essay"];
  for (const kind of kinds) {
    const group = props.paper.questions.filter((q) => q.kind === kind);
    if (!group.length || group.length === props.paper.questions.length) continue;
    const first = group[0].number;
    const last = group[group.length - 1].number;
    const range = first === last ? `السؤال ${first}` : `كل سؤال من ${first} إلى ${last}`;
    const rangeEn = first === last ? `question ${first}` : `questions ${first} through ${last}`;
    notes.set(
      first,
      kind === "mcq"
        ? {
            ar: `اختر الإجابة الصحيحة لـ${range} بوضع علامة × في المربع المجاور للإجابة الصحيحة.`,
            en: `Choose the correct answer for ${rangeEn} by putting × in the box beside it.`,
          }
        : {
            ar: `أجب عن ${range} في الفراغ المخصص، مبيّنًا خطوات الحل.`,
            en: `For ${rangeEn}, write your answer in the space provided and show your work.`,
          },
    );
  }
  return notes;
});

// ارتفاع صندوق الحل بالدرجات: يبدأ من صندوق قصير ويتسع حتى ثلث الصفحة.
function workHeight(marks: number): string {
  return `${Math.min(Math.max(60 + marks * 45, 96), 300)}px`;
}

// سطر التذييل الجاري في كل صفحة مطبوعة (يقرؤه print.css في صندوق هامش الصفحة).
watchEffect(() => {
  if (typeof document === "undefined") return;
  const footer = booklet.value
    ? [props.header.subject, props.header.title, props.header.grade].filter(Boolean).join(" – ")
    : "";
  document.documentElement.style.setProperty("--print-footer", JSON.stringify(footer));
});
</script>

<template>
  <article v-if="!hideSheet" class="sheet" :class="{ booklet }">
    <BookletCover v-if="booklet" :header="header" :paper="paper" />
    <PaperHeader v-else :header="header" />

    <section v-for="question in paper.questions" :key="question.number" class="question" :class="question.kind">
      <p v-if="sectionNotes.has(question.number)" class="section-note">
        <span>{{ sectionNotes.get(question.number)?.ar }}</span>
        <span v-if="booklet" class="en" dir="ltr" lang="en">{{ sectionNotes.get(question.number)?.en }}</span>
      </p>
      <div class="question-head">
        <span v-if="booklet" class="number">{{ question.number }}</span>
        <strong v-else>السؤال {{ question.number }}</strong>
        <span v-if="question.marks" class="marks">{{ marksLabel(question.marks) }}{{ booklet && question.kind === "essay" ? " /" : "" }}</span>
        <span v-if="booklet && question.kind === 'essay'" class="score-cell" aria-hidden="true" />
      </div>
      <div v-for="part in question.parts" :key="part.fingerprint" class="part">
        <p class="stem">
          <bdi v-if="part.label" class="part-label">{{ part.label }}.</bdi>
          <MathText :text="part.stem" />
          <span v-if="part.label && !booklet" class="marks">({{ part.marks }})</span>
        </p>
        <GraphPlot v-if="part.graph" :graph="part.graph" :compact="booklet" />
        <ol v-if="part.options.length" class="options">
          <li v-for="(option, index) in part.options" :key="index" :class="{ 'graph-option': part.option_graphs.length }">
            <span class="box" aria-hidden="true" />
            <span class="option-label">{{ OPTION_LABELS[index] }})</span>
            <GraphPlot v-if="part.option_graphs[index]" :graph="part.option_graphs[index]" compact />
            <MathText v-else :text="option" />
          </li>
        </ol>
        <div v-else-if="booklet" class="work">
          <p class="work-label">
            <span>وضح خطوات الحل</span>
            <span dir="ltr" lang="en">Show your work</span>
          </p>
          <div class="work-box" :style="{ minBlockSize: workHeight(part.marks) }" />
          <span class="part-marks" :aria-label="`الدرجة ${part.marks}`">{{ part.marks }}</span>
        </div>
        <div v-else class="work-space" :data-lines="Math.min(Math.max(part.marks, 2), 6)" />
        <div v-if="replaceable" class="part-tools no-print">
          <button
            type="button"
            class="btn btn-secondary btn-small"
            :disabled="replacing !== ''"
            :aria-label="`استبدال السؤال ${question.number}${part.label ? ' ' + part.label : ''}`"
            @click="emit('replace', question.number, part.label)"
          >
            {{ replacing === part.fingerprint ? "جارٍ الاستبدال" : "استبدال بمسألة أخرى" }}
          </button>
        </div>
      </div>
      <p v-if="booklet && question.number === lastMcq && lastMcq < paper.questions.length" class="section-end">
        <span>انتهت الأسئلة الموضوعية</span>
        <span dir="ltr" lang="en">End of multiple-choice questions</span>
      </p>
    </section>
    <footer class="sheet-foot">
      <span v-if="booklet" class="section-end end-all">
        <span>انتهت جميع الأسئلة</span>
        <span dir="ltr" lang="en">End of all questions</span>
      </span>
      <span v-else>انتهت الأسئلة</span>
      <span>رقم النموذج {{ paper.seed }}{{ modified ? " (معدّل)" : "" }}</span>
    </footer>
    <ScoreTable v-if="booklet" :paper="paper" />
  </article>

  <article v-if="showKey" class="sheet answer-key">
    <PaperHeader :header="{ ...header, title: `${keyTitle}: ${header.title}` }" compact />
    <table v-if="mcqAnswers.length" class="key mcq-key">
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
          <td>{{ row.letter }}</td>
        </tr>
      </tbody>
    </table>
    <table class="key">
      <caption v-if="mcqAnswers.length">الحلول والخطوات بدرجاتها</caption>
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
    <footer class="sheet-foot"><span>رقم النموذج {{ paper.seed }}{{ modified ? " (معدّل)" : "" }}</span></footer>
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
  display: grid;
  gap: var(--space-1);
  margin-block: var(--space-2) var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-sunken);
  border-inline-start: 3px solid var(--color-ink);
  font-size: var(--text-sm);
}
.question {
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
  break-after: avoid;
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
  break-inside: avoid;
}
.stem {
  margin-block: var(--space-2);
}
.part-tools {
  display: flex;
  justify-content: flex-end;
  margin-block-start: var(--space-2);
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
/* مساحة الحل في أوراق العمل تتدرج مع الدرجات (سطر 34px لكل درجة، من 2 إلى 6) */
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

/* الكراسة: رقم السؤال في مربع بالهامش، الخيارات عمودية، صندوق حل بدرجته، وفواصل الأقسام بلغتين */
.booklet .question {
  border-block-end: 0;
  padding-block: var(--space-4) var(--space-2);
}
.booklet .question-head {
  justify-content: flex-start;
  align-items: center;
}
.number {
  display: inline-grid;
  place-items: center;
  min-inline-size: 30px;
  block-size: 30px;
  padding-inline: var(--space-1);
  border: 1.5px solid var(--color-ink);
  font-weight: var(--weight-bold);
}
.booklet .essay .question-head {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-ink);
  background: var(--color-surface-sunken);
}
.booklet .essay .marks {
  margin-inline-start: auto;
  color: var(--color-ink);
}
.score-cell {
  inline-size: 56px;
  block-size: 26px;
  border: 1px solid var(--color-ink);
  background: var(--color-surface);
}
.booklet .options {
  grid-template-columns: minmax(0, 1fr);
  padding-inline-start: var(--space-8);
}
.booklet .stem {
  margin-block: var(--space-3) var(--space-2);
}
.work {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    "label label"
    "box marks";
  column-gap: var(--space-2);
  align-items: start;
  margin-block: var(--space-2) var(--space-3);
}
.work-label {
  grid-area: label;
  display: flex;
  justify-content: space-between;
  margin: 0 0 var(--space-1);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}
.work-box {
  grid-area: box;
  border: 1.5px solid var(--color-ink);
}
.part-marks {
  grid-area: marks;
  display: inline-grid;
  place-items: center;
  inline-size: 28px;
  block-size: 28px;
  border: 1px solid var(--color-ink);
  font-size: var(--text-sm);
  align-self: end;
}
.section-end {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  margin: var(--space-6) 0 0;
  font-weight: var(--weight-bold);
}
.end-all {
  flex: 1 1 auto;
  margin: 0;
  margin-inline-end: var(--space-6);
}

/* المفتاح: جداول */
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
  /* القسم المقالي يبدأ صفحة جديدة كما في الكراسة */
  .booklet .mcq + .essay {
    break-before: page;
  }
  .answer-key {
    break-before: page;
  }
}
</style>
