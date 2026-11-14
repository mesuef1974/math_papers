<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import PageFlipper from "@/components/PageFlipper.vue";
import { requestKey, usePdfStore, type PdfRequest } from "@/stores/pdf";

// تبويب «صفحات PDF»: ملف الخادم الحقيقي نفسه (Chromium) في عارض المتصفح المدمج، فحدود الصفحات وترقيمها
// كما تُطبع لا كما تُقدَّر. الملف يُطلب عند فتح التبويب، ولا يُعاد طلبه مع كل تعديل: حين تتغير الورقة أو
// إعدادات طباعتها تُعلَّم المعاينة قديمةً ويحدّثها المعلم بزر، فلا تتراكم المهام على خيط الخادم الواحد.
const props = defineProps<{ request: PdfRequest }>();
const pdf = usePdfStore();

const stale = computed(() => pdf.previewStatus === "done" && pdf.previewKey !== requestKey(props.request));
// المتصفحات التي لا تعرض PDF داخل الصفحة (أغلب متصفحات الجوال) تعلن ذلك؛ ما لا يعلن شيئًا يُجرَّب فيه الإطار.
const inlineViewer = typeof navigator === "undefined" || navigator.pdfViewerEnabled !== false;

// التقليب: عارض المتصفح لا يبدّل صفحته حين يتغير جزء الرابط وحده، فيُعاد تحميل الإطار لكل صفحة (‎:key‎) وهو يفتح
// الملف على الصفحة المطلوبة (‎#page=N‎). الإطار بنسبة A4 وفوقه طبقة تمنع تمرير العارض، فلا تُرى الصفحات المجاورة.
// العدد من الخادم؛ حين لا يُعرف (0) يبقى العارض وحده بلا أزرار.
const page = ref(1);
const pages = computed(() => pdf.previewPages);
const paged = computed(() => inlineViewer && pages.value > 0);
const frameSrc = computed(() =>
  paged.value ? `${pdf.previewUrl}#page=${page.value}&view=Fit&toolbar=0&navpanes=0` : pdf.previewUrl,
);

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
      <p v-if="!inlineViewer" class="alert alert-info">متصفحك لا يعرض PDF داخل الصفحة. افتح الملف من الرابط أدناه.</p>
      <PageFlipper v-else v-model:page="page" :pages="paged ? pages : 0">
        <div class="frame-box" :class="{ locked: paged }">
          <iframe :key="paged ? page : 0" class="frame" :src="frameSrc" title="صفحات PDF كما تُطبع"></iframe>
          <div v-if="paged" class="lock" aria-hidden="true"></div>
        </div>
      </PageFlipper>
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
.frame-box {
  position: relative;
}
/* صفحة واحدة بنسبة A4 في إطار لا يتجاوز ارتفاع النافذة؛ الطبقة تلتقط العجلة والنقر فلا يتمرر العارض */
.frame-box.locked {
  inline-size: min(100%, calc(85vh * 210 / 297));
  aspect-ratio: 210 / 297;
  margin-inline: auto;
}
.frame-box.locked .frame {
  block-size: 100%;
}
.lock {
  position: absolute;
  inset: 0;
}
.open {
  justify-self: start;
  font-size: var(--text-sm);
}
</style>
