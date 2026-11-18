import { createPinia, setActivePinia } from "pinia";
import type { Paper } from "./papers";
import { usePrintStore } from "./print";

const paper = {
  kind: "exam",
  form: "A",
  generator_version: "v1",
  blueprint: "g10-s1-2026-27-final",
  lesson_code: "",
  title: "اختبار نهاية الفصل الأول",
  seed: 1,
  total_marks: 50,
  is_forecast: false,
  level_marks: {},
  level_counts: {},
  questions: [],
  level: "",
} as Paper;

describe("ترويسة الطباعة", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("الصف من مقرر الورقة لا من ملف الطباعة، والورقة المحفوظة قبله تأخذ صف الملف", () => {
    const print = usePrintStore();
    print.profile.grade = "الصف 12: المسار العلمي / المسار التكنولوجي";
    expect(print.header({ ...paper, grade: "الصف 10" }).grade).toBe("الصف 10");
    expect(print.header(paper).grade).toBe("الصف 12: المسار العلمي / المسار التكنولوجي");
  });
});
