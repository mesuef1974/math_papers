<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/api/client";
import PaperBundle from "@/components/PaperBundle.vue";
import PaperSet from "@/components/PaperSet.vue";
import type { BundleEntry, Paper } from "@/stores/papers";
import type { PdfRequest } from "@/stores/pdf";
import { usePrintStore } from "@/stores/print";
import { ensurePrintFonts } from "@/utils/printFonts";

// صفحة الطباعة للمتصفح الخادمي: تقرأ الحمولة برمز موقّع قصير العمر (بلا جلسة) وتعرض الأوراق بالمكونات
// نفسها، ثم تعلن جاهزيتها في data-print-ready بعد تحميل الخطوط حتى يطبع Chromium ما اكتمل لا ما بدأ.
const route = useRoute();
const print = usePrintStore();
const papers = ref<Paper[]>([]);
const bundle = ref<{ plan: BundleEntry[]; seed: number } | null>(null);
const error = ref("");

function signal(state: "1" | "error") {
  document.documentElement.dataset.printReady = state;
}

onMounted(async () => {
  try {
    const token = String(route.params.token ?? "");
    const payload = await api.get<PdfRequest>(`/pdf/print/${encodeURIComponent(token)}`);
    print.profile = payload.profile;
    print.date = payload.date;
    print.section = payload.section;
    print.showKey = payload.show_key;
    print.bubble = payload.bubble;
    bundle.value = payload.bundle ?? null;
    papers.value = payload.papers;
    await nextTick();
    await ensurePrintFonts();
    await (document.fonts?.ready ?? Promise.resolve());
    signal("1");
  } catch {
    error.value = "صفحة الطباعة غير متاحة أو انتهت مهلتها.";
    signal("error");
  }
});
const hasMcq = () => papers.value.some((paper) => paper.questions.some((q) => q.kind === "mcq"));
</script>

<template>
  <p v-if="error" class="alert alert-error" role="alert">{{ error }}</p>
  <PaperBundle
    v-else-if="papers.length && bundle"
    :papers="papers"
    :plan="bundle.plan"
    :seed="bundle.seed"
    :header="print.header"
    :show-key="print.showKey"
  />
  <PaperSet
    v-else-if="papers.length"
    :papers="papers"
    :header="print.header"
    :show-key="print.showKey"
    :bubble="print.bubble && hasMcq()"
  />
</template>
