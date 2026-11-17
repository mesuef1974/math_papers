<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import AppIcon from "@/components/AppIcon.vue";
import EmptyState from "@/components/EmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { DEFAULT_PERIOD, useDecksStore } from "@/stores/decks";

// عروض الدروس: المعلم يختار الدرس وزمن الحصة، فيُبنى العرض في الخادم من مقاطع الأمثلة المنشورة، ثم ينزّل ملف PPTX.
const decks = useDecksStore();
const auth = useAuthStore();
const lesson = ref("");
const period = ref(DEFAULT_PERIOD);

onMounted(() => {
  if (auth.canGenerate) void decks.load();
});
onBeforeUnmount(() => decks.stop());

const current = computed(() => decks.lessons.find((item) => item.lesson === lesson.value));
const periodValid = computed(() => Number.isInteger(period.value) && period.value >= 30 && period.value <= 90);

function changed() {
  decks.select(lesson.value, period.value);
}

async function build() {
  decks.select(lesson.value, period.value);
  await decks.request();
}
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">العروض التقديمية</span>
    <h1>عروض الدروس</h1>
    <p class="lead">
      اختر الدرس وزمن الحصة، فيُبنى عرض بأمثلة الكتاب وسير الحصة والتقويم، وتنزّله ملف PowerPoint يُعرض من اليمين لليسار.
    </p>
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">حسابك لا يملك صلاحية توليد الأوراق.</p>
  <div v-else class="panel" :aria-busy="decks.loading || decks.busy">
    <p v-if="decks.error" class="alert alert-error" role="alert">{{ decks.error }}</p>
    <EmptyState v-if="decks.loaded && !decks.lessons.length">
      لم تُنشر مقاطع أمثلة بعد، فلا عروض لبنائها. تُنشر من جهاز المالك بأمر النشر.
    </EmptyState>
    <form v-else-if="decks.lessons.length" class="form" @submit.prevent="build">
      <label class="field">
        <span>الدرس</span>
        <select v-model="lesson" class="input" required @change="changed">
          <option value="" disabled>اختر الدرس</option>
          <option v-for="item in decks.lessons" :key="item.lesson" :value="item.lesson">
            {{ item.lesson }} — {{ item.title }} ({{ item.examples }} أمثلة)
          </option>
        </select>
      </label>
      <label class="field narrow">
        <span>زمن الحصة بالدقائق</span>
        <input
          v-model.number="period"
          class="input"
          type="number"
          min="30"
          max="90"
          step="1"
          required
          @change="changed"
        />
      </label>
      <button type="submit" class="btn btn-primary" :disabled="!lesson || !periodValid || decks.busy">
        <AppIcon name="generate" />{{ decks.busy ? "يُبنى العرض…" : "ابنِ العرض" }}
      </button>
    </form>

    <div v-if="decks.status === 'pending'" class="status" role="status">
      يُبنى عرض الدرس {{ decks.lesson }} الآن، وسيظهر رابط التنزيل هنا حين يجهز.
    </div>
    <div v-else-if="decks.status === 'ready'" class="status ready" role="status">
      <p>
        العرض جاهز: الدرس <bdi dir="ltr">{{ decks.lesson }}</bdi
        ><template v-if="current">، {{ current.examples }} أمثلة</template>.
      </p>
      <a class="btn btn-primary" :href="decks.url" download><AppIcon name="print" />نزّل العرض</a>
    </div>
    <p v-else-if="decks.status === 'failed'" class="alert alert-error" role="alert">
      تعذّر بناء العرض{{ decks.detail ? `: ${decks.detail}` : "" }}. أعد الطلب، وإن تكرر الفشل فبلّغ المشرف.
    </p>
  </div>
</template>

<style scoped>
.form {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: end;
}
.form .field {
  flex: 1 1 280px;
}
.form .field.narrow {
  flex: 0 1 160px;
}
.status {
  margin-block-start: var(--space-4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
  justify-content: space-between;
  color: var(--color-ink-soft);
}
.status.ready {
  color: var(--color-ink);
}
</style>
