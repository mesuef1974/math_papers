// جمع «درجة» بالعربية: 1 واحدة، 2 درجتان، 3–10 درجات، 11 وما فوق درجة.
export function marksLabel(marks: number): string {
  if (marks === 1) return "درجة واحدة";
  if (marks === 2) return "درجتان";
  if (marks >= 3 && marks <= 10) return `${marks} درجات`;
  return `${marks} درجة`;
}
