(function () {
  'use strict';
  var root = document.documentElement;

  function setTheme(theme) {
    root.classList.add('theme-switching');
    root.dataset.theme = theme;
    try { localStorage.setItem('theme', theme); } catch (e) { /* storage blocked */ }
    syncToggles();
    setTimeout(function () { root.classList.remove('theme-switching'); }, 250);
  }

  function syncToggles() {
    var dark = root.dataset.theme === 'dark';
    document.querySelectorAll('.theme-toggle').forEach(function (b) {
      b.setAttribute('aria-label', dark ? 'Açık temaya geç' : 'Koyu temaya geç');
      b.title = b.getAttribute('aria-label');
    });
  }

  document.querySelectorAll('.theme-toggle').forEach(function (b) {
    b.addEventListener('click', function () {
      setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark');
    });
  });
  syncToggles();

  // Follow OS changes until the user picks a theme explicitly
  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener && mq.addEventListener('change', function (e) {
    var saved = null;
    try { saved = localStorage.getItem('theme'); } catch (err) { /* ignore */ }
    if (!saved) { root.dataset.theme = e.matches ? 'dark' : 'light'; syncToggles(); }
  });

  document.querySelectorAll('form[data-confirm]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
  });

  document.querySelectorAll('select[data-autosubmit]').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });
})();
