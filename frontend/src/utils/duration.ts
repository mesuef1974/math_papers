// زمن الاختبار بصيغة أغلفة الوزارة («ساعتان ونصف») بدل الدقائق الخام حيث أمكن.
export function durationLabel(minutes: number | null): string {
  if (!minutes) return "";
  const named: Record<number, string> = {
    30: "نصف ساعة",
    45: "ثلاثة أرباع الساعة",
    60: "ساعة",
    90: "ساعة ونصف",
    120: "ساعتان",
    150: "ساعتان ونصف",
    180: "ثلاث ساعات",
  };
  return named[minutes] ?? `${minutes} دقيقة`;
}

// تاريخ اليوم بصيغة قطر (يوم/شهر/سنة) بأرقام لاتينية كما في أوراق الوزارة.
export function todayLabel(now: Date = new Date()): string {
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${now.getFullYear()}`;
}
