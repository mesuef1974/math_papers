<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import PaperSheet from "@/components/PaperSheet.vue";
import { useAuthStore } from "@/stores/auth";
import { usePapersStore } from "@/stores/papers";

const store = usePapersStore();
const auth = useAuthStore();
const mode = ref<"exam" | "worksheet">("exam");
const blueprint = ref("");
const lesson = ref("");
const count = ref(8);
const seedText = ref("");
const showKey = ref(false);

const LEVELS: Record<string, string> = { K: "معرفة", A: "تطبيق", R: "استدلال" };
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
  else await store.generateWorksheet(lesson.value, count.value, seed.value);
}

function print() {
  window.print();
}
</script>

<template>
  <div class="no-print">
    <h1>أوراق رياضيات 12 علمي وتكنولوجي</h1>
    <p class="lead">ولّد اختبارًا تدريبيًا من 40 أو ورقة عمل لدرس واحد، بمسائل جديدة ومفتاح حل.</p>

    <p v-if="!auth.canGenerate" class="panel error" role="alert">
      حسابك لا يملك صلاحية توليد الأوراق. اطلب من المشرف إضافتك إلى مجموعة المعلمين.
    </p>
    <form v-else class="panel" @submit.prevent="generate">
      <fieldset class="modes">
        <legend>نوع الورقة</legend>
        <label><input v-model="mode" type="radio" value="exam" /> اختبار كامل</label>
        <label><input v-model="mode" type="radio" value="worksheet" /> ورقة عمل</label>
      </fieldset>

      <label v-if="mode === 'worksheet'" class="field">
        الدرس
        <select v-model="lesson">
          <option v-for="item in store.worksheetLessons" :key="item.code" :value="item.code">
            {{ item.code }} {{ item.title }}
          </option>
        </select>
      </label>
      <label v-if="mode === 'worksheet'" class="field narrow">
        عدد المسائل
        <input v-model.number="count" type="number" min="1" max="20" />
      </label>
      <label class="field narrow">
        رقم النموذج (اختياري)
        <input v-model="seedText" inputmode="numeric" dir="ltr" :aria-invalid="seedInvalid" />
      </label>

      <div class="actions">
        <button type="submit" :disabled="!ready || store.loading">
          {{ store.loading ? "جارٍ التوليد" : "توليد الورقة" }}
        </button>
        <button v-if="store.paper" type="button" class="secondary" @click="print">طباعة أو حفظ PDF</button>
        <label v-if="store.paper"><input v-model="showKey" type="checkbox" /> إظهار مفتاح الحل</label>
      </div>
      <p v-if="seedInvalid" class="error">رقم النموذج يجب أن يكون أرقامًا فقط.</p>
      <p v-if="store.error" class="error" role="alert">{{ store.error }}</p>
    </form>

    <p v-if="store.paper?.is_forecast" class="notice">
      هذا الاختبار مبني على جدول مواصفات متوقع غير رسمي، فالوزارة لا تصدر جدولًا للثانوية العامة.
      مستويات هذا النموذج:
      <span v-for="(marks, level) in store.paper.level_marks" :key="level" class="level">
        {{ LEVELS[level] }} {{ marks }}
      </span>
    </p>
  </div>

  <PaperSheet v-if="store.paper" :paper="store.paper" :show-key="showKey" />
</template>

<style scoped>
.panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  align-items: end;
}
.modes {
  border: 0;
  padding: 0;
  margin: 0;
  inline-size: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
}
.modes legend {
  color: var(--muted);
  font-size: 15px;
  padding: 0;
}
.field {
  display: grid;
  gap: 4px;
  flex: 1 1 260px;
  color: var(--muted);
  font-size: 15px;
}
.field.narrow {
  flex: 0 1 180px;
}
select,
input:not([type="radio"], [type="checkbox"]) {
  font: inherit;
  color: var(--ink);
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  inline-size: 100%;
}
.actions {
  inline-size: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
}
button {
  font: inherit;
  font-weight: 600;
  background: var(--accent);
  color: var(--surface);
  border: 1px solid var(--accent);
  border-radius: 6px;
  padding: 6px 18px;
  cursor: pointer;
}
button.secondary {
  background: transparent;
  color: var(--accent);
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.error {
  color: var(--risk);
  inline-size: 100%;
  margin: 0;
}
.notice {
  color: var(--muted);
  font-size: 15px;
  margin-block: 14px 0;
}
.level {
  margin-inline-start: 10px;
}
</style>
