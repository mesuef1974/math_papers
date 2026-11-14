// هندسة مخطط التدفق: مواضع العقد والمسارات بإحداثيات viewBox واحد. لا ألوان هنا؛ الألوان من متغيرات الهوية في الصفحة.
import { GROUPS, type GroupId } from "./copilotPipeline";

export const VIEW_W = 1040;
export const VIEW_TOP = 96; // أعلى الرسم: لا فراغ فوق المسار الأول
export const VIEW_H = 1520;
export const NODE_W = 280;
export const NODE_H = 84;

const COL = [990, 660, 330]; // الحافة اليمنى لكل عمود (من اليمين إلى اليسار)
const ROW = {
  a1: 190, a2: 320, a3: 450, a4: 580,
  b1: 804, b2: 978, b3: 1142,
  c1: 1366,
};
const BUS_Y = 933;
const COLLECT_Y = 1102;

export interface Pos { x: number; y: number }
export const POS: Record<number, Pos> = {
  1: { x: COL[0], y: ROW.a1 }, 2: { x: COL[1], y: ROW.a1 }, 3: { x: COL[2], y: ROW.a1 },
  4: { x: COL[2], y: ROW.a2 }, 5: { x: COL[1], y: ROW.a2 }, 6: { x: COL[0], y: ROW.a2 },
  7: { x: COL[0], y: ROW.a3 }, 8: { x: COL[1], y: ROW.a3 }, 9: { x: COL[2], y: ROW.a3 },
  10: { x: COL[2], y: ROW.a4 },
  11: { x: COL[0], y: ROW.b1 }, 12: { x: COL[1], y: ROW.b1 }, 13: { x: COL[2], y: ROW.b1 },
  14: { x: COL[0], y: ROW.b2 }, 15: { x: COL[1], y: ROW.b2 }, 16: { x: COL[2], y: ROW.b2 },
  17: { x: COL[1], y: ROW.b3 },
  18: { x: COL[2], y: ROW.c1 }, 19: { x: COL[1], y: ROW.c1 },
};
/** عقدة البكج النهائي (ليست مرحلة) */
export const PACKAGE: Pos = { x: COL[2], y: ROW.b3 };
/** صندوق المصدر فوق المرحلة 1 */
export const SOURCE_BOX = { x: COL[0] - NODE_W, y: 126, w: NODE_W, h: 36 };

export const LANES: { id: GroupId; y: number; h: number; name: string; note: string }[] = [
  { id: "A", y: 110, h: 590, ...GROUPS.A },
  { id: "B", y: 720, h: 542, ...GROUPS.B },
  { id: "C", y: 1282, h: 218, ...GROUPS.C },
];

const L = (p: Pos) => p.x - NODE_W;
const R = (p: Pos) => p.x;
const cx = (p: Pos) => p.x - NODE_W / 2;
const cy = (p: Pos) => p.y + NODE_H / 2;
const bottom = (p: Pos) => p.y + NODE_H;

export type EdgeKind = "flow" | "feed" | "loop";
export interface Edge {
  id: string;
  kind: EdgeKind;
  d: string;
  /** المرحلتان المرتبطتان بالمسار (للإضاءة عند اختيار عقدة) */
  nodes: number[];
  /** ترتيب النبضة على المسار العام (للتأخير) */
  order: number;
  /** مسار ثابت بلا نبضة (مجمّع) */
  still?: boolean;
}

const left = (a: Pos, b: Pos) => `M${L(a)} ${cy(a)}H${R(b) + 3}`;
const right = (a: Pos, b: Pos) => `M${R(a)} ${cy(a)}H${L(b) - 3}`;
const down = (a: Pos, b: Pos) => `M${cx(a)} ${bottom(a)}V${b.y - 3}`;

const p = POS;
export const EDGES: Edge[] = [
  { id: "e1-2", kind: "flow", nodes: [1, 2], d: left(p[1], p[2]), order: 0 },
  { id: "e2-3", kind: "flow", nodes: [2, 3], d: left(p[2], p[3]), order: 1 },
  { id: "e3-4", kind: "flow", nodes: [3, 4], d: down(p[3], p[4]), order: 2 },
  { id: "e4-5", kind: "flow", nodes: [4, 5], d: right(p[4], p[5]), order: 3 },
  { id: "e5-6", kind: "flow", nodes: [5, 6], d: right(p[5], p[6]), order: 4 },
  { id: "e6-7", kind: "flow", nodes: [6, 7], d: down(p[6], p[7]), order: 5 },
  { id: "e7-8", kind: "flow", nodes: [7, 8], d: left(p[7], p[8]), order: 6 },
  { id: "e8-9", kind: "flow", nodes: [8, 9], d: left(p[8], p[9]), order: 7 },
  { id: "e9-10", kind: "flow", nodes: [9, 10], d: down(p[9], p[10]), order: 8 },
  { id: "e11-12", kind: "flow", nodes: [11, 12], d: left(p[11], p[12]), order: 9 },
  { id: "e12-13", kind: "flow", nodes: [12, 13], d: left(p[12], p[13]), order: 10 },
  { id: "e13-17", kind: "flow", nodes: [13, 17], order: 11,
    d: `M${L(p[13])} ${cy(p[13])}H36V${COLLECT_Y}H${cx(p[14])}` },
  { id: "e14-17", kind: "flow", nodes: [14, 17], d: `M${cx(p[14])} ${bottom(p[14])}V${COLLECT_Y}`, order: 12 },
  { id: "e15-17", kind: "flow", nodes: [15, 17], d: `M${cx(p[15])} ${bottom(p[15])}V${COLLECT_Y}`, order: 12 },
  { id: "e16-17", kind: "flow", nodes: [16, 17], d: `M${cx(p[16])} ${bottom(p[16])}V${COLLECT_Y}`, order: 12 },
  { id: "collect", kind: "flow", nodes: [14, 15, 16, 17], d: `M${cx(p[14])} ${COLLECT_Y}H${cx(p[16])}`, order: 12, still: true },
  { id: "e-to-17", kind: "flow", nodes: [17], d: `M${cx(p[17])} ${COLLECT_Y}V${p[17].y - 3}`, order: 12 },
  { id: "e17-pk", kind: "flow", nodes: [17], d: left(p[17], PACKAGE), order: 13 },
  { id: "epk-18", kind: "flow", nodes: [18], d: down(PACKAGE, p[18]), order: 14 },
  { id: "e18-19", kind: "flow", nodes: [18, 19], d: right(p[18], p[19]), order: 15 },
  // ملف الدرس: من المرحلة 10 عبر الممر الأيسر إلى ناقل أفقي يغذّي 12 و13 من الأسفل و14 و15 و16 من الأعلى
  { id: "feed", kind: "feed", nodes: [10, 12, 13, 14, 15, 16], order: 8,
    d: `M${L(p[10])} ${cy(p[10])}H20V${BUS_Y}H26a10 10 0 0 1 20 0H${cx(p[14])}` },
  { id: "tap12", kind: "feed", nodes: [10, 12], d: `M${cx(p[12])} ${BUS_Y}V${bottom(p[12]) + 3}`, order: 9 },
  { id: "tap13", kind: "feed", nodes: [10, 13], d: `M${cx(p[13])} ${BUS_Y}V${bottom(p[13]) + 3}`, order: 9 },
  { id: "tap14", kind: "feed", nodes: [10, 14], d: `M${cx(p[14])} ${BUS_Y}V${p[14].y - 3}`, order: 10 },
  { id: "tap15", kind: "feed", nodes: [10, 15], d: `M${cx(p[15])} ${BUS_Y}V${p[15].y - 3}`, order: 10 },
  { id: "tap16", kind: "feed", nodes: [10, 16], d: `M${cx(p[16])} ${BUS_Y}V${p[16].y - 3}`, order: 10 },
  { id: "src", kind: "flow", nodes: [1], d: `M${cx(p[1])} ${SOURCE_BOX.y + SOURCE_BOX.h}V${p[1].y - 3}`, order: 0 },
  { id: "loop", kind: "loop", nodes: [19, 11], order: 16,
    d: `M${cx(p[19])} ${bottom(p[19])}V1476H1015V${cy(p[11]) + 14}H${R(p[11]) + 3}` },
];

export const BUS_LABEL = { x: (cx(p[12]) + cx(p[14])) / 2, y: BUS_Y - 8, text: "ملف الدرس يغذّي المراحل 12 إلى 16" };
export const LOOP_LABEL = { x: cx(p[19]) + 14, y: 1468, text: "إتقان المعيار يعدّل وتيرة الخطة" };

export { L as nodeLeft, cx as nodeCx, cy as nodeCy };
