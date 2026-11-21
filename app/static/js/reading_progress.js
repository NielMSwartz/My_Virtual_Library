/* Digital bookmark: quick page updates, progress UI and step controls. */
(function () {
  'use strict';

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function updateProgressUi(form, data) {
    var rowScope = form.closest('[data-progress-scope]');
    var scope = rowScope || form.closest('.book-card') || document;

    if (rowScope) {
      var rowMeta = rowScope.querySelector('.mini-list-copy .muted');
      if (rowMeta) {
        rowMeta.textContent =
          'Page ' + data.page +
          (data.page_count ? ' of ' + data.page_count : '') +
          (data.percent === null ? '' : ' · ' + data.percent + '%');
      }
    }

    var percentLabel = scope.querySelector('.progress-head strong');
    if (percentLabel) {
      percentLabel.textContent = data.percent === null ? 'Page ' + data.page : data.percent + '%';
    }

    var fill = scope.querySelector('.progress-fill');
    if (fill) fill.style.width = data.width + '%';

    var ribbon = scope.querySelector('.ribbon-label');
    if (ribbon) ribbon.textContent = 'Page ' + data.page;

    var firstMeta = scope.querySelector('.progress-meta span');
    if (firstMeta) {
      firstMeta.textContent = data.page_count
        ? data.page + ' / ' + data.page_count + ' pages'
        : 'Page ' + data.page + ' · total unknown';
    }

    var pageInput = form.elements['page'];
    if (pageInput) pageInput.value = data.page;

    var statusSelect = document.querySelector('.detail-status-form select[name="status"]');
    if (statusSelect) statusSelect.value = data.status;
  }

  function submitProgress(form) {
    var input = form.elements['page'];
    if (!input) return;
    var page = Number(input.value);
    var max = input.max ? Number(input.max) : null;

    if (!Number.isFinite(page) || page < 0 || !Number.isInteger(page)) {
      if (window.Bookshelf) window.Bookshelf.showToast('Enter a whole page number of zero or more.', 'error');
      input.focus();
      return;
    }
    if (max !== null && page > max) {
      if (window.Bookshelf) window.Bookshelf.showToast('Page cannot be greater than the total page count.', 'error');
      input.focus();
      return;
    }

    var submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    var token = csrfToken();
    fetch(form.action, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': token
      },
      body: JSON.stringify({ page: page, csrf_token: token })
    })
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok || !body.ok) throw new Error(body.error || 'Could not save the bookmark.');
          return body;
        });
      })
      .then(function (data) {
        updateProgressUi(form, data);
        if (window.Bookshelf) window.Bookshelf.showToast(data.message);
      })
      .catch(function (error) {
        if (window.Bookshelf) window.Bookshelf.showToast(error.message || 'Could not save the bookmark.', 'error');
      })
      .finally(function () {
        if (submitButton) submitButton.disabled = false;
      });
  }

  function init() {
    document.querySelectorAll('[data-progress-form]').forEach(function (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        submitProgress(form);
      });
    });

    document.querySelectorAll('[data-page-step]').forEach(function (button) {
      button.addEventListener('click', function () {
        var form = button.closest('form');
        if (!form) return;
        var input = form.elements['page'];
        if (!input) return;
        var step = Number(button.dataset.pageStep);
        var max = input.max ? Number(input.max) : Infinity;
        var next = Math.min(max, Math.max(0, (Number(input.value) || 0) + step));
        input.value = next;
        submitProgress(form);
      });
    });
  }

  window.BookProgress = { csrfToken: csrfToken, submitProgress: submitProgress };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
