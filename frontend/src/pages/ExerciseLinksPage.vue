<script setup lang="ts">
import { bookRef } from "@/utils/bookRef";
import { computed, onMounted, reactive, ref, watch } from "vue";
import EmptyState from "@/components/EmptyState.vue";
import MathText from "@/components/MathText.vue";
import { useAuthStore } from "@/stores/auth";
import { useCoursesStore } from "@/stores/courses";
import { useExerciseLinksStore, type LinkExercise } from "@/stores/exerciseLinks";

// مراجعة ربط تمارين كتاب الطالب بأمثلتها (للمشرف العام): يختار المقرر والدرس، يصحّح أمثلة التمرين ويعتمده،
// أو يعتمد ربط الدرس كله كما هو. المعتمد لا يغيّره تحميل المعرفة.
const auth = useAuthStore();
const courses = useCoursesStore();
const store = useExerciseLinksStore();
const course = ref("");
const lesson = ref("");
const pendingOnly = ref(false);
const picked = reactive<Record<string, number[]>>({});

const PROVENANCE: Record<string, string> = {
  teacher: "معتمد من معلم",
  ai_unreviewed: "آلي لم يُراجَع",
  derived: "مشتق",
  guide: "دليل المعلم",
};
const KIND: Record<string, string> = { try: "تمرين المثال", practice: "تمارين الدرس" };

const key = (e: LinkExercise) => `${e.kind}-${e.number}`;
const current = computed(() => store.lessons.find((l) => l.code === lesson.value));
const rows = computed(() =>
  (store.links?.exercises ?? []).filter((e) => !pendingOnly.value || !e.reviewed),
);

watch(
  () => store.links,
  (links) => {
    for (const name of Object.keys(picked)) delete picked[name];
    for (const e of links?.exercises ?? []) picked[key(e)] = [...e.examples];
  },
);

watch(course, (slug) => {
  lesson.value = "";
  void store.loadLessons(slug);
});
watch(lesson, (code) => void store.open(code));

onMounted(async () => {
  if (!auth.user?.is_superuser) return;
  if (!courses.courses.length) await courses.load();
  course.value = courses.selected || (courses.courses[0]?.slug ?? "");
});

const changed = (e: LinkExercise) =>
  [...(picked[key(e)] ?? [])].sort((a, b) => a - b).join() !== e.examples.join();

function approveAll() {
  if (window.confirm("يُعتمد ربط كل تمارين الدرس كما هو محفوظ الآن. هل تتابع؟")) void store.approveLesson();
}
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">مراجعة المعرفة</span>
    <h1>تمارين الكتاب وأمثلتها</h1>
    <p class="lead">
      راجع المثال الذي يتدرّب عليه كل تمرين، وصحّحه ثم اعتمده. الأرقام أرقام كتاب الطالب، وما تعتمده لا يغيّره تحديث
      المعرفة.
    </p>
  </header>

  <p v-if="!auth.user?.is_superuser" class="alert alert-error" role="alert">هذه الصفحة للمشرف العام فقط.</p>
  <div v-else class="panel" :aria-busy="store.busy">
    <p v-if="store.error || courses.error" class="alert alert-error" role="alert">
      {{ store.error || courses.error }}
    </p>
    <form class="form" @submit.prevent>
      <label class="field">
        <span>المقرر</span>
        <select v-model="course" class="input" name="course">
          <option v-for="c in courses.courses" :key="c.slug" :value="c.slug">{{ c.title }}</option>
        </select>
      </label>
      <label class="field">
        <span>الدرس</span>
        <select v-model="lesson" class="input" name="lesson" :disabled="!store.lessons.length">
          <option value="" disabled>اختر الدرس</option>
          <option v-for="l in store.lessons" :key="l.code" :value="l.code">
            {{ l.code }} — {{ l.title }} (غير المعتمد {{ l.pending }} من {{ l.total }})
          </option>
        </select>
      </label>
    </form>

    <p v-if="store.busy && !store.links" class="hint" role="status">يُحمَّل…</p>
    <template v-if="store.links">
      <ul class="examples">
        <li v-for="e in store.links.examples" :key="e.number">
          <strong>{{ bookRef("مثال", e.number, e.page) }}</strong>
          <MathText v-if="e.skill" :text="e.skill" />
        </li>
      </ul>

      <div class="bar">
        <label class="check">
          <input v-model="pendingOnly" type="checkbox" name="pending" />
          غير المعتمد فقط
        </label>
        <button
          type="button"
          class="btn"
          data-test="approve-all"
          :disabled="store.busy || !current?.pending"
          @click="approveAll"
        >
          اعتمد ربط الدرس كله
        </button>
      </div>

      <EmptyState v-if="!rows.length">كل تمارين هذا الدرس معتمدة.</EmptyState>
      <div v-else class="scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">التمرين</th>
              <th scope="col">النوع</th>
              <th scope="col">أمثلته</th>
              <th scope="col">المصدر</th>
              <th scope="col">الاعتماد</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="key(row)" :data-exercise="key(row)">
              <th scope="row">{{ bookRef('التمرين', row.number, row.page) }}</th>
              <td>{{ KIND[row.kind] }}</td>
              <td>
                <div class="picks" role="group" :aria-label="`أمثلة ${bookRef('التمرين', row.number, row.page)}`">
                  <label v-for="e in store.links.examples" :key="e.number" class="check">
                    <input v-model="picked[key(row)]" type="checkbox" :value="e.number" />
                    {{ e.number }}
                  </label>
                </div>
              </td>
              <td>{{ PROVENANCE[row.provenance] ?? row.provenance }}</td>
              <td>
                <span v-if="row.reviewed && !changed(row)" class="badge">معتمد</span>
                <button
                  v-else
                  type="button"
                  class="btn btn-secondary btn-small"
                  :disabled="store.busy || !picked[key(row)]?.length"
                  @click="store.review(row, picked[key(row)])"
                >
                  {{ changed(row) ? "احفظ واعتمد" : "اعتمد" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.form,
.bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: end;
}
.form .field {
  flex: 1 1 240px;
}
.bar {
  justify-content: space-between;
  align-items: center;
  margin-block: var(--space-4);
}
.hint {
  color: var(--color-ink-soft);
}
.examples {
  list-style: none;
  margin-block: var(--space-4) 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
}
.examples li {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: baseline;
}
.scroll {
  overflow-x: auto;
}
table {
  inline-size: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: var(--space-2);
  border: var(--border);
  text-align: center;
  vertical-align: middle;
}
.picks {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  justify-content: center;
}
.check {
  display: inline-flex;
  gap: var(--space-1);
  align-items: center;
}
</style>
