// تقسيم نص يتناوب بين عربي ورياضيات: $...$ سطري، $$...$$ معروض، و\$ علامة دولار حرفية.
// علامة غير مغلقة تبقى نصًا كما هي، فلا يتحول باقي الجملة إلى رياضيات بالخطأ.

export interface Segment {
  math: boolean;
  display: boolean;
  value: string;
}

export function splitMath(text: string): Segment[] {
  const out: Segment[] = [];
  let buffer = "";
  let i = 0;
  const flush = () => {
    if (buffer) out.push({ math: false, display: false, value: buffer });
    buffer = "";
  };
  while (i < text.length) {
    if (text[i] === "\\" && text[i + 1] === "$") {
      buffer += "$";
      i += 2;
      continue;
    }
    if (text[i] === "$") {
      const display = text[i + 1] === "$";
      const fence = display ? "$$" : "$";
      const close = text.indexOf(fence, i + fence.length);
      if (close === -1) {
        buffer += text.slice(i);
        break;
      }
      flush();
      out.push({ math: true, display, value: text.slice(i + fence.length, close) });
      i = close + fence.length;
      continue;
    }
    buffer += text[i];
    i += 1;
  }
  flush();
  return out;
}
