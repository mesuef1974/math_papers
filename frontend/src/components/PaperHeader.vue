<script setup lang="ts">
import BrandLockup from "@/components/BrandLockup.vue";
import type { PaperHeaderData } from "@/stores/print";
import { isolateNumberRanges } from "@/utils/bidi";
import { durationLabel } from "@/utils/duration";

// ترويسة بأسلوب أغلفة الوزارة: المدرسة والمادة والصف والزمن والدرجة، ثم سطر الطالب، ثم التعليمات.
// شعار المنصة «أوراق» في بداية الصف الأول كما في تطبيق الهوية على الورق، والمدرسة والمعلم في نهايته.
withDefaults(defineProps<{ header: PaperHeaderData; compact?: boolean }>(), { compact: false });
const DOTS = "....................";
</script>

<template>
  <header class="paper-header" :class="{ compact }">
    <div class="top">
      <BrandLockup class="logo" :height="compact ? 38 : 46" />
      <h2 class="title">{{ isolateNumberRanges(header.title) }}</h2>
      <div class="org">
        <strong v-if="header.school">{{ header.school }}</strong>
        <span v-if="header.teacher">المعلم: {{ header.teacher }}</span>
      </div>
    </div>
    <dl class="meta">
      <div><dt>المادة</dt><dd>{{ header.subject }}</dd></div>
      <div v-if="header.grade"><dt>الصف</dt><dd>{{ header.grade.replace(/^الصف\s+/, "") }}</dd></div>
      <div v-if="header.form"><dt>النموذج</dt><dd>{{ header.form }}</dd></div>
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
/* ترويسة الهوية: خط عنابي سميك تحتها، والعنوان وتسميات البيانات بالعنابي، والذهبي شريط تزيين للتعليمات */
.paper-header {
  border-block-end: 3px solid var(--color-brand);
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
  justify-items: end;
  text-align: end;
  font-size: var(--text-sm);
  line-height: 1.5;
}
.title {
  text-align: center;
  font-size: var(--text-xl);
  margin: 0;
  color: var(--color-brand-strong);
}
.logo {
  justify-self: start;
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
  color: var(--color-brand-strong);
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
  border: 1px solid var(--color-line);
  border-inline-start: 4px solid var(--color-accent);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}
.compact {
  border-block-end-width: 2px;
}
.compact .title {
  font-size: var(--text-lg);
}
@media (max-width: 560px) {
  .top {
    grid-template-columns: 1fr;
    text-align: center;
  }
  .logo,
  .org {
    justify-self: center;
    justify-items: center;
    text-align: center;
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
