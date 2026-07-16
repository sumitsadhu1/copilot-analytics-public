/* Copilot Analytics — shared admin-center app shell for guide pages.
 *
 * Injected via <script defer src="{prefix}assets/shell.js"></script>.
 * Builds the top app bar + left nav rail, reuses the page's existing
 * breadcrumb / PDF button / scroll-spy element, folds any on-page TOC
 * into the rail, and reparents the page content into the shell — without
 * removing the elements the page's own inline scripts rely on.
 */
(function () {
  'use strict';
  var doc = document, body = doc.body;
  if (!body || body.getAttribute('data-shell') === 'on') { return; }

  // 1) Resolve the relative prefix to the site root from the stylesheet link.
  var cssLink = doc.querySelector('link[href*="assets/docs-style.css"]');
  var prefix = cssLink ? cssLink.getAttribute('href').replace(/assets\/docs-style\.css.*$/, '') : '';
  var path = location.pathname;

  function sym(id, inner) { return '<symbol id="' + id + '" viewBox="0 0 24 24">' + inner + '</symbol>'; }
  function icon(id) { return '<svg class="ic"><use href="#' + id + '"></use></svg>'; }

  var SPRITE = '<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>' +
    sym('sh-menu', '<path d="M3 6h18M3 12h18M3 18h18"/>') +
    sym('sh-search', '<circle cx="11" cy="11" r="7"/><path d="M20.5 20.5 16.6 16.6"/>') +
    sym('sh-close', '<path d="M6 6l12 12M18 6 6 18"/>') +
    sym('sh-home', '<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v9h12v-9"/>') +
    sym('sh-target', '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1.1"/>') +
    sym('sh-gear', '<circle cx="12" cy="12" r="3.2"/><path d="M12 3v2.4M12 18.6V21M4.2 4.2l1.7 1.7M18.1 18.1l1.7 1.7M3 12h2.4M18.6 12H21M4.2 19.8l1.7-1.7M18.1 5.9l1.7-1.7"/>') +
    sym('sh-chart', '<path d="M4 3v17h17"/><rect x="7.5" y="12" width="2.8" height="5.5" rx="0.6"/><rect x="12.6" y="8.5" width="2.8" height="9" rx="0.6"/><rect x="17.7" y="5.5" width="2.8" height="12" rx="0.6"/>') +
    sym('sh-book', '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 1 6.5 18H19"/>') +
    sym('sh-arch', '<rect x="9" y="3" width="6" height="4.5" rx="1"/><rect x="3" y="16.5" width="6" height="4.5" rx="1"/><rect x="15" y="16.5" width="6" height="4.5" rx="1"/><path d="M12 7.5v4.5M6 16.5v-2.5h12v2.5"/>') +
    sym('sh-tools', '<path d="M9.5 3h5M10.5 3v5.5L6 17a2 2 0 0 0 1.8 3h8.4a2 2 0 0 0 1.8-3L13.5 8.5V3"/><path d="M8.5 14h7"/>') +
    sym('sh-grid', '<rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/>') +
    sym('sh-sparkle', '<path d="M12 3.5l1.9 4.9 4.9 1.9-4.9 1.9L12 17l-1.9-4.8L5.2 10.3l4.9-1.9z"/>') +
    sym('sh-chat', '<path d="M20.5 12a7.8 7.8 0 0 1-11.3 7L4 20.5 5.5 15.4A7.8 7.8 0 1 1 20.5 12z"/>') +
    '</defs></svg>';

  var NAV = [
    { icon: 'sh-home', label: 'Home', href: 'index.html', on: function () { return /(^|\/)index\.html$/.test(path); } },
    { group: 'Guides' },
    { icon: 'sh-target', label: 'Strategy', href: 'browse.html#strategy', on: function () { return path.indexOf('/1-strategy/') > -1 || path.indexOf('/decide/') > -1 || path.indexOf('/explain/') > -1; } },
    { icon: 'sh-gear', label: 'Setup', href: 'browse.html#setup', on: function () { return path.indexOf('/2-setup/') > -1 || /Implementation_Guide|Setup_Companion|Multi_Agency/i.test(path); } },
    { icon: 'sh-chart', label: 'Operate', href: 'browse.html#operate', on: function () { return path.indexOf('/3-operate/') > -1 || /Lifecycle_Billing|Advanced_Viva/i.test(path); } },
    { icon: 'sh-book', label: 'Reference', href: 'browse.html#reference', on: function () { return path.indexOf('/4-reference/') > -1 || /Copilot_Analytics_FAQ|QuickStart/i.test(path); } },
    { divider: true },
    { icon: 'sh-tools', label: 'Tools', href: 'tools/index.html', on: function () { return path.indexOf('/tools/') > -1 || /Org_Data_Validation/i.test(path); } },
    { icon: 'sh-grid', label: 'Browse all', href: 'browse.html', on: function () { return path.indexOf('browse.html') > -1; } }
  ];

  // 2) Salvage the useful bits of the existing doc-nav, then drop it.
  var docNav = doc.querySelector('.doc-nav');
  var pdfEl = null, crumbEls = [], curSection = null;
  if (docNav) {
    pdfEl = docNav.querySelector('.pdf-btn');
    var left = docNav.querySelector('.doc-nav-left');
    if (left) {
      curSection = left.querySelector('#currentSection');
      left.querySelectorAll('.breadcrumb').forEach(function (b) { if (b !== curSection) { crumbEls.push(b); } });
    }
    docNav.parentNode.removeChild(docNav);
  }

  // 3) Capture any on-page sidebar TOC to fold into the rail.
  var sideNav = doc.querySelector('.sidebar-nav');
  var tocLinks = [];
  if (sideNav) {
    sideNav.querySelectorAll('a').forEach(function (a) { tocLinks.push({ href: a.getAttribute('href'), text: a.textContent }); });
  }

  // 4) Move remaining body content into .doc-content (hide legacy sidebar chrome,
  //    but keep it in the DOM so the page's own scripts never hit a null ref).
  var content = doc.createElement('div');
  content.className = 'doc-content';
  Array.prototype.slice.call(body.childNodes).forEach(function (n) {
    if (n.nodeType === 1 && n.classList &&
        (n.classList.contains('sidebar-nav') || n.classList.contains('sidebar-toggle') || n.classList.contains('sidebar-overlay'))) {
      n.style.display = 'none';
    }
    content.appendChild(n);
  });

  var trust = doc.createElement('aside');
  trust.className = 'trust-strip';
  trust.setAttribute('aria-label', 'Publication status');
  trust.innerHTML = '<strong>Independent publication</strong><span>Last validated 16 July 2026</span>' +
    '<span>Owner: Sumit Sadhu</span>' +
    '<a href="' + prefix + '4-reference/change-history.html">Change history</a>' +
    '<a href="https://github.com/sumitsadhu1/copilot-analytics-public/issues/new">Report a correction</a>';
  content.insertBefore(trust, content.firstChild);

  // 5) Build the shell.
  var spriteHost = doc.createElement('div');
  spriteHost.style.display = 'none';
  spriteHost.innerHTML = SPRITE;

  var skipLink = doc.createElement('a');
  skipLink.className = 'skip-link';
  skipLink.href = '#main-content';
  skipLink.textContent = 'Skip to main content';

  var bar = doc.createElement('header');
  bar.className = 'app-bar';
  bar.innerHTML =
    '<button class="icon-btn" id="shToggle" aria-label="Toggle navigation" aria-expanded="true">' + icon('sh-menu') + '</button>' +
    '<a class="brand" href="' + prefix + 'index.html" aria-label="Copilot Analytics home">' +
      '<span class="brand-tile">' + icon('sh-sparkle') + '</span>' +
      '<span class="brand-name">Copilot Analytics</span>' +
    '</a>' +
    '<nav class="app-crumb" id="shCrumb" aria-label="Breadcrumb"></nav>' +
    '<div class="app-bar-spacer"></div>' +
    '<div class="app-bar-right" id="shRight">' +
      '<button class="icon-btn search-launcher" id="shSearchOpen" type="button" aria-label="Search guides" aria-controls="shSearchPanel" aria-expanded="false">' + icon('sh-search') + '</button>' +
    '</div>';

  var rail = doc.createElement('nav');
  rail.className = 'nav-rail';
  rail.id = 'shRail';
  rail.setAttribute('aria-label', 'Primary');
  var html = '';
  var activeAreaHref = null;
  NAV.forEach(function (it) {
    if (it.group) { html += '<div class="nav-label">' + it.group + '</div>'; return; }
    if (it.divider) { html += '<hr>'; return; }
    var active = false;
    try { active = !!it.on(); } catch (e) { active = false; }
    if (active && !activeAreaHref) { activeAreaHref = it.href; }
    html += '<a class="nav-item' + (active ? ' active' : '') + '" href="' + prefix + it.href + '"' +
      (active ? ' aria-current="page"' : '') + '>' + icon(it.icon) + '<span class="nav-txt">' + it.label + '</span></a>';
  });
  if (tocLinks.length) {
    html += '<hr><div class="nav-label">On this page</div>';
    tocLinks.forEach(function (t) {
      html += '<a class="nav-item nav-sub" href="' + t.href + '"><span class="nav-txt">' + t.text + '</span></a>';
    });
  }
  rail.innerHTML = html;

  var scrim = doc.createElement('div'); scrim.className = 'nav-scrim'; scrim.id = 'shScrim';
  var appBody = doc.createElement('div'); appBody.className = 'app-body';
  var main = doc.createElement('main'); main.className = 'app-main'; main.id = 'main-content'; main.tabIndex = -1;
  var searchPanel = doc.createElement('aside');
  searchPanel.className = 'search-panel';
  searchPanel.id = 'shSearchPanel';
  searchPanel.setAttribute('aria-label', 'Search guides');
  searchPanel.hidden = true;
  searchPanel.innerHTML =
    '<div class="search-panel-header">' +
      '<div><strong>Search guides</strong><span>Find a section across the documentation hub.</span></div>' +
      '<button class="icon-btn" id="shSearchClose" type="button" aria-label="Close search panel">' + icon('sh-close') + '</button>' +
    '</div>' +
    '<div class="search-panel-controls">' +
      '<label class="search-panel-input">' + icon('sh-search') +
        '<input type="search" id="shSearch" placeholder="Search all guides&hellip;" aria-label="Search all guides" autocomplete="off">' +
      '</label>' +
      '<label class="search-keep"><input type="checkbox" id="shSearchKeep"> <span>Keep open while navigating</span></label>' +
    '</div>' +
    '<p class="search-panel-status" id="shSearchStatus" role="status" aria-live="polite">Enter at least two characters.</p>' +
    '<div class="search-panel-results" id="shSearchResults"></div>';
  main.appendChild(content);
  appBody.appendChild(scrim);
  appBody.appendChild(rail);
  appBody.appendChild(main);
  appBody.appendChild(searchPanel);

  body.appendChild(spriteHost);
  body.appendChild(skipLink);
  body.appendChild(bar);
  body.appendChild(appBody);

  // 6) Breadcrumb: Home / <area & section links> / <current page>.
  var crumb = doc.getElementById('shCrumb');
  var homeA = doc.createElement('a');
  homeA.href = prefix + 'index.html';
  homeA.textContent = 'Home';
  crumb.appendChild(homeA);
  var lastCrumb = crumbEls.length - 1;
  crumbEls.forEach(function (b, i) {
    var sep = doc.createElement('span'); sep.className = 'crumb-sep'; sep.textContent = '/';
    crumb.appendChild(sep);
    // The final crumb (when there is no separate #currentSection) is the current page — leave as text.
    if (i === lastCrumb && !curSection) { crumb.appendChild(b); return; }
    // Already a link (e.g. "Troubleshooting Scenarios") — keep its target, normalise the look.
    if (b.tagName === 'A' && b.getAttribute('href')) { b.className = 'crumb-link'; crumb.appendChild(b); return; }
    // Plain area/section crumb -> link it to its Browse section (or the page's active area).
    var txt = (b.textContent || '').trim();
    var target = null;
    for (var j = 0; j < NAV.length; j++) {
      if (NAV[j].label && NAV[j].label.toLowerCase() === txt.toLowerCase()) { target = NAV[j].href; break; }
    }
    if (!target) { target = activeAreaHref; }
    if (target) {
      var la = doc.createElement('a');
      la.href = prefix + target;
      la.textContent = txt;
      la.className = 'crumb-link';
      crumb.appendChild(la);
    } else {
      crumb.appendChild(b);
    }
  });
  if (curSection) { crumb.appendChild(curSection); }

  // 7) Relocate the PDF download into the app bar.
  if (pdfEl) {
    var r = doc.getElementById('shRight');
    r.insertBefore(pdfEl, r.firstChild);
  }

  // 8) Body state.
  body.classList.remove('has-nav', 'has-sidebar');
  body.classList.add('has-shell');
  if (tocLinks.length) { body.classList.add('has-toc'); }
  body.setAttribute('data-shell', 'on');

  // 9) Behaviour: nav toggle (collapse on desktop, drawer on mobile) + search.
  var mq = window.matchMedia('(max-width: 860px)');
  var toggle = doc.getElementById('shToggle');
  function aria() {
    toggle.setAttribute('aria-expanded',
      String(mq.matches ? body.classList.contains('nav-open') : !body.classList.contains('nav-collapsed')));
  }
  toggle.addEventListener('click', function () {
    body.classList.toggle(mq.matches ? 'nav-open' : 'nav-collapsed');
    aria();
  });
  scrim.addEventListener('click', function () { body.classList.remove('nav-open'); aria(); });
  if (mq.addEventListener) { mq.addEventListener('change', function () { body.classList.remove('nav-open'); aria(); }); }

  var searchOpen = doc.getElementById('shSearchOpen');
  var searchClose = doc.getElementById('shSearchClose');
  var searchBox = doc.getElementById('shSearch');
  var searchKeep = doc.getElementById('shSearchKeep');
  var searchStatus = doc.getElementById('shSearchStatus');
  var searchResults = doc.getElementById('shSearchResults');
  var searchIndex = null;
  var searchTimer = null;

  function setSearchOpen(open, focusInput) {
    var scrollTop = main.scrollTop;
    searchPanel.hidden = !open;
    body.classList.toggle('search-panel-open', open);
    searchOpen.setAttribute('aria-expanded', String(open));
    requestAnimationFrame(function () { main.scrollTop = scrollTop; });
    if (open && focusInput) { searchBox.focus(); }
  }

  function appendHighlightedText(parent, text, terms) {
    var pattern = terms.map(function (term) {
      return term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('|');
    if (!pattern) { parent.textContent = text; return; }
    var matcher = new RegExp('(' + pattern + ')', 'gi');
    var offset = 0;
    text.replace(matcher, function (match, _capture, index) {
      if (index > offset) { parent.appendChild(doc.createTextNode(text.slice(offset, index))); }
      var mark = doc.createElement('mark');
      mark.textContent = match;
      parent.appendChild(mark);
      offset = index + match.length;
      return match;
    });
    if (offset < text.length) { parent.appendChild(doc.createTextNode(text.slice(offset))); }
  }

  function renderSearch() {
    var query = searchBox.value.trim();
    var terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    searchResults.textContent = '';
    if (query.length < 2) {
      searchStatus.textContent = 'Enter at least two characters.';
      return;
    }
    if (!searchIndex) {
      searchStatus.textContent = 'Loading the search index...';
      return;
    }
    var matches = searchIndex.filter(function (entry) {
      var haystack = (entry.heading + ' ' + entry.content).toLowerCase();
      return terms.every(function (term) { return haystack.indexOf(term) !== -1; });
    }).slice(0, 20);
    searchStatus.textContent = matches.length
      ? matches.length + ' matching section' + (matches.length === 1 ? '' : 's') + (matches.length === 20 ? ' shown. Refine your search for fewer results.' : '.')
      : 'No matching sections. Try a broader term.';
    matches.forEach(function (entry) {
      var link = doc.createElement('a');
      link.className = 'search-result';
      link.href = prefix + entry.url;
      var source = doc.createElement('span');
      source.className = 'search-result-source';
      source.textContent = entry.doc;
      var heading = doc.createElement('strong');
      appendHighlightedText(heading, entry.heading, terms);
      var preview = doc.createElement('span');
      preview.className = 'search-result-preview';
      var lower = entry.content.toLowerCase();
      var first = terms.reduce(function (found, term) {
        var index = lower.indexOf(term);
        return index !== -1 && (found === -1 || index < found) ? index : found;
      }, -1);
      var start = first > 70 ? first - 50 : 0;
      var excerpt = (start ? '...' : '') + entry.content.slice(start, start + 220);
      if (start + 220 < entry.content.length) { excerpt += '...'; }
      appendHighlightedText(preview, excerpt, terms);
      link.appendChild(source);
      link.appendChild(heading);
      link.appendChild(preview);
      link.addEventListener('click', function () {
        if (searchKeep.checked) {
          sessionStorage.setItem('copilotSearchOpen', 'true');
          sessionStorage.setItem('copilotSearchQuery', query);
        } else {
          sessionStorage.removeItem('copilotSearchOpen');
          sessionStorage.removeItem('copilotSearchQuery');
        }
      });
      searchResults.appendChild(link);
    });
  }

  function loadSearchIndex() {
    if (searchIndex) { renderSearch(); return; }
    fetch(prefix + 'assets/search-index.json')
      .then(function (response) { if (!response.ok) { throw new Error('Search index unavailable'); } return response.json(); })
      .then(function (entries) { searchIndex = entries; renderSearch(); })
      .catch(function () { searchIndex = []; searchStatus.textContent = 'Search is temporarily unavailable.'; });
  }

  searchOpen.addEventListener('click', function () {
    setSearchOpen(true, true);
    loadSearchIndex();
  });
  searchClose.addEventListener('click', function () {
    searchKeep.checked = false;
    sessionStorage.removeItem('copilotSearchOpen');
    sessionStorage.removeItem('copilotSearchQuery');
    setSearchOpen(false, false);
    searchOpen.focus();
  });
  searchKeep.addEventListener('change', function () {
    if (searchKeep.checked) {
      sessionStorage.setItem('copilotSearchOpen', 'true');
      sessionStorage.setItem('copilotSearchQuery', searchBox.value.trim());
    } else {
      sessionStorage.removeItem('copilotSearchOpen');
      sessionStorage.removeItem('copilotSearchQuery');
    }
  });
  searchBox.addEventListener('input', function () {
    if (searchKeep.checked) { sessionStorage.setItem('copilotSearchQuery', searchBox.value.trim()); }
    clearTimeout(searchTimer);
    searchTimer = setTimeout(renderSearch, 120);
  });

  if (sessionStorage.getItem('copilotSearchOpen') === 'true') {
    searchKeep.checked = true;
    searchBox.value = sessionStorage.getItem('copilotSearchQuery') || '';
    setSearchOpen(true, false);
    loadSearchIndex();
  }

  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (!searchPanel.hidden) {
        searchKeep.checked = false;
        sessionStorage.removeItem('copilotSearchOpen');
        sessionStorage.removeItem('copilotSearchQuery');
        setSearchOpen(false, false);
        searchOpen.focus();
      } else if (body.classList.contains('nav-open')) {
        body.classList.remove('nav-open');
        aria();
        toggle.focus();
      }
    }
  });
})();
