<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import EmptyState from "@/components/EmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { type DeckPeriod, useDecksStore } from "@/stores/decks";

// عروض الحصص: المعلم يختار حصة من حصص الدروس، فيُبنى في الخادم عرضها من تحضيرها ومقاطع أمثلتها المنشورة، ثم ينزّل ملف PPTX.
const decks = useDecksStore();
const auth = useAuthStore();
const choice = ref("");

onMounted(() => {
  if (auth.canGenerate) void decks.load();
});
onBeforeUnmount(() => decks.stop());

const id = (p: DeckPeriod) => `${p.lesson}|${p.k}`;
const buildable = (p: DeckPeriod) => p.clips && p.status !== "fail";
const anyBuildable = computed(() => decks.periods.some(buildable));
const current = computed(() =>
  decks.periods.find((p) => id(p) === choice.value),
);
const built = computed(() =>
  decks.periods.find((p) => p.lesson === decks.lesson && p.k === decks.k),
);
const lessons = computed(() => {
  const groups = new Map<string, DeckPeriod[]>();
  for (const p of decks.periods)
    groups.set(p.lesson, [...(groups.get(p.lesson) ?? []), p]);
  return [...groups.entries()].map(([lesson, periods]) => ({
    lesson,
    title: periods[0].title,
    periods,
  }));
});

function label(p: DeckPeriod): string {
  const base = `الحصة ${p.k} من ${p.n} (الأسبوع ${p.week}، ${p.examples} أمثلة)`;
  if (!p.clips) return `${base}: مقاطعها لم تُنشر`;
  if (p.status === "fail") return `${base}: تحضيرها لم يجتز معاييره`;
  if (p.stale) return `${base}: عرضك السابق قديم`;
  return base;
}

function changed() {
  if (current.value) decks.select(current.value.lesson, current.value.k);
}

async function build() {
  if (!current.value) return;
  decks.select(current.value.lesson, current.value.k);
  await decks.request();
}
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">العروض التقديمية</span>
    <h1>عروض الحصص</h1>
    <p class="lead">
      اختر الحصة، فيُبنى عرضها من تحضيرها: أهدافها وأمثلة الكتاب وحلولها والتدريب
      والفحص والواجب، وجانب المعلم في ملاحظات المتحدث. تنزّله ملف PowerPoint يُعرض
      من اليمين لليسار.
    </p>
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">
    حسابك لا يملك صلاحية توليد الأوراق.
  </p>
  <div v-else class="panel" :aria-busy="decks.loading || decks.busy">
    <p v-if="decks.error" class="alert alert-error" role="alert">
      {{ decks.error }}
    </p>
    <EmptyState v-if="decks.loaded && !anyBuildable">
      لم تُنشر مقاطع أمثلة أي حصة بعد، فلا عروض لبنائها. تُنشر من جهاز المالك بأمر
      النشر.
    </EmptyState>
    <form v-else-if="decks.periods.length" class="form" @submit.prevent="build">
      <label class="field">
        <span>الحصة</span>
        <select v-model="choice" class="input" required @change="changed">
          <option value="" disabled>اختر الحصة</option>
          <optgroup
            v-for="group in lessons"
            :key="group.lesson"
            :label="`${group.lesson} — ${group.title}`"
          >
            <option
              v-for="p in group.periods"
              :key="id(p)"
              :value="id(p)"
              :disabled="!buildable(p)"
            >
              {{ label(p) }}
            </option>
          </optgroup>
        </select>
      </label>
      <button
        type="submit"
        class="btn btn-primary"
        :disabled="!current || !buildable(current) || decks.busy"
      >
        <AppIcon name="generate" />{{
          decks.busy ? "يُبنى العرض…" : "ابنِ العرض"
        }}
      </button>
    </form>
    <p v-if="current?.stale" class="alert alert-info stale">
      عدّلتَ تحضير هذه الحصة بعد آخر عرض طلبته لها، فذلك العرض قديم. ابنِ العرض من
      جديد ليطابق تحضيرك.
    </p>

    <div v-if="decks.status === 'pending'" class="status" role="status">
      يُبنى عرض الحصة الآن، وسيظهر رابط التنزيل هنا حين يجهز.
    </div>
    <div
      v-else-if="decks.status === 'ready'"
      class="status ready"
      role="status"
    >
      <p>
        العرض جاهز: الدرس <bdi dir="ltr">{{ decks.lesson }}</bdi><template
          v-if="built"
          >، الحصة {{ built.k }} من {{ built.n }}</template
        >.
      </p>
      <a class="btn btn-primary" :href="decks.url" download
        ><AppIcon name="print" />نزّل العرض</a
      >
    </div>
    <p
      v-else-if="decks.status === 'failed'"
      class="alert alert-error"
      role="alert"
    >
      تعذّر بناء العرض{{ decks.detail ? `: ${decks.detail}` : "" }}. أعد الطلب،
      وإن تكرر الفشل فبلّغ المشرف.
    </p>
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
  flex: 1 1 280px;
}
.status {
  margin-block-start: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
  justify-content: space-between;
  color: var(--color-ink-soft);
}
.status.ready {
  color: var(--color-ink);
}
.stale {
  margin-block: var(--space-3) 0;
}
</style>
