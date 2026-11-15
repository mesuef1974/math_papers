<script setup lang="ts">
import { COPYRIGHT_NAME, COPYRIGHT_PHONE } from "@/utils/brand";
</script>

<template>
  <!-- تذييل الورق: خط علوي، والشعار المقفل يمينًا، وسطران: عنوان الورقة الجاري (--print-footer) ثم سطر الحقوق. -->
  <div class="print-foot-inner">
    <!-- الشعار خلفية لا svg مضمَّنًا: Chromium لا يعيد رسم svg مضمَّن في tfoot المكرَّر بعد الصفحة الأولى -->
    <span class="pf-logo" role="img" aria-label="أوراق"></span>
    <div class="pf-text">
      <p class="pf-title"></p>
      <p class="pf-copy">
        <span>©&nbsp;{{ COPYRIGHT_NAME }}</span>
        <svg
          class="pf-phone"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-label="جوال"
          role="img"
        >
          <rect x="7" y="2.5" width="10" height="19" rx="2.2" />
          <path d="M11 18.5h2" />
        </svg>
        <span dir="ltr" lang="en">{{ COPYRIGHT_PHONE }}</span>
      </p>
    </div>
  </div>
</template>
