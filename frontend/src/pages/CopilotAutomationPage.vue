<script setup lang="ts">
import { computed, ref } from "vue";
import {
  BUNDLE,
  GROUPS,
  SOURCES,
  STAGES,
  STATUS_LABEL,
  splitCode,
  statusCounts,
  type GroupId,
  type StageStatus,
} from "@/data/copilotPipeline";

const group = ref<GroupId | "all">("all");
const status = ref<StageStatus | "all">("all");

const counts = statusCounts();
const groupOptions: { value: GroupId | "all"; label: string }[] = [
  { value: "all", label: "الكل" },
  { value: "A", label: "الاستخراج" },
  { value: "B", label: "البناء" },
  { value: "C", label: "الحصة" },
];
const statusOptions: { value: StageStatus | "all"; label: string }[] = [
  { value: "all", label: "الكل" },
  { value: "done", label: STATUS_LABEL.done },
  { value: "run", label: STATUS_LABEL.run },
  { value: "plan", label: STATUS_LABEL.plan },
];

const visible = computed(() =>
  STAGES.filter((s) => (group.value === "all" || s.group === group.value) && (status.value === "all" || s.status === status.value)),
);
const blocks = computed(() =>
  (Object.keys(GROUPS) as GroupId[])
    .map((id) => ({ id, ...GROUPS[id], stages: visible.value.filter((s) => s.group === id) }))
    .filter((block) => block.stages.length > 0),
);
const badgeClass: Record<StageStatus, string> = { done: "badge-k", run: "badge-r", plan: "" };
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">معاون المعلم</span>
    <h1>أتمتة المعاون: من المصادر إلى بكج الدرس</h1>
    <p class="lead">لكل مرحلة مدخلها ومخرجها ومتطلباتها. التوكنز تُصرف مرة واحدة على التأليف، ويعمل المعاون عند المعلم بلا توكنز.</p>
    <nav class="views" aria-label="عرض المعاون">
      <RouterLink class="btn btn-secondary btn-small" :to="{ name: 'copilot-automation' }">تفصيل المراحل</RouterLink>
      <RouterLink class="btn btn-secondary btn-small" :to="{ name: 'copilot-flow' }">مخطط التدفق الحي</RouterLink>
    </nav>
  </header>

  <section class="stats" aria-label="ملخص الحالة">
    <div class="stat"><strong>{{ STAGES.length }}</strong><span>مرحلة</span></div>
    <div class="stat"><strong>{{ counts.done }}</strong><span>قائمة</span></div>
    <div class="stat"><strong>{{ counts.run }}</strong><span>جارية الآن</span></div>
    <div class="stat"><strong>{{ counts.plan }}</strong><span>مخططة</span></div>
  </section>

  <section class="panel sources" aria-labelledby="sources-h">
    <h2 id="sources-h">المدخلات الأساسية</h2>
    <ul class="chips">
      <li v-for="item in SOURCES" :key="item" class="badge">{{ item }}</li>
    </ul>
  </section>

  <div class="filters" role="group" aria-label="تصفية المراحل">
    <div class="filter">
      <span class="filter-label">المسار</span>
      <div class="segmented">
        <label v-for="o in groupOptions" :key="o.value">
          <input v-model="group" type="radio" name="group" :value="o.value" />
          <span>{{ o.label }}</span>
        </label>
      </div>
    </div>
    <div class="filter">
      <span class="filter-label">الحالة</span>
      <div class="segmented">
        <label v-for="o in statusOptions" :key="o.value">
          <input v-model="status" type="radio" name="status" :value="o.value" />
          <span>{{ o.label }}</span>
        </label>
      </div>
    </div>
  </div>

  <p v-if="blocks.length === 0" class="alert alert-info" role="status">لا مرحلة بهذا الاختيار.</p>

  <section v-for="block in blocks" :key="block.id" class="block" :aria-labelledby="`g-${block.id}`">
    <div class="block-head">
      <h2 :id="`g-${block.id}`">{{ block.name }}</h2>
      <p>{{ block.note }}</p>
    </div>
    <article v-for="stage in block.stages" :id="`stage-${stage.id}`" :key="stage.id" class="stage">
      <header class="stage-head">
        <span class="num">{{ stage.id }}</span>
        <h3>{{ stage.title }}</h3>
        <span class="tag">{{ stage.tag }}</span>
        <span class="badge" :class="badgeClass[stage.status]">{{ STATUS_LABEL[stage.status] }}</span>
      </header>
      <div class="cols">
        <div class="col col-in">
          <h4>المدخل</h4>
          <ul>
            <li v-for="line in stage.inputs" :key="line">
              <template v-for="(part, i) in splitCode(line)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
            </li>
          </ul>
        </div>
        <div class="col col-out">
          <h4>المخرج</h4>
          <ul>
            <li v-for="line in stage.outputs" :key="line">
              <template v-for="(part, i) in splitCode(line)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
            </li>
          </ul>
        </div>
        <div class="col col-req">
          <h4>المتطلبات</h4>
          <ul>
            <li v-for="line in stage.requirements" :key="line">
              <template v-for="(part, i) in splitCode(line)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
            </li>
          </ul>
        </div>
      </div>
    </article>
  </section>

  <section class="panel bundle" aria-labelledby="bundle-h">
    <h2 id="bundle-h">المخرج النهائي: بكج الدرس</h2>
    <p>
      <template v-for="(part, i) in splitCode(BUNDLE)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
    </p>
  </section>
</template>

<style scoped>
.views {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-block-start: var(--space-4);
}
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-8);
  margin-block-end: var(--space-6);
}
.stat {
  display: grid;
}
.stat strong {
  font-size: var(--text-xl);
  font-weight: var(--weight-heading);
  color: var(--color-brand);
  line-height: var(--leading-tight);
  font-variant-numeric: tabular-nums;
}
.stat span {
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
.sources h2 {
  font-size: var(--text-lg);
  margin-block-end: var(--space-3);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-8);
  margin-block: var(--space-6);
}
.filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}
.filter-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
}
.block {
  margin-block-start: var(--space-8);
}
.block-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-1) var(--space-4);
  margin-block-end: var(--space-4);
}
.block-head h2 {
  font-size: var(--text-xl);
  margin: 0;
}
.block-head p {
  margin: 0;
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
.stage {
  background: var(--color-surface);
  border: var(--border);
  border-radius: var(--radius-sm);
  margin-block-end: var(--space-4);
  scroll-margin-block-start: calc(var(--topbar-height) + var(--space-4));
}
.stage-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-block-end: var(--border);
}
.num {
  min-inline-size: 2.2ch;
  font-size: var(--text-2xl);
  font-weight: var(--weight-heading);
  line-height: 1;
  color: var(--color-brand);
  font-variant-numeric: tabular-nums;
}
.stage-head h3 {
  flex: 1 1 14rem;
  margin: 0;
  font-size: var(--text-lg);
  line-height: var(--leading-tight);
}
.tag {
  font-size: var(--text-xs);
  color: var(--color-ink-soft);
  border: var(--border);
  border-radius: var(--radius-sm);
  padding-inline: var(--space-2);
}
.cols {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.col {
  min-inline-size: 0;
  padding: var(--space-3) var(--space-4) var(--space-4);
}
.col + .col {
  border-inline-start: var(--border);
}
.col-in {
  background: var(--color-info-soft);
}
.col-out {
  background: var(--color-success-soft);
}
.col-req {
  background: var(--color-sand-soft);
}
.col h4 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-ink);
}
.col ul {
  margin: 0;
  padding-inline-start: var(--space-5);
  font-size: var(--text-sm);
}
.col li {
  margin-block: var(--space-1);
  overflow-wrap: anywhere;
}
code {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  direction: ltr;
  unicode-bidi: isolate;
  background: var(--color-field);
  border: var(--border);
  border-radius: var(--radius-sm);
  padding-inline: var(--space-1);
}
.bundle {
  margin-block: var(--space-8);
  border-inline-start: 6px solid var(--color-accent);
}
.bundle h2 {
  font-size: var(--text-lg);
}
.bundle p {
  margin: 0;
  color: var(--color-ink-soft);
}
@media (max-width: 760px) {
  .cols {
    grid-template-columns: minmax(0, 1fr);
  }
  .col + .col {
    border-inline-start: 0;
    border-block-start: var(--border);
  }
}
</style>
