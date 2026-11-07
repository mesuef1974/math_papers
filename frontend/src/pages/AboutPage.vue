<template>
  <header class="page-head">
    <span class="eyebrow">عن المنصة</span>
    <h1>عن المولّد</h1>
  </header>
  <div class="panel prose">
    <p>يولّد مسائل أصلية بالمعاملات لدروس الفصل الأول، ويتحقق من كل جواب برمجيًا. لا ينسخ تمارين أي كتاب.</p>
    <p>
      توزيع درجات الاختبار توقع مبني على تحليل الاختبارات السابقة، وليس جدول مواصفات رسميًا، فراجع الورقة قبل
      استعمالها مع طلابك.
    </p>
    <h2>المستويات</h2>
    <ul class="levels">
      <li><span class="badge badge-k">سهل</span> تطبيق مباشر لقاعدة أو تعريف.</li>
      <li><span class="badge badge-a">متوسط</span> خطوات متعددة أو قراءة من تمثيل بياني.</li>
      <li><span class="badge badge-r">مهارات عليا</span> معامل مجهول، أو شرط، أو استنتاج من رسم المشتقة.</li>
    </ul>
  </div>
</template>

<style scoped>
.prose {
  max-inline-size: 72ch;
}
.prose p:last-of-type {
  margin-block-end: var(--space-6);
}
.levels {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-3);
}
.levels .badge {
  margin-inline-end: var(--space-2);
}
</style>
