<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { STAGES, STATUS_LABEL, splitCode, type Stage } from "@/data/copilotPipeline";
import {
  BUS_LABEL,
  EDGES,
  LANES,
  LOOP_LABEL,
  NODE_H,
  NODE_W,
  PACKAGE,
  POS,
  SOURCE_BOX,
  VIEW_H,
  VIEW_TOP,
  VIEW_W,
} from "@/data/copilotLayout";

const TOUR_MS = 1900;

const live = ref(true);
const pinned = ref<number | null>(null);
const tourId = ref(1);
let timer: ReturnType<typeof setInterval> | undefined;

function startTour() {
  stopTour();
  timer = setInterval(() => {
    tourId.value = (tourId.value % STAGES.length) + 1;
  }, TOUR_MS);
}
function stopTour() {
  if (timer !== undefined) clearInterval(timer);
  timer = undefined;
}
onMounted(() => {
  // من يفضّل تقليل الحركة يبدأ بصفحة ساكنة؛ يبقى الاختيار والتفاصيل يعملان دونها.
  live.value = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (live.value) startTour();
});
onBeforeUnmount(stopTour);

function toggleLive() {
  live.value = !live.value;
  if (live.value && pinned.value === null) startTour();
  else stopTour();
}
function select(id: number) {
  if (pinned.value === id) {
    pinned.value = null; // نقرة ثانية تفك التثبيت وتستأنف الجولة
    if (live.value) startTour();
    return;
  }
  pinned.value = id;
  stopTour();
}

const activeId = computed<number>(() => pinned.value ?? tourId.value);
const active = computed<Stage>(() => STAGES.find((s) => s.id === activeId.value) ?? STAGES[0]);
const hotEdges = computed(() => new Set(EDGES.filter((e) => e.nodes.includes(activeId.value)).map((e) => e.id)));
const hotNodes = computed(() => {
  const ids = new Set<number>([activeId.value]);
  for (const e of EDGES) if (hotEdges.value.has(e.id)) e.nodes.forEach((n) => ids.add(n));
  return ids;
});
const packetEdges = EDGES.filter((e) => !e.still);
const badgeClass = { done: "badge-k", run: "badge-r", plan: "" } as const;

function nodeX(id: number): number {
  return POS[id].x - NODE_W;
}
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">معاون المعلم</span>
    <h1>مخطط التدفق الحي</h1>
    <p class="lead">
      كل نبضة على الخطوط بيانات تنتقل من مرحلة إلى التي بعدها. الجولة التلقائية تمر على المراحل بالترتيب، والنقر على مرحلة يثبّتها
      ويُظهر مدخلها ومخرجها ومتطلباتها.
    </p>
    <nav class="views" aria-label="عرض المعاون">
      <RouterLink class="btn btn-secondary btn-small" :to="{ name: 'copilot-automation' }">تفصيل المراحل</RouterLink>
      <RouterLink class="btn btn-secondary btn-small" :to="{ name: 'copilot-flow' }">مخطط التدفق الحي</RouterLink>
    </nav>
  </header>

  <div class="toolbar">
    <button type="button" class="btn btn-primary btn-small" :aria-pressed="live" @click="toggleLive">
      {{ live ? "إيقاف الحركة" : "تشغيل الحركة" }}
    </button>
    <ul class="legend" aria-label="مفتاح الرموز">
      <li><span class="badge badge-k">قائم</span></li>
      <li><span class="badge badge-r">جارٍ الآن</span></li>
      <li><span class="badge">مخطط</span></li>
      <li class="legend-note">النبضة: انتقال البيانات · الخط الرمادي: ملف الدرس · المتقطع العنابي: حلقة التحسين</li>
    </ul>
  </div>

  <section class="panel diagram" aria-label="مخطط تدفق الأتمتة">
    <div class="diagram-scroll">
      <svg
        class="flow"
        :class="{ live }"
        :viewBox="`0 ${VIEW_TOP} ${VIEW_W} ${VIEW_H - VIEW_TOP}`"
        role="group"
        aria-label="تسع عشرة مرحلة في ثلاثة مسارات"
      >
        <defs>
          <marker id="arrow-flow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto-start-reverse">
            <path class="mk mk-flow" d="M0 0L10 5L0 10z" />
          </marker>
          <marker id="arrow-feed" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto-start-reverse">
            <path class="mk mk-feed" d="M0 0L10 5L0 10z" />
          </marker>
          <marker id="arrow-loop" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="11" markerHeight="11" orient="auto-start-reverse">
            <path class="mk mk-loop" d="M0 0L10 5L0 10z" />
          </marker>
        </defs>

        <g v-for="lane in LANES" :key="lane.id" class="lane">
          <rect class="lane-bg" x="10" :y="lane.y" :width="VIEW_W - 20" :height="lane.h" />
          <rect class="lane-bar" :x="VIEW_W - 14" :y="lane.y" width="4" :height="lane.h" />
          <text class="lane-title" x="60" :y="lane.y + 32" text-anchor="end">{{ lane.name }}</text>
          <text class="lane-note" x="60" :y="lane.y + 54" text-anchor="end">{{ lane.note }}</text>
          <rect class="lane-accent" x="60" :y="lane.y + 62" width="72" height="3" />
        </g>

        <g class="source">
          <rect :x="SOURCE_BOX.x" :y="SOURCE_BOX.y" :width="SOURCE_BOX.w" :height="SOURCE_BOX.h" />
          <text :x="SOURCE_BOX.x + SOURCE_BOX.w / 2" :y="SOURCE_BOX.y + 23" text-anchor="middle">دليل المعلم وكتاب الطالب (PDF)</text>
        </g>

        <g class="edges">
          <path
            v-for="e in EDGES"
            :key="e.id"
            class="edge"
            :class="[`k-${e.kind}`, { hot: hotEdges.has(e.id), dim: !hotEdges.has(e.id) }]"
            :d="e.d"
            :marker-end="e.kind === 'feed' ? 'url(#arrow-feed)' : e.kind === 'loop' ? 'url(#arrow-loop)' : e.still ? undefined : 'url(#arrow-flow)'"
          />
        </g>
        <text class="edge-label" :x="BUS_LABEL.x" :y="BUS_LABEL.y" text-anchor="middle">{{ BUS_LABEL.text }}</text>
        <text class="edge-label loop-label" :x="LOOP_LABEL.x" :y="LOOP_LABEL.y" text-anchor="end">{{ LOOP_LABEL.text }}</text>

        <g v-if="live" class="packets" aria-hidden="true">
          <circle
            v-for="e in packetEdges"
            :key="`p-${e.id}`"
            class="packet"
            :class="`k-${e.kind}`"
            r="5"
            :style="`offset-path: path('${e.d}'); animation-delay: ${(e.order * 0.45).toFixed(2)}s`"
          />
        </g>

        <g
          v-for="s in STAGES"
          :key="s.id"
          class="node"
          :class="[`st-${s.status}`, { active: s.id === activeId, dim: !hotNodes.has(s.id) }]"
          role="button"
          tabindex="0"
          :aria-pressed="pinned === s.id"
          :aria-label="`المرحلة ${s.id}: ${s.title}، ${STATUS_LABEL[s.status]}`"
          @click="select(s.id)"
          @keydown.enter.prevent="select(s.id)"
          @keydown.space.prevent="select(s.id)"
        >
          <rect v-if="s.status === 'run'" class="ring" :x="nodeX(s.id)" :y="POS[s.id].y" :width="NODE_W" :height="NODE_H" />
          <rect class="body" :x="nodeX(s.id)" :y="POS[s.id].y" :width="NODE_W" :height="NODE_H" />
          <rect class="badge-box" :x="POS[s.id].x - 30" :y="POS[s.id].y" width="30" height="30" />
          <text class="badge-num" :x="POS[s.id].x - 15" :y="POS[s.id].y + 21" text-anchor="middle">{{ s.id }}</text>
          <text class="n-title" :x="POS[s.id].x - 40" :y="POS[s.id].y + 23" text-anchor="start">{{ s.title }}</text>
          <text class="n-sub" :x="POS[s.id].x - 14" :y="POS[s.id].y + 52" text-anchor="start">{{ s.sub }}</text>
          <text class="n-tag" :x="POS[s.id].x - 14" :y="POS[s.id].y + 74" text-anchor="start">{{ s.tag }}</text>
          <circle class="dot-ping" :cx="nodeX(s.id) + 16" :cy="POS[s.id].y + 69" r="5" />
          <circle class="dot" :cx="nodeX(s.id) + 16" :cy="POS[s.id].y + 69" r="5" />
          <text class="n-state" :x="nodeX(s.id) + 28" :y="POS[s.id].y + 74" text-anchor="end">{{ STATUS_LABEL[s.status] }}</text>
        </g>

        <g class="package">
          <rect class="pk-body" :x="PACKAGE.x - NODE_W" :y="PACKAGE.y" :width="NODE_W" :height="NODE_H" />
          <rect class="pk-frame" :x="PACKAGE.x - NODE_W + 6" :y="PACKAGE.y + 6" :width="NODE_W - 12" :height="NODE_H - 12" />
          <text class="pk-title" :x="PACKAGE.x - NODE_W / 2" :y="PACKAGE.y + 38" text-anchor="middle">بكج الدرس الكامل</text>
          <text class="pk-sub" :x="PACKAGE.x - NODE_W / 2" :y="PACKAGE.y + 60" text-anchor="middle">خطة · عرض · أوراق · تذكرة · واجب</text>
        </g>
      </svg>
    </div>
  </section>

  <section class="panel detail" aria-live="polite" aria-labelledby="detail-h">
    <header class="detail-head">
      <span class="num">{{ active.id }}</span>
      <h2 id="detail-h">{{ active.title }}</h2>
      <span class="badge" :class="badgeClass[active.status]">{{ STATUS_LABEL[active.status] }}</span>
      <span class="tag">{{ active.tag }}</span>
      <span v-if="pinned === null && live" class="auto">جولة تلقائية</span>
      <span v-else-if="pinned !== null" class="auto">مثبّتة، انقر عليها لفك التثبيت</span>
    </header>
    <div class="cols">
      <div class="col col-in">
        <h3>المدخل</h3>
        <ul>
          <li v-for="line in active.inputs" :key="line">
            <template v-for="(part, i) in splitCode(line)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
          </li>
        </ul>
      </div>
      <div class="col col-out">
        <h3>المخرج</h3>
        <ul>
          <li v-for="line in active.outputs" :key="line">
            <template v-for="(part, i) in splitCode(line)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
          </li>
        </ul>
      </div>
      <div class="col col-req">
        <h3>المتطلبات</h3>
        <ul>
          <li v-for="line in active.requirements" :key="line">
            <template v-for="(part, i) in splitCode(line)" :key="i"><code v-if="part.code">{{ part.text }}</code><template v-else>{{ part.text }}</template></template>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped src="../styles/flowDiagram.css"></style>
