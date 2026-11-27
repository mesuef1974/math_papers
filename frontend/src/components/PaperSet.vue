<script setup lang="ts">
import { computed } from "vue";
import AnswerSheet from "@/components/AnswerSheet.vue";
import PaperSheet from "@/components/PaperSheet.vue";
import PrintFrame from "@/components/PrintFrame.vue";
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
    students?: string[]; // حزمة الشعبة: صاحب كل ورقة بترتيبها، فلا تُعدّ الأوراق نماذج
  }>(),
  { bubble: false, replaceable: false, replacing: "", modified: false, students: () => [] },
);
const emit = defineEmits<{ replace: [question: number, label: string] }>();

const FORM_LABELS: Record<string, string> = { A: "أ", B: "ب" };
const multi = computed(() => props.papers.length > 1);
function headerOf(paper: Paper, index: number): PaperHeaderData {
  const student = props.students[index] ?? "";
  return { ...props.header(paper), student, form: multi.value && !student ? FORM_LABELS[paper.form] : "" };
}
const hasMcq = (paper: Paper) => paper.questions.some((q) => q.kind === "mcq");
</script>

<template>
  <div class="paper-set">
    <PrintFrame>
      <template v-for="(paper, index) in papers" :key="`sheet-${index}`">
        <div class="form-block">
          <PaperSheet
            :paper="paper"
            :header="headerOf(paper, index)"
            :show-key="false"
            :replaceable="replaceable && index === 0"
            :replacing="replacing"
            :modified="modified && index === 0"
            @replace="(q, l) => emit('replace', q, l)"
          />
          <AnswerSheet v-if="bubble && hasMcq(paper)" :paper="paper" :header="headerOf(paper, index)" />
        </div>
      </template>
      <template v-if="showKey">
        <div v-for="(paper, index) in papers" :key="`key-${index}`" class="form-block">
          <PaperSheet :paper="paper" :header="headerOf(paper, index)" show-key hide-sheet :modified="modified && index === 0" />
          <AnswerSheet v-if="bubble && hasMcq(paper)" :paper="paper" :header="headerOf(paper, index)" answers />
        </div>
      </template>
    </PrintFrame>
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
