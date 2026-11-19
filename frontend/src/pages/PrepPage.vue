<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "@/components/AppIcon.vue";
import EmptyState from "@/components/EmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { periodKey, usePrepsStore, type CheckStatus, type PrepPeriod } from "@/stores/preps";
import { isolateNumberRanges } from "@/utils/bidi";

// تحضير الحصة: المعلم يختار حصة من حصص الدروس بترتيب الخطة، فيرى تحضيرها بمراحله ومعاييره، وينزّله Word بنموذج الوزارة.
// الهدف الذي لم تُعتمد نصوص وحدته يظهر «معلَّقًا» بوصف مختصر يكمله المعلم.
const preps = usePrepsStore();
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const selected = ref("");

const STATUS_LABELS: Record<CheckStatus, string> = { pass: "ناجح", fail: "فاشل", pending: "معلَّق" };

const lessons = computed(() => {
  const groups = new Map<string, PrepPeriod[]>();
  for (const period of preps.periods) {
    const list = groups.get(period.lesson) ?? [];
    list.push(period);
    groups.set(period.lesson, list);
  }
  return [...groups.entries()].map(([lesson, periods]) => ({ lesson, title: periods[0].title, periods }));
});

const sheet = computed(() => preps.sheet);
const blocking = computed(() => sheet.value?.checks.filter((c) => c.kind === "blocking") ?? []);
const others = computed(() => sheet.value?.checks.filter((c) => c.kind !== "blocking") ?? []);

async function openSelected() {
  const [lesson, k] = selected.value.split("/");
  if (!lesson || !k) return;
  await router.replace({ query: { lesson, k } });
  await preps.open(lesson, Number(k));
}

onMounted(async () => {
  if (!auth.canGenerate) return;
  await preps.load();
  const lesson = String(route.query.lesson ?? "");
  const k = Number(route.query.k);
  const found = preps.periods.find((p) => p.lesson === lesson && p.k === k) ?? preps.periods[0];
  if (found) {
    selected.value = periodKey(found);
    await openSelected();
  }
});

watch(selected, (value, previous) => {
  if (previous && value !== previous) void openSelected();
});
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">تحضير الحصة</span>
    <h1>تحضير الحصص</h1>
    <p class="lead">
      اختر حصة من حصص الدروس بترتيب الخطة الفصلية، فترى تحضيرها بمراحله الست وأزمنتها ومعاييره، وتنزّله ملف Word بنموذج
      الوزارة.
    </p>
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">حسابك لا يملك صلاحية توليد الأوراق.</p>
  <div v-else class="panel" :aria-busy="preps.loading || preps.opening">
    <p v-if="preps.error" class="alert alert-error" role="alert">{{ preps.error }}</p>
    <EmptyState v-if="preps.loaded && !preps.periods.length">لا حصص دروس في الخطة الفصلية بعد.</EmptyState>
    <form v-else-if="preps.periods.length" class="form" @submit.prevent>
      <label class="field">
        <span>الحصة</span>
        <select v-model="selected" class="input" required>
          <optgroup v-for="group in lessons" :key="group.lesson" :label="`${group.lesson} ${group.title}`">
            <option v-for="period in group.periods" :key="periodKey(period)" :value="periodKey(period)">
              {{ group.lesson }} — الحصة {{ period.k }} من {{ period.n }} (الأسبوع {{ period.week }})
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
        <bdi dir="ltr">{{ sheet.lesson }}</bdi> {{ sheet.lesson_title }}
      </h2>
      <p>
        {{ sheet.grade }}، الوحدة {{ sheet.unit }}، {{ sheet.day_date }}، {{ sheet.minutes }} دقيقة،
        الفصل {{ sheet.semester }} {{ isolateNumberRanges(sheet.year) }}
      </p>
    </header>

    <p v-if="sheet.pending" class="alert alert-info">
      نصوص أهداف هذه الوحدة لم تُعتمد بعد: يظهر كل هدف وصفًا مختصرًا «معلَّقًا» تكمله في ملف Word حتى تُعتمد.
    </p>

    <dl class="facts">
      <div>
        <dt>نتاجات التعلم</dt>
        <dd>{{ sheet.outcomes || "—" }}</dd>
      </div>
      <div>
        <dt>مصادر التعلم</dt>
        <dd>{{ sheet.main_sources }}</dd>
      </div>
      <div>
        <dt>التهيئة ({{ sheet.warmup_minutes }} د)</dt>
        <dd>{{ sheet.warmup }}</dd>
      </div>
    </dl>

    <h3>أهداف التعلم</h3>
    <div class="table-scroll">
      <table class="grid">
        <thead>
          <tr>
            <th scope="col">الهدف</th>
            <th scope="col">التعليم والتعلم</th>
            <th scope="col">التقويم البنائي</th>
            <th scope="col">الزمن</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(objective, i) in sheet.objectives" :key="i">
            <tr>
              <td rowspan="2">
                <span v-if="objective.pending" class="badge status-pending">معلَّق</span>
                {{ objective.text }}
              </td>
              <td>{{ objective.teach_activity }}</td>
              <td>{{ objective.teach_assessment }}</td>
              <td rowspan="2">{{ objective.teach_minutes + objective.check_minutes }} د</td>
            </tr>
            <tr>
              <td>{{ objective.check_activity }}</td>
              <td>{{ objective.check_assessment }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <dl class="facts">
      <div>
        <dt>الغلق الختامي ({{ sheet.closing_minutes }} د)</dt>
        <dd>{{ sheet.closing }}</dd>
      </div>
      <div>
        <dt>التمايز</dt>
        <dd>أساسي {{ sheet.basic || "—" }}، متقدم {{ sheet.advanced || "—" }}</dd>
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

    <h3>معايير التحضير</h3>
    <ul class="checks">
      <li v-for="check in [...blocking, ...others]" :key="check.code">
        <span class="badge" :class="`status-${check.status}`">{{ STATUS_LABELS[check.status] }}</span>
        <bdi dir="ltr" class="code">{{ check.code }}</bdi>
        {{ check.title }}<template v-if="check.kind === 'warning'"> (تنبيه)</template>
        <ul v-if="check.details.length" class="details">
          <li v-for="detail in check.details" :key="detail">{{ detail }}</li>
        </ul>
      </li>
    </ul>
  </article>
</template>

<style scoped>
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
