<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import PaperSheet from "@/components/PaperSheet.vue";
import { useAuthStore } from "@/stores/auth";
import { LEVEL_NAMES, usePapersStore, type Level } from "@/stores/papers";

const store = usePapersStore();
const auth = useAuthStore();
const mode = ref<"exam" | "worksheet">("exam");
const blueprint = ref("");
const lesson = ref("");
const count = ref(8);
const seedText = ref("");
const showKey = ref(false);
const level = ref<Level | "">("");

const LEVELS = LEVEL_NAMES as Record<string, string>;
const lessonLevels = computed(() => store.lessons.find((item) => item.code === lesson.value)?.levels ?? []);
watch(lesson, () => {
  if (level.value && !lessonLevels.value.includes(level.value)) level.value = "";
});
const seed = computed(() => (/^\d+$/.test(seedText.value.trim()) ? Number(seedText.value.trim()) : null));
const seedInvalid = computed(() => seedText.value.trim() !== "" && seed.value === null);
const ready = computed(() => !seedInvalid.value && (mode.value === "exam" ? blueprint.value : lesson.value));

onMounted(() => {
  if (auth.canGenerate) void store.loadOptions();
});
watch(
  () => [store.blueprints, store.worksheetLessons] as const,
  ([blueprints, lessons]) => {
    blueprint.value ||= blueprints[0]?.slug ?? "";
    lesson.value ||= lessons[0]?.code ?? "";
  },
);

async function generate() {
  if (mode.value === "exam") await store.generateExam(blueprint.value, seed.value);
  else await store.generateWorksheet(lesson.value, count.value, seed.value, level.value);
}

function print() {
  window.print();
}
</script>

<template>
  <div class="no-print">
    <header class="page-head">
      <span class="eyebrow">المنهج القطري، <bdi dir="ltr">2026-2027</bdi></span>
      <h1>أوراق رياضيات 12 علمي وتكنولوجي</h1>
      <p class="lead">ولّد اختبارًا تدريبيًا من 40 أو ورقة عمل لدرس واحد، بمسائل جديدة في كل مرة ومفتاح حل.</p>
    </header>

    <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">
      حسابك لا يملك صلاحية توليد الأوراق. اطلب من المشرف إضافتك إلى مجموعة المعلمين.
    </p>
    <form v-else class="panel generator" @submit.prevent="generate">
      <fieldset class="mode">
        <legend class="visually-hidden">نوع الورقة</legend>
        <div class="segmented">
          <label><input v-model="mode" type="radio" value="exam" /><span>اختبار كامل</span></label>
          <label><input v-model="mode" type="radio" value="worksheet" /><span>ورقة عمل</span></label>
        </div>
      </fieldset>

      <div class="fields">
        <label v-if="mode === 'worksheet'" class="field wide">
          الدرس
          <select v-model="lesson" class="select">
            <option v-for="item in store.worksheetLessons" :key="item.code" :value="item.code">
              {{ item.code }} {{ item.title }}
            </option>
          </select>
        </label>
        <label v-if="mode === 'worksheet'" class="field">
          المستوى
          <select v-model="level" class="select">
            <option value="">كل المستويات</option>
            <option v-for="(name, code) in LEVEL_NAMES" :key="code" :value="code" :disabled="!lessonLevels.includes(code)">
              {{ name }}{{ lessonLevels.includes(code) ? "" : " (غير متاح)" }}
            </option>
          </select>
        </label>
        <label v-if="mode === 'worksheet'" class="field">
          عدد المسائل
          <input v-model.number="count" class="input" type="number" min="1" max="20" />
        </label>
        <label class="field">
          رقم النموذج (اختياري)
          <input v-model="seedText" class="input" inputmode="numeric" dir="ltr" :aria-invalid="seedInvalid" />
        </label>
      </div>

      <div class="actions">
        <button type="submit" class="btn btn-primary" :disabled="!ready || store.loading">
          {{ store.loading ? "جارٍ التوليد" : "توليد الورقة" }}
        </button>
        <button v-if="store.paper" type="button" class="btn btn-secondary" @click="print">طباعة أو حفظ PDF</button>
        <label v-if="store.paper" class="check"><input v-model="showKey" type="checkbox" /> إظهار مفتاح الحل</label>
      </div>
      <p v-if="seedInvalid" class="alert alert-error">رقم النموذج يجب أن يكون أرقامًا فقط.</p>
      <p v-if="store.error" class="alert alert-error" role="alert">{{ store.error }}</p>
    </form>

    <div v-if="store.paper?.is_forecast" class="alert alert-info notice">
      <p>هذا الاختبار مبني على جدول مواصفات متوقع غير رسمي، فالوزارة لا تصدر جدولًا للثانوية العامة.</p>
      <p class="levels">
        <span>درجات المستويات في هذا النموذج:</span>
        <span
          v-for="(marks, code) in store.paper.level_marks"
          :key="code"
          class="badge"
          :class="`badge-${String(code).toLowerCase()}`"
        >
          {{ LEVELS[code] }} {{ marks }}
        </span>
      </p>
    </div>
  </div>

  <PaperSheet v-if="store.paper" :paper="store.paper" :show-key="showKey" />
</template>

<style scoped>
.generator {
  display: grid;
  gap: var(--space-5);
}
.mode {
  border: 0;
  margin: 0;
  padding: 0;
  min-inline-size: 0;
}
.fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-4);
}
.wide {
  grid-column: 1 / -1;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3) var(--space-4);
}
.notice {
  margin-block-start: var(--space-4);
}
.notice p {
  margin: 0;
}
.notice .levels {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-block-start: var(--space-2);
}
</style>
