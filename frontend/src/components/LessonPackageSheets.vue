<script setup lang="ts">
import { bookRef } from "@/utils/bookRef";
import GraphPlot from "@/components/GraphPlot.vue";
import MathText from "@/components/MathText.vue";
import PaperHeader from "@/components/PaperHeader.vue";
import type { PaperHeaderData, PrintProfile } from "@/stores/print";
import type { LessonPackage, PackageEntry, PackageSheet } from "@/types/lessonPackage";

// باقة الحصة المطبوعة: ورقة لكل نوع في صفحتها ثم مفتاح الإجابة. تمرين الكتاب برقمه وصفحته وحدهما.
// حروف بدائل بنود الفحص والخروج عربية بترتيبها كما في العرض وإدخال النتائج.
const props = defineProps<{ pack: LessonPackage; profile: PrintProfile; date: string; section: string }>();

const LETTERS = ["أ", "ب", "ج", "د"];
const DOTS = "....................";
const BOOK_ANSWER = "الإجابة في دليل المعلم";

function header(sheet: PackageSheet): PaperHeaderData {
  return {
    school: props.profile.school,
    teacher: props.profile.teacher_name,
    subject: props.profile.subject,
    grade: props.pack.grade,
    title: `${sheet.title} — الدرس ${props.pack.lesson}: ${props.pack.lesson_title} (الحصة ${props.pack.k})`,
    minutes: null,
    date: props.date,
    section: props.section,
    totalMarks: 0,
    instructions: "",
    seed: 0,
  };
}

function bookText(entry: PackageEntry): string {
  return `${bookRef("تمرين", entry.number!, entry.page)} من كتاب الطالب`;
}
</script>

<template>
  <article v-for="sheet in pack.sheets" :key="sheet.kind" class="sheet pack-sheet" :data-kind="sheet.kind">
    <!-- بطاقة الخروج تتكرر في الصفحة بعدد طلابها، وغيرها نسخة واحدة -->
    <section v-for="copy in sheet.per_page" :key="copy" class="copy" :class="{ card: sheet.per_page > 1 }">
      <PaperHeader v-if="sheet.per_page === 1" :header="header(sheet)" />
      <p v-else class="card-head">
        <strong>{{ sheet.title }} — الدرس {{ pack.lesson }}، الحصة {{ pack.k }}</strong>
        <span>الاسم: {{ DOTS }} الشعبة: {{ section || DOTS }}</span>
      </p>
      <ul v-if="sheet.per_page === 1" class="objectives">
        <li v-for="[example, text] in sheet.objectives" :key="example">
          هدف {{ bookRef("المثال", example, sheet.example_pages?.[example]) }}: {{ text }}
        </li>
      </ul>
      <p v-if="sheet.entries.some((e) => e.source === 'book')" class="note">تُحل تمارين كتاب الطالب في الدفتر.</p>
      <ol class="entries">
        <li v-for="(entry, index) in sheet.entries" :key="index">
          <p class="stem">
            <span v-if="entry.source === 'book'">{{ bookText(entry) }}</span>
            <MathText v-else :text="entry.stem" />
            <span v-if="sheet.per_page === 1 && entry.example" class="tag">
              — {{ bookRef("مثال", entry.example, sheet.example_pages?.[entry.example]) }}
            </span>
          </p>
          <GraphPlot v-if="entry.graph" :graph="entry.graph" compact />
          <ol v-if="entry.options.length" class="options">
            <li v-for="(option, i) in entry.options" :key="i">
              <span class="box" aria-hidden="true" /> {{ LETTERS[i] }}) <MathText :text="option" />
            </li>
          </ol>
          <!-- تمارين الكتاب تُحل في الدفتر: أسطر الحل للمسائل المطبوعة وحدها -->
          <div v-else-if="entry.source !== 'book'" class="work" aria-hidden="true"><span v-for="line in 4" :key="line" /></div>
        </li>
      </ol>
    </section>
  </article>

  <article class="sheet pack-sheet pack-key" data-kind="key">
    <PaperHeader compact :header="{ ...header(pack.sheets[0]), title: `مفتاح الإجابة — الدرس ${pack.lesson} (الحصة ${pack.k})` }" />
    <section v-for="sheet in pack.sheets" :key="sheet.kind">
      <h3>{{ sheet.title }}</h3>
      <ol>
        <li v-for="(entry, index) in sheet.entries" :key="index">
          <template v-if="entry.source === 'book'">{{ bookText(entry) }}: {{ BOOK_ANSWER }}</template>
          <template v-else-if="entry.options.length">
            {{ LETTERS[entry.answer_index] }}) <MathText :text="entry.options[entry.answer_index]" />
          </template>
          <template v-else>
            <MathText :text="entry.answer" />
            <span v-if="entry.steps.length" class="steps">
              <MathText v-for="(step, i) in entry.steps" :key="i" :text="step" />
            </span>
          </template>
        </li>
      </ol>
    </section>
  </article>
</template>

<style scoped>
.entries > li {
  margin-block-end: var(--space-3);
  break-inside: avoid;
}
.stem {
  margin: 0 0 var(--space-1);
}
.tag {
  margin-inline-start: var(--space-2);
  font-size: var(--print-small);
  color: var(--color-ink-soft);
}
.objectives,
.note {
  font-size: var(--print-small);
}
.options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-1) var(--space-4);
  list-style: none;
  padding: 0;
}
.box {
  display: inline-block;
  inline-size: 0.8em;
  block-size: 0.8em;
  border: 1px solid var(--color-line-strong);
}
.work span {
  display: block;
  block-size: 2.2em;
  border-block-end: 1px dotted var(--color-line-strong);
}
.card {
  border: 1px dashed var(--color-line-strong);
  padding: var(--space-3);
  margin-block-end: var(--space-3);
  font-size: var(--print-small);
  break-inside: avoid;
}
.card-head {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-2);
  margin: 0;
}
.card .work {
  display: none;
}
.steps {
  display: grid;
  font-size: var(--print-small);
  color: var(--color-ink-soft);
}
@media print {
  .pack-sheet {
    break-before: page;
  }
  .pack-sheet:first-of-type {
    break-before: auto;
  }
}
</style>
