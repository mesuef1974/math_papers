<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { requestKey, usePdfStore, type PdfRequest } from "@/stores/pdf";

// تبويب «صفحات PDF»: ملف الخادم الحقيقي نفسه (Chromium) في عارض المتصفح المدمج، فحدود الصفحات وترقيمها
// كما تُطبع لا كما تُقدَّر. الملف يُطلب عند فتح التبويب، ولا يُعاد طلبه مع كل تعديل: حين تتغير الورقة أو
// إعدادات طباعتها تُعلَّم المعاينة قديمةً ويحدّثها المعلم بزر، فلا تتراكم المهام على خيط الخادم الواحد.
const props = defineProps<{ request: PdfRequest }>();
const pdf = usePdfStore();

const stale = computed(() => pdf.previewStatus === "done" && pdf.previewKey !== requestKey(props.request));
// المتصفحات التي لا تعرض PDF داخل الصفحة (أغلب متصفحات الجوال) تعلن ذلك؛ ما لا يعلن شيئًا يُجرَّب فيه الإطار.
const inlineViewer = typeof navigator === "undefined" || navigator.pdfViewerEnabled !== false;

// التقليب: عارض المتصفح يفتح الملف على صفحة محددة بجزء الرابط (‎#page=N‎)، وتغيير الجزء وحده يبدّل الصفحة دون
// إعادة تحميل الملف. العدد من الخادم؛ حين لا يُعرف (0) يبقى العارض وحده بلا أزرار.
const page = ref(1);
const pages = computed(() => pdf.previewPages);
const paged = computed(() => inlineViewer && pages.value > 0);
const frameSrc = computed(() =>
  paged.value ? `${pdf.previewUrl}#page=${page.value}&view=Fit&toolbar=0&navpanes=0` : pdf.previewUrl,
);

function go(target: number) {
  const next = Math.round(target);
  page.value = Math.min(Math.max(Number.isFinite(next) ? next : 1, 1), Math.max(pages.value, 1));
}

function onPageInput(event: Event) {
  const input = event.target as HTMLInputElement;
  go(input.valueAsNumber);
  input.value = String(page.value);
}

// الكتاب العربي يبدأ من اليمين: السهم الأيسر والصفحة التالية، والأيمن والسابقة.
function onKey(event: KeyboardEvent) {
  if (!paged.value || (event.target as HTMLElement).tagName === "INPUT") return;
  const moves: Record<string, () => void> = {
    ArrowLeft: () => go(page.value + 1),
    PageDown: () => go(page.value + 1),
    ArrowRight: () => go(page.value - 1),
    PageUp: () => go(page.value - 1),
    Home: () => go(1),
    End: () => go(pages.value),
  };
  const move = moves[event.key];
  if (!move) return;
  event.preventDefault();
  move();
}

watch(
  () => pdf.previewUrl,
  () => {
    page.value = 1;
  },
);

function refresh() {
  void pdf.preview(props.request);
}

onMounted(() => {
  if (!pdf.previewBusy && !pdf.previewFresh(props.request)) refresh();
});
</script>

<template>
  <section class="pdf-preview no-print" aria-label="صفحات PDF كما تُطبع" @keydown="onKey">
    <p v-if="pdf.previewBusy" class="state" role="status">{{ pdf.previewText }}</p>
    <div v-else-if="pdf.previewStatus === 'error'" class="alert alert-error notice" role="alert">
      <span>{{ pdf.previewError }}</span>
      <button type="button" class="btn btn-secondary btn-small" @click="refresh">إعادة المحاولة</button>
    </div>
    <template v-else-if="pdf.previewStatus === 'done'">
      <div v-if="stale" class="alert alert-info notice" role="status">
        <span>تغيّرت الورقة أو إعدادات طباعتها بعد هذه المعاينة.</span>
        <button type="button" class="btn btn-secondary btn-small" @click="refresh">تحديث المعاينة</button>
      </div>
      <p v-if="!inlineViewer" class="alert alert-info">متصفحك لا يعرض PDF داخل الصفحة. افتح الملف من الرابط أدناه.</p>
      <template v-else>
        <nav v-if="paged" class="pager" aria-label="تقليب الصفحات">
          <button type="button" class="btn btn-secondary" :disabled="page <= 1" @click="go(page - 1)">
            <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><polyline points="9 6 15 12 9 18" /></svg>
            السابقة
          </button>
          <label class="where">
            <span class="visually-hidden">رقم الصفحة</span>
            <input
              class="input"
              type="number"
              inputmode="numeric"
              min="1"
              :max="pages"
              :value="page"
              @change="onPageInput"
            />
            <span aria-live="polite">من <bdi dir="ltr">{{ pages }}</bdi></span>
          </label>
          <button type="button" class="btn btn-secondary" :disabled="page >= pages" @click="go(page + 1)">
            التالية
            <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><polyline points="15 6 9 12 15 18" /></svg>
          </button>
        </nav>
        <iframe class="frame" :src="frameSrc" title="صفحات PDF كما تُطبع"></iframe>
      </template>
      <a class="open" :href="pdf.previewUrl" target="_blank" rel="noopener">فتح الملف في نافذة مستقلة</a>
    </template>
  </section>
</template>

<style scoped>
.pdf-preview {
  display: grid;
  gap: var(--space-3);
  margin-block-start: var(--space-6);
}
.state {
  margin: 0;
  padding: var(--space-6);
  border: var(--border);
  border-radius: var(--radius-md);
  background: var(--color-surface-sunken);
  color: var(--color-ink-soft);
  text-align: center;
}
.notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2) var(--space-4);
}
/* العارض يملأ الحاوية ويتولّى هو تكبير الصفحات؛ الارتفاع من ارتفاع النافذة حتى تُرى صفحة كاملة تقريبًا */
.frame {
  display: block;
  inline-size: 100%;
  block-size: clamp(480px, 85vh, 1400px);
  border: var(--border);
  border-radius: var(--radius-md);
  background: var(--color-surface-sunken);
}
.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}
.pager .btn {
  gap: var(--space-2);
  min-inline-size: 7.5rem;
}
.chev {
  inline-size: 1.1em;
  block-size: 1.1em;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.75;
  stroke-linecap: square;
  stroke-linejoin: miter;
}
.where {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-ink-soft);
}
.where .input {
  inline-size: 4.5rem;
  text-align: center;
}
.open {
  justify-self: start;
  font-size: var(--text-sm);
}
</style>
