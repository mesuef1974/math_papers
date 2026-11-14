<script setup lang="ts">
import BrandLockup from "@/components/BrandLockup.vue";
import BrandMark from "@/components/BrandMark.vue";

// قالب الشريحة 16:9 من identity/applications/slide-title وslide-content: شريحة العنوان (عنوان كبير وخط ذهبي تزييني وقفل الشعار)
// وشريحة المحتوى (عنوان بخط عنابي وبنود بمربعات عنابية والرمز ورقم الشريحة في التذييل). الأحجام نسبة إلى عرض الإطار فتتسع مع أي حجم عرض.
withDefaults(defineProps<{ layout?: "title" | "content"; title: string; subtitle?: string; page?: number }>(), {
  layout: "content",
  subtitle: "",
  page: undefined,
});
</script>

<template>
  <section class="slide" :class="`slide-${layout}`" :aria-label="title">
    <template v-if="layout === 'title'">
      <div class="title-block">
        <h2 class="slide-title">{{ title }}</h2>
        <span class="rule rule-accent" aria-hidden="true"></span>
        <p v-if="subtitle" class="slide-subtitle">{{ subtitle }}</p>
      </div>
      <footer class="foot foot-title"><BrandLockup :height="56" /></footer>
    </template>
    <template v-else>
      <header class="head">
        <h2 class="slide-title">{{ title }}</h2>
        <span class="rule rule-brand" aria-hidden="true"></span>
      </header>
      <div class="body"><slot /></div>
      <footer class="foot foot-content">
        <BrandMark :size="44" />
        <span v-if="page !== undefined" class="page-no">{{ page }}</span>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.slide {
  position: relative;
  inline-size: 100%;
  aspect-ratio: 16 / 9;
  container-type: inline-size;
  overflow: hidden;
  background: var(--color-paper);
  color: var(--color-ink);
  border: var(--border);
  padding: 7cqw 9.4cqw;
  display: flex;
  flex-direction: column;
}
.slide-title {
  margin: 0;
  font-weight: var(--weight-heading);
  line-height: var(--leading-tight);
  text-wrap: balance;
}
.rule {
  display: block;
  block-size: 0.4cqw;
  margin-block: 2cqw;
}
.rule-accent {
  inline-size: 12.5cqw;
  background: var(--color-accent);
}
.rule-brand {
  inline-size: 8.3cqw;
  background: var(--color-brand);
}
/* شريحة العنوان: الكتلة في منتصف الارتفاع عند الطرف الأيمن (RTL) */
.title-block {
  margin-block: auto;
  max-inline-size: 62%;
}
.title-block .slide-title {
  font-size: 5.2cqw;
}
.slide-title {
  font-size: 3.8cqw;
}
.slide-subtitle {
  margin: 0;
  font-size: 2.2cqw;
  color: var(--color-ink-soft);
}
.foot-title {
  display: flex;
  justify-content: flex-start; /* RTL: الطرف الأيمن */
}
/* شريحة المحتوى */
.body {
  flex: 1;
  min-block-size: 0;
  margin-block-start: 3cqw;
  font-size: 2.1cqw;
  line-height: 1.9;
}
.body :deep(ul) {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 2cqw;
}
.body :deep(li) {
  position: relative;
  padding-inline-start: 3cqw;
}
.body :deep(li)::before {
  content: "";
  position: absolute;
  inset-inline-start: 0;
  inset-block-start: 1.2cqw;
  inline-size: 1cqw;
  block-size: 1cqw;
  background: var(--color-brand);
}
.foot-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-direction: row-reverse;
}
.page-no {
  font-size: 1.6cqw;
  color: var(--color-ink-soft);
  font-variant-numeric: tabular-nums;
}
</style>
