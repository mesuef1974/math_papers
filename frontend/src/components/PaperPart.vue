<script setup lang="ts">
import ErrorSpottingPart from "@/components/ErrorSpottingPart.vue";
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import type { Part } from "@/stores/papers";
import { OPTION_LABELS } from "@/utils/options";

// جزء من سؤال: نصه ورسمه، ثم بدائله أو مساحة حله (صندوق بدرجته في الكراسة، وأسطر منقّطة في ورقة العمل).
// زر الاستبدال (شاشة فقط) في هامش الصفحة خارج مجرى المحتوى، فلا يغيّر ارتفاع الجزء عمّا يُطبع.
const props = withDefaults(
  defineProps<{
    part: Part;
    number: number; // رقم السؤال، لتسمية زر الاستبدال
    booklet: boolean;
    replaceable?: boolean;
    replacing?: string; // بصمة الجزء الجاري استبداله
  }>(),
  { replaceable: false, replacing: "" },
);
const emit = defineEmits<{ replace: [label: string] }>();

// خيارات قصيرة (أعداد وصيغ) تُصفّ في عمودين حتى في الكراسة؛ الطويلة وحدها تبقى عمودًا واحدًا.
const SHORT_OPTION = 26;
const shortOptions = () =>
  props.part.option_graphs.length === 0 && props.part.options.every((option) => option.length <= SHORT_OPTION);

// ارتفاع صندوق الحل بالدرجات: يبدأ من صندوق قصير ويتسع حتى ثلث الصفحة.
function workHeight(marks: number): string {
  return `${Math.min(Math.max(60 + marks * 45, 96), 300)}px`;
}

// أسطر مساحة الحل: سطر لكل درجة وسطر زائد (3 إلى 6)، وأربعة حين لا درجات (ورقة العمل)،
// وستة على الأقل بجانب الرسم ليملأ ارتفاعه. السطر الأخير بلا خط: يغلقه فاصل السؤال فلا يتجاور خطان.
function workLines(): number {
  const lines = Math.min(Math.max((props.part.marks || 3) + 1, 3), 6);
  return props.part.graph ? Math.max(lines, 6) : lines;
}
</script>

<template>
  <div class="part" :class="{ side: !booklet && part.graph && !part.options.length }">
    <p class="stem">
      <bdi v-if="part.label" class="part-label" dir="rtl">{{ part.label }}.</bdi>
      <MathText :text="part.stem" />
      <span v-if="part.label && !booklet" class="marks">({{ part.marks }})</span>
    </p>
    <GraphPlot v-if="part.graph" :graph="part.graph" :compact="booklet" />
    <ErrorSpottingPart v-if="part.spotting" :steps="part.spotting.steps" />
    <ol
      v-if="part.options.length"
      class="options"
      :class="{ 'options-short': shortOptions(), 'options-graphs': part.option_graphs.length > 0 }"
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
    <div v-else class="work-space" :data-lines="workLines()" aria-hidden="true">
      <span v-for="line in workLines()" :key="line" class="rule" />
    </div>
    <div v-if="replaceable" class="part-tools no-print">
      <button
        type="button"
        class="btn btn-secondary btn-small"
        title="استبدال بمسألة أخرى"
        :disabled="replacing !== ''"
        :aria-busy="replacing === part.fingerprint"
        :aria-label="`استبدال السؤال ${number}${part.label ? ' ' + part.label : ''}`"
        @click="emit('replace', part.label)"
      >
        {{ replacing === part.fingerprint ? "جارٍ" : "بدّل" }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.part {
  position: relative; /* مرجع زر الاستبدال في الهامش */
  break-inside: avoid;
}
.stem {
  margin-block: var(--space-2);
}
.booklet .stem {
  margin-block: var(--space-3) var(--space-2);
}
.part-label {
  display: inline-block;
  font-weight: var(--weight-bold);
  color: var(--color-brand-strong);
  /* الوسم يُقرأ بترقيم عربي (‎.A‎ بصريًا: الحرف يمينًا ثم النقطة) وبعده مسافة قبل نص السؤال */
  margin-inline-end: var(--space-3);
  min-inline-size: 1.3em;
}
/*
  زر الاستبدال في هامش الصفحة عند نهاية السطر، خارج مجرى المحتوى. يعاكس تصغير الورقة فيبقى بحجم اللمس
  على الشاشات الضيقة، وإزاحته مضروبة في التصغير نفسه ليبقى ملاصقًا لحافة الورقة.
*/
.part-tools {
  position: absolute;
  inset-block-start: 0;
  inset-inline-end: calc(-1 * var(--page-margin-inline) * var(--paper-zoom));
  zoom: calc(1 / var(--paper-zoom));
}
.part-tools .btn {
  padding-inline: var(--space-2);
  background: var(--color-sheet);
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
.part.side > .stem {
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
/* الرسم المجاور لأسطر الحل أصغر قليلًا، فتتسع ثلاثة أسئلة بيانية في الصفحة */
.part.side :deep(svg) {
  max-block-size: 50mm;
}

/* الكراسة: الخيارات عمودية وصندوق حل بدرجته */
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
@media print {
  .options li {
    break-inside: avoid;
  }
}
</style>
