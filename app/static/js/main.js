/* Shared UI behaviour: navigation, dialogs, feedback and image fallbacks. */
(function () {
  'use strict';

  var config = window.BOOK_TRACKER || {};

  function initSidebar() {
    var sidebar = document.getElementById('sidebar');
    var backdrop = document.querySelector('.sidebar-backdrop');
    var toggle = document.querySelector('[data-sidebar-open]');
    if (!sidebar || !backdrop || !toggle) return;

    function setOpen(open) {
      sidebar.classList.toggle('is-open', open);
      backdrop.classList.toggle('is-visible', open);
      toggle.setAttribute('aria-expanded', String(open));
      document.body.style.overflow = open ? 'hidden' : '';
    }

    toggle.addEventListener('click', function () { setOpen(!sidebar.classList.contains('is-open')); });
    backdrop.addEventListener('click', function () { setOpen(false); });
    document.querySelectorAll('[data-sidebar-close]').forEach(function (el) {
      el.addEventListener('click', function () { setOpen(false); });
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') setOpen(false);
    });
    sidebar.addEventListener('click', function (event) {
      if (event.target.closest('a')) setOpen(false);
    });
  }

  function initFlashes() {
    document.querySelectorAll('[data-flash-close]').forEach(function (button) {
      button.addEventListener('click', function () {
        var flash = button.closest('.flash');
        if (flash) flash.remove();
      });
    });
  }

  function initCoverFallback() {
    if (!config.placeholder) return;
    document.addEventListener('error', function (event) {
      var target = event.target;
      if (!(target instanceof HTMLImageElement)) return;
      if (!target.classList.contains('book-cover') && !target.classList.contains('result-cover')) return;
      if (target.dataset.fallbackApplied) return;
      target.dataset.fallbackApplied = '1';
      target.src = config.placeholder;
    }, true);
  }

  function showToast(message, type) {
    var stack = document.getElementById('toast-stack');
    if (!stack) return;
    var toast = document.createElement('div');
    toast.className = 'toast' + (type === 'error' ? ' toast--error' : '');
    toast.setAttribute('role', 'status');
    var icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('class', 'icon');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('stroke-width', '2');
    icon.setAttribute('stroke-linecap', 'round');
    icon.setAttribute('stroke-linejoin', 'round');
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = type === 'error'
      ? '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>'
      : '<polyline points="20 6 9 17 4 12"></polyline>';
    var label = document.createElement('span');
    label.textContent = message;
    toast.appendChild(icon);
    toast.appendChild(label);
    stack.appendChild(toast);
    window.setTimeout(function () { toast.remove(); }, 3600);
  }

  function openConfirm(options) {
    var settings = options || {};
    var root = document.getElementById('modal-root');
    if (!root) return Promise.resolve(window.confirm(settings.message || 'Are you sure?'));

    var title = document.getElementById('modal-title');
    var body = document.getElementById('modal-body');
    var actions = document.getElementById('modal-actions');
    title.textContent = settings.title || 'Are you sure?';
    body.textContent = settings.message || '';
    actions.innerHTML = '';

    return new Promise(function (resolve) {
      var closeHandlers = [];

      function finish(value) {
        root.hidden = true;
        document.removeEventListener('keydown', onKey);
        closeHandlers.forEach(function (item) { item.el.removeEventListener('click', item.fn); });
        document.body.style.overflow = '';
        resolve(value);
      }
      function onKey(event) {
        if (event.key === 'Escape') finish(false);
      }

      var cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'btn btn-outline';
      cancel.textContent = settings.cancelLabel || 'Cancel';
      cancel.addEventListener('click', function () { finish(false); });

      var confirm = document.createElement('button');
      confirm.type = 'button';
      confirm.className = 'btn ' + (settings.danger ? 'btn-danger-solid' : 'btn-primary');
      confirm.textContent = settings.confirmLabel || 'Confirm';
      confirm.addEventListener('click', function () { finish(true); });

      actions.appendChild(cancel);
      actions.appendChild(confirm);
      root.hidden = false;
      document.body.style.overflow = 'hidden';
      document.addEventListener('keydown', onKey);
      root.querySelectorAll('[data-modal-close]').forEach(function (closeBtn) {
        var handler = function () { finish(false); };
        closeBtn.addEventListener('click', handler);
        closeHandlers.push({ el: closeBtn, fn: handler });
      });
      confirm.focus();
    });
  }

  function initDeleteConfirmations() {
    document.querySelectorAll('[data-confirm-delete]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        openConfirm({
          title: form.dataset.confirmTitle || 'Are you sure?',
          message: form.dataset.confirmMessage || 'This cannot be undone.',
          confirmLabel: 'Delete book',
          danger: true
        }).then(function (confirmed) {
          if (confirmed) form.submit();
        });
      });
    });
  }

  function init() {
    initSidebar();
    initFlashes();
    initCoverFallback();
    initDeleteConfirmations();
  }

  window.Bookshelf = { showToast: showToast, openConfirm: openConfirm };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
