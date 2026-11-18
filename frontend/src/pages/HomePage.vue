<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "@/components/AppIcon.vue";
import PaperBundle from "@/components/PaperBundle.vue";
import PagedSheet from "@/components/PagedSheet.vue";
import PaperSet from "@/components/PaperSet.vue";
import PdfPreview from "@/components/PdfPreview.vue";
import PrintSettings from "@/components/PrintSettings.vue";
import { usePaperFit } from "@/composables/usePaperFit";
import { useAuthStore } from "@/stores/auth";
import { useCoursesStore } from "@/stores/courses";
import { LEVEL_NAMES, PURPOSE_LEVEL, PURPOSE_NAMES, usePapersStore, type Level, type Purpose } from "@/stores/papers";
import { usePdfStore, type PdfRequest } from "@/stores/pdf";
import { usePrintStore } from "@/stores/print";
import { useSavedStore } from "@/stores/saved";

const store = usePapersStore();
const courses = useCoursesStore();
const auth = useAuthStore();
const print = usePrintStore();
const saved = useSavedStore();
const pdf = usePdfStore();
const route = useRoute();
const router = useRouter();
const saveTitle = ref("");
const savedNow = ref(false);
const mode = ref<"exam" | "quiz" | "worksheet" | "bundle">("exam");
const blueprint = ref("");
const lesson = ref("");
const secondLesson = ref(""); // الدرس الثاني في الاختبار القصير، اختياري
const count = ref(8);
const seedText = ref("");
const level = ref<Level | "">("");
const purpose = ref<Purpose>("");
const twin = ref(false);
const sheetWrap = ref<HTMLElement | null>(null);
usePaperFit(sheetWrap); // الورقة بعرض A4، وتُصغَّر كلها حين تضيق الشاشة
const forms = computed(() => (store.paper ? [store.paper, ...(store.twin ? [store.twin] : [])] : []));
const hasMcq = computed(() => store.paper?.questions.some((q) => q.kind === "mcq") ?? false);
// العرض: الورقة الحية القابلة للاستبدال، أو صفحات ملف PDF الحقيقي من الخادم بحدودها وترقيمها.
const view = ref<"paged" | "sheet" | "pdf">("paged");
// طلب ملف الخادم (PDF وWord والمعاينة): النماذج المعروضة كما هي مع ترويسة المعلم وحقول هذه الطباعة وخياراتها.
const serverRequest = computed<PdfRequest | null>(() =>
  store.paper || store.bundle
    ? {
        papers: store.bundle ?? forms.value,
        profile: print.profile,
        date: print.date,
        section: print.section,
        show_key: print.showKey,
        bubble: !store.bundle && print.bubble && hasMcq.value,
        bundle: store.bundle ? { plan: store.bundlePlan, seed: store.bundleSeed } : null,
      }
    : null,
);

const lessonLevels = computed(() => store.lessons.find((item) => item.code === lesson.value)?.levels ?? []);
watch(lesson, () => {
  if (level.value && !lessonLevels.value.includes(level.value)) level.value = "";
  if (purpose.value && !lessonLevels.value.includes(PURPOSE_LEVEL[purpose.value])) purpose.value = "";
  if (secondLesson.value === lesson.value) secondLesson.value = "";
});
const seed = computed(() => (/^\d+$/.test(seedText.value.trim()) ? Number(seedText.value.trim()) : null));
const seedInvalid = computed(() => seedText.value.trim() !== "" && seed.value === null);
const ready = computed(
  () => !seedInvalid.value && (mode.value === "worksheet" || mode.value === "quiz" ? lesson.value : blueprint.value),
);
const levelEntries = Object.entries(LEVEL_NAMES) as [Level, string][];
const purposeEntries = Object.entries(PURPOSE_NAMES) as [Purpose, string][];
function purposeAvailable(code: Purpose): boolean {
  return code === "" || lessonLevels.value.includes(PURPOSE_LEVEL[code]);
}
// الاختبار الكامل والحزمة يحتاجان جدول مواصفات جاهزًا للمقرر المختار؛ بدونه تبقى ورقة العمل والاختبار القصير.
const hasBlueprints = computed(() => store.blueprints.length > 0);
const pageTitle = computed(() => courses.current?.title ?? "أوراق الرياضيات");
const academicYear = computed(() => courses.current?.academic_year ?? "");
const generateLabel = computed(() => {
  if (mode.value === "bundle") return "توليد الحزمة";
  if (mode.value === "quiz") return "توليد الاختبار القصير";
  return "توليد الورقة";
});

// تغيير المقرر يعيد تحميل دروسه وجداوله ويُسقط اختيارات المقرر السابق؛ الورقة المعروضة تبقى كما هي.
async function loadCourseOptions(course: string) {
  lesson.value = "";
  secondLesson.value = "";
  blueprint.value = "";
  await store.loadOptions(course);
  if (!hasBlueprints.value && (mode.value === "exam" || mode.value === "bundle")) mode.value = "worksheet";
}
watch(
  () => courses.selected,
  (course, previous) => {
    if (course && course !== previous) void loadCourseOptions(course);
  },
);

onMounted(async () => {
  if (!auth.canGenerate) return;
  if (courses.courses.length) void loadCourseOptions(courses.selected);
  else {
    // المراقب يحمّل دروس المقرر الافتراضي حين يُختار؛ بلا مقرر (تعذر الطلب) تبقى دروس المقرر الحالي في الخادم
    await courses.load();
    if (!courses.selected) void loadCourseOptions("");
  }
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
    else if (mode.value === "quiz") await store.generateQuiz([lesson.value, secondLesson.value], seed.value, twin.value);
    else await store.generateWorksheet(lesson.value, count.value, seed.value, level.value, twin.value, purpose.value);
  }
  if ((store.paper || store.bundle) && !store.error) {
    // قارئ الشاشة ولوحة المفاتيح ينتقلان إلى الورقة الجديدة بدل البقاء على زر التوليد
    if (view.value === "pdf") view.value = "paged"; // ورقة جديدة: المعاينة القديمة لا تخصها
    await nextTick();
    sheetWrap.value?.focus();
  }
}

function printPaper() {
  window.print();
}

function downloadServerFile(format: "pdf" | "docx", template: "awraq" | "school" = "awraq") {
  if (!serverRequest.value) return;
  void pdf.download({ ...serverRequest.value, template }, undefined, format);
}
</script>

<template>
  <div class="no-print">
    <header class="page-head">
      <span class="eyebrow">المنهج القطري<template v-if="academicYear">، <bdi dir="ltr">{{ academicYear }}</bdi></template></span>
      <h1>{{ pageTitle }}</h1>
      <p class="lead">
        ولّد اختبارًا تدريبيًا من 40، أو اختبارًا قصيرًا من 10 لدرس أو درسين، أو ورقة عمل لدرس (عادية أو علاجية أو
        إثرائية)، بمسائل جديدة في كل مرة ومفتاح حل.
      </p>
    </header>

    <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">
      حسابك لا يملك صلاحية توليد الأوراق. اطلب من المشرف إضافتك إلى مجموعة المعلمين.
    </p>
    <form v-else class="panel generator" :aria-busy="store.loading || store.optionsLoading || courses.loading" @submit.prevent="generate">
      <label v-if="courses.courses.length > 1" class="field course">
        المقرر
        <select
          class="select"
          :value="courses.selected"
          :disabled="store.loading"
          @change="courses.select(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="item in courses.courses" :key="item.slug" :value="item.slug" :disabled="!item.has_generators">
            {{ item.title }}{{ item.has_generators ? "" : " (لا مولّدات بعد)" }}
          </option>
        </select>
      </label>
      <fieldset class="mode">
        <legend class="visually-hidden">نوع الورقة</legend>
        <div class="segmented">
          <label><input v-model="mode" type="radio" value="exam" :disabled="!hasBlueprints" /><span><AppIcon name="test" />اختبار كامل</span></label>
          <label><input v-model="mode" type="radio" value="quiz" /><span><AppIcon name="problem" />اختبار قصير</span></label>
          <label><input v-model="mode" type="radio" value="worksheet" /><span><AppIcon name="worksheet" />ورقة عمل</span></label>
          <label><input v-model="mode" type="radio" value="bundle" :disabled="!hasBlueprints" /><span><AppIcon name="curriculum" />كل أوراق العمل بضغطة</span></label>
        </div>
      </fieldset>
      <p v-if="!hasBlueprints && !store.optionsLoading && store.lessons.length" class="mode-hint">
        جدول مواصفات هذا المقرر لم تكتمل مولّدات دروسه بعد، فالاختبار الكامل والحزمة غير متاحين؛ ورقة العمل والاختبار القصير متاحان.
      </p>

      <p v-if="mode === 'bundle'" class="mode-hint">
        ورقة لكل درس في جدول المواصفات، عدد مسائلها من وزن الدرس في الجدول، مرتبة سهل ثم متوسط ثم مهارات عليا،
        مع غلاف وفهرس. رقم الحزمة يعيد الأوراق نفسها.
      </p>
      <p v-if="mode === 'quiz'" class="mode-hint">
        اختبار من 10 درجات: أربعة أسئلة موضوعية بدرجة وسؤالان مقاليان بثلاث درجات، تتناوب على الدرسين إن اخترت درسين.
      </p>
      <div class="fields">
        <label v-if="mode === 'worksheet' || mode === 'quiz'" class="field" :class="mode === 'worksheet' ? 'wide' : ''">
          {{ mode === "quiz" ? "الدرس الأول" : "الدرس" }}
          <select v-model="lesson" class="select">
            <option v-for="item in store.worksheetLessons" :key="item.code" :value="item.code">
              {{ item.code }} {{ item.title }}
            </option>
          </select>
        </label>
        <label v-if="mode === 'quiz'" class="field">
          الدرس الثاني (اختياري)
          <select v-model="secondLesson" class="select">
            <option value="">درس واحد فقط</option>
            <option
              v-for="item in store.worksheetLessons.filter((row) => row.code !== lesson)"
              :key="item.code"
              :value="item.code"
            >
              {{ item.code }} {{ item.title }}
            </option>
          </select>
        </label>
        <label v-if="mode === 'worksheet'" class="field">
          غرض الورقة
          <select v-model="purpose" class="select">
            <option v-for="[code, name] in purposeEntries" :key="code" :value="code" :disabled="!purposeAvailable(code)">
              {{ name }}{{ purposeAvailable(code) ? "" : " (غير متاح)" }}
            </option>
          </select>
        </label>
        <label v-if="mode === 'worksheet' && !purpose" class="field">
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
          <template v-else><AppIcon name="generate" />{{ generateLabel }}</template>
        </button>
        <button v-if="store.paper || store.bundle" type="button" class="btn btn-secondary" @click="printPaper">
          <AppIcon name="print" />طباعة أو حفظ PDF
        </button>
        <button v-if="store.paper || store.bundle" type="button" class="btn btn-secondary" :disabled="pdf.busy" @click="downloadServerFile('pdf')">
          {{ pdf.busy ? pdf.statusText : "تنزيل PDF من الخادم" }}
        </button>
        <button v-if="store.paper || store.bundle" type="button" class="btn btn-secondary" :disabled="pdf.busy" @click="downloadServerFile('docx')">
          {{ pdf.busy ? pdf.statusText : "تصدير Word (DOCX)" }}
        </button>
        <button
          v-if="store.paper?.kind === 'exam' && !store.bundle"
          type="button"
          class="btn btn-secondary"
          :disabled="pdf.busy"
          @click="downloadServerFile('docx', 'school')"
        >
          {{ pdf.busy ? pdf.statusText : "Word بقالب المدرسة" }}
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
      <p v-if="courses.error" class="alert alert-error" role="alert">{{ courses.error }}</p>
      <p v-if="store.error" class="alert alert-error" role="alert" aria-live="assertive">{{ store.error }}</p>
      <p v-if="pdf.error" class="alert alert-error" role="alert">{{ pdf.error }}</p>
      <p v-else-if="pdf.status === 'done'" class="hint" role="status">{{ pdf.statusText }}.</p>
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

    <fieldset v-if="serverRequest" class="view-switch">
      <legend class="visually-hidden">طريقة عرض الورقة</legend>
      <div class="segmented">
        <label><input v-model="view" type="radio" value="paged" /><span><AppIcon name="worksheet" />الورقة صفحة بصفحة</span></label>
        <label><input v-model="view" type="radio" value="sheet" /><span><AppIcon name="worksheet" />الورقة متصلة</span></label>
        <label><input v-model="view" type="radio" value="pdf" /><span><AppIcon name="print" />صفحات PDF</span></label>
      </div>
      <p class="hint">
        {{
          view === "pdf"
            ? "ملف الخادم نفسه بحدود صفحاته وترقيمها كما يُطبع. الاستبدال من عرضَي «الورقة»."
            : view === "paged"
              ? "صفحة واحدة في كل مرة بالتقليب. حدود الصفحات هنا تقديرية؛ حدودها الحقيقية في «صفحات PDF»."
              : "الورقة متصلة من أولها إلى آخرها؛ «صفحات PDF» تعرض الملف الحقيقي بحدود صفحاته وترقيمها."
        }}
      </p>
    </fieldset>
  </div>

  <PdfPreview v-if="view === 'pdf' && serverRequest" :request="serverRequest" />
  <!-- الورقة تبقى في الصفحة خلف تبويب PDF (مخفية على الشاشة وحدها) حتى تطبعها «طباعة أو حفظ PDF» من المتصفح -->
  <div
    v-if="store.paper || store.bundle"
    ref="sheetWrap"
    class="sheet-focus"
    :class="{ 'behind-pdf': view === 'pdf' }"
    tabindex="-1"
    aria-live="polite"
    :aria-label="store.paper?.title ?? 'حزمة أوراق العمل'"
  >
    <PagedSheet :enabled="view === 'paged'">
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
    </PagedSheet>
  </div>
</template>

<style scoped>
.generator {
  display: grid;
  gap: var(--space-5);
}
.course {
  max-inline-size: 32rem;
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
.view-switch {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-4);
  border: 0;
  margin: var(--space-5) 0 0;
  padding: 0;
  min-inline-size: 0;
}
.view-switch .hint {
  margin: 0;
}
/* خلف تبويب PDF: الورقة تغيب عن الشاشة وحدها وتبقى للطباعة */
@media screen {
  .behind-pdf {
    display: none;
  }
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
/* الجوال (screens/mobile): رأس الصفحة بطاقة عنابية كبيرة بنصف قطر 3× */
@media (max-width: 900px) {
  .page-head {
    padding: var(--space-6) var(--space-5);
    border-radius: var(--radius-xl);
    background: var(--color-brand);
    color: var(--color-on-brand);
  }
  .page-head .eyebrow,
  .page-head .lead {
    color: var(--color-on-brand);
  }
  .page-head h1 {
    color: var(--color-on-brand);
    font-size: var(--text-xl);
  }
}
</style>
