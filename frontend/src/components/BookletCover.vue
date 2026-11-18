<script setup lang="ts">
import { computed } from "vue";
import BrandLockup from "@/components/BrandLockup.vue";
import BrandPattern from "@/components/BrandPattern.vue";
import type { Paper } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";
import { isolateNumberRanges } from "@/utils/bidi";
import { durationLabel } from "@/utils/duration";

// غلاف كراسة الاختبار وصفحة تعليماتها على نسق كراسات الوزارة: الغلاف صفحة، والتعليمات الثنائية صفحة.
const props = defineProps<{ header: PaperHeaderData; paper: Paper }>();
const DOTS = "........................................";

const mcqCount = computed(() => props.paper.questions.filter((q) => q.kind === "mcq").length);
const essayCount = computed(() => props.paper.questions.length - mcqCount.value);
const duration = computed(() => (props.header.minutes ? durationLabel(props.header.minutes) : ""));

// ملاحظة التدريب للجدول التوقّعي وحده؛ الجدول الرسمي يغطي الفصل كما أعلنته الوزارة (يطابقه cover_notes في word/builder.py).
const FORECAST_NOTE = "هذا الاختبار للتدريب ولا يغطي جميع موضوعات الفصل.";
const BOOK_NOTE = "الاختبار لا يغني عن الكتاب المدرسي ولا عن الخطة الفصلية.";
const coverNotes = computed(() => (props.paper.is_forecast ? [FORECAST_NOTE, BOOK_NOTE] : [BOOK_NOTE]));

const rules = computed(() => [
  {
    ar: `عدد الأسئلة ${props.paper.questions.length}: ${mcqCount.value} موضوعية و${essayCount.value} مقالية، والدرجة الكلية ${props.header.totalMarks}.`,
    en: `${props.paper.questions.length} items: ${mcqCount.value} multiple-choice and ${essayCount.value} constructed-response, ${props.header.totalMarks} marks in total.`,
  },
  {
    ar: duration.value ? `زمن الاختبار ${duration.value}.` : "",
    en: props.header.minutes ? `Testing time: ${props.header.minutes} minutes.` : "",
  },
  {
    ar: "أجب بقلم أزرق أو أسود، واستعمل قلم الرصاص للرسوم فقط.",
    en: "Answer in blue or black ink; use a pencil for drawings only.",
  },
  {
    ar: "في الأسئلة الموضوعية ضع علامة × في المربع المجاور للإجابة الصحيحة، ولا تختر أكثر من إجابة واحدة.",
    en: "For multiple-choice items, mark × in the box beside the correct answer; choose one answer only.",
  },
  {
    ar: "لتغيير إجابتك املأ المربع الذي اخترته أولًا، ثم ضع × في المربع الجديد.",
    en: "To change an answer, fill in the box you marked first, then mark × in the new box.",
  },
  {
    ar: "في الأسئلة المقالية اكتب الحل في الفراغ المخصص موضحًا خطواته؛ ما يُكتب خارجه لا يُصحَّح.",
    en: "For constructed-response items, write your solution with its steps in the space provided; work outside it is not marked.",
  },
  {
    ar: "الآلة الحاسبة العلمية غير البيانية مسموح بها.",
    en: "A non-graphing scientific calculator is allowed.",
  },
  {
    ar: "لا تقضِ وقتًا طويلًا في سؤال واحد؛ انتقل إلى غيره ثم عد إليه.",
    en: "Do not spend too long on one item; move on and come back to it.",
  },
]);
</script>

<template>
  <section class="cover">
    <div class="cover-pattern" aria-hidden="true"><BrandPattern :tile="140" /></div>
    <BrandLockup :height="78" />
    <div class="org">
      <strong v-if="header.school">{{ header.school }}</strong>
      <span v-if="header.teacher">المعلم: {{ header.teacher }}</span>
    </div>
    <h2 class="exam-title">
      اختبار {{ header.subject }}
      <span v-if="paper.is_forecast">(تدريبي)</span>
    </h2>
    <p class="line">{{ isolateNumberRanges(header.title) }}</p>
    <p v-if="header.grade" class="line">{{ header.grade }}</p>
    <p v-if="header.form" class="line">النموذج {{ header.form }}</p>
    <dl class="facts">
      <div v-if="duration"><dt>زمن الاختبار</dt><dd>{{ duration }}</dd></div>
      <div><dt>الدرجة الكلية</dt><dd>{{ header.totalMarks }} درجة</dd></div>
      <div v-if="header.date"><dt>التاريخ</dt><dd><bdi dir="ltr">{{ header.date }}</bdi></dd></div>
    </dl>
    <p class="student">اسم الطالب: {{ DOTS }}</p>
    <p class="student">الشعبة: {{ header.section || DOTS.slice(0, 16) }}</p>
    <div class="notes">
      <strong>ملاحظات:</strong>
      <ul>
        <li v-for="note in coverNotes" :key="note">{{ note }}</li>
      </ul>
    </div>
  </section>

  <section class="instructions">
    <h3 class="heading">
      <span>تعليمات عامة</span>
      <span dir="ltr" lang="en">General instructions</span>
    </h3>
    <div class="columns">
      <ul class="rules">
        <template v-for="rule in rules" :key="rule.en">
          <li v-if="rule.ar">{{ rule.ar }}</li>
        </template>
      </ul>
      <ul class="rules" dir="ltr" lang="en">
        <template v-for="rule in rules" :key="rule.en">
          <li v-if="rule.en">{{ rule.en }}</li>
        </template>
      </ul>
    </div>
    <div class="marking">
      <div class="sample">
        <span class="mark-box x" aria-hidden="true">×</span>
        <span>إجابة صحيحة التأشير</span>
        <span dir="ltr" lang="en">Correctly marked</span>
      </div>
      <div class="sample">
        <span class="mark-box filled" aria-hidden="true" />
        <span class="mark-box x" aria-hidden="true">×</span>
        <span>إجابة مغيَّرة: المملوء ملغى والمؤشَّر معتمد</span>
        <span dir="ltr" lang="en">Changed answer: the filled box is cancelled</span>
      </div>
      <div class="sample">
        <span class="mark-box x" aria-hidden="true">×</span>
        <span class="mark-box x" aria-hidden="true">×</span>
        <span>علامتان: لا تُحتسب الإجابة</span>
        <span dir="ltr" lang="en">Two marks: no credit</span>
      </div>
    </div>
    <p v-if="header.instructions" class="teacher-note"><strong>تعليمات المعلم:</strong> {{ header.instructions }}</p>
  </section>
</template>

<style scoped>
/* شريط النمط على حافة الغلاف العليا: خارج مجرى المحتوى (absolute) فلا يغيّر ارتفاع الغلاف، وفوق الشعار لا خلفه */
.cover-pattern {
  position: absolute;
  inset-inline: 0;
  inset-block-start: 0;
  block-size: 18mm;
  overflow: hidden;
}
.cover {
  position: relative;
  display: grid;
  justify-items: center;
  text-align: center;
  gap: var(--space-4);
  padding-block: calc(18mm + var(--space-4)) var(--space-8);
  border-block-end: 3px solid var(--color-brand);
  margin-block-end: var(--space-6);
  /* الغلاف يملأ معظم صفحته ومحتواه في وسطها؛ على الورق يحسبها المتصفح من ارتفاع الصفحة نفسها */
  min-block-size: calc(0.7 * (var(--page-height) - var(--page-margin-block-start) - var(--page-margin-block-end)));
  align-content: center;
}
.org {
  display: grid;
  gap: var(--space-1);
  font-size: var(--print-small);
}
.exam-title {
  margin: var(--space-6) 0 0;
  font-size: 26pt;
  color: var(--color-brand-strong);
}
/* شريط ذهبي قصير تحت عنوان الغلاف: تزيين الهوية */
.exam-title::after {
  content: "";
  display: block;
  inline-size: 84px;
  block-size: 4px;
  margin: var(--space-3) auto 0;
  background: var(--color-accent);
}
.line {
  margin: 0;
  font-size: var(--print-title);
  font-weight: var(--weight-medium);
}
/* بيانات الاختبار صندوق واحد بخانات: التسمية بالعنابي فوق القيمة */
.facts {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  margin: var(--space-4) 0 0;
  border: 1px solid var(--color-brand);
  background: var(--color-brand-soft);
  font-size: var(--print-small);
}
.facts div {
  display: grid;
  justify-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-8);
  border-inline-start: 1px solid var(--color-brand);
}
.facts div:first-child {
  border-inline-start: 0;
}
.facts dt {
  font-size: var(--text-xs);
  color: var(--color-brand-strong);
}
.facts dd {
  margin: 0;
  font-weight: var(--weight-bold);
}
.student {
  margin: 0;
  font-size: var(--print-title);
}
.notes {
  justify-self: start;
  text-align: start;
  margin-block-start: var(--space-8);
}
.notes ul {
  margin: var(--space-1) 0 0;
  padding-inline-start: var(--space-5);
}
.instructions {
  border-block-end: 3px solid var(--color-brand);
  padding-block-end: var(--space-4);
  margin-block-end: var(--space-6);
}
.heading {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  margin: 0 0 var(--space-3);
  padding-block-end: var(--space-2);
  border-block-end: 2px solid var(--color-brand);
  font-size: var(--text-lg);
  color: var(--color-brand-strong);
}
.columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-6);
}
.rules {
  margin: 0;
  padding-inline-start: var(--space-5);
  font-size: var(--print-small);
  line-height: 1.7;
}
.marking {
  display: grid;
  gap: var(--space-2);
  margin-block-start: var(--space-4);
  padding: var(--space-3);
  border: 1px solid var(--color-line);
  border-inline-start: 4px solid var(--color-accent);
  border-radius: var(--radius-sm);
  font-size: var(--print-small);
}
.sample {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.sample [lang="en"] {
  margin-inline-start: auto;
}
.mark-box {
  display: inline-grid;
  place-items: center;
  inline-size: 16px;
  block-size: 16px;
  border: 1.5px solid var(--color-ink);
  border-radius: 2px;
  font-weight: var(--weight-bold);
  line-height: 1;
}
.mark-box.filled {
  background: var(--color-ink);
}
.teacher-note {
  margin: var(--space-3) 0 0;
  font-size: var(--print-small);
}
@media print {
  .cover,
  .instructions {
    break-after: page;
    border-block-end: 0;
    margin-block-end: 0;
  }
  .cover {
    min-block-size: 70vh;
  }
}
</style>
