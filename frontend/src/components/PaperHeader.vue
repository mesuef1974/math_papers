<script setup lang="ts">
import type { PaperHeaderData } from "@/stores/print";
import { isolateNumberRanges } from "@/utils/bidi";
import { durationLabel } from "@/utils/duration";

// ترويسة بأسلوب أغلفة الوزارة: المدرسة والمادة والصف والزمن والدرجة، ثم سطر الطالب، ثم التعليمات.
// الخانة الأخيرة في الصف الأول محجوزة لشعار المنصة عند اعتماده.
withDefaults(defineProps<{ header: PaperHeaderData; compact?: boolean }>(), { compact: false });
const DOTS = "....................";
</script>

<template>
  <header class="paper-header" :class="{ compact }">
    <div class="top">
      <div class="org">
        <strong v-if="header.school">{{ header.school }}</strong>
        <span v-if="header.teacher">المعلم: {{ header.teacher }}</span>
      </div>
      <h2 class="title">{{ isolateNumberRanges(header.title) }}</h2>
      <div class="logo-slot" aria-hidden="true" />
    </div>
    <dl class="meta">
      <div><dt>المادة</dt><dd>{{ header.subject }}</dd></div>
      <div v-if="header.grade"><dt>الصف</dt><dd>{{ header.grade }}</dd></div>
      <div v-if="header.minutes"><dt>زمن الاختبار</dt><dd>{{ durationLabel(header.minutes) }}</dd></div>
      <div v-if="header.totalMarks"><dt>الدرجة الكلية</dt><dd>{{ header.totalMarks }} درجة</dd></div>
      <div v-if="header.date"><dt>التاريخ</dt><dd><bdi dir="ltr">{{ header.date }}</bdi></dd></div>
    </dl>
    <div v-if="!compact" class="student">
      <span class="grow">اسم الطالب: {{ DOTS }}{{ DOTS }}</span>
      <span>الشعبة: {{ header.section || DOTS }}</span>
      <span v-if="header.totalMarks">الدرجة: ........ / {{ header.totalMarks }}</span>
    </div>
    <p v-if="!compact && header.instructions" class="instructions">
      <strong>تعليمات:</strong> {{ header.instructions }}
    </p>
  </header>
</template>

<style scoped>
.paper-header {
  border-block-end: 2px solid var(--color-ink);
  padding-block-end: var(--space-3);
  margin-block-end: var(--space-3);
  display: grid;
  gap: var(--space-3);
}
.top {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: var(--space-3);
}
.org {
  display: grid;
  font-size: var(--text-sm);
  line-height: 1.5;
}
.title {
  text-align: center;
  font-size: var(--text-xl);
  margin: 0;
}
.logo-slot {
  justify-self: end;
  inline-size: 48px;
  block-size: 48px;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-6);
  margin: 0;
  font-size: var(--text-sm);
}
.meta div {
  display: flex;
  gap: var(--space-1);
}
.meta dt {
  font-weight: var(--weight-bold);
}
.meta dt::after {
  content: ":";
}
.meta dd {
  margin: 0;
}
.student {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-6);
  padding-block-start: var(--space-2);
  border-block-start: 1px solid var(--color-line);
}
.grow {
  flex: 1 1 auto;
}
.instructions {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}
.compact {
  border-block-end-width: 1px;
}
.compact .title {
  font-size: var(--text-lg);
}
@media (max-width: 560px) {
  .top {
    grid-template-columns: 1fr;
    text-align: center;
  }
  .logo-slot {
    display: none;
  }
}
@media print {
  .title {
    font-size: var(--print-title);
  }
  .meta,
  .org,
  .instructions {
    font-size: var(--print-small);
  }
}
</style>
