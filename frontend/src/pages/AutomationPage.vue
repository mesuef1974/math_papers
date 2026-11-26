<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api, ApiError } from "@/api/client";
import FactoryDiagram, { type BoardCard as Card } from "@/components/FactoryDiagram.vue";

interface Board {
  received_at: string | null;
  board: { stages: string[]; cards: Card[]; pulse: { text: string; warn: boolean } } | null;
}

const REFRESH_MS = 10_000;
// المشغّل يرسل كل 5 دقائق على الأقل؛ ما تجاوز هذا يعني أن الجهاز مطفأ أو الإرسال متعطل.
const STALE_MS = 12 * 60_000;
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
    <FactoryDiagram :cards="cards" :pulse="data.board.pulse" />

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
.rows {
  list-style: none;
  padding: 0;
}
.rows li {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-block: var(--space-2);
  border-block-end: 1px solid var(--color-line);
}
</style>
