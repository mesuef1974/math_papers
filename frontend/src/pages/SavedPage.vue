<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import EmptyState from "@/components/EmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { usePapersStore } from "@/stores/papers";
import { useSavedStore, type SavedSummary } from "@/stores/saved";
import { dateLabel } from "@/utils/duration";

// أوراقي: قائمة الأوراق المحفوظة، فتح للطباعة أو التعديل، تسمية، وحذف بخطوتين (لا نافذة تأكيد).
const saved = useSavedStore();
const papers = usePapersStore();
const auth = useAuthStore();
const router = useRouter();
const renaming = ref<number | null>(null);
const newTitle = ref("");
const confirming = ref<number | null>(null);
const busy = ref<number | null>(null);

onMounted(() => {
  if (auth.canGenerate) void saved.load();
});

const KIND: Record<SavedSummary["kind"], string> = { exam: "اختبار", worksheet: "ورقة عمل", quiz: "اختبار قصير" };

function scope(item: SavedSummary): string {
  if (item.kind === "exam") return `من ${item.total_marks}`;
  if (item.kind === "quiz") {
    const codes = item.lesson_code.split(",");
    return `${codes.length > 1 ? "الدرسان" : "الدرس"} ${codes.join(" و")} من ${item.total_marks}`;
  }
  return `الدرس ${item.lesson_code}`;
}

async function open(item: SavedSummary) {
  busy.value = item.id;
  const row = await saved.open(item.id);
  busy.value = null;
  if (!row) return;
  papers.openSaved(row);
  await router.push({ name: "home" });
}

function startRename(item: SavedSummary) {
  renaming.value = item.id;
  newTitle.value = item.title;
  confirming.value = null;
}

async function rename(item: SavedSummary) {
  if (newTitle.value.trim() && newTitle.value.trim() !== item.title) {
    await saved.update(item.id, { title: newTitle.value });
  }
  renaming.value = null;
}

async function remove(item: SavedSummary) {
  if (confirming.value !== item.id) {
    confirming.value = item.id;
    renaming.value = null;
    return;
  }
  busy.value = item.id;
  await saved.remove(item.id);
  busy.value = null;
  confirming.value = null;
  if (papers.savedId === item.id) papers.savedId = null;
}
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">الأوراق المحفوظة</span>
    <h1>أوراقي</h1>
    <p class="lead">كل ورقة تُحفظ كما طُبعت، فتعود إليها ولو تغيّرت المولّدات، وتستبدل مسائلها وتحفظ من جديد.</p>
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">حسابك لا يملك صلاحية توليد الأوراق.</p>
  <div v-else class="panel" :aria-busy="saved.loading">
    <p v-if="saved.error" class="alert alert-error" role="alert">{{ saved.error }}</p>
    <EmptyState v-if="saved.loaded && !saved.items.length">
      لا أوراق محفوظة بعد. ولّد ورقة من <RouterLink to="/">الرئيسية</RouterLink> ثم احفظها.
    </EmptyState>
    <table v-else-if="saved.items.length" class="list">
      <thead>
        <tr>
          <th scope="col">الورقة</th>
          <th scope="col">النوع</th>
          <th scope="col">المسائل</th>
          <th scope="col">آخر تحديث</th>
          <th scope="col"><span class="visually-hidden">إجراءات</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in saved.items" :key="item.id" :class="{ current: papers.savedId === item.id }">
          <td class="title-cell">
            <form v-if="renaming === item.id" class="rename" @submit.prevent="rename(item)">
              <input v-model="newTitle" class="input" maxlength="200" required aria-label="الاسم الجديد" />
              <button type="submit" class="btn btn-primary btn-small">حفظ الاسم</button>
              <button type="button" class="btn btn-secondary btn-small" @click="renaming = null">إلغاء</button>
            </form>
            <template v-else>
              <strong>{{ item.title }}</strong>
              <small>{{ scope(item) }}، رقم النموذج <bdi dir="ltr">{{ item.seed }}</bdi
                >{{ item.replacement_count ? `، ${item.replacement_count} استبدال` : "" }}</small>
            </template>
          </td>
          <td>{{ KIND[item.kind] }}</td>
          <td class="num">{{ item.question_count }}</td>
          <td><bdi dir="ltr">{{ dateLabel(item.updated_at) }}</bdi></td>
          <td class="actions">
            <button type="button" class="btn btn-primary btn-small" :disabled="busy === item.id" @click="open(item)">
              فتح
            </button>
            <button type="button" class="btn btn-secondary btn-small" @click="startRename(item)">تسمية</button>
            <button
              type="button"
              class="btn btn-secondary btn-small"
              :class="{ danger: confirming === item.id }"
              :disabled="busy === item.id"
              @click="remove(item)"
            >
              {{ confirming === item.id ? "تأكيد الحذف" : "حذف" }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.list {
  inline-size: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.list th,
.list td {
  padding: var(--space-3) var(--space-2);
  border-block-end: 1px solid var(--color-line);
  text-align: start;
  vertical-align: middle;
}
.list thead th {
  color: var(--color-ink-soft);
  font-weight: var(--weight-medium);
}
.current {
  background: var(--color-brand-soft);
}
.title-cell {
  min-inline-size: 220px;
}
.title-cell small {
  display: block;
  color: var(--color-ink-soft);
}
.num {
  white-space: nowrap;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: flex-end;
}
.danger {
  color: var(--color-danger);
  border-color: var(--color-danger);
}
.rename {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}
.rename .input {
  flex: 1 1 160px;
  min-block-size: 32px;
}
@media (max-width: 720px) {
  .list thead {
    display: none;
  }
  .list tr {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-1) var(--space-3);
    padding-block: var(--space-3);
    border-block-end: 1px solid var(--color-line);
  }
  .list td {
    border: 0;
    padding: 0;
  }
  .title-cell,
  .actions {
    grid-column: 1 / -1;
  }
  .actions {
    justify-content: flex-start;
  }
}
</style>
