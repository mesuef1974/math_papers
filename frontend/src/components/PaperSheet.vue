<script setup lang="ts">
import { computed, onMounted, watchEffect } from "vue";
import BookletCover from "@/components/BookletCover.vue";
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import PaperHeader from "@/components/PaperHeader.vue";
import ScoreTable from "@/components/ScoreTable.vue";
import { LEVEL_NAMES, type Paper, type Part, type Question } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { marksLabel } from "@/utils/marks";
import { ensurePrintFonts } from "@/utils/printFonts";

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
    runningFooter?: boolean; // الحزمة تضبط تذييلها الجاري بنفسها، فتعطّل تذييل كل ورقة
  }>(),
  { hideSheet: false, replaceable: false, replacing: "", modified: false, runningFooter: true },
);
const emit = defineEmits<{ replace: [question: number, label: string] }>();

// الورقة ظهرت على الشاشة: يُحمَّل خط الطباعة مسبقًا ليكون جاهزًا عند فتح نافذة الطباعة
onMounted(() => void ensurePrintFonts());

// حروف لاتينية من اليسار إلى اليمين كما في أوراق الاختبار المطبوعة.
const OPTION_LABELS = ["A", "B", "C", "D"];
const booklet = computed(() => props.paper.kind === "exam");
const keyTitle = computed(() => (booklet.value ? "دليل تقدير الدرجات" : "مفتاح الحل"));

// جدول الإجابات الموضوعية في المفتاح: رقم كل سؤال وحرف إجابته.
const mcqAnswers = computed(() =>
  props.paper.questions
    .filter((q) => q.kind === "mcq" && (q.parts[0]?.answer_index ?? -1) >= 0)
    .map((q) => ({ number: q.number, letter: OPTION_LABELS[q.parts[0].answer_index] })),
);
// أوراق العمل بلا درجات، فلا يُعرض لها عمود درجة فارغ في المفتاح.
const hasMarks = computed(() => props.paper.questions.some((q) => q.parts.some((p) => p.marks > 0)));

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

// خيارات قصيرة (أعداد وصيغ) تُصفّ في عمودين حتى في الكراسة؛ الطويلة وحدها تبقى عمودًا واحدًا.
const SHORT_OPTION = 26;
const shortOptions = (part: Question["parts"][number]) =>
  part.option_graphs.length === 0 && part.options.every((option) => option.length <= SHORT_OPTION);

// ارتفاع صندوق الحل بالدرجات: يبدأ من صندوق قصير ويتسع حتى ثلث الصفحة.
function workHeight(marks: number): string {
  return `${Math.min(Math.max(60 + marks * 45, 96), 300)}px`;
}

// أسطر مساحة الحل: سطر لكل درجة وسطر زائد (3 إلى 6)، وأربعة حين لا درجات (ورقة العمل)،
// وستة على الأقل بجانب الرسم ليملأ ارتفاعه. السطر الأخير بلا خط: يغلقه فاصل السؤال فلا يتجاور خطان.
function workLines(part: Question["parts"][number]): number {
  const lines = Math.min(Math.max((part.marks || 3) + 1, 3), 6);
  return part.graph ? Math.max(lines, 6) : lines;
}

// سطر التذييل الجاري في كل صفحة مطبوعة (يقرؤه print.css في صندوق هامش الصفحة).
watchEffect(() => {
  if (typeof document === "undefined" || !props.runningFooter) return;
  const footer = booklet.value
    ? [props.header.subject, props.header.title, props.header.grade].filter(Boolean).join(" – ")
    : props.header.title;
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
      <div
        v-for="part in question.parts"
        :key="part.fingerprint"
        class="part"
        :class="{ side: !booklet && part.graph && !part.options.length }"
      >
        <p class="stem">
          <bdi v-if="part.label" class="part-label" dir="rtl">{{ part.label }}.</bdi>
          <MathText :text="part.stem" />
          <span v-if="part.label && !booklet" class="marks">({{ part.marks }})</span>
        </p>
        <GraphPlot v-if="part.graph" :graph="part.graph" :compact="booklet" />
        <ol
          v-if="part.options.length"
          class="options"
          :class="{ 'options-short': shortOptions(part), 'options-graphs': part.option_graphs.length > 0 }"
        >
          <li v-for="(option, index) in part.options" :key="index" :class="{ 'graph-option': part.option_graphs.length }">
            <span class="box" aria-hidden="true" />
            <bdi class="option-label" dir="ltr">{{ OPTION_LABELS[index] }}.</bdi>
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
        <div v-else class="work-space" :data-lines="workLines(part)" aria-hidden="true">
          <span v-for="line in workLines(part)" :key="line" class="rule" />
        </div>
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
              <td>
                <p v-if="row.plain || row.final" class="answer">
                  <span v-if="row.final" class="final-label">الجواب النهائي: </span><MathText :text="part.answer" />
                </p>
                <ol v-if="row.steps.length" class="steps" :class="{ marked: !row.plain }" :start="row.start">
                  <li v-for="step in row.steps" :key="step"><MathText :text="step" /></li>
                </ol>
              </td>
              <td v-if="hasMarks" class="num step-mark"><bdi dir="ltr">{{ row.marks || "" }}</bdi></td>
              <td v-if="index === 0" class="lesson" :rowspan="rows.length">{{ part.lesson }}</td>
              <td v-if="index === 0" :rowspan="rows.length">
                <span class="badge" :class="`badge-${part.level.toLowerCase()}`">{{ LEVEL_NAMES[part.level] }}</span>
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
.sheet {
  background: var(--color-sheet);
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
  background: var(--color-brand-soft);
  border-inline-start: 4px solid var(--color-brand);
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
/* رقم السؤال شارة مصمتة بلون الهوية، على الشاشة والورق */
.question-head strong {
  background: var(--color-brand);
  color: var(--color-on-brand);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
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
  color: var(--color-brand-strong);
  /* الوسم يُقرأ بترقيم عربي (‎.A‎ بصريًا: الحرف يمينًا ثم النقطة) وبعده مسافة قبل نص السؤال */
  margin-inline-end: var(--space-3);
  min-inline-size: 1.3em;
}
.options {
  direction: ltr; /* A يسارًا ثم B، فالسطر التالي */
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
  font-weight: var(--weight-bold);
  color: var(--color-brand-strong);
}
/* مساحة الحل في أوراق العمل: أسطر منقّطة للكتابة، سطر لكل درجة (2 إلى 6) */
.work-space {
  display: grid;
  margin-block: var(--space-1) var(--space-2);
}
.rule {
  display: block;
  block-size: 30px;
  border-block-end: 1px dotted var(--color-line-strong);
}
.rule:last-child {
  border-block-end: 0;
}
/* سؤال برسم بلا بدائل: الرسم في جهة وأسطر الحل بجانبه، فلا يضيع عرض الصفحة */
.part.side {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: var(--space-6);
  align-items: start;
}
.part.side > .stem,
.part.side > .part-tools {
  grid-column: 1 / -1;
}
.part.side > .graph {
  grid-column: 2;
  grid-row: 2;
}
/* أسطر الحل تتوزع على ارتفاع الرسم المجاور */
.part.side > .work-space {
  grid-column: 1;
  grid-row: 2;
  align-self: stretch;
  grid-auto-rows: 1fr;
}
.part.side .rule {
  block-size: auto;
  min-block-size: 30px;
}
@media (max-width: 560px) {
  .part.side {
    grid-template-columns: minmax(0, 1fr);
  }
  .part.side > .graph,
  .part.side > .work-space {
    grid-column: 1;
    grid-row: auto;
  }
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
  border: 1.5px solid var(--color-brand);
  background: var(--color-brand-soft);
  color: var(--color-brand-strong);
  font-weight: var(--weight-bold);
}
.booklet .essay .question-head {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-brand);
  background: var(--color-brand-soft);
}
.booklet .essay .number {
  background: var(--color-sheet);
}
.booklet .essay .marks {
  margin-inline-start: auto;
  color: var(--color-ink);
}
.score-cell {
  inline-size: 56px;
  block-size: 26px;
  border: 1px solid var(--color-ink);
  background: var(--color-sheet);
}
.booklet .options {
  grid-template-columns: minmax(0, 1fr);
  padding-inline-start: var(--space-8);
}
/* الخيارات القصيرة وخيارات الرسوم عمودان في الكراسة أيضًا: A B ثم C D، فتتسع الصفحة لأسئلة أكثر */
.booklet .options-short,
.booklet .options-graphs {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: var(--space-8);
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
  background: var(--color-brand);
  color: var(--color-on-brand);
  border-color: var(--color-brand);
  font-weight: var(--weight-bold);
}
.key tbody tr {
  break-inside: avoid;
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
.steps.marked {
  margin-block: 0;
  color: var(--color-ink);
}
.final-label {
  font-weight: var(--weight-bold);
  color: var(--color-brand-strong);
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
@media (max-width: 560px) {
  .sheet {
    padding: var(--space-4);
  }
  .options {
    grid-template-columns: minmax(0, 1fr);
  }
  /* الجوال: خط وخانات أصغر حتى يتسع عمود الإجابة، وما زاد يُمرَّر داخل إطار الجدول */
  .key {
    font-size: var(--text-xs);
  }
  .key th,
  .key td {
    padding: var(--space-1) var(--space-2);
  }
  .steps {
    padding-inline-start: var(--space-4);
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
  .options li {
    break-inside: avoid;
  }
  /* سؤال الاختيار من متعدد كتلة واحدة: نصه وبدائله في الصفحة نفسها */
  .question.mcq {
    break-inside: avoid;
  }
  /* خط مستقيم بعرض المحتوى كاملًا بين كل سؤال والذي يليه */
  .question,
  .booklet .question {
    border-block-end: 1px solid var(--color-line-strong);
  }
  .question:last-of-type {
    border-block-end: 0;
  }
  /* القسم المقالي يبدأ صفحة جديدة كما في الكراسة */
  .booklet .mcq + .essay {
    break-before: page;
  }
  .answer-key {
    break-before: page;
  }
  /* تذييل الورقة لا ينفرد في صفحة وحده */
  .sheet-foot {
    break-before: avoid;
  }
  /* خط الختام بلون الفواصل: يغلق مساحة حل السؤال الأخير */
  .sheet:not(.booklet) .sheet-foot {
    border-block-start-color: var(--color-line-strong);
  }
  /* الرسم المجاور لأسطر الحل أصغر قليلًا، فتتسع ثلاثة أسئلة بيانية في الصفحة */
  .part.side :deep(svg) {
    max-block-size: 50mm;
  }
  .question:last-of-type {
    break-after: avoid;
  }
}
</style>
