<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PaperBundle from "@/components/PaperBundle.vue";
import PaperSet from "@/components/PaperSet.vue";
import PrintSettings from "@/components/PrintSettings.vue";
import { useAuthStore } from "@/stores/auth";
import { LEVEL_NAMES, usePapersStore, type Level } from "@/stores/papers";
import { usePrintStore } from "@/stores/print";
import { useSavedStore } from "@/stores/saved";

const store = usePapersStore();
const auth = useAuthStore();
const print = usePrintStore();
const saved = useSavedStore();
const route = useRoute();
const router = useRouter();
const saveTitle = ref("");
const savedNow = ref(false);
const mode = ref<"exam" | "worksheet" | "bundle">("exam");
const blueprint = ref("");
const lesson = ref("");
const count = ref(8);
const seedText = ref("");
const level = ref<Level | "">("");
const twin = ref(false);
const sheetWrap = ref<HTMLElement | null>(null);
const forms = computed(() => (store.paper ? [store.paper, ...(store.twin ? [store.twin] : [])] : []));
const hasMcq = computed(() => store.paper?.questions.some((q) => q.kind === "mcq") ?? false);

const lessonLevels = computed(() => store.lessons.find((item) => item.code === lesson.value)?.levels ?? []);
watch(lesson, () => {
  if (level.value && !lessonLevels.value.includes(level.value)) level.value = "";
});
const seed = computed(() => (/^\d+$/.test(seedText.value.trim()) ? Number(seedText.value.trim()) : null));
const seedInvalid = computed(() => seedText.value.trim() !== "" && seed.value === null);
const ready = computed(() => !seedInvalid.value && (mode.value === "worksheet" ? lesson.value : blueprint.value));
const levelEntries = Object.entries(LEVEL_NAMES) as [Level, string][];

onMounted(async () => {
  if (!auth.canGenerate) return;
  void store.loadOptions();
  // رابط مباشر إلى ورقة محفوظة: /?saved=ID
  const id = Number(route.query.saved);
  if (Number.isInteger(id) && id > 0 && store.savedId !== id) {
    const row = await saved.open(id);
    if (row) store.openSaved(row);
    await router.replace({ query: {} });
  }
});
// اسم الحفظ يتبع الورقة الحالية حتى يكتب المعلم اسمًا
watch(
  () => store.paper,
  (paper) => {
    saveTitle.value = store.savedTitle || paper?.title || "";
    savedNow.value = false;
  },
  { immediate: true },
);

async function replace(question: number, label: string) {
  await store.replacePart(question, label);
  savedNow.value = false;
}

async function savePaper() {
  if (!store.paper || !store.recipe) return;
  const row = store.savedId
    ? await saved.update(store.savedId, { title: saveTitle.value, paper: store.paper, recipe: store.recipe })
    : await saved.save(saveTitle.value, store.paper, store.recipe);
  if (row) {
    store.savedId = row.id;
    store.savedTitle = row.title;
    savedNow.value = true;
  }
}
watch(
  () => [store.blueprints, store.worksheetLessons] as const,
  ([blueprints, lessons]) => {
    blueprint.value ||= blueprints[0]?.slug ?? "";
    lesson.value ||= lessons[0]?.code ?? "";
  },
);

async function generate() {
  if (mode.value === "bundle") {
    store.paper = null;
    await store.generateBundle(blueprint.value, seed.value);
  } else {
    store.bundle = null;
    if (mode.value === "exam") await store.generateExam(blueprint.value, seed.value, twin.value);
    else await store.generateWorksheet(lesson.value, count.value, seed.value, level.value, twin.value);
  }
  if ((store.paper || store.bundle) && !store.error) {
    // قارئ الشاشة ولوحة المفاتيح ينتقلان إلى الورقة الجديدة بدل البقاء على زر التوليد
    await nextTick();
    sheetWrap.value?.focus();
  }
}

function printPaper() {
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
    <form v-else class="panel generator" :aria-busy="store.loading || store.optionsLoading" @submit.prevent="generate">
      <fieldset class="mode">
        <legend class="visually-hidden">نوع الورقة</legend>
        <div class="segmented">
          <label><input v-model="mode" type="radio" value="exam" /><span>اختبار كامل</span></label>
          <label><input v-model="mode" type="radio" value="worksheet" /><span>ورقة عمل</span></label>
          <label><input v-model="mode" type="radio" value="bundle" /><span>كل أوراق العمل بضغطة</span></label>
        </div>
      </fieldset>

      <p v-if="mode === 'bundle'" class="mode-hint">
        ورقة لكل درس في جدول المواصفات، عدد مسائلها من وزن الدرس في الجدول، مرتبة سهل ثم متوسط ثم مهارات عليا،
        مع غلاف وفهرس. رقم الحزمة يعيد الأوراق نفسها.
      </p>
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
            <option v-for="[code, name] in levelEntries" :key="code" :value="code" :disabled="!lessonLevels.includes(code)">
              {{ name }}{{ lessonLevels.includes(code) ? "" : " (غير متاح)" }}
            </option>
          </select>
        </label>
        <label v-if="mode === 'worksheet'" class="field">
          عدد المسائل
          <input v-model.number="count" class="input" type="number" min="1" max="20" />
        </label>
        <label v-if="mode !== 'bundle'" class="check field-check">
          <input v-model="twin" type="checkbox" />
          نموذجان أ وب (البنية نفسها بأعداد مختلفة)
        </label>
        <label class="field">
          رقم النموذج (اختياري)
          <input
            v-model="seedText"
            class="input"
            inputmode="numeric"
            dir="ltr"
            :aria-invalid="seedInvalid"
            :aria-describedby="seedInvalid ? 'seed-error' : undefined"
          />
        </label>
      </div>

      <div class="actions">
        <button type="submit" class="btn btn-primary" :disabled="!ready || store.loading">
          <template v-if="store.loading && mode === 'bundle'">جارٍ توليد {{ store.bundleDone }} من {{ store.bundlePlan.length }}</template>
          <template v-else-if="store.loading">جارٍ التوليد</template>
          <template v-else>{{ mode === "bundle" ? "توليد الحزمة" : "توليد الورقة" }}</template>
        </button>
        <button v-if="store.paper || store.bundle" type="button" class="btn btn-secondary" @click="printPaper">
          طباعة أو حفظ PDF
        </button>
        <label v-if="store.paper || store.bundle" class="check">
          <input v-model="print.showKey" type="checkbox" /> {{ store.bundle ? "المفاتيح في آخر الحزمة" : "مفتاح الحل في صفحة أخيرة" }}
        </label>
        <label v-if="store.paper && hasMcq" class="check">
          <input v-model="print.bubble" type="checkbox" /> ورقة تظليل للأسئلة الموضوعية
        </label>
      </div>
      <p v-if="store.paper || store.bundle" class="print-hint">
        في نافذة الطباعة اختر A4 وألغِ «الترويسات والتذييلات» حتى لا يطبع المتصفح الرابط والتاريخ فوق الورقة.
      </p>
      <p v-if="seedInvalid" id="seed-error" class="alert alert-error">رقم النموذج يجب أن يكون أرقامًا فقط.</p>
      <p v-if="store.error" class="alert alert-error" role="alert" aria-live="assertive">{{ store.error }}</p>
    </form>
    <form v-if="store.paper && store.recipe" class="panel save" :aria-busy="saved.saving" @submit.prevent="savePaper">
      <label class="field grow">
        اسم الورقة في أوراقي
        <input v-model="saveTitle" class="input" maxlength="200" required />
      </label>
      <button type="submit" class="btn btn-secondary" :disabled="saved.saving || !saveTitle.trim()">
        {{ saved.saving ? "جارٍ الحفظ" : store.savedId ? "تحديث الورقة المحفوظة" : "حفظ في أوراقي" }}
      </button>
      <span v-if="savedNow" class="hint" role="status">حُفظت. <RouterLink to="/saved">أوراقي</RouterLink></span>
      <span v-else-if="store.twin" class="hint">يُحفظ النموذج أ؛ والنموذج ب يُعاد من رقم النموذج نفسه.</span>
      <span v-else-if="store.modified" class="hint">استُبدلت مسائل، فرقم النموذج وحده لا يعيد هذه الورقة؛ احفظها.</span>
      <p v-if="saved.error" class="alert alert-error wide" role="alert">{{ saved.error }}</p>
    </form>
    <PrintSettings v-if="auth.canGenerate" />

    <div v-if="store.paper?.is_forecast" class="alert alert-info notice">
      <p>هذا الاختبار مبني على جدول مواصفات متوقع غير رسمي، فالوزارة لا تصدر جدولًا للثانوية العامة.</p>
      <p class="levels">
        <span>درجات المستويات في هذا النموذج:</span>
        <span
          v-for="[code, name] in levelEntries.filter(([code]) => store.paper?.level_marks[code])"
          :key="code"
          class="badge"
          :class="`badge-${code.toLowerCase()}`"
        >
          {{ name }} {{ store.paper?.level_marks[code] }}
        </span>
      </p>
    </div>
  </div>

  <div
    v-if="store.paper || store.bundle"
    ref="sheetWrap"
    class="sheet-focus"
    tabindex="-1"
    aria-live="polite"
    :aria-label="store.paper?.title ?? 'حزمة أوراق العمل'"
  >
    <PaperSet
      v-if="store.paper"
      :papers="forms"
      :header="print.header"
      :show-key="print.showKey"
      :bubble="print.bubble && hasMcq"
      :modified="store.modified"
      :replacing="store.replacing"
      replaceable
      @replace="replace"
    />
    <PaperBundle
      v-else-if="store.bundle"
      :papers="store.bundle"
      :plan="store.bundlePlan"
      :seed="store.bundleSeed"
      :header="print.header"
      :show-key="print.showKey"
    />
  </div>
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
.field-check {
  align-self: end;
  min-block-size: 42px;
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
.sheet-focus:focus-visible {
  box-shadow: none;
}
.save {
  margin-block-start: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3) var(--space-4);
}
.save .grow {
  flex: 1 1 240px;
}
.save .wide {
  flex-basis: 100%;
}
.hint {
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.print-hint,
.mode-hint {
  margin: 0;
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
</style>
