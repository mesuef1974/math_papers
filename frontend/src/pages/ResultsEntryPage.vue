<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import EmptyState from "@/components/EmptyState.vue";
import { useAuthStore } from "@/stores/auth";
import { useCoursesStore } from "@/stores/courses";
import { useMisconceptionsStore } from "@/stores/misconceptions";
import { useResultsEntryStore, type ResultRow } from "@/stores/resultsEntry";

// إدخال نتائج بطاقات الخروج: المعلم يختار المقرر والدرس والشعبة، فتظهر بنود الدرس كما عُرضت على الطلاب (من الخادم)
// وجدول بصف لكل طالب وعمود لكل بند. الصفوف في ذاكرة الصفحة وحدها: لا localStorage ولا sessionStorage.
interface Row {
  enrollment_no: string;
  first_name: string;
  last_name: string;
  choices: string[]; // لكل بند: "" متروك، أو رقم الخيار من 1 إلى 4
}

const LETTERS = ["أ", "ب", "ج", "د"];
// ما يقبله عمود البند من لوحة المفاتيح: رقم الخيار (غربي أو مشرقي) أو حرفه
const KEYS: Record<string, string> = {
  "1": "1", "2": "2", "3": "3", "4": "4",
  "١": "1", "٢": "2", "٣": "3", "٤": "4",
  "أ": "1", "ا": "1", "ب": "2", "ج": "3", "د": "4",
};

const auth = useAuthStore();
const courses = useCoursesStore();
const lookup = useMisconceptionsStore(); // شعب المعلم ودروس المقرر: المصدر نفسه الذي تقرأ منه اللوحة
const store = useResultsEntryStore();
const course = ref("");
const lesson = ref("");
const section = ref("");
const rows = ref<Row[]>([]);
const pasted = ref("");
const notice = ref("");
const grid = ref<HTMLElement | null>(null);

const ready = computed(() => Boolean(course.value && lesson.value && section.value));
const blankRow = (): Row => ({
  enrollment_no: "",
  first_name: "",
  last_name: "",
  choices: store.items.map(() => ""),
});

onMounted(async () => {
  if (!auth.canGenerate) return;
  store.clear();
  await Promise.all([
    courses.courses.length ? Promise.resolve() : courses.load(),
    lookup.loadSections(),
  ]);
  course.value = courses.selected || (courses.courses[0]?.slug ?? "");
  if (lookup.sections.length === 1) section.value = lookup.sections[0];
});

watch(course, (slug) => {
  lesson.value = "";
  void lookup.loadLessons(slug);
});

watch([course, lesson, section], async ([c, l, s]) => {
  notice.value = "";
  rows.value = [];
  if (!(c && l && s)) return store.clear();
  await store.load(c, l, s, lookup.sections.includes(s));
  if (!store.loaded) return;
  // طلاب الشعبة المسجلون سابقًا واختياراتهم المحفوظة في بنود هذا الدرس، ثم صف فارغ للإضافة
  rows.value = store.students.map((student) => ({
    enrollment_no: student.enrollment_no,
    first_name: student.first_name,
    last_name: student.last_name,
    choices: store.items.map((item) => {
      const saved = student.results.find(
        (r) => r.example === item.example && r.seed === item.seed,
      );
      return saved ? String(saved.choice + 1) : "";
    }),
  }));
  rows.value.push(blankRow());
});

function focusCell(row: number, column: string) {
  void nextTick(() =>
    grid.value
      ?.querySelector<HTMLInputElement>(`[data-cell="${row}:${column}"]`)
      ?.focus(),
  );
}

// النزول في العمود نفسه؛ بعد آخر صف يُضاف صف جديد ويبدأ من رقم قيده.
function moveDown(row: number, column: string) {
  if (row + 1 < rows.value.length) return focusCell(row + 1, column);
  rows.value.push(blankRow());
  focusCell(row + 1, "no");
}

function moveUp(row: number, column: string) {
  if (row > 0) focusCell(row - 1, column);
}

// خانة البند حرف واحد: آخر ما كُتب يحدد الخيار، وما ليس خيارًا يفرغها. بعد الاختيار ينتقل التركيز إلى الطالب التالي.
function onChoice(row: number, index: number, event: Event) {
  const input = event.target as HTMLInputElement;
  const value = KEYS[input.value.trim().slice(-1)] ?? "";
  rows.value[row].choices[index] = value;
  input.value = value;
  if (value) moveDown(row, `c${index}`);
}

function addRow() {
  rows.value.push(blankRow());
  focusCell(rows.value.length - 1, "no");
}

// سطر لكل طالب: رقم القيد ثم الاسم الأول ثم اسم العائلة، مفصولة بجدولة (نسخ من جدول) أو فاصلة أو مسافات.
// الاسم الأطول من كلمتين في خانة واحدة يؤخذ أوله وآخره (الأول والعائلة)، ولا يُحفظ غيرهما.
function parseLine(line: string): Omit<Row, "choices"> | null {
  const separated = /[\t,،;]/.test(line);
  const parts = (separated ? line.split(/[\t,،;]/) : line.trim().split(/\s+/))
    .map((part) => part.trim().replace(/\s+/g, " "))
    .filter(Boolean);
  if (parts.length < 2) return null;
  const [enrollment_no, ...rest] = parts;
  if (separated && rest.length >= 2)
    return { enrollment_no, first_name: rest[0], last_name: rest[1] };
  const words = rest.join(" ").split(" ");
  if (words.length < 2) return { enrollment_no, first_name: words[0], last_name: "" };
  return { enrollment_no, first_name: words[0], last_name: words[words.length - 1] };
}

function addPasted(text: string) {
  const students = text.split(/\r?\n/).map(parseLine).filter((s) => s !== null);
  if (!students.length) {
    notice.value = "لم يُقرأ أي طالب: اكتب في كل سطر رقم القيد ثم الاسم الأول ثم اسم العائلة.";
    return;
  }
  const kept = rows.value.filter(
    (row) => row.enrollment_no.trim() || row.first_name.trim() || row.last_name.trim(),
  );
  for (const student of students) {
    const existing = kept.find((row) => row.enrollment_no.trim() === student.enrollment_no);
    if (existing) Object.assign(existing, student);
    else kept.push({ ...student, choices: store.items.map(() => "") });
  }
  rows.value = [...kept, blankRow()];
  pasted.value = "";
  notice.value = `أُضيف من القائمة ${students.length} طالبًا إلى الجدول.`;
}

// لصق قائمة متعددة الأسطر في خانة رقم القيد يملأ الجدول دفعة واحدة؛ اللصق العادي في الخانة كما هو.
function onPasteCell(event: ClipboardEvent) {
  const text = event.clipboardData?.getData("text") ?? "";
  if (!/\n/.test(text.trim())) return;
  event.preventDefault();
  addPasted(text);
}

// البند المتروك لا يُرسل، والصف الفارغ كله يُهمل. الصحة ونوع الخطأ يشتقهما الخادم من البند.
function entries(): ResultRow[] {
  const out: ResultRow[] = [];
  for (const row of rows.value) {
    row.choices.forEach((choice, index) => {
      if (!choice) return;
      const item = store.items[index];
      out.push({
        enrollment_no: row.enrollment_no.trim(),
        first_name: row.first_name.trim(),
        last_name: row.last_name.trim(),
        example: item.example,
        seed: item.seed,
        choice: Number(choice) - 1,
      });
    });
  }
  return out;
}

async function save() {
  notice.value = "";
  const results = entries();
  if (!results.length) {
    store.saved = null;
    notice.value = "لا اختيار مدخل: اكتب رقم الخيار لطالب واحد على الأقل.";
    return;
  }
  const done = await store.save(course.value, lesson.value, section.value, results);
  if (!done) return;
  lookup.last = { course: course.value, lesson: lesson.value, section: section.value };
  void lookup.loadSections(); // الشعبة الجديدة صارت من شعب المعلم
}
</script>

<template>
  <header class="page-head">
    <span class="eyebrow">تشخيص الخطأ</span>
    <h1>إدخال نتائج الطلاب</h1>
    <p class="lead">
      اختر المقرر والدرس والشعبة، فتظهر بنود بطاقات الخروج كما عُرضت على
      الطلاب. اكتب لكل طالب رقم الخيار الذي اختاره، ثم احفظ لتظهر الأخطاء في
      لوحة سوء الفهم.
    </p>
  </header>

  <p v-if="!auth.canGenerate" class="alert alert-error" role="alert">
    حسابك لا يملك صلاحية توليد الأوراق.
  </p>
  <div v-else class="panel" :aria-busy="store.loading || store.saving">
    <form class="form" @submit.prevent>
      <label class="field">
        <span>المقرر</span>
        <select v-model="course" class="input" name="course" required>
          <option value="" disabled>اختر المقرر</option>
          <option v-for="c in courses.courses" :key="c.slug" :value="c.slug">
            {{ c.title }}
          </option>
        </select>
      </label>
      <label class="field">
        <span>الدرس</span>
        <select
          v-model="lesson"
          class="input"
          name="lesson"
          required
          :disabled="!lookup.lessons.length"
        >
          <option value="" disabled>اختر الدرس</option>
          <option v-for="l in lookup.lessons" :key="l.code" :value="l.code">
            {{ l.code }} — {{ l.title }}
          </option>
        </select>
      </label>
      <label class="field">
        <span>الشعبة (من شعبك، أو اسم شعبة جديدة)</span>
        <input
          v-model.lazy.trim="section"
          class="input"
          name="section"
          list="entry-sections"
          maxlength="40"
          autocomplete="off"
          required
        />
        <datalist id="entry-sections">
          <option v-for="s in lookup.sections" :key="s" :value="s" />
        </datalist>
      </label>
    </form>

    <p
      v-if="store.error || lookup.error || courses.error"
      class="alert alert-error message"
      role="alert"
    >
      {{ store.error || lookup.error || courses.error }}
    </p>
    <p v-if="store.loading" class="hint" role="status">تُحمَّل بنود الدرس…</p>

    <template v-else-if="ready && store.loaded">
      <EmptyState v-if="!store.items.length" class="empty">
        لا بند موضوعي في بطاقات خروج هذا الدرس، فلا نتائج تُدخل له.
      </EmptyState>
      <template v-else>
        <ol class="items">
          <li v-for="(item, index) in store.items" :key="`${item.example}:${item.seed}`" class="item">
            <h2>
              البند {{ index + 1 }}
              <span class="badge">الحصة {{ item.k }} من {{ item.n }}</span>
              <span class="badge">المثال {{ item.example }}</span>
            </h2>
            <p class="stem">{{ item.stem }}</p>
            <ol class="options">
              <li v-for="(option, i) in item.options" :key="i">
                <span class="option-key">{{ i + 1 }} ({{ LETTERS[i] }})</span>
                <span>{{ option }}</span>
              </li>
            </ol>
          </li>
        </ol>

        <div class="paste">
          <label class="field">
            <span>
              لصق قائمة الطلاب: سطر لكل طالب (رقم القيد، الاسم الأول، اسم
              العائلة)
            </span>
            <textarea v-model="pasted" class="input" name="roster" rows="3" />
          </label>
          <button
            type="button"
            class="btn btn-secondary btn-small"
            data-test="add-pasted"
            :disabled="!pasted.trim()"
            @click="addPasted(pasted)"
          >
            أضف القائمة إلى الجدول
          </button>
        </div>

        <form @submit.prevent="save">
          <div class="table-scroll">
            <table ref="grid" class="grid">
              <caption class="visually-hidden">
                اختيارات طلاب الشعبة {{ section }} في بنود الدرس {{ lesson }}
              </caption>
              <thead>
                <tr>
                  <th scope="col">رقم القيد</th>
                  <th scope="col">الاسم الأول</th>
                  <th scope="col">اسم العائلة</th>
                  <th v-for="(item, index) in store.items" :key="index" scope="col">
                    البند {{ index + 1 }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, r) in rows" :key="r">
                  <td>
                    <input
                      v-model="row.enrollment_no"
                      class="input"
                      dir="ltr"
                      maxlength="20"
                      autocomplete="off"
                      :data-cell="`${r}:no`"
                      :aria-label="`رقم القيد، الصف ${r + 1}`"
                      @paste="onPasteCell"
                      @keydown.enter.prevent="moveDown(r, 'no')"
                    />
                  </td>
                  <td>
                    <input
                      v-model="row.first_name"
                      class="input"
                      maxlength="30"
                      autocomplete="off"
                      :data-cell="`${r}:first`"
                      :aria-label="`الاسم الأول، الصف ${r + 1}`"
                      @keydown.enter.prevent="moveDown(r, 'first')"
                    />
                  </td>
                  <td>
                    <input
                      v-model="row.last_name"
                      class="input"
                      maxlength="30"
                      autocomplete="off"
                      :data-cell="`${r}:last`"
                      :aria-label="`اسم العائلة، الصف ${r + 1}`"
                      @keydown.enter.prevent="moveDown(r, 'last')"
                    />
                  </td>
                  <td v-for="(item, i) in store.items" :key="i" class="choice">
                    <input
                      class="input"
                      inputmode="numeric"
                      autocomplete="off"
                      :value="row.choices[i]"
                      :data-cell="`${r}:c${i}`"
                      :aria-label="`البند ${i + 1}، الصف ${r + 1}: رقم الخيار من 1 إلى 4`"
                      @input="onChoice(r, i, $event)"
                      @keydown.enter.prevent="moveDown(r, `c${i}`)"
                      @keydown.down.prevent="moveDown(r, `c${i}`)"
                      @keydown.up.prevent="moveUp(r, `c${i}`)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="hint">
            في عمود البند اكتب 1 إلى 4 (أو حرف الخيار) فينتقل المؤشر إلى الطالب
            التالي، وEnter ينزل صفًّا ويضيف صفًّا بعد الأخير. الخانة المتروكة لا
            تُرسل.
          </p>
          <div class="actions">
            <button type="submit" class="btn btn-primary" :disabled="store.saving">
              {{ store.saving ? "يُحفظ…" : "احفظ النتائج" }}
            </button>
            <button type="button" class="btn btn-secondary" data-test="add-row" @click="addRow">
              أضف طالبًا
            </button>
          </div>
        </form>

        <p v-if="notice" class="alert alert-info message" role="status">{{ notice }}</p>
        <p v-if="store.saved" class="alert alert-info message" role="status" data-test="saved">
          حُفظت {{ store.saved.results }} نتيجة لعدد {{ store.saved.students }} من
          الطلاب (جديدة {{ store.saved.created }}، معدَّلة
          {{ store.saved.updated }}).
          <RouterLink to="/misconceptions">افتح لوحة سوء الفهم</RouterLink>
        </p>
      </template>
    </template>
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
  flex: 1 1 200px;
}
.hint {
  margin-block: var(--space-3) 0;
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
.message,
.empty {
  margin-block-start: var(--space-4);
}
.items {
  list-style: none;
  margin-block: var(--space-5) var(--space-4);
  margin-inline: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: var(--space-4);
}
.item {
  padding: var(--space-4);
  border: var(--border);
  border-inline-start: 4px solid var(--color-brand);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}
.item h2 {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--weight-bold);
}
.stem {
  margin-block: var(--space-2);
  color: var(--color-ink);
}
.options {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-1);
}
.options li {
  display: flex;
  gap: var(--space-3);
  padding-block: var(--space-1);
  border-block-start: var(--border);
}
.option-key {
  flex: none;
  font-size: var(--text-sm);
  color: var(--color-ink-soft);
}
.paste {
  display: grid;
  gap: var(--space-2);
  justify-items: start;
  margin-block-end: var(--space-4);
}
.paste .field {
  inline-size: 100%;
}
.grid {
  inline-size: 100%;
  border-collapse: collapse;
}
.grid th,
.grid td {
  padding: var(--space-1);
  border: var(--border);
  text-align: center;
  vertical-align: middle;
}
.grid th {
  font-size: var(--text-sm);
  font-weight: var(--weight-bold);
  color: var(--color-ink);
  background: var(--color-surface-sunken);
  white-space: nowrap;
}
.grid td {
  min-inline-size: 120px;
}
.grid td.choice {
  min-inline-size: 72px;
  inline-size: 72px;
}
.choice .input {
  text-align: center;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-block-start: var(--space-4);
}
</style>
