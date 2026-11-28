<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "@/components/AppIcon.vue";
import CourseSelect from "@/components/CourseSelect.vue";
import EmptyState from "@/components/EmptyState.vue";
import ObjectiveEditor from "@/components/ObjectiveEditor.vue";
import PrepOverridePanel from "@/components/PrepOverridePanel.vue";
import LessonPackagePanel from "@/components/LessonPackagePanel.vue";
import {
  usePrepObjectives,
  type ObjectiveDraft,
} from "@/composables/usePrepObjectives";
import { useAuthStore } from "@/stores/auth";
import { useCoursesStore } from "@/stores/courses";
import {
  periodKey,
  usePrepsStore,
  type CheckStatus,
  type PrepObjective,
  type PeriodOverride,
  type PrepPeriod,
  type SharedObjective,
  type SuggestionStatus,
} from "@/stores/preps";
import { isolateNumberRanges } from "@/utils/bidi";
import { paperRoute } from "@/utils/paperLink";

// تحضير الحصة: المعلم يختار حصة من حصص الخطة بترتيبها، فيرى تحضيرها بمراحله ومعاييره، وينزّله Word بنموذج الوزارة.
// الهدف الذي لم تُعتمد نصوص وحدته يظهر «معلَّقًا» بوصف مختصر يكمله المعلم. حصة غير الدرس (تهيئة، اختبار قصير، مراجعة،
// اختبار، مشروع، دعم) تحضيرها مشترك بأنشطتها وروابط أوراقها في «أوراق»، بلا أهداف ولا تعديل.
const preps = usePrepsStore();
const courses = useCoursesStore();
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const selected = ref("");

const STATUS_LABELS: Record<CheckStatus, string> = {
  pass: "ناجح",
  fail: "فاشل",
  pending: "معلَّق",
};
const SUGGESTION_LABELS: Record<SuggestionStatus, string> = {
  pending: "اقتراحك قيد المراجعة",
  accepted: "قُبل اقتراحك وسيصل النسخة المعتمدة",
  rejected: "رُفض اقتراحك",
  applied: "قُبل اقتراحك وصار في النسخة المعتمدة",
};

// مراجعة المعلم لأهداف حصته: هدف واحد يُعدَّل في مكانه، ونسخته الشخصية لا يراها غيره.
const review = usePrepObjectives();
const editing = ref<number | null>(null);
const reviewedOn = (iso: string) =>
  new Date(iso).toLocaleDateString("ar-u-nu-latn", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
const sharedText = (s: SharedObjective) =>
  [s.behavior, s.condition, s.criterion].filter(Boolean).join(" ");

async function saveObjective(objective: PrepObjective, draft: ObjectiveDraft) {
  if (
    objective.example !== null &&
    (await review.save(objective.example, draft))
  )
    editing.value = null;
}

async function resetObjective(objective: PrepObjective) {
  if (objective.example !== null && (await review.reset(objective.example)))
    editing.value = null;
}

const lessons = computed(() => {
  const groups = new Map<string, PrepPeriod[]>();
  for (const period of preps.periods) {
    const list = groups.get(period.lesson) ?? [];
    list.push(period);
    groups.set(period.lesson, list);
  }
  return [...groups.entries()].map(([lesson, periods]) => {
    const isLesson = (periods[0].kind ?? "lesson") === "lesson";
    return {
      lesson,
      title: periods[0].title,
      label: isLesson ? `${lesson} ${periods[0].title}` : periods[0].title,
      short: isLesson ? lesson : periods[0].title,
      periods,
    };
  });
});

const sheet = computed(() => preps.sheet);
const isLesson = computed(() => (sheet.value?.kind ?? "lesson") === "lesson");
const stageLabels = computed(() =>
  Object.fromEntries((sheet.value?.stages ?? []).map((s) => [s.name, s.label])),
);

// تعديل المعلم لتحضير حصته: الحفظ يعيد الورقة بعد إعادة الاشتقاق والفحص، والاسترجاع يعيد التحضير المشترك للدرس.
const saveOverride = (change: PeriodOverride) => preps.saveOverride(change);
const resetOverride = () => preps.saveOverride(null);
const blocking = computed(
  () => sheet.value?.checks.filter((c) => c.kind === "blocking") ?? [],
);
const others = computed(
  () => sheet.value?.checks.filter((c) => c.kind !== "blocking") ?? [],
);

async function openSelected() {
  const [lesson, k] = selected.value.split("/");
  if (!lesson || !k) return;
  editing.value = null;
  review.error.value = "";
  preps.editError = "";
  await router.replace({ query: { course: courses.selected, lesson, k } });
  await preps.open(lesson, Number(k));
}

async function loadCourse(lesson = "", k = 0) {
  await preps.load();
  const found =
    preps.periods.find((p) => p.lesson === lesson && p.k === k) ??
    preps.periods[0];
  if (found) {
    selected.value = periodKey(found);
    await openSelected();
  }
}

let ready = false;
onMounted(async () => {
  if (!auth.canGenerate) return;
  await courses.ensure(String(route.query.course ?? ""));
  await loadCourse(String(route.query.lesson ?? ""), Number(route.query.k));
  ready = true;
});

watch(
  () => courses.selected,
  async () => {
    if (!ready) return;
    selected.value = "";
    editing.value = null;
    preps.reset();
    await loadCourse();
  },
);

watch(selected, (value, previous) => {
  if (previous && value !== previous) void openSelected();
});
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">تحضير الحصة</span>
    <h1>تحضير الحصص</h1>
    <p class="lead">
      اختر حصة من حصص الخطة الفصلية بترتيبها، فترى تحضيرها بمراحله وأزمنتها
      ومعاييره، وتنزّله ملف Word بنموذج الوزارة.
    </p>
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">
    حسابك لا يملك صلاحية توليد الأوراق.
  </p>
  <div v-else class="panel" :aria-busy="preps.loading || preps.opening">
    <p v-if="preps.error" class="alert alert-error" role="alert">
      {{ preps.error }}
    </p>
    <CourseSelect :disabled="preps.opening || preps.saving" />
    <EmptyState v-if="preps.loaded && !preps.periods.length"
      >لا حصص في الخطة الفصلية بعد.</EmptyState
    >
    <form v-else-if="preps.periods.length" class="form" @submit.prevent>
      <label class="field">
        <span>الحصة</span>
        <select v-model="selected" class="input" required>
          <optgroup
            v-for="group in lessons"
            :key="group.lesson"
            :label="group.label"
          >
            <option
              v-for="period in group.periods"
              :key="periodKey(period)"
              :value="periodKey(period)"
            >
              {{ group.short }} — الحصة {{ period.k }} من
              {{ period.n }} (الأسبوع {{ period.week
              }}{{ period.customized ? "، معدَّل" : "" }})
            </option>
          </optgroup>
        </select>
      </label>
      <a v-if="sheet" class="btn btn-primary" :href="preps.url" download>
        <AppIcon name="print" />نزّل Word بنموذج الوزارة
      </a>
    </form>
  </div>

  <article v-if="sheet" class="panel prep" aria-live="polite">
    <header class="prep-head">
      <h2>
        <template v-if="isLesson"
          ><bdi dir="ltr">{{ sheet.lesson }}</bdi>
        </template>{{ sheet.lesson_title }}
      </h2>
      <p>
        {{ sheet.grade }}<template v-if="sheet.unit"
          >، الوحدة {{ sheet.unit }}</template
        >، {{ sheet.day_date }}،
        {{ sheet.minutes }} دقيقة، الفصل {{ sheet.semester }}
        {{ isolateNumberRanges(sheet.year) }}
      </p>
    </header>

    <p v-if="sheet.pending" class="alert alert-info">
      نصوص أهداف هذه الوحدة لم تُعتمد بعد: يظهر كل هدف وصفًا مختصرًا «معلَّقًا» تكمله
      في ملف Word حتى تُعتمد.
    </p>

    <dl class="facts">
      <div v-if="isLesson">
        <dt>نتاجات التعلم</dt>
        <dd>{{ sheet.outcomes || "—" }}</dd>
      </div>
      <div v-else>
        <dt>نطاق الدروس</dt>
        <dd>
          <template v-if="sheet.scope?.length">
            <bdi v-for="(code, i) in sheet.scope" :key="code" dir="ltr"
              >{{ code }}{{ i < sheet.scope.length - 1 ? "، " : "" }}</bdi
            >
          </template>
          <template v-else>—</template>
        </dd>
      </div>
      <div>
        <dt>مصادر التعلم</dt>
        <dd>{{ sheet.main_sources }}</dd>
      </div>
      <div>
        <dt>التهيئة ({{ sheet.warmup_minutes }} د)</dt>
        <dd class="activity">{{ sheet.warmup }}</dd>
      </div>
    </dl>

    <section v-if="!isLesson" class="papers" aria-labelledby="papers-title">
      <h3 id="papers-title">أوراق الحصة</h3>
      <ul v-if="sheet.papers?.length" class="paper-links">
        <li v-for="paper in sheet.papers" :key="paper.label">
          <RouterLink
            class="btn btn-secondary btn-small"
            :to="paperRoute(sheet.course, paper)"
            >{{ paper.label }}</RouterLink
          >
        </li>
      </ul>
      <p v-else class="muted">
        لا ورقة مولَّدة لهذه الحصة؛ يكمل المعلم أدواتها.
      </p>
    </section>

    <div class="objectives-head">
      <h3>{{ isLesson ? "أهداف التعلم" : "أنشطة الحصة" }}</h3>
      <template v-if="isLesson && !sheet.pending">
        <p v-if="sheet.review && !sheet.review.stale" class="reviewed">
          راجعتَها في {{ reviewedOn(sheet.review.reviewed_at) }}
        </p>
        <template v-else>
          <span v-if="sheet.review?.stale" class="badge status-fail"
            >تحتاج مراجعة</span
          >
          <button
            type="button"
            class="btn btn-secondary btn-small review-btn"
            :disabled="review.busy.value !== null"
            @click="review.markReviewed()"
          >
            راجعتُ أهداف الحصة
          </button>
        </template>
      </template>
    </div>
    <p v-if="review.error.value" class="alert alert-error" role="alert">
      {{ review.error.value }}
    </p>
    <div class="table-scroll">
      <table class="grid">
        <thead>
          <tr>
            <th scope="col">{{ isLesson ? "الهدف" : "النشاط" }}</th>
            <th scope="col">التعليم والتعلم</th>
            <th scope="col">التقويم البنائي</th>
            <th scope="col">الزمن</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(objective, i) in sheet.objectives" :key="i">
            <tr>
              <td rowspan="2" class="objective">
                <span v-if="objective.pending" class="badge status-pending"
                  >معلَّق</span
                >
                <span v-if="objective.mine" class="badge status-mine"
                  >نسختي</span
                >
                {{ objective.text }}
                <div
                  v-if="objective.stale && objective.mine && objective.shared"
                  class="alert alert-info stale"
                >
                  <p>تغيّر النص المعتمد بعد تعديلك:</p>
                  <p>المعتمد الآن: {{ sharedText(objective.shared) }}</p>
                  <p>نسختك: {{ objective.text }}</p>
                  <div class="actions">
                    <button
                      type="button"
                      class="btn btn-secondary btn-small"
                      :disabled="review.busy.value !== null"
                      @click="review.keepMine(objective)"
                    >
                      إبقاء نسختي
                    </button>
                    <button
                      type="button"
                      class="btn btn-secondary btn-small"
                      :disabled="review.busy.value !== null"
                      @click="resetObjective(objective)"
                    >
                      استرجاع المعتمد
                    </button>
                  </div>
                </div>
                <p v-if="objective.suggestion" class="suggestion">
                  {{ SUGGESTION_LABELS[objective.suggestion.status]
                  }}<template v-if="objective.suggestion.note"
                    >: {{ objective.suggestion.note }}</template
                  >
                </p>
                <button
                  v-if="objective.editable && editing !== objective.example"
                  type="button"
                  class="btn btn-secondary btn-small edit-btn"
                  :disabled="editing !== null || review.busy.value !== null"
                  @click="editing = objective.example"
                >
                  تعديل
                </button>
              </td>
              <td class="activity">{{ objective.teach_activity }}</td>
              <td class="activity">{{ objective.teach_assessment }}</td>
              <td rowspan="2">
                {{ objective.teach_minutes + objective.check_minutes }} د
              </td>
            </tr>
            <tr>
              <td class="activity">{{ objective.check_activity }}</td>
              <td>{{ objective.check_assessment }}</td>
            </tr>
            <tr
              v-if="editing !== null && editing === objective.example"
              class="editing"
            >
              <td colspan="4">
                <ObjectiveEditor
                  :objective="objective"
                  :busy="review.busy.value !== null"
                  @save="saveObjective(objective, $event)"
                  @cancel="editing = null"
                  @reset="resetObjective(objective)"
                />
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <dl class="facts">
      <div>
        <dt>الغلق الختامي ({{ sheet.closing_minutes }} د)</dt>
        <dd class="activity">{{ sheet.closing }}</dd>
      </div>
      <div v-if="isLesson">
        <dt>التمايز</dt>
        <dd>
          أساسي {{ sheet.basic || "—" }}، متقدم {{ sheet.advanced || "—" }}
        </dd>
      </div>
      <div>
        <dt>الواجب</dt>
        <dd>{{ sheet.homework || "—" }}</dd>
      </div>
    </dl>

    <h3>مراحل الحصة</h3>
    <div class="table-scroll">
      <table class="grid">
        <thead>
          <tr>
            <th scope="col">المرحلة</th>
            <th scope="col">الاستراتيجية</th>
            <th scope="col">الزمن</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="stage in sheet.stages" :key="stage.name">
            <td>{{ stage.label }}</td>
            <td>{{ stage.strategy || "—" }}</td>
            <td>{{ stage.minutes }} د</td>
          </tr>
        </tbody>
      </table>
    </div>

    <LessonPackagePanel
      :course="sheet.course"
      :lesson="sheet.lesson"
      :k="sheet.k"
      :version="sheet"
    />

    <PrepOverridePanel
      v-if="sheet.edit"
      :edit="sheet.edit"
      :k="sheet.k"
      :n="sheet.n"
      :labels="stageLabels"
      :saving="preps.saving"
      :error="preps.editError"
      @save="saveOverride"
      @reset="resetOverride"
    />

    <h3>معايير التحضير</h3>
    <ul class="checks">
      <li v-for="check in [...blocking, ...others]" :key="check.code">
        <span class="badge" :class="`status-${check.status}`">{{
          STATUS_LABELS[check.status]
        }}</span>
        <bdi dir="ltr" class="code">{{ check.code }}</bdi>
        {{ check.title
        }}<template v-if="check.kind === 'warning'"> (تنبيه)</template>
        <ul v-if="check.details.length" class="details">
          <li v-for="detail in check.details" :key="detail">{{ detail }}</li>
        </ul>
      </li>
    </ul>
  </article>
</template>

<style scoped>
/* النشاط ودور المعلم ودور الطالب كلٌّ في سطر */
.activity {
  white-space: pre-line;
}

.form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: end;
}
.form .field {
  flex: 1 1 320px;
}
.prep {
  margin-block-start: var(--space-4);
  display: grid;
  gap: var(--space-4);
}
.prep h2,
.prep h3 {
  margin: 0;
}
.prep-head p {
  margin: 0;
  color: var(--color-ink-soft);
}
.facts {
  display: grid;
  gap: var(--space-3);
  margin: 0;
}
.facts dt {
  font-weight: var(--weight-medium);
}
.facts dd {
  margin: 0;
  color: var(--color-ink-soft);
}
.grid {
  inline-size: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.grid th,
.grid td {
  border: 1px solid var(--color-line);
  padding: var(--space-2);
  text-align: center;
  vertical-align: middle;
}
.grid th {
  background: var(--color-surface-sunken);
}
.objectives-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}
.review-btn {
  margin-inline-start: auto;
}
.reviewed {
  margin: 0;
  margin-inline-start: auto;
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.objective {
  text-align: start;
}
.objective .badge {
  margin-inline-end: var(--space-1);
}
.stale,
.suggestion {
  margin-block: var(--space-2) 0;
  font-size: var(--text-sm);
}
.stale p {
  margin: 0;
}
.suggestion {
  color: var(--color-ink-soft);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-block-start: var(--space-2);
}
.edit-btn {
  display: flex;
  margin-block-start: var(--space-2);
}
.grid .editing td {
  text-align: start;
  background: var(--color-surface-sunken);
}
.status-mine {
  color: var(--color-ink);
  background: var(--color-brand-soft);
  border-color: transparent;
}
.papers {
  display: grid;
  gap: var(--space-2);
}
.paper-links {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.muted {
  margin: 0;
  color: var(--color-ink-soft);
}
.checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
}
.code {
  font-weight: var(--weight-medium);
}
.details {
  margin-block: var(--space-1) 0;
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.status-pass {
  color: var(--color-success);
  background: var(--color-success-soft);
  border-color: transparent;
}
.status-fail {
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border-color: transparent;
}
.status-pending {
  color: var(--color-ink);
  background: var(--color-info-soft);
  border-color: transparent;
}
</style>
