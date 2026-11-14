<script setup lang="ts">
import { computed, useId } from "vue";
import type { Graph } from "@/stores/papers";

// رسم متجه بأسلوب الكتاب: شبكة على الأعداد الصحيحة، محوران بسهمين، نقاط مفتوحة ومغلقة.
// الإحداثيات رياضية (y للأعلى) وتُحوَّل هنا. الرسم دائمًا من اليسار لليمين مهما كان اتجاه الصفحة.
const props = withDefaults(defineProps<{ graph: Graph; compact?: boolean }>(), { compact: false });

const PAD = 22;
// معرّف السهم فريد لكل رسم؛ الصفحة تحمل رسومًا كثيرة والمعرّف المكرر HTML غير صالح.
const arrowId = `axis-arrow-${useId()}`;

// اسم الدالة مائل وعلامات الاشتقاق قائمة: الخط المائل المضمَّن لا يحمل العلامة، فكان المتصفح يرسمها بخط من الجهاز.
const label = computed(() => {
  const text = props.graph.label.replace(/″/g, "′′");
  const cut = text.search(/′/);
  return cut < 0 ? { name: text, primes: "" } : { name: text.slice(0, cut), primes: text.slice(cut) };
});

const view = computed(() => {
  const [xMin, xMax, yMin, yMax] = props.graph.window;
  const UNIT = props.compact ? 17 : 26; // خيارات الرسوم أصغر حتى يتسع خياران في السطر
  const sx = (v: number) => PAD + (v - xMin) * UNIT;
  const sy = (v: number) => PAD + (yMax - v) * UNIT;
  const step = Math.max(xMax - xMin, yMax - yMin) > 12 ? 2 : 1;
  const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
  const path = (points: number[][]) => points.map(([px, py], i) => `${i ? "L" : "M"}${sx(px).toFixed(1)},${sy(py).toFixed(1)}`).join("");
  return {
    width: (xMax - xMin) * UNIT + PAD * 2,
    height: (yMax - yMin) * UNIT + PAD * 2,
    xs: range(xMin, xMax),
    ys: range(yMin, yMax),
    xTicks: range(xMin, xMax).filter((v) => v !== 0 && v % step === 0 && v !== xMax && v !== xMin),
    yTicks: range(yMin, yMax).filter((v) => v !== 0 && v % step === 0 && v !== yMax && v !== yMin),
    sx,
    sy,
    xMin,
    xMax,
    yMin,
    yMax,
    curves: props.graph.curves.map(path),
    lines: props.graph.lines.map(path),
  };
});

const title = computed(() => `تمثيل بياني للدالة ${props.graph.label}`);
</script>

<template>
  <figure class="graph" dir="ltr">
    <svg
      :viewBox="`0 0 ${view.width} ${view.height}`"
      :width="view.width"
      :height="view.height"
      role="img"
      :aria-label="title"
    >
      <defs>
        <marker :id="arrowId" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" class="axis-head" />
        </marker>
      </defs>
      <g class="grid">
        <line v-for="v in view.xs" :key="`gx${v}`" :x1="view.sx(v)" :x2="view.sx(v)" :y1="view.sy(view.yMin)" :y2="view.sy(view.yMax)" />
        <line v-for="v in view.ys" :key="`gy${v}`" :x1="view.sx(view.xMin)" :x2="view.sx(view.xMax)" :y1="view.sy(v)" :y2="view.sy(v)" />
      </g>
      <g class="axes">
        <line :x1="view.sx(view.xMin)" :x2="view.sx(view.xMax) + 10" :y1="view.sy(0)" :y2="view.sy(0)" :marker-start="`url(#${arrowId})`" :marker-end="`url(#${arrowId})`" />
        <line :x1="view.sx(0)" :x2="view.sx(0)" :y1="view.sy(view.yMin)" :y2="view.sy(view.yMax) - 10" :marker-start="`url(#${arrowId})`" :marker-end="`url(#${arrowId})`" />
        <text :x="view.sx(view.xMax) + 6" :y="view.sy(0) - 8" class="axis-name">x</text>
        <text :x="view.sx(0) + 8" :y="view.sy(view.yMax) - 4" class="axis-name">y</text>
      </g>
      <line
        v-for="v in graph.asymptotes"
        :key="`as${v}`"
        class="asymptote"
        :x1="view.sx(v)"
        :x2="view.sx(v)"
        :y1="view.sy(view.yMin)"
        :y2="view.sy(view.yMax)"
      />
      <!-- الأرقام بهالة بلون الخلفية تحت المنحنى؛ المنحنى في المقدمة فوق الشبكة والمحاور والأرقام -->
      <g class="ticks">
        <text v-for="v in view.xTicks" :key="`tx${v}`" :x="view.sx(v)" :y="view.sy(0) + 15" text-anchor="middle">{{ v }}</text>
        <text v-for="v in view.yTicks" :key="`ty${v}`" :x="view.sx(0) - 6" :y="view.sy(v) + 4" text-anchor="end">{{ v }}</text>
      </g>
      <path v-for="(d, i) in view.lines" :key="`l${i}`" :d="d" class="helper" />
      <path v-for="(d, i) in view.curves" :key="`c${i}`" :d="d" class="curve" />
      <circle
        v-for="([px, py, closed], i) in graph.dots"
        :key="`d${i}`"
        :cx="view.sx(px)"
        :cy="view.sy(py)"
        r="4.2"
        :class="closed ? 'dot closed' : 'dot open'"
      />
    </svg>
    <figcaption v-if="!compact" class="caption">
      <i>y</i> = <i>{{ label.name }}</i>{{ label.primes }}(<i>x</i>)
    </figcaption>
  </figure>
</template>

<style scoped>
.graph {
  margin-block: 8px;
  margin-inline: 0;
  display: inline-grid;
  justify-items: center;
  gap: 2px;
  max-inline-size: 100%;
}
svg {
  max-inline-size: 100%;
  block-size: auto;
  color: var(--color-ink);
  font-family: var(--font-math);
}
/* على الورق رسم المسألة بارتفاع أقصى 62mm بالنسبة نفسها، فيتسع سؤالان بيانيان في الصفحة ولا يُقصّ شيء */
@media print {
  svg {
    max-block-size: 62mm;
    inline-size: auto;
  }
}
.grid line {
  stroke: var(--color-line-strong);
  stroke-width: 1;
}
.axes line {
  stroke: currentColor;
  stroke-width: 1.3;
}
.axis-head {
  fill: currentColor;
}
.axis-name {
  fill: currentColor;
  font-style: italic;
  font-size: 15px;
}
.ticks text {
  fill: var(--color-ink-soft);
  font-size: 12px;
  stroke: var(--color-sheet);
  stroke-width: 3.5px;
  stroke-linejoin: round;
  paint-order: stroke;
}
.curve {
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.asymptote,
.helper {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.3;
  stroke-dasharray: 6 5;
}
.dot {
  stroke: currentColor;
  stroke-width: 1.8;
}
.dot.closed {
  fill: currentColor;
}
.dot.open {
  fill: var(--color-sheet);
}
.caption {
  font-family: var(--font-math);
  font-size: 15px;
}
</style>
