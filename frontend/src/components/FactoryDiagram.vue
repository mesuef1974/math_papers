<script setup lang="ts">
// رسم المصنع بنمط «مخطط التدفق الحي»: محطاته كما يعمل المشغّل، وأعداد البطاقات من البث.
// اللوحة المحلية (scripts/factory_view.py) ترسم المحطات نفسها.
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

export interface BoardCard {
  id: string;
  title: string;
  group: string;
  at_stage: number;
  age: string;
  url: string;
  note: string;
}

const props = defineProps<{ cards: BoardCard[]; pulse: { text: string; warn: boolean } }>();

const W = 1040;
const H = 730;
const NW = 280;
const NH = 84;
const TOUR_MS = 1900;
const COL = [990, 660, 330]; // الحافة اليمنى لكل عمود، من اليمين إلى اليسار

interface Station {
  key: string;
  title: string;
  sub: string;
  tag: string;
  x: number;
  y: number;
  inputs: string;
  outputs: string;
  rule: string;
}

const STATIONS: Station[] = [
  { key: "backlog", title: "البطاقات", sub: "مواصفة وشرط نجاح", tag: "دفتر البطاقات", x: COL[0], y: 80,
    inputs: "طلبك أو بند من الخطة", outputs: "بطاقة بمواصفة", rule: "لا تُنفَّذ بطاقة دون شرط نجاح" },
  { key: "queue", title: "الطابور", sub: "المشغّل كل 5 دقائق", tag: "المهمة المجدولة", x: COL[1], y: 80,
    inputs: "بطاقة مجهَّزة", outputs: "بطاقة محجوزة للتنفيذ", rule: "إخفاقان متتاليان يوقفان المشغّل حتى تستأنفه" },
  { key: "build", title: "التنفيذ", sub: "Sonnet في شجرة مستقلة", tag: "git worktree", x: COL[2], y: 80,
    inputs: "المواصفة", outputs: "إيداع على فرع البطاقة", rule: "النموذج لا يدفع ولا يفتح طلبًا" },
  { key: "check", title: "الفحص المحلي", sub: "ruff والهجرات والاختبارات", tag: "prepush_check", x: COL[2], y: 210,
    inputs: "رأس الإيداع", outputs: "إيصال فحص على الرأس نفسه", rule: "لا إعادة لفشل الفحص، ولا دفع دون نجاحه" },
  { key: "review", title: "المراجعة المستقلة", sub: "Opus للقراءة فقط", tag: "رأي لا اعتماد", x: COL[1], y: 210,
    inputs: "الفرق بعد الفحص", outputs: "ملاحظات على الطلب", rule: "المراجعة الآلية رأي لا اعتماد" },
  { key: "approve", title: "اعتمادك", sub: "البوابة البشرية", tag: "اعتمد N", x: COL[0], y: 404,
    inputs: "طلب بفحوص خضراء", outputs: "سطر اعتماد مربوط برأس الإيداع", rule: "لا دمج قبل اعتمادك، ويسقط الاعتماد إن تغيّر الرأس" },
  { key: "deploy", title: "الدمج والنشر", sub: "GitHub ثم Railway", tag: "merge_gate", x: COL[1], y: 404,
    inputs: "طلب معتمد", outputs: "دمج في main ونشر", rule: "ما يمسّ الحرّاس والمسارات المحظورة لا يُدفع ولا يُدمج آليًا" },
  { key: "live", title: "منشورة", sub: "خلال 48 ساعة", tag: "تحقق من النشر", x: COL[2], y: 404,
    inputs: "نشر Railway", outputs: "ميزة في الإنتاج", rule: "تبقى ظاهرة 48 ساعة" },
  { key: "stuck", title: "تحتاج نظرًا", sub: "فشل أو انقطاع", tag: "يدوي", x: COL[0], y: 598,
    inputs: "فشل أو انقطاع", outputs: "قرارك: إعادة أو إلغاء", rule: "إعادة واحدة للانقطاع أو فشل النموذج" },
];
const WORKER = { x: COL[1], y: 598 };

const LANES = [
  { y: 40, h: 290, name: "من البطاقة إلى المراجعة" },
  { y: 364, h: 150, name: "اعتمادك ثم النشر" },
  { y: 558, h: 150, name: "الحراسة ونبض المشغّل" },
];

const at = (key: string) => STATIONS.find((s) => s.key === key)!;
const cx = (key: string) => at(key).x - NW / 2;
const cy = (key: string) => at(key).y + NH / 2;
const left = (a: string, b: string) => `M${at(a).x - NW} ${cy(a)}H${at(b).x + 3}`;
const right = (a: string, b: string) => `M${at(a).x} ${cy(a)}H${at(b).x - NW - 3}`;
const down = (a: string, b: string) => `M${cx(a)} ${at(a).y + NH}V${at(b).y - 3}`;

interface Edge {
  kind: "flow" | "feed" | "loop";
  from: string;
  to: string;
  d: string;
}
const EDGES: Edge[] = [
  { kind: "flow", from: "backlog", to: "queue", d: left("backlog", "queue") },
  { kind: "flow", from: "queue", to: "build", d: left("queue", "build") },
  { kind: "flow", from: "build", to: "check", d: down("build", "check") },
  { kind: "flow", from: "check", to: "review", d: right("check", "review") },
  { kind: "flow", from: "review", to: "approve", d: `M${cx("review")} ${at("review").y + NH}V347H${cx("approve")}V${at("approve").y - 3}` },
  { kind: "flow", from: "approve", to: "deploy", d: left("approve", "deploy") },
  { kind: "flow", from: "deploy", to: "live", d: left("deploy", "live") },
  { kind: "feed", from: "check", to: "stuck", d: `M${at("check").x - NW} ${cy("check")}H22V536H${cx("stuck")}V${at("stuck").y - 3}` },
  { kind: "loop", from: "stuck", to: "queue", d: `M${at("stuck").x} ${cy("stuck")}H1018V22H${cx("queue")}V${at("queue").y - 3}` },
];
const STATION = ["queue", "build", "check", "review", "approve", "deploy"]; // بترتيب مراحل اللقطة
const SAFEGUARDS = [
  "لا دمج قبل اعتمادك، والاعتماد مربوط برأس الإيداع فيسقط إن تغيّر",
  "النموذج لا يدفع ولا يفتح طلبًا؛ المشغّل وحده، وبعد فحص ناجح على الرأس نفسه",
  "ما يمسّ الحرّاس والمسارات المحظورة لا يُدفع آليًا",
  "إعادة واحدة للانقطاع أو فشل النموذج، ولا إعادة لفشل الفحص",
  "إخفاقان متتاليان يوقفان المشغّل حتى تستأنفه",
  "المراجعة الآلية رأي لا اعتماد",
];

function stationOf(card: BoardCard): string {
  if (card.group === "backlog" || card.group === "stuck") return card.group;
  if (card.group === "done") return card.note === "منشورة" ? "live" : "deploy";
  return STATION[Math.min(card.at_stage, STATION.length - 1)];
}

type Tone = "run" | "done" | "wait" | "bad" | "plan";
const TONE_LABEL: Record<Tone, string> = { run: "تعمل الآن", done: "فيها بطاقات", wait: "تنتظرك", bad: "متعثرة", plan: "هادئة" };

function tone(key: string, cards: BoardCard[]): Tone {
  if (cards.some((c) => c.group === "running")) return "run";
  if (!cards.length || key === "backlog") return "plan";
  return key === "stuck" ? "bad" : key === "approve" ? "wait" : "done";
}

const short = (text: string, limit: number) => (text.length <= limit ? text : `${text.slice(0, limit - 1)}…`);

const nodes = computed(() =>
  STATIONS.map((s, i) => {
    const cards = props.cards.filter((c) => stationOf(c) === s.key);
    return { ...s, num: i + 1, cards, state: tone(s.key, cards), line: cards[0] ? short(cards[0].title, 34) : s.sub };
  }),
);

const live = ref(true);
const pinned = ref<string | null>(null);
const tour = ref(0);
let timer: ReturnType<typeof setInterval> | undefined;

function stopTour() {
  if (timer !== undefined) clearInterval(timer);
  timer = undefined;
}
function startTour() {
  stopTour();
  timer = setInterval(() => (tour.value = (tour.value + 1) % STATIONS.length), TOUR_MS);
}
onMounted(() => {
  live.value = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (live.value) startTour();
});
onBeforeUnmount(stopTour);

function toggleLive() {
  live.value = !live.value;
  if (live.value && pinned.value === null) startTour();
  else stopTour();
}
function select(key: string) {
  if (pinned.value === key) {
    pinned.value = null; // نقرة ثانية تفك التثبيت وتستأنف الجولة
    if (live.value) startTour();
    return;
  }
  pinned.value = key;
  stopTour();
}

const activeKey = computed(() => pinned.value ?? STATIONS[tour.value].key);
const active = computed(() => nodes.value.find((n) => n.key === activeKey.value) ?? nodes.value[0]);
const edges = computed(() =>
  EDGES.map((e, order) => ({ ...e, order, hot: e.from === activeKey.value || e.to === activeKey.value })),
);
const hotNodes = computed(
  () => new Set([activeKey.value, ...edges.value.filter((e) => e.hot).flatMap((e) => [e.from, e.to])]),
);
const worker = computed(() => (props.pulse.warn ? "bad" : nodes.value.some((n) => n.state === "run") ? "run" : "done"));
</script>

<template>
  <div class="factory">
    <div class="toolbar">
      <button type="button" class="btn btn-primary btn-small" :aria-pressed="live" @click="toggleLive">
        {{ live ? "إيقاف الحركة" : "تشغيل الحركة" }}
      </button>
      <span class="legend-note">النبضة: مسار البطاقة · المتقطع العنابي: العودة إلى الطابور · الأعداد من آخر لقطة وصلت</span>
    </div>

    <section class="panel diagram" aria-label="رسم المصنع">
      <div class="diagram-scroll">
        <svg class="flow" :class="{ live }" :viewBox="`0 0 ${W} ${H}`" role="group" aria-label="محطات المصنع">
          <defs>
            <marker
              v-for="kind in ['flow', 'feed', 'loop']"
              :id="`factory-${kind}`"
              :key="kind"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerUnits="userSpaceOnUse"
              markerWidth="11"
              markerHeight="11"
              orient="auto-start-reverse"
            >
              <path class="mk" :class="`mk-${kind}`" d="M0 0L10 5L0 10z" />
            </marker>
          </defs>

          <g v-for="lane in LANES" :key="lane.name" class="lane">
            <rect class="lane-bg" x="34" :y="lane.y" :width="W - 68" :height="lane.h" />
            <rect class="lane-bar" :x="W - 38" :y="lane.y" width="4" :height="lane.h" />
            <text class="lane-note" x="48" :y="lane.y + 22" text-anchor="end">{{ lane.name }}</text>
          </g>

          <g class="edges">
            <path
              v-for="e in edges"
              :key="`${e.from}-${e.to}`"
              class="edge"
              :class="[`k-${e.kind}`, e.hot ? 'hot' : 'dim']"
              :d="e.d"
              :marker-end="`url(#factory-${e.kind})`"
            />
          </g>

          <g v-if="live" class="packets" aria-hidden="true">
            <circle
              v-for="e in edges"
              :key="`p-${e.from}-${e.to}`"
              class="packet"
              :class="`k-${e.kind}`"
              r="5"
              :style="`offset-path: path('${e.d}'); animation-delay: ${(e.order * 0.45).toFixed(2)}s`"
            />
          </g>

          <g
            v-for="n in nodes"
            :key="n.key"
            class="node"
            :class="[`st-${n.state}`, n.state, { active: n.key === activeKey, dim: !hotNodes.has(n.key) }]"
            :data-station="n.key"
            role="button"
            tabindex="0"
            :aria-pressed="pinned === n.key"
            :aria-label="`${n.title}: ${n.cards.length} بطاقة، ${TONE_LABEL[n.state]}`"
            @click="select(n.key)"
            @keydown.enter.prevent="select(n.key)"
            @keydown.space.prevent="select(n.key)"
          >
            <rect v-if="n.state === 'run'" class="ring" :x="n.x - NW" :y="n.y" :width="NW" :height="NH" />
            <rect class="body" :x="n.x - NW" :y="n.y" :width="NW" :height="NH" />
            <rect class="badge-box" :x="n.x - 30" :y="n.y" width="30" height="30" />
            <text class="badge-num" :x="n.x - 15" :y="n.y + 21" text-anchor="middle">{{ n.num }}</text>
            <text class="n-title" :x="n.x - 40" :y="n.y + 23" text-anchor="start">{{ n.title }}</text>
            <text class="n-sub" :x="n.x - 14" :y="n.y + 52" text-anchor="start">{{ n.line }}</text>
            <text class="n-tag" :x="n.x - 14" :y="n.y + 74" text-anchor="start">{{ n.tag }}</text>
            <circle class="dot-ping" :cx="n.x - NW + 16" :cy="n.y + 69" r="5" />
            <circle class="dot" :cx="n.x - NW + 16" :cy="n.y + 69" r="5" />
            <text class="n-state" :x="n.x - NW + 28" :y="n.y + 74" text-anchor="end">{{ n.cards.length }} · {{ TONE_LABEL[n.state] }}</text>
          </g>

          <g class="node worker" :class="`st-${worker}`">
            <rect class="body" :x="WORKER.x - 2 * NW - 50" :y="WORKER.y" :width="2 * NW + 50" :height="NH" />
            <text class="n-title" :x="WORKER.x - 14" :y="WORKER.y + 28" text-anchor="start">المشغّل (MathPapers-Runner)</text>
            <text class="n-sub" :x="WORKER.x - 14" :y="WORKER.y + 58" text-anchor="start">{{ short(pulse.text, 90) }}</text>
          </g>
        </svg>
      </div>
    </section>

    <section class="panel detail" aria-labelledby="factory-detail-h">
      <header class="detail-head">
        <span class="num">{{ active.num }}</span>
        <h2 id="factory-detail-h">{{ active.title }}</h2>
        <span class="badge">{{ active.cards.length }} · {{ TONE_LABEL[active.state] }}</span>
        <span class="tag">{{ active.tag }}</span>
        <span v-if="pinned === null && live" class="auto">جولة تلقائية</span>
        <span v-else-if="pinned !== null" class="auto">مثبّتة، انقر عليها لفك التثبيت</span>
      </header>
      <div class="cols">
        <div class="col col-in">
          <h3>البطاقات الآن</h3>
          <ul>
            <li v-for="card in active.cards" :key="card.id"><bdi>{{ card.title }}</bdi> · {{ card.age }}</li>
            <li v-if="!active.cards.length">لا بطاقات</li>
          </ul>
        </div>
        <div class="col col-out">
          <h3>المدخل ثم المخرج</h3>
          <ul>
            <li>{{ active.inputs }}</li>
            <li>{{ active.outputs }}</li>
          </ul>
        </div>
        <div class="col col-req">
          <h3>الصمّام</h3>
          <ul>
            <li>{{ active.rule }}</li>
          </ul>
        </div>
      </div>
    </section>

    <section class="panel safeguards">
      <h2>الصمّامات</h2>
      <ul class="valves">
        <li v-for="item in SAFEGUARDS" :key="item">{{ item }}</li>
      </ul>
    </section>
  </div>
</template>

<style scoped src="../styles/flowDiagram.css"></style>
<style scoped>
.st-wait .body {
  fill: var(--color-brand-soft);
  stroke: var(--color-brand);
  stroke-width: 3;
}
.st-wait .badge-box,
.st-wait .dot {
  fill: var(--color-brand);
}
.st-bad .body {
  fill: var(--color-danger-soft);
  stroke: var(--color-danger);
}
.st-bad .badge-box,
.st-bad .dot {
  fill: var(--color-danger);
}
.worker {
  cursor: default;
}
.safeguards {
  margin-block-start: var(--space-4);
}
.valves {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: var(--space-1) var(--space-6);
}
</style>
