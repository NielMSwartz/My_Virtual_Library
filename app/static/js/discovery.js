/* Online book search: render results and prefill the manual entry form. */
(function () {
  'use strict';

  var form = document.getElementById('online-search-form');
  if (!form) return;

  var config = window.BOOK_TRACKER || {};
  var queryInput = document.getElementById('online-query');
  var resultsBox = document.getElementById('search-results');
  var feedbackBox = document.getElementById('search-feedback');
  var bookForm = document.getElementById('book-form');
  var currentResults = [];

  function setField(name, value) {
    var element = bookForm && bookForm.elements[name];
    if (element && value !== undefined && value !== null && value !== '') {
      element.value = value;
    }
  }

  function showFeedback(message, type) {
    feedbackBox.textContent = message || '';
    feedbackBox.className = 'search-feedback' + (type ? ' search-feedback--' + type : '');
    feedbackBox.hidden = !message;
  }

  function setLoading(loading) {
    var button = form.querySelector('button[type="submit"]');
    button.disabled = loading;
    queryInput.disabled = loading;
    if (!loading) return;

    showFeedback('Searching the book catalogues…', 'info');
    resultsBox.hidden = false;
    resultsBox.innerHTML = '';
    for (var i = 0; i < 4; i += 1) {
      var skeleton = document.createElement('div');
      skeleton.className = 'skeleton';
      resultsBox.appendChild(skeleton);
    }
  }

  function buildResult(result, index) {
    var card = document.createElement('article');
    card.className = 'result-card';

    var cover = document.createElement('img');
    cover.className = 'result-cover';
    cover.src = result.cover_small_url || result.cover_url || config.placeholder;
    cover.alt = result.title ? 'Cover of ' + result.title : 'No cover available';
    cover.loading = 'lazy';
    card.appendChild(cover);

    var info = document.createElement('div');
    info.className = 'result-info';

    var title = document.createElement('h3');
    title.className = 'result-title';
    title.textContent = result.title || 'Untitled';
    info.appendChild(title);

    var meta = document.createElement('p');
    meta.className = 'result-meta';
    var metaParts = [
      result.authors || 'Unknown author',
      result.publication_year || '',
      result.page_count ? result.page_count + ' pages' : ''
    ].filter(Boolean);
    meta.textContent = metaParts.join(' · ');
    info.appendChild(meta);

    if (result.description) {
      var description = document.createElement('p');
      description.className = 'result-desc';
      description.textContent = result.description;
      info.appendChild(description);
    }

    var sourceNote = document.createElement('p');
    sourceNote.className = 'result-status muted';
    sourceNote.textContent = result.source === 'open_library' ? 'Open Library' : 'Google Books';
    info.appendChild(sourceNote);

    if (result.in_library) {
      var existing = document.createElement('a');
      existing.className = 'btn btn-outline btn-sm';
      existing.href = '/books/' + result.book_id;
      existing.textContent = 'Already in your library';
      info.appendChild(existing);
    } else {
      var pick = document.createElement('button');
      pick.type = 'button';
      pick.className = 'btn btn-primary btn-sm';
      pick.textContent = 'Use this book';
      pick.addEventListener('click', function () { useResult(index); });
      info.appendChild(pick);
    }

    card.appendChild(info);
    return card;
  }

  function useResult(index) {
    var result = currentResults[index];
    if (!result) return;

    setField('title', result.title);
    setField('authors', result.authors || 'Unknown author');
    setField('cover_url', result.cover_url);
    setField('cover_small_url', result.cover_small_url);
    setField('isbn', result.isbn);
    setField('publisher', result.publisher);
    setField('publication_year', result.publication_year);
    setField('page_count', result.page_count);
    setField('description', result.description);
    setField('genre', result.genre);
    setField('source', result.source);
    setField('external_id', result.external_id);

    bookForm.classList.add('is-prefilled');
    if (window.Bookshelf) {
      window.Bookshelf.showToast('Details loaded — review them, then save the book.');
    }
    bookForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
    var titleField = bookForm.elements['title'];
    if (titleField) titleField.focus({ preventScroll: true });
  }

  function render(payload) {
    currentResults = payload.results || [];
    resultsBox.innerHTML = '';

    if (!currentResults.length) {
      resultsBox.hidden = true;
      showFeedback(
        payload.warning || 'No matches found. Try a different search, or add the book manually below.',
        payload.warning ? 'error' : 'info'
      );
      return;
    }

    showFeedback(payload.warning || currentResults.length + ' match(es) found. Choose one to fill in the form.', payload.warning ? 'error' : 'info');
    currentResults.forEach(function (result, index) {
      resultsBox.appendChild(buildResult(result, index));
    });
    resultsBox.hidden = false;
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var query = queryInput.value.trim();
    if (query.length < 2) {
      showFeedback('Enter at least two characters to search.', 'info');
      queryInput.focus();
      return;
    }

    setLoading(true);
    fetch(config.onlineSearchUrl + '?q=' + encodeURIComponent(query), {
      headers: { Accept: 'application/json' }
    })
      .then(function (response) {
        if (!response.ok) throw new Error('Search request failed');
        return response.json();
      })
      .then(render)
      .catch(function () {
        resultsBox.hidden = true;
        showFeedback('Search is unavailable right now. You can still add the book manually below.', 'error');
      })
      .finally(function () {
        setLoading(false);
      });
  });
})();
