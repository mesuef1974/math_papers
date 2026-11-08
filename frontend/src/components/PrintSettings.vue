<script setup lang="ts">
import { onMounted } from "vue";
import { usePrintStore } from "@/stores/print";

// إعدادات الطباعة: الترويسة الدائمة (تُحفظ في حساب المعلم) وحقول هذه الطباعة فقط (التاريخ والشعبة).
const print = usePrintStore();
onMounted(() => void print.load());
</script>

<template>
  <details class="panel settings">
    <summary>إعدادات الطباعة والترويسة</summary>
    <form class="grid" :aria-busy="print.saving" @submit.prevent="print.save()">
      <label class="field wide">
        اسم المدرسة
        <input v-model="print.profile.school" class="input" maxlength="160" autocomplete="organization" />
      </label>
      <label class="field">
        اسم المعلم
        <input v-model="print.profile.teacher_name" class="input" maxlength="120" autocomplete="name" />
      </label>
      <label class="field">
        المادة
        <input v-model="print.profile.subject" class="input" maxlength="80" required />
      </label>
      <label class="field wide">
        الصف والمسار
        <input v-model="print.profile.grade" class="input" maxlength="120" />
      </label>
      <label class="field">
        زمن الاختبار (دقيقة)
        <input v-model.number="print.profile.exam_minutes" class="input" type="number" min="10" max="300" dir="ltr" />
      </label>
      <label class="field">
        الشعبة (لهذه الطباعة)
        <input v-model="print.section" class="input" maxlength="20" />
      </label>
      <label class="field">
        التاريخ (لهذه الطباعة)
        <input v-model="print.date" class="input" maxlength="12" dir="ltr" />
      </label>
      <label class="field wide">
        تعليمات الاختبار
        <textarea v-model="print.profile.exam_instructions" class="input" rows="2" maxlength="500" />
      </label>
      <label class="field wide">
        تعليمات ورقة العمل
        <textarea v-model="print.profile.worksheet_instructions" class="input" rows="2" maxlength="500" />
      </label>
      <div class="actions wide">
        <button type="submit" class="btn btn-secondary" :disabled="print.saving">
          {{ print.saving ? "جارٍ الحفظ" : "حفظ الترويسة في حسابي" }}
        </button>
        <span v-if="print.saved" class="hint" role="status">حُفظت.</span>
        <span class="hint">التاريخ والشعبة لهذه الطباعة فقط ولا يُحفظان.</span>
      </div>
      <p v-if="print.error" class="alert alert-error wide" role="alert">{{ print.error }}</p>
    </form>
  </details>
</template>

<style scoped>
.settings {
  margin-block-start: var(--space-4);
}
summary {
  cursor: pointer;
  font-weight: var(--weight-medium);
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-4);
  margin-block-start: var(--space-4);
}
.wide {
  grid-column: 1 / -1;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}
.hint {
  color: var(--color-ink-soft);
  font-size: var(--text-sm);
}
textarea.input {
  resize: vertical;
  min-block-size: 0;
}
</style>
