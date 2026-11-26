import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GENERATE_PERMISSION, useAuthStore } from "@/stores/auth";
import { useMisconceptionsStore } from "@/stores/misconceptions";

const courses = [
  {
    slug: "g10-s1",
    title: "العاشر، الفصل الأول",
    grade: 10,
    track: "",
    semester: 1,
    academic_year: "2026-2027",
    edition: "",
    language: "ar",
    is_current: true,
    lesson_count: 1,
    has_generators: true,
  },
];
const lessons = [
  { code: "1.1", title: "الدوال الرئيسة", unit: 1, examinable: true, has_generator: true, levels: [] },
];
// بندان كما يرسلهما الخادم: المثال والبذرة والنص، بلا أي دلالة على الصحيح
const items = [
  { k: 1, n: 2, example: 2, seed: 4711, stem: "ما رأس الدالة؟", options: ["(1, 2)", "(2, 1)", "(-1, 2)", "(1, -2)"] },
  { k: 2, n: 2, example: 4, seed: 9002, stem: "ما محور التماثل؟", options: ["x = 1", "x = -1", "y = 1", "y = -1"] },
];
const ITEMS_PATH = "/results/g10-s1/1.1/items";
const ROSTER_PATH = "/results/g10-s1/1.1?section=10%2F3";

let sections: string[] = [];
let roster: unknown[] = [];
const get = vi.fn();
const post = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    api: {
      ...actual.api,
      get: (...a: unknown[]) => get(...a),
      post: (...a: unknown[]) => post(...a),
    },
  };
});

const ResultsEntryPage = (await import("./ResultsEntryPage.vue")).default;
const stubs = { RouterLink: { props: ["to"], template: '<a :href="to"><slot /></a>' } };

async function open(section = "10/3") {
  const wrapper = mount(ResultsEntryPage, { global: { stubs }, attachTo: document.body });
  await flushPromises();
  await wrapper.find('select[name="lesson"]').setValue("1.1");
  const input = wrapper.find('input[name="section"]');
  await input.setValue(section);
  await input.trigger("change");
  await flushPromises();
  return wrapper;
}

const cell = (wrapper: VueWrapper, row: number, column: string) =>
  wrapper.find<HTMLInputElement>(`[data-cell="${row}:${column}"]`);

async function fillStudent(wrapper: VueWrapper, row: number, no: string, first: string, last: string) {
  await cell(wrapper, row, "no").setValue(no);
  await cell(wrapper, row, "first").setValue(first);
  await cell(wrapper, row, "last").setValue(last);
}

describe("ResultsEntryPage", () => {
  const setItem = vi.spyOn(Storage.prototype, "setItem");

  beforeEach(() => {
    setActivePinia(createPinia());
    sections = ["10/3"];
    roster = [];
    setItem.mockClear();
    post.mockReset().mockResolvedValue({ students: 2, results: 3, created: 3, updated: 0 });
    get.mockReset().mockImplementation((path: string) => {
      if (path === "/courses") return Promise.resolve(courses);
      if (path === "/results/sections") return Promise.resolve(sections);
      if (path.startsWith("/lessons")) return Promise.resolve(lessons);
      if (path === ITEMS_PATH) return Promise.resolve({ course: "g10-s1", lesson: "1.1", items });
      if (path === ROSTER_PATH) return Promise.resolve({ students: roster });
      return Promise.reject(new Error(`مسار غير متوقع: ${path}`));
    });
    useAuthStore().user = {
      id: 1,
      username: "t",
      is_staff: false,
      admin_url: "",
      permissions: [GENERATE_PERMISSION],
    };
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("إدخال طالبين وبندين يرسل الجسم المتوقع بلا البند المتروك ولا يكتب في التخزين المحلي", async () => {
    const wrapper = await open();
    expect(get).toHaveBeenCalledWith(ITEMS_PATH);
    expect(wrapper.findAll(".item .stem").map((p) => p.text())).toEqual(items.map((i) => i.stem));
    expect(wrapper.findAll(".item")[0].findAll(".options li")).toHaveLength(4);

    await fillStudent(wrapper, 0, "1001", "سالم", "المري");
    await cell(wrapper, 0, "c0").setValue("2");
    await cell(wrapper, 0, "c1").setValue("د"); // حرف الخيار كرقمه
    await wrapper.find('[data-test="add-row"]').trigger("click");
    await fillStudent(wrapper, 1, "1002", "عبد الله", "آل ثاني");
    await cell(wrapper, 1, "c0").setValue("1"); // البند الثاني متروك لهذا الطالب
    await cell(wrapper, 1, "c1").setValue("7"); // ليس خيارًا: تبقى الخانة فارغة
    expect(cell(wrapper, 1, "c1").element.value).toBe("");

    await wrapper.find('button[type="submit"]').trigger("submit");
    await flushPromises();

    expect(post).toHaveBeenCalledTimes(1);
    expect(post).toHaveBeenCalledWith("/results/g10-s1/1.1", {
      section: "10/3",
      results: [
        { enrollment_no: "1001", first_name: "سالم", last_name: "المري", example: 2, seed: 4711, choice: 1 },
        { enrollment_no: "1001", first_name: "سالم", last_name: "المري", example: 4, seed: 9002, choice: 3 },
        { enrollment_no: "1002", first_name: "عبد الله", last_name: "آل ثاني", example: 2, seed: 4711, choice: 0 },
      ],
    });
    const saved = wrapper.find('[data-test="saved"]');
    expect(saved.text()).toContain("حُفظت 3 نتيجة");
    expect(saved.find("a").attributes("href")).toBe("/misconceptions");
    expect(useMisconceptionsStore().last).toEqual({ course: "g10-s1", lesson: "1.1", section: "10/3" });
    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });

  it("إعادة الفتح تعبئ طلاب الشعبة واختياراتهم المحفوظة في بنود الدرس", async () => {
    roster = [
      {
        enrollment_no: "1001",
        first_name: "سالم",
        last_name: "المري",
        results: [
          { example: 4, seed: 9002, choice: 3, correct: true, error_kind: null, misconception: null },
          { example: 2, seed: 1, choice: 0, correct: true, error_kind: null, misconception: null }, // بذرة بند آخر
        ],
      },
      { enrollment_no: "1002", first_name: "ناصر", last_name: "الكواري", results: [] },
    ];
    const wrapper = await open();
    expect(get).toHaveBeenCalledWith(ROSTER_PATH);
    expect(wrapper.findAll("tbody tr")).toHaveLength(3); // الطالبان وصف فارغ للإضافة
    expect(cell(wrapper, 0, "no").element.value).toBe("1001");
    expect(cell(wrapper, 0, "first").element.value).toBe("سالم");
    expect(cell(wrapper, 0, "last").element.value).toBe("المري");
    expect(cell(wrapper, 0, "c0").element.value).toBe("");
    expect(cell(wrapper, 0, "c1").element.value).toBe("4");
    expect(cell(wrapper, 1, "first").element.value).toBe("ناصر");
    expect(cell(wrapper, 1, "c1").element.value).toBe("");
  });

  it("شعبة جديدة لا يُطلب طلابها من الخادم ويبدأ جدولها فارغًا", async () => {
    const wrapper = await open("10/7");
    expect(get).toHaveBeenCalledWith(ITEMS_PATH);
    expect(get.mock.calls.some(([path]) => String(path).includes("10%2F7"))).toBe(false);
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
  });

  it("رسالة 422 من الخادم تظهر للمعلم كما هي وتبقى الصفوف", async () => {
    const { ApiError } = await import("@/api/client");
    const detail = "اسم العائلة للطالب 1001 مطلوب، بحد أقصى 30 حرفًا وكلمتين (لا اسم رباعي)";
    post.mockRejectedValue(new ApiError(422, detail));
    const wrapper = await open();
    await fillStudent(wrapper, 0, "1001", "سالم", "");
    await cell(wrapper, 0, "c0").setValue("3");
    await wrapper.find('button[type="submit"]').trigger("submit");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').text()).toBe(detail);
    expect(wrapper.find('[data-test="saved"]').exists()).toBe(false);
    expect(cell(wrapper, 0, "no").element.value).toBe("1001");
    expect(cell(wrapper, 0, "c0").element.value).toBe("3");
  });

  it("لصق قائمة الأسماء يملأ الصفوف دفعة واحدة، والاسم الرباعي يؤخذ أوله وآخره", async () => {
    const wrapper = await open();
    await wrapper
      .find('textarea[name="roster"]')
      .setValue("1001\tسالم\tالمري\n1002, عبد الله, آل ثاني\n1003 ناصر بن حمد الكواري\n\n");
    await wrapper.find('[data-test="add-pasted"]').trigger("click");
    const names = [0, 1, 2].map((r) =>
      ["no", "first", "last"].map((c) => cell(wrapper, r, c).element.value),
    );
    expect(names).toEqual([
      ["1001", "سالم", "المري"],
      ["1002", "عبد الله", "آل ثاني"],
      ["1003", "ناصر", "الكواري"],
    ]);
    expect(wrapper.findAll("tbody tr")).toHaveLength(4);
    expect(wrapper.text()).toContain("أُضيف من القائمة 3 طلاب إلى الجدول.");
    expect(post).not.toHaveBeenCalled();
  });

  it("الإدخال بلوحة المفاتيح: رقم الخيار ينقل التركيز إلى الطالب التالي وEnter يضيف صفًّا بعد الأخير", async () => {
    roster = [
      { enrollment_no: "1001", first_name: "سالم", last_name: "المري", results: [] },
      { enrollment_no: "1002", first_name: "ناصر", last_name: "الكواري", results: [] },
    ];
    const wrapper = await open();
    cell(wrapper, 0, "c0").element.focus();
    await cell(wrapper, 0, "c0").setValue("2");
    await flushPromises();
    expect(document.activeElement).toBe(cell(wrapper, 1, "c0").element);
    await cell(wrapper, 2, "c0").trigger("keydown", { key: "Enter" });
    await flushPromises();
    expect(wrapper.findAll("tbody tr")).toHaveLength(4);
    expect(document.activeElement).toBe(cell(wrapper, 3, "no").element);
  });

  it("الحفظ بلا أي اختيار لا يرسل شيئًا", async () => {
    const wrapper = await open();
    await fillStudent(wrapper, 0, "1001", "سالم", "المري");
    await wrapper.find('button[type="submit"]').trigger("submit");
    await flushPromises();
    expect(post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("لا اختيار مدخل");
  });
});
