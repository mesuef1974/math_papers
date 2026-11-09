<script setup lang="ts">
import { type ThemeMode, useThemeStore } from "@/stores/theme";

const theme = useThemeStore();
const options: { mode: ThemeMode; label: string }[] = [
  { mode: "light", label: "نهاري" },
  { mode: "auto", label: "تلقائي" },
  { mode: "dark", label: "ليلي" },
];
</script>

<template>
  <div class="theme-toggle" role="group" aria-label="سمة الواجهة">
    <button
      v-for="item in options"
      :key="item.mode"
      type="button"
      class="theme-option"
      :aria-pressed="theme.mode === item.mode"
      @click="theme.set(item.mode)"
    >
      <svg class="theme-glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
        <template v-if="item.mode === 'light'">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
        </template>
        <template v-else-if="item.mode === 'dark'">
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
        </template>
        <template v-else>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 4v16" />
          <path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none" />
        </template>
      </svg>
      <span class="visually-hidden">{{ item.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.theme-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--color-surface-sunken);
  border: var(--border);
  border-radius: var(--radius-md);
}
.theme-option {
  display: inline-grid;
  place-items: center;
  inline-size: 32px;
  block-size: 32px;
  padding: 0;
  color: var(--color-ink-soft);
  background: none;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color var(--duration) var(--ease), color var(--duration) var(--ease);
}
.theme-option:hover {
  color: var(--color-ink);
}
.theme-option[aria-pressed="true"] {
  color: var(--color-brand);
  background: var(--color-field);
  box-shadow: var(--shadow-sm);
}
.theme-glyph {
  inline-size: 20px;
  block-size: 20px;
}
</style>
