<script setup lang="ts">
import PaperPart from "@/components/PaperPart.vue";
import type { Question } from "@/stores/papers";
import { marksLabel } from "@/utils/marks";

// سؤال في الورقة: تعليمات قسمه إن كان أوله، ثم رأسه (شارة رقمه ودرجته)، ثم أجزاؤه، ثم ختام القسم الموضوعي.
withDefaults(
  defineProps<{
    question: Question;
    booklet: boolean;
    note?: { ar: string; en: string }; // تعليمات القسم قبل أول سؤال فيه
    endsMcq?: boolean; // آخر سؤال موضوعي وبعده مقالي
    replaceable?: boolean;
    replacing?: string;
  }>(),
  { note: undefined, endsMcq: false, replaceable: false, replacing: "" },
);
const emit = defineEmits<{ replace: [question: number, label: string] }>();
</script>

<template>
  <section class="question" :class="question.kind">
    <p v-if="note" class="section-note">
      <span>{{ note.ar }}</span>
      <span v-if="booklet" class="en" dir="ltr" lang="en">{{ note.en }}</span>
    </p>
    <div class="question-head">
      <span v-if="booklet" class="number">{{ question.number }}</span>
      <strong v-else>السؤال {{ question.number }}</strong>
      <span v-if="question.marks" class="marks">{{ marksLabel(question.marks) }}{{ booklet && question.kind === "essay" ? " /" : "" }}</span>
      <span v-if="booklet && question.kind === 'essay'" class="score-cell" aria-hidden="true" />
    </div>
    <PaperPart
      v-for="part in question.parts"
      :key="part.fingerprint"
      :part="part"
      :number="question.number"
      :booklet="booklet"
      :replaceable="replaceable"
      :replacing="replacing"
      @replace="(label) => emit('replace', question.number, label)"
    />
    <p v-if="endsMcq" class="section-end">
      <span>انتهت الأسئلة الموضوعية</span>
      <span dir="ltr" lang="en">End of multiple-choice questions</span>
    </p>
  </section>
</template>

<style scoped>
/* خط مستقيم بعرض المحتوى كاملًا بين كل سؤال والذي يليه، على الشاشة والورق */
.question {
  padding-block: var(--space-3);
  border-block-end: 1px solid var(--color-line-strong);
}
.booklet .question {
  padding-block: var(--space-4) var(--space-2);
}
.question:last-of-type {
  border-block-end: 0;
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
.question-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--space-3);
  break-after: avoid;
}
/* رقم السؤال شارة مصمتة بلون الهوية */
.question-head strong {
  background: var(--color-brand);
  color: var(--color-on-brand);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}
/* درجة السؤال في رأسه ودرجة الجزء بعد نصه */
.question :deep(.marks) {
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}

/* الكراسة: رقم السؤال في مربع، ورأس المقالي شريط بدرجته وخانة رصدها */
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
.booklet .essay .question-head .marks {
  margin-inline-start: auto;
  color: var(--color-ink);
}
.score-cell {
  inline-size: 56px;
  block-size: 26px;
  border: 1px solid var(--color-ink);
  background: var(--color-sheet);
}
@media print {
  /* سؤال الاختيار من متعدد كتلة واحدة: نصه وبدائله في الصفحة نفسها */
  .question.mcq {
    break-inside: avoid;
  }
  /* القسم المقالي يبدأ صفحة جديدة كما في الكراسة */
  .booklet .mcq + .essay {
    break-before: page;
  }
  .question:last-of-type {
    break-after: avoid;
  }
}
</style>
