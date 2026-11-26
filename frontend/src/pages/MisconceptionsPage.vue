<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import EmptyState from "@/components/EmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { useCoursesStore } from "@/stores/courses";
import { useMisconceptionsStore } from "@/stores/misconceptions";

// لوحة سوء الفهم: المعلم يختار المقرر والدرس وشعبة من شعبه، فيرى لكل نوع خطأ عدد طلابه وأسماءهم. قراءة فقط؛
// الإدخال في صفحة ResultsEntryPage.
const auth = useAuthStore();
const courses = useCoursesStore();
const store = useMisconceptionsStore();
const course = ref("");
const lesson = ref("");
const section = ref("");

onMounted(async () => {
  if (!auth.canGenerate) return;
  store.clear();
  await Promise.all([
    courses.courses.length ? Promise.resolve() : courses.load(),
    store.loadSections(),
  ]);
  const last = store.last; // بعد حفظ نتائج من صفحة الإدخال تُفتح اللوحة على ما أُدخل
  course.value = last?.course || courses.selected || (courses.courses[0]?.slug ?? "");
  if (last) {
    await nextTick(); // بعد أن يفرغ تبديل المقرر خانة الدرس
    lesson.value = last.lesson;
    section.value = last.section;
  } else if (store.sections.length === 1) section.value = store.sections[0];
});

watch(course, (slug) => {
  lesson.value = "";
  void store.loadLessons(slug);
});

watch([course, lesson, section], ([c, l, s]) => {
  if (c && l && s) void store.load(c, l, s);
  else store.clear();
});

const board = computed(() => store.board);
const examplesText = (examples: number[]) => examples.join("، ");
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">تشخيص الخطأ</span>
    <h1>لوحة سوء الفهم</h1>
    <p class="lead">
      اختر المقرر والدرس والشعبة، فترى لكل نوع خطأ الطلاب الذين وقعوا فيه في
      بنود الدرس والأمثلة التي ظهر فيها، مرتبة من الأكثر شيوعًا.
    </p>
    <RouterLink
      v-if="auth.canGenerate"
      class="btn btn-secondary btn-small"
      to="/results/entry"
      >أدخل نتائج الطلاب</RouterLink
    >
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">
    حسابك لا يملك صلاحية توليد الأوراق.
  </p>
  <div v-else class="panel" :aria-busy="store.loading">
    <p v-if="store.error || courses.error" class="alert alert-error" role="alert">
      {{ store.error || courses.error }}
    </p>
    <EmptyState v-if="store.sectionsLoaded && !store.sections.length">
      لا شعب لك بعد: تظهر الشعبة هنا بعد إدخال نتائج طلابها في بنود درس.
    </EmptyState>
    <template v-else-if="store.sectionsLoaded">
      <form class="form" @submit.prevent>
        <label class="field">
          <span>المقرر</span>
          <select v-model="course" class="input" name="course" required>
            <option value="" disabled>اختر المقرر</option>
            <option v-for="c in courses.courses" :key="c.slug" :value="c.slug">
              {{ c.title }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>الدرس</span>
          <select
            v-model="lesson"
            class="input"
            name="lesson"
            required
            :disabled="!store.lessons.length"
          >
            <option value="" disabled>اختر الدرس</option>
            <option v-for="l in store.lessons" :key="l.code" :value="l.code">
              {{ l.code }} — {{ l.title }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>الشعبة</span>
          <select v-model="section" class="input" name="section" required>
            <option value="" disabled>اختر الشعبة</option>
            <option v-for="s in store.sections" :key="s" :value="s">
              {{ s }}
            </option>
          </select>
        </label>
      </form>

      <p v-if="store.loading" class="hint" role="status">تُحمَّل اللوحة…</p>
      <template v-else-if="board">
        <EmptyState v-if="!board.entered" class="empty">
          لا نتائج مدخلة لهذه الشعبة في هذا الدرس بعد (عدد طلابها
          {{ board.students }}).
        </EmptyState>
        <template v-else>
          <dl class="summary">
            <div class="stat">
              <dt>أجابوا صحيحًا</dt>
              <dd data-test="correct">{{ board.correct }}</dd>
            </div>
            <div class="stat">
              <dt>لم تُدخل نتائجهم</dt>
              <dd data-test="missing">{{ board.missing }}</dd>
            </div>
            <div class="stat">
              <dt>طلاب الشعبة</dt>
              <dd data-test="students">{{ board.students }}</dd>
            </div>
          </dl>
          <p v-if="!board.kinds.length" class="alert alert-info" role="status">
            لا أخطاء مسجَّلة: كل من أُدخلت نتائجهم أجابوا صحيحًا.
          </p>
          <ul v-else class="kinds">
            <li
              v-for="kind in board.kinds"
              :key="kind.kind"
              class="kind"
              :data-kind="kind.kind"
            >
              <div class="kind-head">
                <h2>{{ kind.label }}</h2>
                <span class="badge count">عدد الطلاب: {{ kind.count }}</span>
              </div>
              <p class="examples">
                الأمثلة: {{ examplesText(kind.examples) }}
              </p>
              <ul class="students">
                <li v-for="s in kind.students" :key="s.enrollment_no">
                  <span class="name">{{ s.first_name }} {{ s.last_name }}</span>
                  <bdi dir="ltr" class="enrollment">{{ s.enrollment_no }}</bdi>
                </li>
              </ul>
            </li>
          </ul>
        </template>
      </template>
    </template>
  </div>
</template>

<style scoped>
.form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: end;
}
.form .field {
  flex: 1 1 200px;
}
.hint {
  margin-block: var(--space-4) 0;
  color: var(--color-ink-soft);
}
.empty {
  margin-block-start: var(--space-4);
}
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-block: var(--space-5) var(--space-4);
}
.stat {
  flex: 1 1 140px;
  padding: var(--space-3) var(--space-4);
  border: var(--border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-sunken);
}
.stat dt {
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
.stat dd {
  margin: 0;
  font-size: var(--text-xl);
  font-weight: var(--weight-heading);
  color: var(--color-ink);
}
.kinds {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr));
  gap: var(--space-4);
}
.kind {
  padding: var(--space-4);
  border: var(--border);
  border-inline-start: 4px solid var(--color-brand);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
.kind-head {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  justify-content: space-between;
}
.kind-head h2 {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-bold);
  line-height: var(--leading-tight);
}
.examples {
  margin-block: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
.students {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-1);
}
.students li {
  display: flex;
  gap: var(--space-3);
  justify-content: space-between;
  padding-block: var(--space-1);
  border-block-start: var(--border);
}
.enrollment {
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
</style>
