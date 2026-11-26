import { studentCount } from "./arabicCount";

describe("studentCount", () => {
  it.each([
    [1, "طالب واحد"],
    [2, "طالبان"],
    [3, "3 طلاب"],
    [10, "10 طلاب"],
    [11, "11 طالبًا"],
    [99, "99 طالبًا"],
    [100, "100 طالب"],
    [102, "102 طالب"],
    [103, "103 طلاب"],
    [111, "111 طالبًا"],
  ])("يصوغ العدد %i", (n, text) => {
    expect(studentCount(n)).toBe(text);
  });
});
