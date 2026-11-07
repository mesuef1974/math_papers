// في نص عربي ينقلب ترتيب «2026-2027» إلى «2027-2026». نعزل كل مدى رقمي باتجاه LTR (LRI … PDI).
const RANGE = /\d+(?:\s*[-–/]\s*\d+)+/g;

export function isolateNumberRanges(text: string): string {
  return text.replace(RANGE, (range) => `⁦${range}⁩`);
}
