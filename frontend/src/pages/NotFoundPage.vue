<template>
  <section class="container-narrow not-found">
    <header class="page-head">
      <span class="eyebrow">404</span>
      <h1>الصفحة غير موجودة</h1>
      <p class="lead">الرابط الذي فتحته لا يقابل صفحة في المنصة.</p>
    </header>
    <RouterLink class="btn btn-primary" to="/">العودة إلى توليد الأوراق</RouterLink>
  </section>
</template>

<style scoped>
.not-found {
  padding-block-start: var(--space-6);
}
</style>
