<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { openPdf, PageRenderer } from "@/utils/pdfPages";

// صفحة واحدة من ملف الخادم على canvas بدقة الشاشة وبنسبتها الحقيقية، كاملةً في الحاوية. التقليب لا يُفرغ اللوحة:
// الصفحة الجديدة تُرسم في الخلفية (أو تُؤخذ من المخزن إن كانت جارةً سابقة التحميل) ثم تُنسخ فوق القديمة دفعة
// واحدة، فلا إطار فارغ بين صفحتين. حين تتغير مساحة الحاوية يبقى المرسوم ظاهرًا مصغَّرًا أو مكبَّرًا بالأنماط
// حتى يُعاد رسمه بالدقة الجديدة.
const props = defineProps<{ url: string; page: number; pages: number }>();

const box = ref<HTMLDivElement>();
const canvas = ref<HTMLCanvasElement>();
const ratio = ref(210 / 297);
const ready = ref(false);
const failed = ref(false);
const busy = ref(false);

let renderer: PageRenderer | null = null;
let turn = 0; // آخر طلب عرض: ما سبقه ونتيجته تتأخر يُهمَل
let observer: ResizeObserver | undefined;
let settle: ReturnType<typeof setTimeout> | undefined;

function density(): number {
  return typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
}

async function show() {
  const active = renderer;
  const target = canvas.value;
  if (!active || !target) return;
  const mine = ++turn;
  busy.value = true;
  try {
    const drawn = await active.page(props.page);
    if (mine !== turn) return;
    target.width = drawn.width;
    target.height = drawn.height;
    target.getContext("2d")?.drawImage(drawn, 0, 0);
    ready.value = true;
    busy.value = false;
    active.prefetch(props.page, props.pages);
  } catch {
    if (mine !== turn) return;
    busy.value = false;
    failed.value = true;
  }
}

async function load() {
  renderer?.destroy();
  renderer = null;
  ready.value = false;
  failed.value = false;
  const width = box.value?.clientWidth ?? 0;
  if (!props.url || width <= 0) return; // الحاوية مخفية: يبدأ الرسم حين تظهر وتُقاس
  try {
    const next = new PageRenderer(await openPdf(props.url), width, density());
    renderer = next;
    ratio.value = await next.ratio();
    await show();
  } catch {
    failed.value = true;
  }
}

function onResize() {
  clearTimeout(settle);
  settle = setTimeout(() => {
    const width = box.value?.clientWidth ?? 0;
    if (width <= 0) return;
    if (!renderer) {
      void load();
      return;
    }
    renderer.resize(width, density());
    void show();
  }, 150);
}

watch(() => props.url, load);
watch(() => props.page, show);

onMounted(() => {
  void load();
  if (box.value && typeof ResizeObserver !== "undefined") {
    observer = new ResizeObserver(onResize);
    observer.observe(box.value);
  }
});

onBeforeUnmount(() => {
  turn += 1;
  clearTimeout(settle);
  observer?.disconnect();
  renderer?.destroy();
  renderer = null;
});
</script>

<template>
  <div ref="box" class="page-box" :style="{ '--ratio': String(ratio) }" :aria-busy="busy">
    <canvas
      v-show="ready"
      ref="canvas"
      class="page-canvas"
      role="img"
      :aria-label="`الصفحة ${page} من ${pages}`"
    ></canvas>
    <p v-if="failed" class="alert alert-error state" role="alert">
      <span>تعذر عرض الصفحة هنا.</span>
      <button type="button" class="btn btn-secondary btn-small" @click="load">إعادة المحاولة</button>
    </p>
    <p v-else-if="!ready" class="state" role="status">جارٍ رسم الصفحة…</p>
  </div>
</template>

<style scoped>
/* صفحة كاملة بنسبتها داخل الحاوية: الارتفاع ما يتّسع للنافذة بعد شريط التقليب وتبويب الجوال السفلي (11rem)،
   وبحدّ أدنى لعرض مقروء على النوافذ القصيرة؛ الورقة بيضاء دائمًا كالمطبوع */
.page-box {
  position: relative;
  inline-size: min(100%, max(20rem, calc((100dvh - 11rem) * var(--ratio))));
  aspect-ratio: var(--ratio);
  margin-inline: auto;
  border: var(--border);
  border-radius: var(--radius-md);
  background: var(--color-surface-sunken);
  overflow: hidden;
}
.page-canvas {
  display: block;
  inline-size: 100%;
  block-size: 100%;
}
.state {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: var(--space-2);
  margin: 0;
  color: var(--color-ink-soft);
  text-align: center;
}
</style>
