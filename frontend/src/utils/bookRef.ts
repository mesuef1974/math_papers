// المصدر الوحيد في الواجهة لنص الإشارة إلى مثال أو تمرين بعينه برقم صفحته؛ نظير `book_ref` في الخادم.
export function bookRef(word: "مثال" | "المثال" | "تمرين" | "التمرين", number: number, page?: number | null): string {
  return page ? `${word} ${number} (ص ${page})` : `${word} ${number}`;
}
