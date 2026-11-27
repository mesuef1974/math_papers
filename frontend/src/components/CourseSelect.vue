<script setup lang="ts">
import { useCoursesStore } from "@/stores/courses";

// اختيار المقرر: مصدر واحد للصفحات كلها، ولا يظهر حين لا بديل.
defineProps<{ disabled?: boolean }>();
const courses = useCoursesStore();
</script>

<template>
  <label v-if="courses.courses.length > 1" class="field course">
    المقرر
    <select
      class="select"
      :value="courses.selected"
      :disabled="disabled"
      @change="courses.select(($event.target as HTMLSelectElement).value)"
    >
      <option v-for="item in courses.courses" :key="item.slug" :value="item.slug" :disabled="!item.has_generators">
        {{ item.title }}{{ item.has_generators ? "" : " (لا مولّدات بعد)" }}
      </option>
    </select>
  </label>
</template>
