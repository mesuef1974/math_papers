<script setup lang="ts">
import { bookRef } from "@/utils/bookRef";
import { computed, ref, watch } from "vue";
import type { PeriodOverride, PrepEdit } from "@/stores/preps";

// تعديل المعلم لتحضير حصته (له وحده): نقل مثال إلى الحصة المجاورة، واستراتيجية كل مرحلة، والتمارين المحذوفة.
// الخادم يعيد الاشتقاق والمعايير ويرفض ما يُفشل معيارًا حاجبًا برسالته؛ قواعد النقل هنا تعطيل للأزرار فقط.
const props = defineProps<{
  edit: PrepEdit;
  k: number;
  n: number;
  labels: Record<string, string>;
  saving: boolean;
  error: string;
}>();
const emit = defineEmits<{ save: [change: PeriodOverride]; reset: [] }>();

const MAX_EXAMPLES = 3;
const allocation = ref<number[][]>([]);
const strategies = ref<Record<string, string>>({});
const kept = ref<Set<number>>(new Set());

function fromProps() {
  allocation.value = props.edit.allocation.map((g) => [...g]);
  strategies.value = Object.fromEntries(
    props.edit.stages
      .filter((s) => s.chosen)
      .map((s) => [s.name, s.chosen as string]),
  );
  kept.value = new Set(
    props.edit.exercises.filter((x) => !props.edit.removed.includes(x)),
  );
}
watch(() => props.edit, fromProps, { immediate: true });

const mine = computed(() => allocation.value[props.k - 1] ?? []);
const lastPeriod = computed(() => props.k === props.n);
// حصة تقبل مثالًا: ليست الأخيرة (للتمايز والتقويم) ولم تبلغ السقف
const accepts = (k: number) =>
  k >= 1 &&
  k < props.n &&
  (allocation.value[k - 1]?.length ?? MAX_EXAMPLES) < MAX_EXAMPLES;
const canGiveBack = computed(
  () => mine.value.length > 1 && accepts(props.k - 1),
);
const canGiveForward = computed(
  () => mine.value.length > 1 && accepts(props.k + 1),
);
const moved = computed(
  () =>
    JSON.stringify(allocation.value) !== JSON.stringify(props.edit.allocation),
);
const choosable = computed(() =>
  props.edit.stages.filter((s) => s.options.length > 1),
);

function moveBack() {
  const [first, ...rest] = mine.value;
  allocation.value[props.k - 2].push(first);
  allocation.value[props.k - 1] = rest;
}

function moveForward() {
  const rest = mine.value.slice(0, -1);
  allocation.value[props.k].unshift(mine.value[mine.value.length - 1]);
  allocation.value[props.k - 1] = rest;
}

function toggle(exercise: number, on: boolean) {
  const next = new Set(kept.value);
  if (on) next.add(exercise);
  else next.delete(exercise);
  kept.value = next;
}

function setStrategy(stage: string, slug: string) {
  const next = { ...strategies.value };
  if (slug) next[stage] = slug;
  else delete next[stage];
  strategies.value = next;
}

function save() {
  emit("save", {
    ...(moved.value ? { allocation: allocation.value } : {}),
    strategies: strategies.value,
    removed: props.edit.exercises.filter((x) => !kept.value.has(x)),
  });
}

const titleOf = (stage: PrepEdit["stages"][number], slug: string) =>
  stage.options.find((o) => o.slug === slug)?.title ?? slug;
</script>

<template>
  <section class="override" aria-labelledby="override-title">
    <div class="override-head">
      <h3 id="override-title">تعديل تحضيري</h3>
      <span v-if="edit.state === 'active'" class="badge status-mine">معدَّل</span>
      <p class="hint">
        التعديل لك وحدك، ولا يتغير التحضير المشترك. يُعاد فحص التحضير قبل الحفظ.
      </p>
    </div>
    <p v-if="edit.state === 'invalid'" class="alert alert-info">
      تعديلك المحفوظ لهذا الدرس لم يعد يطابق أمثلته، فأُهمل وظهر التحضير المشترك.
      احفظ تعديلًا جديدًا أو استرجع المشترك.
    </p>
    <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>

    <fieldset v-if="!lastPeriod" class="group">
      <legend>أمثلة الحصة</legend>
      <p class="examples">
        <span v-for="example in mine" :key="example" class="chip"
          >{{ bookRef("مثال", example, edit.example_pages?.[example]) }}</span
        >
      </p>
      <div class="actions">
        <button
          v-if="k > 1"
          type="button"
          class="btn btn-secondary btn-small"
          :disabled="!canGiveBack || saving"
          @click="moveBack"
        >
          انقل {{ bookRef("المثال", mine[0]!, edit.example_pages?.[mine[0]!]) }} إلى الحصة {{ k - 1 }}
        </button>
        <button
          v-if="k + 1 < n"
          type="button"
          class="btn btn-secondary btn-small"
          :disabled="!canGiveForward || saving"
          @click="moveForward"
        >
          انقل {{ bookRef("المثال", mine[mine.length - 1]!, edit.example_pages?.[mine[mine.length - 1]!]) }} إلى الحصة {{ k + 1 }}
        </button>
      </div>
      <p v-if="moved" class="hint">
        بعد النقل:
        <template v-for="(group, i) in allocation" :key="i"
          ><template v-if="i">، </template>الحصة {{ i + 1 }}:
          {{ group.length ? group.join(" و") : "بلا مثال جديد" }}</template
        >
      </p>
    </fieldset>

    <fieldset v-if="choosable.length" class="group">
      <legend>استراتيجيات المراحل</legend>
      <label v-for="stage in choosable" :key="stage.name" class="field">
        <span>{{ labels[stage.name] ?? stage.name }}</span>
        <select
          class="input"
          :value="strategies[stage.name] ?? ''"
          :disabled="saving"
          @change="
            setStrategy(stage.name, ($event.target as HTMLSelectElement).value)
          "
        >
          <option value="">
            المشتقة آليًا{{
              stage.chosen ? "" : `: ${titleOf(stage, stage.current)}`
            }}
          </option>
          <option
            v-for="option in stage.options"
            :key="option.slug"
            :value="option.slug"
          >
            {{ option.title }}
          </option>
        </select>
      </label>
    </fieldset>

    <fieldset v-if="edit.exercises.length" class="group">
      <legend>تمارين الحصة</legend>
      <p class="hint">
        أزل علامة التمرين لحذفه من التدريب الصفي والتمايز والواجب.
      </p>
      <div class="exercises">
        <label v-for="exercise in edit.exercises" :key="exercise" class="check">
          <input
            type="checkbox"
            :checked="kept.has(exercise)"
            :disabled="saving"
            @change="
              toggle(exercise, ($event.target as HTMLInputElement).checked)
            "
          />
          <bdi dir="ltr">{{ exercise }}</bdi>
        </label>
      </div>
    </fieldset>

    <div class="actions">
      <button
        type="button"
        class="btn btn-primary"
        :disabled="saving"
        @click="save"
      >
        {{ saving ? "يُحفظ…" : "احفظ التعديل" }}
      </button>
      <button
        v-if="edit.state !== 'none'"
        type="button"
        class="btn btn-secondary"
        :disabled="saving"
        @click="emit('reset')"
      >
        استرجع التحضير المشترك للدرس
      </button>
      <button
        type="button"
        class="btn btn-secondary"
        :disabled="saving"
        @click="fromProps"
      >
        تراجع
      </button>
    </div>
  </section>
</template>

<style scoped>
.override {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-surface-sunken);
}
.override-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
}
.override-head h3 {
  margin: 0;
}
.hint {
  margin: 0;
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.override-head .hint {
  flex-basis: 100%;
}
.group {
  display: grid;
  gap: var(--space-2);
  margin: 0;
  padding: var(--space-3);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
}
.group legend {
  font-weight: var(--weight-medium);
  padding-inline: var(--space-1);
}
.examples,
.exercises,
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0;
}
.chip {
  padding-block: var(--space-1);
  padding-inline: var(--space-2);
  border-radius: var(--radius-md);
  background: var(--color-brand-soft);
  color: var(--color-ink);
  font-size: var(--text-sm);
}
.check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  min-inline-size: 3.5rem;
}
.status-mine {
  color: var(--color-ink);
  background: var(--color-brand-soft);
  border-color: transparent;
}
</style>
