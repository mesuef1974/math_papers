<script setup lang="ts">
import { computed } from "vue";
import AnswerSheet from "@/components/AnswerSheet.vue";
import PaperSheet from "@/components/PaperSheet.vue";
import type { Paper } from "@/stores/papers";
import type { PaperHeaderData } from "@/stores/print";

// مجموعة نماذج الورقة (أ، وب إن طُلب): الأوراق أولًا بورقة تظليلها، ثم المفاتيح كلها في الآخر.
// الاستبدال على النموذج أ فقط؛ النموذج ب يُعاد حتميًا من رقم النموذج.
const props = withDefaults(
  defineProps<{
    papers: Paper[];
    header: (paper: Paper) => PaperHeaderData;
    showKey: boolean;
    bubble?: boolean;
    replaceable?: boolean;
    replacing?: string;
    modified?: boolean;
  }>(),
  { bubble: false, replaceable: false, replacing: "", modified: false },
);
const emit = defineEmits<{ replace: [question: number, label: string] }>();

const FORM_LABELS: Record<string, string> = { A: "أ", B: "ب" };
const multi = computed(() => props.papers.length > 1);
function headerOf(paper: Paper): PaperHeaderData {
  return { ...props.header(paper), form: multi.value ? FORM_LABELS[paper.form] : "" };
}
const hasMcq = (paper: Paper) => paper.questions.some((q) => q.kind === "mcq");
</script>

<template>
  <div class="paper-set">
    <template v-for="(paper, index) in papers" :key="`sheet-${paper.form}`">
      <div class="form-block">
        <PaperSheet
          :paper="paper"
          :header="headerOf(paper)"
          :show-key="false"
          :replaceable="replaceable && index === 0"
          :replacing="replacing"
          :modified="modified && index === 0"
          @replace="(q, l) => emit('replace', q, l)"
        />
        <AnswerSheet v-if="bubble && hasMcq(paper)" :paper="paper" :header="headerOf(paper)" />
      </div>
    </template>
    <template v-if="showKey">
      <div v-for="(paper, index) in papers" :key="`key-${paper.form}`" class="form-block">
        <PaperSheet :paper="paper" :header="headerOf(paper)" show-key hide-sheet :modified="modified && index === 0" />
        <AnswerSheet v-if="bubble && hasMcq(paper)" :paper="paper" :header="headerOf(paper)" answers />
      </div>
    </template>
  </div>
</template>

<style scoped>
@media print {
  .form-block {
    break-before: page;
  }
  .form-block:first-child {
    break-before: auto;
  }
}
</style>
