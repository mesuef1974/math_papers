import { describe, expect, it } from "vitest";
import { planPages } from "./paging";

describe("planPages: تقسيم الورقة المتصلة إلى صفحات", () => {
  it("ورقة أقصر من الصفحة صفحة واحدة بنهايتها", () => {
    expect(planPages([{ top: 0, bottom: 400, cuts: [0, 100, 250] }], 1000)).toEqual([{ start: 0, end: 400 }]);
  });

  it("الصفحة تنتهي عند آخر حدّ يتّسع لها فلا يُقطع عنصر في وسطه", () => {
    const pages = planPages([{ top: 0, bottom: 2200, cuts: [0, 300, 700, 950, 1300, 1900] }], 1000);
    expect(pages).toEqual([
      { start: 0, end: 950 },
      { start: 950, end: 1900 },
      { start: 1900, end: 2200 },
    ]);
  });

  it("نهاية كل صفحة بداية التالية فلا يتكرر محتوى بين صفحتين", () => {
    const pages = planPages([{ top: 0, bottom: 3000, cuts: [400, 900, 1500, 2100, 2600] }], 1000);
    pages.slice(0, -1).forEach((page, index) => expect(page.end).toBe(pages[index + 1].start));
    expect(pages.at(-1)?.end).toBe(3000);
  });

  it("عنصر أطول من الصفحة يُقطع عند ارتفاع الصفحة ويتقدم التقسيم", () => {
    const pages = planPages([{ top: 0, bottom: 2500, cuts: [0] }], 1000);
    expect(pages).toEqual([
      { start: 0, end: 1000 },
      { start: 1000, end: 2000 },
      { start: 2000, end: 2500 },
    ]);
  });

  it("كل ورقة تبدأ صفحاتها من رأسها وإحداثياتها مطلقة", () => {
    const pages = planPages(
      [
        { top: 0, bottom: 1500, cuts: [800] },
        { top: 1900, bottom: 2400, cuts: [] },
      ],
      1000,
    );
    expect(pages).toEqual([
      { start: 0, end: 800 },
      { start: 800, end: 1500 },
      { start: 1900, end: 2400 },
    ]);
  });

  it("ارتفاع غير صالح لا يعطي صفحات ولا يدور", () => {
    expect(planPages([{ top: 0, bottom: 100, cuts: [] }], 0)).toEqual([]);
    expect(planPages([], 1000)).toEqual([]);
  });
});
