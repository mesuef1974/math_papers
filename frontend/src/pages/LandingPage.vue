<script setup lang="ts">
import { onMounted, ref } from "vue";
import BrandMark from "@/components/BrandMark.vue";
import { playMarkIntro } from "@/utils/markIntro";

// الصفحة الافتتاحية من screens/landing.html في دليل الهوية v8: النص والبطاقات الثلاث في العمود الأول (يمينًا في RTL)،
// ولوح الرمز على خلفية brand-soft في الثاني. تظهر للزائر وحده؛ المسجَّل يذهب إلى التوليد.
const tile = ref<HTMLElement | null>(null);
onMounted(() => playMarkIntro(tile.value?.querySelector("svg")));

const values = [
  { title: "دقيقة", text: "كل مسألة مربوطة بدرسها في المنهج، وكل رقم ورمز في موضعه، والورقة تُطبع كما ظهرت على الشاشة." },
  { title: "هادئة", text: "خطوات قليلة ومساحات بيضاء ولغة مطمئنة، فلا إلحاح ولا تنبيهات تقاطع عمل المعلم." },
  { title: "واضحة", text: "تقول ما ستفعله قبل أن تفعله، بكلمات المعلم نفسه: درس، مستوى، ورقة، طباعة." },
];
</script>

<template>
  <div class="landing">
    <section class="landing-copy" aria-labelledby="landing-title">
      <span class="landing-chip">من المنهج إلى الورقة، بضغطة</span>
      <h1 id="landing-title" class="landing-title">ورقتك من منهجك، بثلاثة مستويات</h1>
      <div class="landing-actions">
        <RouterLink class="btn btn-primary" :to="{ name: 'login', query: { next: '/' } }">ولّد الورقة</RouterLink>
        <RouterLink class="btn btn-secondary" :to="{ name: 'about' }">عن المنصة</RouterLink>
      </div>
      <ul id="features" class="landing-values">
        <li v-for="item in values" :key="item.title" class="landing-card">
          <b class="landing-card-title">{{ item.title }}</b>
          <p>{{ item.text }}</p>
        </li>
      </ul>
    </section>
    <aside class="landing-aside" aria-hidden="true">
      <div ref="tile" class="landing-tile">
        <BrandMark :size="172" />
      </div>
    </aside>
  </div>
</template>

<style scoped>
.landing {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  min-block-size: calc(100vh - var(--topbar-height));
}
.landing-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-6);
  padding: var(--space-16) var(--space-12) var(--space-12);
}
.landing-chip {
  display: inline-block;
  padding: 2px var(--space-3);
  border-radius: var(--radius-pill);
  background: var(--color-sand-soft);
  color: var(--color-ink);
  font-size: var(--text-xs);
}
.landing-title {
  max-inline-size: 14ch;
  font-size: clamp(2.25rem, 1.4rem + 3vw, 3.5rem);
  line-height: 1.3;
}
.landing-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}
.landing-values {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin: var(--space-6) 0 0;
  padding: 0;
  list-style: none;
}
.landing-card {
  background: var(--color-surface);
  border: var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-5);
}
.landing-card-title {
  display: block;
  color: var(--color-brand);
  font-size: var(--text-lg);
  font-weight: var(--weight-bold);
}
.landing-card p {
  margin: 0.4em 0 0;
  color: var(--color-ink-soft);
}
.landing-aside {
  display: grid;
  place-items: center;
  background: var(--color-brand-soft);
}
.landing-tile {
  display: grid;
  place-items: center;
  inline-size: 260px;
  block-size: 260px;
  background: var(--color-paper);
  border: var(--border);
  border-radius: var(--radius-tile);
}
@media (max-width: 900px) {
  .landing {
    grid-template-columns: 1fr;
  }
  .landing-copy {
    padding: var(--space-8) var(--space-5);
  }
  .landing-aside {
    display: none;
  }
}
@media (max-width: 640px) {
  .landing-values {
    grid-template-columns: 1fr;
  }
}
</style>
