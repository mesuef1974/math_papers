<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import PageFlipper from "@/components/PageFlipper.vue";
import { planPages, type PageWindow, type SheetSpan } from "@/utils/paging";

// الورقة صفحة بصفحة: كل صفحة بطاقة A4 بهوامشها، ونافذتها تعرض مقطعًا من الورقة المتصلة (تُزاح المنصة بدل نقل
// العناصر)، فلا يتغير شيء في مكوّنات الورقة ولا في الطباعة: الطباعة تعيد الورقة متصلة (‎@media print‎ أدناه).
const props = defineProps<{ enabled: boolean }>();

const stage = ref<HTMLElement | null>(null);
const windowEl = ref<HTMLElement | null>(null);
const page = ref(1);
const starts = ref<PageWindow[]>([{ start: 0, end: 0 }]);
const pages = computed(() => (props.enabled ? starts.value.length : 0));
const current = computed(() => starts.value[Math.min(page.value, starts.value.length) - 1] ?? { start: 0, end: 0 });
const shift = computed(() => current.value.start);
// بكسل واحد يُقتطع من نهاية الصفحة التي تتبعها صفحة من الورقة نفسها، فلا يتسرب حدّ العنصر التالي بتقريب الكسور
const length = computed(() => {
  const index = Math.min(page.value, starts.value.length) - 1;
  const follows = starts.value[index + 1]?.start === current.value.end;
  return Math.max(current.value.end - current.value.start - (follows ? 1 : 0), 0);
});

let observers: { resize: ResizeObserver | null; mutation: MutationObserver | null } = { resize: null, mutation: null };
let frame = 0;

function spans(root: HTMLElement): SheetSpan[] {
  const rootRect = root.getBoundingClientRect();
  const scale = root.offsetWidth ? rootRect.width / root.offsetWidth : 1;
  const y = (element: Element) => (element.getBoundingClientRect().top - rootRect.top) / (scale || 1);
  const sheets = [...root.querySelectorAll<HTMLElement>(".sheet")].filter(
    (sheet) => !sheet.parentElement?.closest(".sheet"),
  );
  return sheets.map((sheet) => {
    const top = y(sheet);
    // أول جزء في السؤال ليس حدًّا: رأس السؤال يبقى مع أول أجزائه (‎break-after: avoid‎ في الطباعة)
    const cuts = [...sheet.querySelectorAll(":scope > *, .question, .part")]
      .filter((element) => !element.matches(".part") || element.closest(".question")?.querySelector(".part") !== element)
      .map(y);
    return { top, bottom: top + sheet.getBoundingClientRect().height / (scale || 1), cuts };
  });
}

function measure() {
  frame = 0;
  const root = stage.value;
  const box = windowEl.value;
  if (!props.enabled || !root || !box) return;
  const found = spans(root);
  const height = box.clientHeight;
  const next = found.length ? planPages(found, height) : [{ start: 0, end: height }];
  if (next.length !== starts.value.length || next.some(
      (value, index) =>
        Math.abs(value.start - starts.value[index].start) > 0.5 || Math.abs(value.end - starts.value[index].end) > 0.5,
    )) {
    starts.value = next.length ? next : [{ start: 0, end: height }];
  }
  if (page.value > starts.value.length) page.value = starts.value.length;
}

function schedule() {
  if (frame) return;
  frame = requestAnimationFrame(measure);
}

function observe() {
  release();
  const root = stage.value;
  if (!root || !props.enabled) return;
  if (typeof ResizeObserver !== "undefined") {
    observers.resize = new ResizeObserver(schedule);
    observers.resize.observe(root);
  }
  observers.mutation = new MutationObserver(schedule);
  observers.mutation.observe(root, { childList: true, subtree: true, characterData: true });
  void document.fonts?.ready.then(schedule);
  schedule();
}

function release() {
  observers.resize?.disconnect();
  observers.mutation?.disconnect();
  observers = { resize: null, mutation: null };
  if (frame) cancelAnimationFrame(frame);
  frame = 0;
}

onMounted(() => void nextTick(observe));
watch(
  () => props.enabled,
  () => void nextTick(observe),
);
onBeforeUnmount(release);
</script>

<template>
  <PageFlipper v-if="enabled" v-model:page="page" :pages="pages" class="paged">
    <div class="card paged-card" data-testid="paged-card">
      <div ref="windowEl" class="window">
        <div class="clip" :style="{ blockSize: `${length}px` }">
          <div ref="stage" class="stage" :style="{ transform: `translateY(${-shift}px)` }">
            <slot />
          </div>
        </div>
      </div>
    </div>
  </PageFlipper>
  <slot v-else />
</template>

<style scoped>
/* بطاقة الصفحة بحجم A4 وهوامشها؛ تُصغَّر كلها بنسبة --paper-zoom (من usePaperFit) حين تضيق الحاوية */
.card {
  inline-size: var(--page-width);
  block-size: var(--page-height);
  box-sizing: border-box;
  padding-block: var(--page-margin-block-start) var(--page-margin-block-end);
  margin-inline: auto;
  zoom: var(--paper-zoom, 1);
  background: var(--color-sheet);
  outline: 1px solid var(--color-line);
  box-shadow: var(--shadow-md);
}
.window {
  position: relative;
  block-size: 100%;
  overflow: hidden;
}
.clip {
  position: relative;
  overflow: hidden;
}
.stage {
  /* ورقة الشاشة داخل المنصة بلا تصغير ولا إطار؛ الفراغ أسفل كل ورقة بارتفاع النافذة فلا يتسرب ما بعدها */
  --paper-zoom: 1;
  position: absolute;
  inset-inline: 0;
  inset-block-start: 0;
}
.stage :deep(.sheet) {
  margin: 0;
  margin-block-end: calc(var(--page-height) - var(--page-margin-block-start) - var(--page-margin-block-end));
  padding-block: 0;
  outline: none;
  box-shadow: none;
}
@media print {
  .card {
    inline-size: 100%;
    block-size: auto;
    margin: 0;
    padding: 0;
    zoom: 1;
    outline: none;
    box-shadow: none;
  }
  .window {
    overflow: visible;
    block-size: auto;
  }
  .clip {
    overflow: visible;
    block-size: auto !important;
  }
  .stage {
    position: static;
    transform: none !important;
  }
  .stage :deep(.sheet) {
    margin-block-end: 0;
  }
}
</style>
