(function () {
  'use strict';
  var root = document.documentElement;

  /* ------------------------------------------------------------ helpers */
  function csrfToken() {
    var el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  var toastRegion = null;
  function toast(text, type, link) {
    if (!toastRegion) {
      toastRegion = document.createElement('div');
      toastRegion.className = 'toast-region';
      toastRegion.setAttribute('role', 'status');
      toastRegion.setAttribute('aria-live', 'polite');
      document.body.appendChild(toastRegion);
    }
    var t = document.createElement('div');
    t.className = 'toast' + (type === 'error' ? ' error' : '');
    t.textContent = text;
    if (link) {
      var a = document.createElement('a');
      a.href = link.href;
      a.textContent = link.text;
      t.appendChild(document.createTextNode(' '));
      t.appendChild(a);
    }
    toastRegion.appendChild(t);
    setTimeout(function () { t.remove(); }, type === 'error' ? 6000 : 3500);
  }

  function postForm(url, body) {
    return fetch(url, {
      method: 'POST',
      body: body,
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken() }
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, data: d }; });
    });
  }

  /* ------------------------------------------------------------ theme */
  function syncToggles() {
    var dark = root.dataset.theme === 'dark';
    document.querySelectorAll('.theme-toggle').forEach(function (b) {
      b.setAttribute('aria-label', dark ? 'Açık temaya geç' : 'Koyu temaya geç');
      b.title = b.getAttribute('aria-label');
    });
  }
  document.querySelectorAll('.theme-toggle').forEach(function (b) {
    b.addEventListener('click', function () {
      var theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      root.classList.add('theme-switching');
      root.dataset.theme = theme;
      try { localStorage.setItem('theme', theme); } catch (e) { /* storage blocked */ }
      syncToggles();
      setTimeout(function () { root.classList.remove('theme-switching'); }, 250);
    });
  });
  syncToggles();
  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  if (mq.addEventListener) {
    mq.addEventListener('change', function (e) {
      var saved = null;
      try { saved = localStorage.getItem('theme'); } catch (err) { /* ignore */ }
      if (!saved) { root.dataset.theme = e.matches ? 'dark' : 'light'; syncToggles(); }
    });
  }

  /* ------------------------------------------------------------ generic */
  document.querySelectorAll('form[data-confirm]').forEach(function (f) {
    f.addEventListener('submit', function (e) { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
  });
  document.querySelectorAll('select[data-autosubmit]').forEach(function (s) {
    s.addEventListener('change', function () { s.form.submit(); });
  });

  /* ------------------------------------------------------------ create task (stay on page) */
  var createForm = document.getElementById('task-create-form');
  if (createForm) {
    var recent = document.getElementById('recent-tasks');

    var clearErrors = function () {
      createForm.querySelectorAll('[data-error-for]').forEach(function (el) {
        el.textContent = '';
        if (el.dataset.errorFor === '__all__') el.hidden = true;
      });
      createForm.querySelectorAll('[aria-invalid]').forEach(function (el) { el.removeAttribute('aria-invalid'); });
    };

    var showErrors = function (errors) {
      var first = null;
      Object.keys(errors).forEach(function (name) {
        var box = createForm.querySelector('[data-error-for="' + name + '"]');
        if (box) {
          box.textContent = errors[name].map(function (e) { return e.message; }).join(' ');
          box.hidden = false;
        }
        var input = createForm.querySelector('[name="' + name + '"]');
        if (input) { input.setAttribute('aria-invalid', 'true'); first = first || input; }
      });
      if (first) first.focus();
    };

    var addRecent = function (task) {
      if (!recent) return;
      var empty = recent.querySelector('[data-empty]');
      if (empty) empty.remove();
      var li = document.createElement('li');
      li.className = 'sev-row ' + task.severity.toLowerCase();
      var a = document.createElement('a');
      a.className = 'title';
      a.href = task.url;
      a.textContent = task.title;
      var code = document.createElement('span');
      code.className = 'code';
      code.textContent = task.code;
      li.appendChild(a);
      li.appendChild(code);
      recent.insertBefore(li, recent.firstChild);
      while (recent.children.length > 8) recent.lastElementChild.remove();
    };

    createForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = createForm.querySelector('[type=submit]');
      btn.disabled = true;
      clearErrors();
      postForm(createForm.action || window.location.href, new FormData(createForm))
        .then(function (res) {
          if (!res.ok) { showErrors(res.data.errors || { __all__: [{ message: 'Task kaydedilemedi.' }] }); return; }
          var task = res.data.task;
          createForm.elements.title.value = '';
          createForm.elements.description.value = '';
          var medium = createForm.querySelector('input[name=severity][value=MEDIUM]');
          if (medium) medium.checked = true;
          createForm.elements.status.value = 'OPEN';
          if (createForm.elements.due_date) createForm.elements.due_date.value = '';
          if (createForm.elements.backup_assignee) createForm.elements.backup_assignee.value = '';
          addRecent(task);
          toast(res.data.message, null, { href: task.url, text: 'Görüntüle' });
          createForm.elements.title.focus();
        })
        .catch(function () { toast('Bağlantı kurulamadı, task kaydedilmedi. Tekrar deneyin.', 'error'); })
        .finally(function () { btn.disabled = false; });
    });
  }

  /* ------------------------------------------------------------ kanban */
  var board = document.querySelector('[data-board]');
  if (board) {
    var lanes = Array.prototype.slice.call(board.querySelectorAll('.lane'));
    var order = lanes.map(function (l) { return l.dataset.status; });
    var PENDING = ['OPEN', 'IN_PROGRESS'];
    var dragged = null;

    var refreshLanes = function () {
      lanes.forEach(function (lane) {
        var n = lane.querySelectorAll('.card').length;
        lane.querySelector('[data-count]').textContent = n;
        lane.querySelector('.lane-list').classList.toggle('is-empty', n === 0);
      });
    };

    var bump = function (name, delta) {
      var el = document.querySelector('[data-stat="' + name + '"]');
      if (!el) return;
      var v = Math.max(0, (parseInt(el.textContent, 10) || 0) + delta);
      el.textContent = v;
      if (name === 'critical' || name === 'overdue') el.classList.toggle('crit', v > 0);
    };

    // Son tarihi geçmiş kart tamamlanınca gecikmiş sayılmaz; geri alınınca tekrar gecikmiş olur
    var syncOverdue = function (card, isPending) {
      if (!card.dataset.due || new Date(card.dataset.due) >= new Date()) return false;
      var badge = card.querySelector('[data-overdue-badge]');
      if (isPending && !badge) {
        badge = document.createElement('span');
        badge.className = 'badge overdue';
        badge.setAttribute('data-overdue-badge', '');
        badge.textContent = 'Gecikmiş';
        var code = card.querySelector('.card-meta .code');
        code.parentNode.insertBefore(badge, code.nextSibling);
      } else if (!isPending && badge) {
        badge.remove();
      }
      var due = card.querySelector('.card-meta .due');
      if (due) due.classList.toggle('red', isPending);
      return true;
    };

    var adjustStats = function (card, from, to) {
      var wasPending = PENDING.indexOf(from) !== -1;
      var isPending = PENDING.indexOf(to) !== -1;
      if (wasPending === isPending) return;
      var d = isPending ? 1 : -1;
      bump('pending', d);
      bump('done', -d);
      if (card.dataset.severity === 'CRITICAL') bump('critical', d);
      if (syncOverdue(card, isPending)) bump('overdue', d);
    };

    var moveCard = function (card, lane, before, fromButton) {
      // Önceki taşıma kaydedilmeden yeni taşıma yok: aksi halde hata durumunda geri alma yanlış sütuna döner
      if (card.classList.contains('saving')) return;
      var from = card.closest('.lane').dataset.status;
      var to = lane.dataset.status;
      var list = lane.querySelector('.lane-list');
      if (from === to) { list.insertBefore(card, before); return; }

      var prevParent = card.parentNode;
      var prevNext = card.nextSibling;
      list.insertBefore(card, before || (fromButton ? list.firstChild : null));
      refreshLanes();
      adjustStats(card, from, to);
      if (fromButton) {
        var focusBtn = card.querySelector('[data-move="' + fromButton + '"]');
        if (to === order[0] || to === order[order.length - 1]) focusBtn = card.querySelector('[data-move="' + -fromButton + '"]');
        if (focusBtn) focusBtn.focus();
      }

      card.classList.add('saving');
      var title = card.querySelector('.card-title').textContent;
      postForm(card.dataset.url, new URLSearchParams({ status: to }))
        .then(function (res) {
          if (!res.ok) throw new Error(res.data.error || 'Durum güncellenemedi.');
          toast('"' + title + '" ' + res.data.task.status_label.toLocaleLowerCase('tr') + ' olarak güncellendi.');
        })
        .catch(function (err) {
          prevParent.insertBefore(card, prevNext);
          refreshLanes();
          adjustStats(card, to, from);
          toast(err.message === 'Failed to fetch' ? 'Bağlantı kurulamadı, durum değiştirilmedi.' : err.message, 'error');
        })
        .finally(function () { card.classList.remove('saving'); });
    };

    var cardAfter = function (list, y) {
      var cards = list.querySelectorAll('.card:not(.dragging)');
      for (var i = 0; i < cards.length; i++) {
        var r = cards[i].getBoundingClientRect();
        if (y < r.top + r.height / 2) return cards[i];
      }
      return null;
    };

    board.addEventListener('dragstart', function (e) {
      var card = e.target.closest && e.target.closest('.card');
      if (!card) return;
      dragged = card;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.id);
    });
    board.addEventListener('dragend', function () {
      if (dragged) dragged.classList.remove('dragging');
      dragged = null;
      lanes.forEach(function (l) { l.classList.remove('over'); });
    });
    lanes.forEach(function (lane) {
      lane.addEventListener('dragover', function (e) {
        if (!dragged) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        lane.classList.add('over');
      });
      lane.addEventListener('dragleave', function (e) {
        if (!lane.contains(e.relatedTarget)) lane.classList.remove('over');
      });
      lane.addEventListener('drop', function (e) {
        e.preventDefault();
        lane.classList.remove('over');
        if (!dragged) return;
        var list = lane.querySelector('.lane-list');
        moveCard(dragged, lane, cardAfter(list, e.clientY));
      });
    });
    board.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-move]');
      if (!btn) {
        // Kartın boş bir yerine tıklanınca task detayına git (link ve butonlar kendi işini yapar)
        var clicked = e.target.closest('.card');
        if (clicked && !e.target.closest('a, button')) {
          var link = clicked.querySelector('.card-title');
          if (e.ctrlKey || e.metaKey) window.open(link.href, '_blank');
          else window.location.href = link.href;
        }
        return;
      }
      var card = btn.closest('.card');
      var step = parseInt(btn.dataset.move, 10);
      var idx = order.indexOf(card.closest('.lane').dataset.status) + step;
      if (idx < 0 || idx >= lanes.length) return;
      moveCard(card, lanes[idx], null, step);
    });
  }

  /* ------------------------------------------------------------ bulk actions */
  var scope = document.querySelector('[data-bulk-scope]');
  if (scope) {
    var bulkForm = document.getElementById('bulk-form');
    var headToggle = scope.querySelector('.actions [data-bulk-toggle]');
    var allBox = scope.querySelector('[data-bulk-all]');
    var countEl = scope.querySelector('[data-bulk-count]');
    var opSel = scope.querySelector('[data-bulk-op]');
    var userSel = scope.querySelector('[data-bulk-user]');
    var boxes = function () { return scope.querySelectorAll('input[name=ids]'); };

    var update = function () {
      var all = boxes();
      var n = 0;
      all.forEach(function (b) { if (b.checked) n++; });
      countEl.textContent = n + ' task seçildi';
      allBox.checked = n > 0 && n === all.length;
      allBox.indeterminate = n > 0 && n < all.length;
    };

    var setSelecting = function (on) {
      scope.classList.toggle('selecting', on);
      bulkForm.hidden = !on;
      if (headToggle) headToggle.setAttribute('aria-pressed', on ? 'true' : 'false');
      if (!on) boxes().forEach(function (b) { b.checked = false; });
      update();
    };

    scope.querySelectorAll('[data-bulk-toggle]').forEach(function (b) {
      b.addEventListener('click', function () { setSelecting(!scope.classList.contains('selecting')); });
    });
    allBox.addEventListener('change', function () {
      boxes().forEach(function (b) { b.checked = allBox.checked; });
      update();
    });
    scope.addEventListener('change', function (e) { if (e.target.name === 'ids') update(); });
    opSel.addEventListener('change', function () {
      userSel.hidden = !(opSel.value === 'assign' || opSel.value === 'unassign');
    });
    bulkForm.addEventListener('submit', function (e) {
      var n = 0;
      boxes().forEach(function (b) { if (b.checked) n++; });
      if (!n) { e.preventDefault(); toast('Önce en az bir task seçin.', 'error'); }
    });
  }
})();
