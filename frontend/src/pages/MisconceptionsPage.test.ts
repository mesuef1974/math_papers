import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GENERATE_PERMISSION, useAuthStore } from "@/stores/auth";

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
    lesson_count: 2,
    has_generators: true,
  },
];
const lessons = [
  { code: "1.1", title: "الدوال الرئيسة", unit: 1, examinable: true, has_generator: true, levels: [] },
  { code: "1.2", title: "صيغة الرأس", unit: 1, examinable: true, has_generator: true, levels: [] },
];
// لوحة كما يرسلها الخادم: مرتبة تنازليًا بعدد الطلاب
const board = {
  course: "g10-s1",
  lesson: "1.1",
  section: "10/3",
  students: 5,
  entered: 4,
  correct: 1,
  missing: 1,
  kinds: [
    {
      kind: "sign",
      label: "عكس إشارة",
      count: 2,
      examples: [1, 2],
      students: [
        { enrollment_no: "1001", first_name: "سالم", last_name: "المري", examples: [1, 2] },
        { enrollment_no: "1002", first_name: "عبد الله", last_name: "آل ثاني", examples: [1] },
      ],
    },
    {
      kind: "swap",
      label: "تبديل إحداثيين أو قيمتين",
      count: 1,
      examples: [3],
      students: [
        { enrollment_no: "1002", first_name: "عبد الله", last_name: "آل ثاني", examples: [3] },
      ],
    },
  ],
};

let sections: string[] = [];
let boardOut: unknown = board;
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

const MisconceptionsPage = (await import("./MisconceptionsPage.vue")).default;

async function choose(lesson = "1.1", section = "10/3") {
  const wrapper = mount(MisconceptionsPage);
  await flushPromises();
  await wrapper.find('select[name="lesson"]').setValue(lesson);
  await wrapper.find('select[name="section"]').setValue(section);
  await flushPromises();
  return wrapper;
}

describe("MisconceptionsPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    sections = ["10/1", "10/3"];
    boardOut = board;
    post.mockReset();
    get.mockReset().mockImplementation((path: string) => {
      if (path === "/courses") return Promise.resolve(courses);
      if (path === "/results/sections") return Promise.resolve(sections);
      if (path.startsWith("/lessons")) return Promise.resolve(lessons);
      return Promise.resolve(boardOut);
    });
    useAuthStore().user = {
      id: 1,
      username: "t",
      is_staff: false,
      admin_url: "",
      permissions: [GENERATE_PERMISSION],
    };
  });

  it("يعرض بطاقة لكل نوع خطأ باسمه وعدد طلابه وأسمائهم، وأعداد الصحيح وغير المدخل", async () => {
    const wrapper = await choose();
    expect(get).toHaveBeenCalledWith("/lessons?course=g10-s1");
    expect(get).toHaveBeenCalledWith("/misconceptions/g10-s1/1.1?section=10%2F3");
    const cards = wrapper.findAll(".kind");
    expect(cards.map((c) => c.find("h2").text())).toEqual([
      "عكس إشارة",
      "تبديل إحداثيين أو قيمتين",
    ]);
    expect(cards.map((c) => c.find(".count").text())).toEqual([
      "عدد الطلاب: 2",
      "عدد الطلاب: 1",
    ]);
    expect(cards[0].findAll(".students li").map((li) => li.find(".name").text())).toEqual([
      "سالم المري",
      "عبد الله آل ثاني",
    ]);
    expect(cards[0].text()).toContain("1001");
    expect(cards[0].find(".examples").text()).toBe("الأمثلة: 1، 2");
    expect(wrapper.find('[data-test="correct"]').text()).toBe("1");
    expect(wrapper.find('[data-test="missing"]').text()).toBe("1");
    expect(wrapper.find('[data-test="students"]').text()).toBe("5");
    expect(post).not.toHaveBeenCalled(); // لا إدخال نتائج من الواجهة
  });

  function withPack(pack: () => Promise<unknown>) {
    get.mockImplementation((path: string) => {
      if (path === "/courses") return Promise.resolve(courses);
      if (path === "/results/sections") return Promise.resolve(sections);
      if (path.startsWith("/lessons")) return Promise.resolve(lessons);
      if (path.startsWith("/remedial-packs")) return pack();
      return Promise.resolve(board);
    });
  }

  it("زر الأوراق العلاجية يطلب حزمة الشعبة ويعرض رابط تنزيلها", async () => {
    withPack(() => Promise.resolve({ status: "idle", detail: "" }));
    post.mockResolvedValue({ status: "ready", detail: "" });
    const wrapper = await choose();
    await wrapper.find('[data-test="remedial"]').trigger("click");
    await flushPromises();
    expect(post).toHaveBeenCalledWith("/remedial-packs/g10-s1/1.1", {
      section: "10/3",
    });
    expect(wrapper.find("a[download]").attributes("href")).toContain(
      "/remedial-packs/g10-s1/1.1/download?section=10%2F3",
    );
    for (const storage of [localStorage, sessionStorage])
      expect(JSON.stringify({ ...storage })).not.toContain("سالم");
  });

  it("خادم بلا وسيط (503) يعطّل الزر ويذكر السبب", async () => {
    const { ApiError } = await import("@/api/client");
    withPack(() =>
      Promise.reject(new ApiError(503, "خدمة المهام الخلفية غير مفعّلة")),
    );
    const wrapper = await choose();
    const button = wrapper.find('[data-test="remedial"]');
    expect(button.attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("خدمة المهام الخلفية غير مفعّلة");
  });

  it("شعبة بلا نتائج في الدرس تظهر حالتها الفارغة بلا بطاقات", async () => {
    boardOut = { ...board, entered: 0, correct: 0, missing: 5, kinds: [] };
    const wrapper = await choose();
    expect(wrapper.text()).toContain("لا نتائج مدخلة لهذه الشعبة في هذا الدرس بعد");
    expect(wrapper.findAll(".kind")).toHaveLength(0);
    expect(wrapper.find(".summary").exists()).toBe(false);
  });

  it("نتائج كلها صحيحة تُذكر بلا بطاقات أخطاء", async () => {
    boardOut = { ...board, entered: 4, correct: 4, kinds: [] };
    const wrapper = await choose();
    expect(wrapper.text()).toContain("لا أخطاء مسجَّلة");
    expect(wrapper.find('[data-test="correct"]').text()).toBe("4");
  });

  it("معلم بلا شعب يرى الحالة الفارغة لا نموذج الاختيار", async () => {
    sections = [];
    const wrapper = mount(MisconceptionsPage);
    await flushPromises();
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.text()).toContain("لا شعب لك بعد");
  });

  it("رفض الخادم (403) يظهر رسالةً ولا تبقى لوحة", async () => {
    const { ApiError } = await import("@/api/client");
    get.mockImplementation((path: string) => {
      if (path === "/courses") return Promise.resolve(courses);
      if (path === "/results/sections") return Promise.resolve(sections);
      if (path.startsWith("/lessons")) return Promise.resolve(lessons);
      return Promise.reject(new ApiError(403, "الشعبة ليست من شعبك"));
    });
    const wrapper = await choose();
    expect(wrapper.find('[role="alert"]').text()).toContain("الشعبة ليست من شعبك");
    expect(wrapper.findAll(".kind")).toHaveLength(0);
  });
});
