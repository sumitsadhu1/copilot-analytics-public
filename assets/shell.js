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
    '<div class="app-search" id="shSearchWrap">' + icon('sh-search') +
      '<input type="search" id="shSearch" placeholder="Search all guides&hellip;" aria-label="Search guides" autocomplete="off">' +
    '</div>' +
    '<div class="app-bar-right" id="shRight"></div>';

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
  main.appendChild(content);
  appBody.appendChild(scrim);
  appBody.appendChild(rail);
  appBody.appendChild(main);

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

  var searchBox = doc.getElementById('shSearch');
  searchBox.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      var q = searchBox.value.trim();
      location.href = prefix + 'browse.html' + (q ? '?q=' + encodeURIComponent(q) : '');
    }
  });
  doc.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && body.classList.contains('nav-open')) {
      body.classList.remove('nav-open');
      aria();
      toggle.focus();
    }
  });
})();
