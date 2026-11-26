// في نص عربي ينقلب ترتيب «2026-2027» إلى «2027-2026». نعزل كل مدى رقمي باتجاه LTR (LRI … PDI).
// نظير isolate_number_ranges في apps/papers/domain/bidi.py: المدى داخل تعبير رياضي («8 - 4 x») طرحٌ لا مدى،
// وعزله يفصله عن متغيره فلا يُعزل، ولا يُمسّ مقطع معزول سلفًا.
const RANGE = /\d+(?:\s*[-–/]\s*\d+)+/g;
const ISOLATED = /(‎[^‎‏]*‏|⁦[^⁦⁩]*⁩)/;
// متغير لاتيني أو يوناني، أو عملية، أو أس ودليل
const NEIGHBOUR = "A-Za-zͰ-Ͽ+=×÷·*^_/<>≤≥≠≈±∓√∞→∈−⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎";
const BETWEEN = "[\\s()\\[\\]{}|-]*"; // ما يُتخطّى بين المدى وجاره
// «DOK» اختصار لا متغير
const MATH_AFTER = new RegExp(`^(?:[.٫]\\d+)*${BETWEEN}(?![A-Z]{3,}(?![A-Za-z]))[${NEIGHBOUR}]`);
const DECIMALS_BEFORE = /(?:\d+[.٫])+$/;
const MATH_BEFORE = new RegExp(`[${NEIGHBOUR}]${BETWEEN}$`);
const ABBREVIATION_BEFORE = new RegExp(`[A-Z]{3,}${BETWEEN}$`);
const IMPLICIT_OR_MINUS = /(?:\d[([]|(?:^|[\s([{|])-)$/; // «2(3 - 1)» و«-2 - 3»

function inExpression(text: string, start: number, end: number): boolean {
  if (MATH_AFTER.test(text.slice(end))) return true;
  const before = text.slice(0, start).replace(DECIMALS_BEFORE, "");
  return IMPLICIT_OR_MINUS.test(before) || (MATH_BEFORE.test(before) && !ABBREVIATION_BEFORE.test(before));
}

export function isolateNumberRanges(text: string): string {
  // الأجزاء الفردية من `split` مقاطع معزولة سلفًا تبقى كما هي
  return text
    .split(ISOLATED)
    .map((part, i) =>
      i % 2
        ? part
        : part.replace(RANGE, (range: string, offset: number) =>
            inExpression(part, offset, offset + range.length) ? range : `⁦${range}⁩`,
          ),
    )
    .join("");
}
