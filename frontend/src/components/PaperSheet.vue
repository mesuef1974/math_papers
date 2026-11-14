<script setup lang="ts">
import { computed, onMounted, watchEffect } from "vue";
import AnswerKey from "@/components/AnswerKey.vue";
import BookletCover from "@/components/BookletCover.vue";
import PaperHeader from "@/components/PaperHeader.vue";
import PaperQuestion from "@/components/PaperQuestion.vue";
import ScoreTable from "@/components/ScoreTable.vue";
import type { Paper, Question } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { ensurePrintFonts } from "@/utils/printFonts";

// الورقة ومفتاحها. الأسئلة في PaperQuestion وأجزاؤها في PaperPart والمفتاح في AnswerKey.
// الورقة على الشاشة بقواعد الورق نفسها (نطاق .sheet في styles/print.css): ما يُرى هو ما يُطبع.
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

// الورقة ظهرت على الشاشة: يُحمَّل خط الطباعة مسبقًا، فهو خط عرضها أيضًا
onMounted(() => void ensurePrintFonts());

const booklet = computed(() => props.paper.kind === "exam");
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

    <PaperQuestion
      v-for="question in paper.questions"
      :key="question.number"
      :question="question"
      :booklet="booklet"
      :note="sectionNotes.get(question.number)"
      :ends-mcq="booklet && question.number === lastMcq && lastMcq < paper.questions.length"
      :replaceable="replaceable"
      :replacing="replacing"
      @replace="(number, label) => emit('replace', number, label)"
    />
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

  <AnswerKey v-if="showKey" :paper="paper" :header="header" :modified="modified" />
</template>

<style scoped>
/* فواصل الأقسام بلغتين: ختام الموضوعي داخل السؤال، وختام الورقة في تذييلها */
.sheet :deep(.section-end) {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  margin: var(--space-6) 0 0;
  font-weight: var(--weight-bold);
}
.sheet .end-all {
  flex: 1 1 auto;
  margin: 0;
  margin-inline-end: var(--space-6);
}
/* خط الختام بلون الفواصل: يغلق مساحة حل السؤال الأخير */
.sheet:not(.booklet) .sheet-foot {
  border-block-start-color: var(--color-line-strong);
}
@media print {
  /* تذييل الورقة لا ينفرد في صفحة وحده */
  .sheet-foot {
    break-before: avoid;
  }
}
</style>
