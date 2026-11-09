// مبدّل سمة الإدارة: يشارك تفضيل المنصة نفسه (المفتاح math_papers_theme)، ولا يستعمل theme.js الخاص بـ Django.
(function () {
  var KEY = "math_papers_theme";
  var root = document.documentElement;
  var buttons = document.querySelectorAll("[data-theme-set]");
  function current() {
    try {
      var v = localStorage.getItem(KEY);
      return v === "light" || v === "dark" ? v : "auto";
    } catch (e) {
      return "auto";
    }
  }
  function paint(mode) {
    buttons.forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-theme-set") === mode));
    });
  }
  function apply(mode) {
    if (mode === "auto") delete root.dataset.theme;
    else root.dataset.theme = mode;
    try {
      if (mode === "auto") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, mode);
    } catch (e) {
      /* التفضيل يسري في هذه الصفحة فقط */
    }
    paint(mode);
  }
  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      apply(b.getAttribute("data-theme-set"));
    });
  });
  paint(current());
})();
