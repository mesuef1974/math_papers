<script setup lang="ts">
// تقليب صفحة واحدة: شريط السابقة والتالية ورقم الصفحة ومفاتيح الأسهم حول أي محتوى (ورقة الشاشة أو ملف PDF).
// الصفحات تُرقَّم من 1؛ العدد 0 يعني «غير معروف» فلا يظهر الشريط ولا تعمل المفاتيح.
const page = defineModel<number>("page", { required: true });
const props = defineProps<{ pages: number }>();

function go(target: number) {
  const next = Math.round(target);
  page.value = Math.min(Math.max(Number.isFinite(next) ? next : 1, 1), Math.max(props.pages, 1));
}

function onPageInput(event: Event) {
  const input = event.target as HTMLInputElement;
  go(input.valueAsNumber);
  input.value = String(page.value);
}

// الكتاب العربي يبدأ من اليمين: السهم الأيسر والصفحة التالية، والأيمن والسابقة.
function onKey(event: KeyboardEvent) {
  if (props.pages <= 0 || (event.target as HTMLElement).tagName === "INPUT") return;
  const moves: Record<string, () => void> = {
    ArrowLeft: () => go(page.value + 1),
    PageDown: () => go(page.value + 1),
    ArrowRight: () => go(page.value - 1),
    PageUp: () => go(page.value - 1),
    Home: () => go(1),
    End: () => go(props.pages),
  };
  const move = moves[event.key];
  if (!move) return;
  event.preventDefault();
  move();
}
</script>

<template>
  <div class="flipper" @keydown="onKey">
    <nav v-if="pages > 0" class="pager no-print" aria-label="تقليب الصفحات">
      <button type="button" class="btn btn-secondary" :disabled="page <= 1" @click="go(page - 1)">
        <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><polyline points="9 6 15 12 9 18" /></svg>
        السابقة
      </button>
      <label class="where">
        <span class="visually-hidden">رقم الصفحة</span>
        <input class="input" type="number" inputmode="numeric" min="1" :max="pages" :value="page" @change="onPageInput" />
        <span aria-live="polite">من <bdi dir="ltr">{{ pages }}</bdi></span>
      </label>
      <button type="button" class="btn btn-secondary" :disabled="page >= pages" @click="go(page + 1)">
        التالية
        <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><polyline points="15 6 9 12 15 18" /></svg>
      </button>
    </nav>
    <slot />
  </div>
</template>

<style scoped>
.flipper {
  display: grid;
  gap: var(--space-3);
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
</style>
