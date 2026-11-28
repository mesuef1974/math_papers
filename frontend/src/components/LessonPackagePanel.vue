<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";
import { useLessonPackageStore } from "@/stores/lessonPackage";

// باقة الحصة: محتواها قبل التنزيل، ثم طلب بنائها وتنزيلها. `version` يتغير مع تعديل التحضير فتُقرأ الحالة من جديد.
const props = defineProps<{
  course: string;
  lesson: string;
  k: number;
  version?: unknown;
}>();

const pack = useLessonPackageStore();

watch(
  () => [props.course, props.lesson, props.k, props.version],
  () => void pack.select(props.course, props.lesson, props.k),
  { immediate: true },
);
onBeforeUnmount(() => pack.reset());
</script>

<template>
  <section class="lesson-package" aria-labelledby="package-title">
    <h3 id="package-title">باقة الحصة</h3>
    <p class="hint">
      ملف مضغوط واحد: التحضير والعرض وأوراق الحصة ومفتاح الإجابة.
    </p>
    <ul v-if="pack.sheets.length" data-test="package-sheets">
      <li v-for="title in pack.sheets" :key="title">{{ title }}</li>
    </ul>
    <ul v-if="pack.notes.length" class="hint" data-test="package-notes">
      <li v-for="note in pack.notes" :key="note">{{ note }}</li>
    </ul>
    <div class="actions">
      <button
        type="button"
        class="btn btn-secondary"
        data-test="package-build"
        :disabled="pack.busy || !!pack.unavailable"
        :aria-describedby="pack.unavailable ? 'package-reason' : undefined"
        @click="pack.request()"
      >
        {{ pack.status === "stale" ? "أعد بناء الباقة" : "جهّز الباقة" }}
      </button>
      <a v-if="pack.url" class="btn btn-primary" :href="pack.url" download
        >نزّل الباقة</a
      >
    </div>
    <p v-if="pack.unavailable" id="package-reason" class="hint">
      {{ pack.unavailable }}
    </p>
    <p v-else-if="pack.busy" class="hint" role="status">
      تُبنى الباقة، وقد يستغرق ذلك دقائق…
    </p>
    <p v-else-if="pack.status === 'stale'" class="hint" role="status">
      الباقة المبنية قديمة: تغيّر التحضير بعدها.
    </p>
    <p
      v-else-if="pack.error || pack.status === 'failed'"
      class="alert alert-error"
      role="alert"
    >
      {{ pack.error || pack.detail }}
    </p>
  </section>
</template>

<style scoped>
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.hint {
  font-size: var(--print-small);
  color: var(--color-ink-soft);
}
</style>
