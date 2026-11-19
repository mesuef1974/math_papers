<script setup lang="ts">
import { computed, ref, useId } from "vue";
import { NOTE_MAX, TEXT_MAX, TEXT_MIN, type ObjectiveDraft } from "@/composables/usePrepObjectives";
import type { PrepObjective } from "@/stores/preps";

// تعديل المعلم لهدف مثال في مكانه: السلوك ثابت من الملف المعتمد، والشرط والمعيار وحدهما يُعدَّلان (قرار المالك 2).
const props = defineProps<{ objective: PrepObjective; busy: boolean }>();
const emit = defineEmits<{ save: [draft: ObjectiveDraft]; cancel: []; reset: [] }>();

const start = props.objective.mine ?? props.objective.shared;
const condition = ref(start?.condition ?? "");
const criterion = ref(start?.criterion ?? "");
const suggest = ref(false);
const note = ref("");
const id = useId();

const clean = (text: string) => text.replace(/\s+/g, " ").trim();
const valid = (text: string) => clean(text).length >= TEXT_MIN && clean(text).length <= TEXT_MAX;
const canSave = computed(() => !props.busy && valid(condition.value) && valid(criterion.value));

function submit() {
  if (!canSave.value) return;
  emit("save", {
    condition: clean(condition.value),
    criterion: clean(criterion.value),
    suggest: suggest.value,
    note: suggest.value ? clean(note.value) : "",
  });
}
</script>

<template>
  <form class="editor" :aria-busy="busy" @submit.prevent="submit">
    <p class="behavior">
      <span class="label">السلوك (ثابت)</span>
      {{ objective.shared?.behavior }}
    </p>
    <label class="field">
      <span>الشرط</span>
      <textarea
        v-model="condition"
        class="input"
        rows="2"
        :maxlength="TEXT_MAX"
        required
        :aria-invalid="!valid(condition)"
        :aria-describedby="`${id}-condition`"
      />
      <small :id="`${id}-condition`" class="count">{{ clean(condition).length }} / {{ TEXT_MAX }}</small>
    </label>
    <label class="field">
      <span>المعيار</span>
      <textarea
        v-model="criterion"
        class="input"
        rows="2"
        :maxlength="TEXT_MAX"
        required
        :aria-invalid="!valid(criterion)"
        :aria-describedby="`${id}-criterion`"
      />
      <small :id="`${id}-criterion`" class="count">{{ clean(criterion).length }} / {{ TEXT_MAX }}</small>
    </label>
    <label class="check">
      <input v-model="suggest" type="checkbox" />
      <span>اقترحه للنسخة المعتمدة</span>
    </label>
    <label v-if="suggest" class="field">
      <span>ملاحظة للمراجِع (اختيارية)</span>
      <input v-model="note" class="input" :maxlength="NOTE_MAX" />
    </label>
    <div class="actions">
      <button type="submit" class="btn btn-primary btn-small" :disabled="!canSave">حفظ نسختي</button>
      <button type="button" class="btn btn-secondary btn-small" :disabled="busy" @click="emit('cancel')">إلغاء</button>
      <button
        v-if="objective.mine"
        type="button"
        class="btn btn-secondary btn-small"
        :disabled="busy"
        @click="emit('reset')"
      >
        استرجاع المعتمد
      </button>
    </div>
  </form>
</template>

<style scoped>
.editor {
  display: grid;
  gap: var(--space-3);
  text-align: start;
}
.behavior {
  margin: 0;
}
.label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  color: var(--color-ink-soft);
}
.count {
  justify-self: end;
  font-weight: var(--weight-regular);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
