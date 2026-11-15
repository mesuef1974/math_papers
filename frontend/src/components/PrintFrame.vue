<script setup lang="ts">
import PrintFooter from "@/components/PrintFooter.vue";

// إطار الطباعة. Chromium لا يرسم الصور في صناديق هوامش @page، ولا يثبّت tfoot الجدول في أسفل صفحته الأخيرة؛ فالتذييل
// قطعتان: tfoot فارغ مخفي (print-reserve) يحجز حيّز الشريط في أسفل كل صفحة بتكرار الجدول، وعنصر ثابت (print-foot)
// يرسم الشريط في الحيّز المحجوز نفسه في كل صفحة. على الشاشة يُجرَّد الجدول فيبقى المحتوى كتلة عادية ولا يظهر التذييل (print.css).
</script>

<template>
  <table class="print-frame">
    <tbody>
      <tr>
        <td><slot /></td>
      </tr>
    </tbody>
    <tfoot class="print-reserve" aria-hidden="true">
      <tr>
        <td></td>
      </tr>
    </tfoot>
  </table>
  <div class="print-foot"><PrintFooter /></div>
</template>
