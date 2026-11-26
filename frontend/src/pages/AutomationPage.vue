<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api, ApiError } from "@/api/client";

interface Card {
  id: string;
  title: string;
  group: string;
  at_stage: number;
  age: string;
  url: string;
  note: string;
}
interface Board {
  received_at: string | null;
  board: { stages: string[]; cards: Card[]; pulse: { text: string; warn: boolean } } | null;
}

const REFRESH_MS = 10_000;
// المشغّل يرسل كل 5 دقائق على الأقل؛ ما تجاوز هذا يعني أن الجهاز مطفأ أو الإرسال متعطل.
const STALE_MS = 12 * 60_000;
const DONE_LIMIT = 5;
const GROUPS: [string, string][] = [
  ["running", "تعمل الآن"],
  ["approval", "تنتظر اعتمادك"],
  ["queued", "في الطابور"],
  ["stuck", "عالقة وتحتاج نظرًا"],
  ["done", "انتهت خلال 48 ساعة"],
  ["backlog", "لم تُجهَّز بعد"],
];

const data = ref<Board | null>(null);
const error = ref("");
const now = ref(Date.now());
let timer: number | undefined;

async function load() {
  if (document.hidden) return;
  try {
    data.value = await api.get<Board>("/automation/board");
    error.value = "";
  } catch (failure) {
    const forbidden = failure instanceof ApiError && failure.status === 403;
    if (forbidden) data.value = null;
    error.value = forbidden ? "هذه الصفحة للمشرف العام فقط." : "تعذّر التحديث؛ تُعاد المحاولة تلقائيًا.";
  }
  now.value = Date.now();
}

onMounted(() => {
  void load();
  timer = window.setInterval(load, REFRESH_MS);
  document.addEventListener("visibilitychange", load);
});
onBeforeUnmount(() => {
  window.clearInterval(timer);
  document.removeEventListener("visibilitychange", load);
});

const received = computed(() => (data.value?.received_at ? new Date(data.value.received_at) : null));
const stale = computed(() => !!received.value && now.value - received.value.getTime() > STALE_MS);
const cards = computed(() => data.value?.board?.cards ?? []);
const sections = computed(() =>
  GROUPS.map(([id, name]) => ({ id, name, cards: cards.value.filter((c) => c.group === id) })).filter(
    (s) => s.cards.length,
  ),
);
// المخطط: الحية والعالقة في مرحلتها، وأحدث المنتهية في الأخيرة.
const columns = computed(() => {
  const stages = data.value?.board?.stages ?? [];
  const last = stages.length - 1;
  return stages.map((label, i) => ({
    label,
    cards:
      i === last
        ? cards.value.filter((c) => c.group === "done").slice(0, DONE_LIMIT)
        : cards.value.filter((c) => !["done", "backlog"].includes(c.group) && c.at_stage === i),
  }));
});
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">المشغّل</span>
    <h1>البث الحي للأتمتة</h1>
    <p v-if="received" class="lead">آخر وصول من الجهاز: <bdi>{{ received.toLocaleString("ar-QA-u-nu-latn") }}</bdi></p>
  </header>

  <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>
  <p v-if="data && !data.board" class="alert alert-info" role="status">لم تصل لقطة من الجهاز بعد.</p>

  <template v-if="data?.board">
    <p v-if="stale" class="alert alert-error" role="alert">انقطع البث: ما يظهر هو آخر لقطة وصلت.</p>
    <p class="alert" :class="data.board.pulse.warn ? 'alert-error' : 'alert-info'" role="status">
      {{ data.board.pulse.text }}
    </p>

    <ol class="flow" aria-label="مخطط المراحل">
      <li v-for="column in columns" :key="column.label" class="panel column">
        <h2>{{ column.label }} <span class="badge">{{ column.cards.length }}</span></h2>
        <p v-for="card in column.cards" :key="card.id" class="chip" :class="card.group" :title="card.title">
          <code dir="ltr">{{ card.id.slice(-6) }}</code> <bdi>{{ card.title }}</bdi>
        </p>
      </li>
    </ol>

    <section v-for="section in sections" :key="section.id" class="panel" :aria-label="section.name">
      <h2>{{ section.name }} <span class="badge">{{ section.cards.length }}</span></h2>
      <ul class="rows">
        <li v-for="card in section.cards" :key="card.id">
          <code dir="ltr">{{ card.id }}</code>
          <bdi>{{ card.title }}</bdi>
          <small>{{ card.age }}<template v-if="card.note"> · {{ card.note }}</template></small>
          <a v-if="card.url" :href="card.url" target="_blank" rel="noopener noreferrer">الطلب</a>
        </li>
      </ul>
    </section>
  </template>
</template>

<style scoped>
.flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: var(--space-3);
  list-style: none;
  padding: 0;
}
.column h2 {
  font-size: 1rem;
}
.chip {
  border: 1px solid var(--color-border);
  border-inline-start-width: 4px;
  border-radius: 8px;
  padding: var(--space-2);
  overflow-wrap: anywhere;
}
.chip.running,
.chip.approval {
  border-inline-start-color: var(--color-brand);
}
.rows {
  list-style: none;
  padding: 0;
}
.rows li {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-block: var(--space-2);
  border-block-end: 1px solid var(--color-border);
}
</style>
