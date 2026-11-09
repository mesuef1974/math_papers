<script setup lang="ts">
import { computed } from "vue";
import answerKey from "@/assets/icons/answer-key.svg?raw";
import curriculum from "@/assets/icons/curriculum.svg?raw";
import generate from "@/assets/icons/generate.svg?raw";
import levelChallenge from "@/assets/icons/level-challenge.svg?raw";
import levelEasy from "@/assets/icons/level-easy.svg?raw";
import print from "@/assets/icons/print.svg?raw";
import problem from "@/assets/icons/problem.svg?raw";
import teacher from "@/assets/icons/teacher.svg?raw";
import test from "@/assets/icons/test.svg?raw";
import worksheet from "@/assets/icons/worksheet.svg?raw";

// أيقونات هوية «أوراق» (خط 1.75 بلا تعبئة، تأخذ لون النص). المصدر ملفات SVG ثابتة من الحزمة المعتمدة، لا مدخلات مستخدم.
const ICONS = {
  "answer-key": answerKey,
  curriculum,
  generate,
  "level-challenge": levelChallenge,
  "level-easy": levelEasy,
  print,
  problem,
  teacher,
  test,
  worksheet,
} as const;
export type IconName = keyof typeof ICONS;

const props = defineProps<{ name: IconName }>();
const svg = computed(() => ICONS[props.name]);
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <span class="icon" aria-hidden="true" v-html="svg"></span>
</template>
