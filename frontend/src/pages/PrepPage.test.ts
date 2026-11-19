import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GENERATE_PERMISSION, useAuthStore } from "@/stores/auth";

// تحضير حصة حقيقي من الخادم (العاشر، الدرس 1.2، الحصة 1) بأهداف معلَّقة لأن نصوص الوحدة لم تُعتمد.
const sheet = {
  "course": "g10-s1",
  "lesson": "1.2",
  "lesson_title": "الدوال التربيعية بصيغة الرأس",
  "unit": 1,
  "k": 1,
  "n": 3,
  "week": 2,
  "number": 6,
  "minutes": 45,
  "year": "2026-2027",
  "semester": "الأول",
  "grade": "الصف 10",
  "unit_label": "الوحدة 1",
  "day_date": "الأسبوع 2، الحصة 1 من 3",
  "outcomes": "10.3.2، 10.3.3",
  "main_sources": "كتاب الطالب: مثال 1 (ص 12)، مثال 2 (ص 13)، مثال 3 (ص 13)",
  "support_sources": "العرض التقديمي للحصة، وورقة عمل مولَّدة من «أوراق»",
  "warmup": "توقّع قبل أن تحسب: استدعاء الدرس 1.1",
  "warmup_minutes": 5,
  "objectives": [
    {
      "example": 1,
      "text": "مثال 1 (ص 12، عمق 1، الفعل: يحسب) — نص الهدف معلَّق حتى اعتماد الوحدة",
      "pending": true,
      "teach_activity": "مثال 1 (ص 12): مثال محلول بالتفكير بصوت عالٍ",
      "teach_assessment": "«جرّب» على المثال 1: استكشاف بالأزواج",
      "teach_minutes": 8,
      "check_activity": "تدريب صفي 15، 16: ابحث عن الخطأ",
      "check_assessment": "سؤال الخروج معلَّق: لا صيغة لمهارة المثال 1 بعد",
      "check_minutes": 3
    },
    {
      "example": 2,
      "text": "مثال 2 (ص 13، عمق 1، الفعل: يحسب) — نص الهدف معلَّق حتى اعتماد الوحدة",
      "pending": true,
      "teach_activity": "مثال 2 (ص 13): مثال محلول بالتفكير بصوت عالٍ",
      "teach_assessment": "«جرّب» على المثال 2: استكشاف بالأزواج",
      "teach_minutes": 8,
      "check_activity": "تدريب صفي 22، 23: ابحث عن الخطأ",
      "check_assessment": "سؤال الخروج معلَّق: لا صيغة لمهارة المثال 2 بعد",
      "check_minutes": 3
    },
    {
      "example": 3,
      "text": "مثال 3 (ص 13، عمق 3، الفعل: يحلل) — نص الهدف معلَّق حتى اعتماد الوحدة",
      "pending": true,
      "teach_activity": "مثال 3 (ص 13): مثال محلول بالتفكير بصوت عالٍ",
      "teach_assessment": "«جرّب» على المثال 3: استكشاف بالأزواج",
      "teach_minutes": 8,
      "check_activity": "تدريب صفي 13، 27: ابحث عن الخطأ",
      "check_assessment": "بطاقة خروج من مهارة المثال 3 (عمق 1)",
      "check_minutes": 3
    }
  ],
  "closing": "بطاقة الخروج: بطاقة خروج من مهارة المثال 3",
  "closing_minutes": 5,
  "homework": "تمارين الكتاب 10، 11، 14، 20، 21، 24، 28، 29",
  "basic": "17–19",
  "advanced": "10، 11، 14",
  "quiz": "",
  "stages": [
    {
      "name": "warmup",
      "label": "التهيئة والمراجعة",
      "minutes": 5,
      "strategy": "توقّع قبل أن تحسب"
    },
    {
      "name": "objectives",
      "label": "الأهداف والمفردات",
      "minutes": 2,
      "strategy": ""
    },
    {
      "name": "direct",
      "label": "التعليم المباشر",
      "minutes": 13,
      "strategy": "مثال محلول بالتفكير بصوت عالٍ"
    },
    {
      "name": "guided",
      "label": "الممارسة الموجهة",
      "minutes": 11,
      "strategy": "استكشاف بالأزواج"
    },
    {
      "name": "independent",
      "label": "الممارسة المستقلة المتمايزة",
      "minutes": 9,
      "strategy": "ابحث عن الخطأ"
    },
    {
      "name": "closing",
      "label": "التقويم الختامي والغلق",
      "minutes": 5,
      "strategy": "بطاقة الخروج"
    }
  ],
  "checks": [
    {
      "code": "T2",
      "title": "صياغة الأهداف",
      "status": "pending",
      "kind": "blocking",
      "details": [
        "المثال 1: نص الهدف ينتظر ملف الوحدة",
        "المثال 2: نص الهدف ينتظر ملف الوحدة",
        "المثال 3: نص الهدف ينتظر ملف الوحدة"
      ]
    },
    {
      "code": "T2b",
      "title": "اكتمال سلسلة الهدف",
      "status": "fail",
      "kind": "blocking",
      "details": [
        "المثال 1: بلا صيغة لسؤال الخروج",
        "المثال 2: بلا صيغة لسؤال الخروج"
      ]
    },
    {
      "code": "T2c",
      "title": "اعتماد نصوص الوحدة",
      "status": "pending",
      "kind": "blocking",
      "details": [
        "الوحدة 1: لم يُولَّد ملفها بعد"
      ]
    },
    {
      "code": "T4",
      "title": "التدريب الصفي",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T5",
      "title": "التدرج في العمق",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T6",
      "title": "الزمن والمراحل",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T7",
      "title": "التقويم التكويني",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T8",
      "title": "التمايز",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T9",
      "title": "الواجب",
      "status": "pass",
      "kind": "warning",
      "details": []
    },
    {
      "code": "T10",
      "title": "الربط بما قبلها",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T12",
      "title": "الحصة الأخيرة",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T13",
      "title": "الحقول المغلقة",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T1",
      "title": "التغطية",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T3",
      "title": "المعايير",
      "status": "pass",
      "kind": "blocking",
      "details": []
    },
    {
      "code": "T11",
      "title": "حمل الحصص",
      "status": "pass",
      "kind": "blocking",
      "details": []
    }
  ],
  "pending": true
};

const periods = [
  { lesson: "1.2", title: sheet.lesson_title, unit: 1, k: 1, n: 3, week: 2, status: "fail" },
  { lesson: "1.2", title: sheet.lesson_title, unit: 1, k: 2, n: 3, week: 2, status: "pending" },
];

const get = vi.fn();
const replace = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, get: (...a: unknown[]) => get(...a) } };
});
vi.mock("vue-router", () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ replace }) }));

const PrepPage = (await import("./PrepPage.vue")).default;

describe("PrepPage", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    get.mockReset();
    get.mockImplementation((url: string) => Promise.resolve(url.endsWith("/1.2/1") ? sheet : periods));
    useAuthStore().user = { id: 1, username: "t", is_staff: false, admin_url: "", permissions: [GENERATE_PERMISSION] };
  });

  it("يفتح أول حصة ويعرض أهدافها معلَّقة ومعاييرها ورابط Word", async () => {
    const wrapper = mount(PrepPage);
    await flushPromises();
    expect(get).toHaveBeenCalledWith("/preps/g10-s1/1.2/1");
    expect(wrapper.findAll("option")).toHaveLength(2);
    expect(wrapper.find("a.btn-primary").attributes("href")).toBe("/api/v1/preps/g10-s1/1.2/1/word");
    expect(wrapper.find(".alert-info").text()).toContain("لم تُعتمد");
    expect(wrapper.findAll(".status-pending").length).toBeGreaterThanOrEqual(sheet.objectives.length);
    expect(wrapper.text()).toContain(sheet.objectives[0].text);
    expect(wrapper.findAll(".checks > li")).toHaveLength(sheet.checks.length);
    expect(wrapper.findAll("tbody tr").length).toBe(sheet.objectives.length * 2 + sheet.stages.length);
  });

  it("بلا صلاحية لا يطلب شيئًا", async () => {
    useAuthStore().user = { id: 1, username: "t", is_staff: false, admin_url: "", permissions: [] };
    const wrapper = mount(PrepPage);
    await flushPromises();
    expect(get).not.toHaveBeenCalled();
    expect(wrapper.find(".alert-error").exists()).toBe(true);
  });
});
