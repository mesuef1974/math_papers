<script setup lang="ts">
import { computed } from "vue";
import type { Paper } from "@/stores/papers";

// صفحة رصد الدرجات في آخر الكراسة كما في كراسات الوزارة: الموضوعي صفًا واحدًا، وكل سؤال مقالي صفًا، ثم المجموع.
const props = defineProps<{ paper: Paper }>();
const DOTS = "....................";

const rows = computed(() => {
  const mcq = props.paper.questions.filter((q) => q.kind === "mcq");
  const essays = props.paper.questions.filter((q) => q.kind !== "mcq");
  const list: { label: string; marks: number }[] = [];
  if (mcq.length) {
    const first = mcq[0].number;
    const last = mcq[mcq.length - 1].number;
    list.push({ label: first === last ? `${first}` : `${first} – ${last}`, marks: mcq.reduce((sum, q) => sum + q.marks, 0) });
  }
  for (const question of essays) list.push({ label: `${question.number}`, marks: question.marks });
  return list;
});
const total = computed(() => rows.value.reduce((sum, row) => sum + row.marks, 0));
</script>

<template>
  <section class="score-page">
    <p class="warning">الطلاب: لا تكتب على هذه الصفحة</p>
    <h3 class="heading">جدول رصد الدرجات</h3>
    <div class="table-scroll">
      <table class="score">
        <thead>
          <tr>
            <th scope="col">رقم السؤال</th>
            <th scope="col">الدرجة</th>
            <th scope="col">درجة الطالب</th>
            <th scope="col">المصحح</th>
            <th scope="col">المراجع</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.label">
            <th scope="row"><bdi dir="ltr">{{ row.label }}</bdi></th>
            <td class="num">{{ row.marks }}</td>
            <td />
            <td />
            <td />
          </tr>
          <tr class="total">
            <th scope="row">المجموع</th>
            <td class="num">{{ total }}</td>
            <td />
            <td />
            <td />
          </tr>
        </tbody>
      </table>
    </div>
    <p class="words">الدرجة بالحروف: {{ DOTS }}{{ DOTS }}</p>
  </section>
</template>

<style scoped>
.score-page {
  margin-block-start: var(--space-8);
  padding-block-start: var(--space-4);
  border-block-start: 3px solid var(--color-brand);
}
.warning {
  display: inline-block;
  margin: 0 0 var(--space-4);
  padding: var(--space-1) var(--space-3);
  border: 2px solid var(--color-brand);
  color: var(--color-brand-strong);
  font-weight: var(--weight-bold);
}
.heading {
  margin: 0 0 var(--space-3);
  font-size: var(--text-lg);
  color: var(--color-brand-strong);
}
.score {
  inline-size: 100%;
  border-collapse: collapse;
}
.score th,
.score td {
  border: 1px solid var(--color-ink);
  padding: var(--space-3);
  text-align: center;
  block-size: 44px;
}
.score thead th {
  background: var(--color-brand);
  color: var(--color-on-brand);
}
.score tbody th {
  font-weight: var(--weight-medium);
}
.num {
  font-weight: var(--weight-bold);
}
.total th,
.total td {
  background: var(--color-brand-soft);
}
.words {
  margin: var(--space-6) 0 0;
  font-size: var(--text-lg);
}
@media print {
  .score-page {
    break-before: page;
    border-block-start: 0;
    margin-block-start: 0;
  }
}
</style>
