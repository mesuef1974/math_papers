<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import PageFlipper from "@/components/PageFlipper.vue";
import PdfPageView from "@/components/PdfPageView.vue";
import { requestKey, usePdfStore, type PdfRequest } from "@/stores/pdf";

// تبويب «صفحات PDF»: ملف الخادم الحقيقي نفسه (Chromium) في عارض المتصفح المدمج، فحدود الصفحات وترقيمها
// كما تُطبع لا كما تُقدَّر. الملف يُطلب عند فتح التبويب، ولا يُعاد طلبه مع كل تعديل: حين تتغير الورقة أو
// إعدادات طباعتها تُعلَّم المعاينة قديمةً ويحدّثها المعلم بزر، فلا تتراكم المهام على خيط الخادم الواحد.
const props = defineProps<{ request: PdfRequest }>();
const pdf = usePdfStore();

const stale = computed(() => pdf.previewStatus === "done" && pdf.previewKey !== requestKey(props.request));
// المتصفحات التي لا تعرض PDF داخل الصفحة (أغلب متصفحات الجوال) تعلن ذلك؛ ما لا يعلن شيئًا يُجرَّب فيه الإطار.
const inlineViewer = typeof navigator === "undefined" || navigator.pdfViewerEnabled !== false;

// التقليب: صفحات الملف تُرسم على canvas بدقة الشاشة (PdfPageView) بدل عارض المتصفح الذي كان يُعاد بناؤه مع كل
// صفحة فيومض وجودته بحجم إطاره؛ فلا يلزم عارض داخلي في المتصفح ويعمل التقليب في الجوال أيضًا. العدد من الخادم؛
// حين لا يُعرف (0) يبقى عارض المتصفح وحده بلا أزرار، وبلا عارض داخلي يُعرض رابط الفتح.
const page = ref(1);
const pages = computed(() => pdf.previewPages);
const paged = computed(() => pages.value > 0);

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
  <section class="pdf-preview no-print" aria-label="صفحات PDF كما تُطبع">
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
      <PageFlipper v-if="paged" v-model:page="page" :pages="pages">
        <PdfPageView :url="pdf.previewUrl" :page="page" :pages="pages" />
      </PageFlipper>
      <p v-else-if="!inlineViewer" class="alert alert-info">متصفحك لا يعرض PDF داخل الصفحة. افتح الملف من الرابط أدناه.</p>
      <iframe v-else class="frame" :src="pdf.previewUrl" title="صفحات PDF كما تُطبع"></iframe>
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
/* عارض المتصفح عند جهل عدد الصفحات: يملأ الحاوية ويتولّى هو التكبير */
.frame {
  display: block;
  inline-size: 100%;
  block-size: clamp(480px, 85vh, 1400px);
  border: var(--border);
  border-radius: var(--radius-md);
  background: var(--color-surface-sunken);
}
.open {
  justify-self: start;
  font-size: var(--text-sm);
}
</style>
