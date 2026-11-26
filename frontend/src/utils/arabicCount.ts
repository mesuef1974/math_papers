// العدد والمعدود لـ«طالب»: 1 و2 بلا رقم، 3–10 جمع، 11–99 مفرد منصوب، وما انتهى بمئة أو بواحد أو اثنين بعدها مفرد.
export function studentCount(n: number): string {
  if (n === 1) return "طالب واحد";
  if (n === 2) return "طالبان";
  const tail = n % 100;
  if (tail >= 3 && tail <= 10) return `${n} طلاب`;
  if (tail >= 11) return `${n} طالبًا`;
  return `${n} طالب`;
}
