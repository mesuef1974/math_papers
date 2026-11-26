<script setup lang="ts">
// رسم المصنع: محطاته كما يعمل المشغّل. نسخة الواجهة من scripts/factory_view.py (اللوحة المحلية).
import { computed } from "vue";

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

const W = 1000;
const H = 440;
const BW = 168;
const BH = 96;
// [المفتاح، العنوان، ما يجري فيها، x، y]
const NODES: [string, string, string, number, number][] = [
  ["backlog", "البطاقات", "مواصفة وشرط نجاح", 816, 48],
  ["queue", "الطابور", "المشغّل كل 5 دقائق", 612, 48],
  ["build", "التنفيذ", "Sonnet في شجرة مستقلة", 408, 48],
  ["check", "الفحص المحلي", "ruff والهجرات والاختبارات", 204, 48],
  ["review", "المراجعة المستقلة", "Opus للقراءة فقط", 16, 48],
  ["approve", "اعتمادك", "البوابة البشرية", 16, 224],
  ["deploy", "الدمج والنشر", "GitHub ثم Railway", 204, 224],
  ["live", "منشورة", "خلال 48 ساعة", 408, 224],
  ["stuck", "تحتاج نظرًا", "فشل أو انقطاع", 816, 224],
];
const EDGES: [string, string][] = [
  ["backlog", "queue"],
  ["queue", "build"],
  ["build", "check"],
  ["check", "review"],
  ["review", "approve"],
  ["approve", "deploy"],
  ["deploy", "live"],
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

function tone(key: string, cards: BoardCard[]): string {
  if (cards.some((c) => c.group === "running")) return "run";
  if (!cards.length || key === "backlog") return "idle";
  return key === "stuck" ? "bad" : key === "approve" ? "wait" : "ok";
}

const short = (text: string, limit: number) => (text.length <= limit ? text : `${text.slice(0, limit - 1)}…`);

const nodes = computed(() =>
  NODES.map(([key, title, sub, x, y]) => {
    const cards = props.cards.filter((c) => stationOf(c) === key);
    return { key, title, sub, x, y, count: cards.length, state: tone(key, cards), note: short(cards[0]?.title ?? "", 24) };
  }),
);

const edges = computed(() => {
  const running = new Set(nodes.value.filter((n) => n.state === "run").map((n) => n.key));
  const spot = Object.fromEntries(NODES.map(([key, , , x, y]) => [key, { x, y }]));
  return EDGES.map(([a, b]) => {
    const from = spot[a];
    const to = spot[b];
    const left = to.x < from.x;
    const d =
      from.y === to.y
        ? `M${left ? from.x : from.x + BW},${from.y + BH / 2} L${left ? to.x + BW : to.x},${to.y + BH / 2}`
        : `M${from.x + BW / 2},${from.y + BH} L${to.x + BW / 2},${to.y}`;
    return { d, running: running.has(b) };
  });
});

const worker = computed(() =>
  props.pulse.warn ? "bad" : nodes.value.some((n) => n.state === "run") ? "run" : "",
);
</script>

<template>
  <div class="factory">
    <div class="canvas">
      <svg :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="رسم المصنع">
        <defs>
          <marker id="factory-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" class="head" />
          </marker>
        </defs>
        <text x="984" y="28" class="lane">① من البطاقة إلى الطلب</text>
        <text x="984" y="204" class="lane">② اعتمادك ثم الدمج والنشر</text>
        <template v-for="(edge, i) in edges" :key="i">
          <path :d="edge.d" class="flow" :class="{ run: edge.running }" marker-end="url(#factory-arrow)" />
          <path v-if="edge.running" :d="edge.d" class="packet" />
        </template>
        <g
          v-for="node in nodes"
          :key="node.key"
          class="node"
          :class="[node.state, { human: node.key === 'approve' }]"
          :data-station="node.key"
          :transform="`translate(${node.x},${node.y})`"
        >
          <rect v-if="node.state === 'run'" class="halo" x="-7" y="-7" :width="BW + 14" :height="BH + 14" rx="20" />
          <rect :width="BW" :height="BH" rx="14" />
          <text :x="BW - 12" y="24" class="title">{{ node.title }}</text>
          <text :x="BW - 12" y="42" class="sub">{{ node.sub }}</text>
          <text :x="BW - 12" y="68" class="note">{{ node.note }}</text>
          <circle cx="22" cy="20" r="13" class="badge" />
          <text x="22" y="25" class="count">{{ node.count }}</text>
        </g>
        <g transform="translate(16,352)" class="node" :class="worker">
          <rect width="968" height="72" rx="14" />
          <text x="952" y="28" class="title">المشغّل (MathPapers-Runner)</text>
          <text x="952" y="54" class="sub">{{ short(pulse.text, 130) }}</text>
        </g>
      </svg>
    </div>
    <section class="panel">
      <h2>الصمّامات</h2>
      <ul class="valves">
        <li v-for="item in SAFEGUARDS" :key="item">{{ item }}</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.canvas {
  overflow-x: auto;
}
svg {
  inline-size: 100%;
  min-inline-size: 760px;
  block-size: auto;
  display: block;
  direction: rtl;
}
text {
  text-anchor: start;
  fill: var(--color-ink);
}
.lane {
  font-size: 15px;
  font-weight: 700;
  fill: var(--color-ink-soft);
}
.title {
  font-size: 15px;
  font-weight: 700;
}
.sub {
  font-size: 11.5px;
  fill: var(--color-ink-soft);
}
.note {
  font-size: 12px;
  font-weight: 600;
  fill: var(--color-brand);
}
.count {
  font-size: 13px;
  font-weight: 700;
  text-anchor: middle;
}
.badge {
  fill: var(--color-surface-sunken);
  stroke: var(--color-line-strong);
}
.node rect {
  fill: var(--color-surface);
  stroke: var(--color-line-strong);
  stroke-width: 1.5;
}
.node.ok rect {
  stroke: var(--color-success);
  stroke-width: 2;
}
.node.run rect {
  stroke: var(--color-info);
  stroke-width: 3;
  fill: var(--color-info-soft);
}
.node.bad rect {
  stroke: var(--color-danger);
  fill: var(--color-danger-soft);
}
.node.human rect {
  stroke: var(--color-brand);
  stroke-dasharray: 5 4;
}
.node.human.wait rect {
  fill: var(--color-brand-soft);
  stroke-width: 3;
}
.node .halo {
  fill: none;
  stroke: var(--color-info);
  stroke-width: 6;
  animation: halo 1.6s ease-in-out infinite;
}
.flow {
  fill: none;
  stroke: var(--color-line-strong);
  stroke-width: 2.5;
}
.flow.run {
  stroke: var(--color-info);
  stroke-width: 3.5;
  stroke-dasharray: 8 7;
  animation: march 0.7s linear infinite;
}
.packet {
  fill: none;
  stroke: var(--color-info);
  stroke-width: 9;
  stroke-linecap: round;
  stroke-dasharray: 0.5 400;
  animation: travel 1.4s linear infinite;
}
.head {
  fill: var(--color-line-strong);
}
.valves {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr));
  gap: var(--space-1) var(--space-6);
}
@keyframes march {
  from {
    stroke-dashoffset: 15;
  }
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes halo {
  0%,
  100% {
    opacity: 0.12;
  }
  50% {
    opacity: 0.5;
  }
}
@keyframes travel {
  from {
    stroke-dashoffset: 60;
  }
  to {
    stroke-dashoffset: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .flow.run,
  .node .halo {
    animation: none;
  }
  .packet {
    display: none;
  }
}
</style>
