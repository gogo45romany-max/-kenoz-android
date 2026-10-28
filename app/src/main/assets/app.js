/* KENOZ — offline library app (Android WebView + browser preview) */
(function () {
  'use strict';

  /* ------------------------------------------------------------------ */
  /* platform                                                            */
  /* ------------------------------------------------------------------ */
  var Native = window.KenozAndroid || null;

  var Store = {
    get: function (key, fallback) {
      try {
        var raw = Native ? Native.getPref(key) : localStorage.getItem(key);
        if (raw === null || raw === undefined || raw === '') return fallback;
        return JSON.parse(raw);
      } catch (e) { return fallback; }
    },
    set: function (key, value) {
      try {
        var raw = JSON.stringify(value);
        if (Native) Native.setPref(key, raw); else localStorage.setItem(key, raw);
      } catch (e) { /* ignore */ }
    }
  };

  var Files = {
    cache: new Map(),
    text: function (path) {
      if (Native) {
        return new Promise(function (resolve, reject) {
          var s = Native.readAsset('content/' + path);
          if (!s) reject(new Error('missing asset: ' + path)); else resolve(s);
        });
      }
      return fetch('content/' + path).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status + ' — ' + path);
        return r.text();
      });
    },
    json: function (path, cacheIt) {
      if (cacheIt !== false && Files.cache.has(path)) return Promise.resolve(Files.cache.get(path));
      return Files.text(path).then(function (t) {
        var j = JSON.parse(t);
        if (cacheIt !== false) Files.cache.set(path, j);
        return j;
      });
    }
  };

  var prefs = {
    theme: Store.get('theme', 'light'),
    font: Store.get('font', 19),
    lh: Store.get('lh', 2.02),
    last: Store.get('last', null),
    bookmarks: Store.get('bookmarks', [])
  };

  function savePref(key) { Store.set(key, prefs[key]); }

  /* ------------------------------------------------------------------ */
  /* utils                                                               */
  /* ------------------------------------------------------------------ */
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function $(sel) { return document.querySelector(sel); }

  function icon(name, size) {
    var paths = {
      book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v18H6.5A2.5 2.5 0 0 1 4 18.5z"/><path d="M11 3h6.5A2.5 2.5 0 0 1 20 5.5v13a2.5 2.5 0 0 1-2.5 2.5H11"/>',
      clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
      church: '<path d="M12 2.5v4M10 4.5h4"/><path d="M12 6.5 5 11v9h14v-9z"/><path d="M9.5 20v-5h5v5"/>',
      calendar: '<rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M8 3v4M16 3v4M3.5 10h17"/>',
      star: '<path d="M12 3.2l2.6 5.4 5.9.8-4.3 4.1 1.1 5.9-5.3-2.9-5.3 2.9 1.1-5.9L3.5 9.4l5.9-.8z"/>',
      music: '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.6"/><circle cx="16.5" cy="16" r="2.6"/>',
      harp: '<path d="M5 20V8a7 7 0 0 1 14 0v12"/><path d="M5 13h14M8 20v-6M12 20v-7M16 20v-6"/>',
      pray: '<path d="M12 21V9"/><path d="M12 9c0-3 2-6 4.5-6.5C17.5 6 15 9 12 9z"/><path d="M12 9c0-3-2-6-4.5-6.5C6.5 6 9 9 12 9z"/><path d="M8 21h8"/>',
      guide: '<circle cx="12" cy="12" r="8.5"/><path d="M15.5 8.5 13 13l-4.5 2.5L11 11z"/>',
      search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
      song: '<path d="M4 7h9M4 12h9M4 17h6"/><path d="M17 6v10.5"/><circle cx="15" cy="18" r="2"/>',
      cross: '<path d="M12 3v18M7 9h10"/>',
      heart: '<path d="M12 20s-7.5-4.6-7.5-9.4A4.1 4.1 0 0 1 12 8a4.1 4.1 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/>',
      chev: '<path d="M9 6l6 6-6 6"/>',
      close: '<path d="M6 6l12 12M18 6L6 18"/>'
    };
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    if (size) { svg.setAttribute('width', size); svg.setAttribute('height', size); }
    svg.innerHTML = paths[name] || paths.book;
    return svg;
  }

  function toast(msg) {
    var t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toast._h);
    toast._h = setTimeout(function () { t.classList.remove('show'); }, 2200);
  }

  var DIAC = /[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/;

  function normMap(s) {
    var out = '', map = [];
    for (var i = 0; i < s.length; i++) {
      var ch = s.charAt(i);
      if (DIAC.test(ch)) continue;
      if (ch === '\u0640') continue;
      if ('أإآٱ'.indexOf(ch) >= 0) ch = 'ا';
      else if (ch === 'ى') ch = 'ي';
      else if (ch === 'ة') ch = 'ه';
      else if (ch === 'ؤ') ch = 'و';
      else if (ch === 'ئ') ch = 'ي';
      out += ch;
      map.push(i);
    }
    return { n: out.toLowerCase(), map: map };
  }

  function norm(s) { return normMap(s).n; }

  function tokensOf(q) {
    return norm(q).split(/[^\w\u0600-\u06FF]+/).filter(function (t) { return t.length >= 2; });
  }

  function copticToday(d) {
    d = d || new Date();
    var today = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    function newYear(gy) {
      var cy = gy - 283;
      return new Date(gy, 8, (cy % 4 === 0) ? 12 : 11);
    }
    var gy = today.getFullYear();
    var ny = newYear(gy);
    if (today < ny) { gy -= 1; ny = newYear(gy); }
    var diff = Math.round((today - ny) / 86400000);
    var month = Math.floor(diff / 30);
    var day = (diff % 30) + 1;
    return { year: gy - 283, month: month, day: day, name: COPTIC_MONTHS[Math.min(month, 12)] };
  }

  var COPTIC_MONTHS = ['توت', 'بابه', 'هاتور', 'كيهك', 'طوبة', 'أمشير', 'برمهات',
    'برمودة', 'بشنس', 'بؤونة', 'أبيب', 'مسرى', 'النسئ'];

  var AR_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];
  function arNum(n) {
    return String(n).replace(/\d/g, function (d) { return AR_DIGITS[+d]; });
  }
  function fmtCount(n) { return arNum(n); }

  /* ------------------------------------------------------------------ */
  /* state                                                               */
  /* ------------------------------------------------------------------ */
  var state = {
    catalog: null,
    stack: [],
    indexes: new Map(),
    docs: new Map(),
    view: null
  };

  function getIndex(secId) {
    if (state.indexes.has(secId)) return Promise.resolve(state.indexes.get(secId));
    return Files.json(secId + '/index.json').then(function (j) {
      state.indexes.set(secId, j);
      return j;
    });
  }

  function docKey(secId, file) { return secId + '/' + file; }

  function getDoc(secId, file) {
    var key = docKey(secId, file);
    if (state.docs.has(key)) return Promise.resolve(state.docs.get(key));
    return Files.json(secId + '/' + file, false).then(function (j) {
      state.docs.set(key, j);
      if (state.docs.size > 14) state.docs.delete(state.docs.keys().next().value);
      return j;
    });
  }

  function sectionMeta(id) {
    if (!state.catalog) return null;
    for (var i = 0; i < state.catalog.sections.length; i++) {
      if (state.catalog.sections[i].id === id) return state.catalog.sections[i];
    }
    return null;
  }

  /* ------------------------------------------------------------------ */
  /* navigation                                                          */
  /* ------------------------------------------------------------------ */
  function rememberScroll() {
    if (state.view && state.view.type !== 'home') state.view.scroll = window.scrollY;
  }

  function go(view) {
    rememberScroll();
    state.stack.push(view);
    render();
  }
  function replace(view) {
    rememberScroll();
    state.stack[state.stack.length - 1] = view;
    render();
  }
  function back() {
    if (state.stack.length > 1) {
      rememberScroll();
      state.stack.pop();
      render();
      return true;
    }
    return false;
  }
  window.kenozBack = function () { return back(); };

  function render() {
    var view = state.stack[state.stack.length - 1];
    state.view = view;
    var barTitle = $('#barTitle');
    var btnBack = $('#btnBack');
    if (state.stack.length > 1) btnBack.classList.remove('hidden');
    else btnBack.classList.add('hidden');

    var viewEl = $('#view');
    viewEl.scrollTop = 0;
    window.scrollTo(0, 0);

    var title = 'كنوز';
    if (view.type === 'section') title = (sectionMeta(view.id) || {}).title || 'قسم';
    else if (view.type === 'doc') title = view.title || 'قراءة';
    else if (view.type === 'search') title = 'البحث';
    else if (view.type === 'bookmarks') title = 'محفوظاتي';
    else if (view.type === 'settings') title = 'الإعدادات';
    barTitle.textContent = title;

    var nav = $('#bottomnav');
    Array.prototype.forEach.call(nav.querySelectorAll('button'), function (b) {
      b.classList.toggle('active', b.dataset.nav === view.type ||
        (view.type === 'section' || view.type === 'doc') && b.dataset.nav === 'home');
    });

    var toolbar = document.querySelector('.toolbar');
    if (toolbar) toolbar.remove();

    var renderer = {
      home: renderHome,
      section: renderSection,
      doc: renderDoc,
      search: renderSearch,
      bookmarks: renderBookmarks,
      settings: renderSettings
    }[view.type];

    viewEl.innerHTML = '';
    var loading = el('div', 'loading');
    loading.appendChild(el('div', 'spinner'));
    viewEl.appendChild(loading);

    Promise.resolve()
      .then(function () { return renderer(view); })
      .then(function (node) {
        if (state.view !== view) return;
        clear(viewEl);
        viewEl.appendChild(node);
        if (view.scroll) window.scrollTo(0, view.scroll);
      })
      .catch(function (err) {
        clear(viewEl);
        var box = el('div', 'empty');
        box.appendChild(el('div', null, 'تعذّر تحميل المحتوى'));
        box.appendChild(el('small', null, String(err && err.message || err)));
        viewEl.appendChild(box);
      });
  }

  /* ------------------------------------------------------------------ */
  /* home                                                                */
  /* ------------------------------------------------------------------ */
  function renderHome() {
    var frag = document.createDocumentFragment();

    var hero = el('section', 'hero');
    hero.appendChild(el('h1', null, '✝ كنوز'));
    hero.appendChild(el('p', null, 'مكتبة الكنيسة القبطية الأرثوذكسية — ' + fmtCount(state.catalog.docs) + ' مستندًا للقراءة دون اتصال'));

    var cd = copticToday();
    var today = el('div', 'today');
    today.appendChild(el('div', 'd', arNum(cd.day) + ' ' + cd.name + ' ' + arNum(cd.year) + ' ش'));
    var links = el('div', 'links');
    var b1 = el('button', null, 'سنكسار اليوم');
    b1.onclick = function () { openSynaxarium(cd); };
    var b2 = el('button', null, 'قطمارس اليوم');
    b2.onclick = function () { openDailyKatamars(cd); };
    links.appendChild(b1); links.appendChild(b2);
    today.appendChild(links);
    hero.appendChild(today);
    frag.appendChild(hero);

    frag.appendChild(verseCard());

    if (prefs.last) {
      var cont = el('div', 'continue');
      var ic = el('div', 'ic', '↺');
      var txt = el('div', 'txt');
      txt.appendChild(el('b', null, prefs.last.title || 'متابعة القراءة'));
      txt.appendChild(el('small', null, prefs.last.sectionTitle || ''));
      cont.appendChild(ic); cont.appendChild(txt);
      cont.onclick = function () {
        go({ type: 'doc', sec: prefs.last.sec, file: prefs.last.file, title: prefs.last.title });
      };
      frag.appendChild(cont);
    }

    var box = el('div', 'searchbox');
    box.appendChild(icon('search'));
    var input = el('input');
    input.placeholder = 'ابحث في المكتبة…';
    input.readOnly = true;
    input.onfocus = function () { input.blur(); go({ type: 'search', q: '' }); };
    input.onclick = input.onfocus;
    box.appendChild(input);
    frag.appendChild(box);

    var head = el('div', 'section-title');
    head.appendChild(el('h2', null, 'أقسام المكتبة'));
    frag.appendChild(head);

    var grid = el('div', 'cards');
    state.catalog.sections.forEach(function (s) {
      var card = el('button', 'card');
      var ic = el('div', 'ic');
      ic.appendChild(icon(s.icon));
      var n = el('span', 'n', fmtCount(s.count));
      card.appendChild(ic); card.appendChild(n);
      card.appendChild(el('b', null, s.title));
      card.appendChild(el('small', null, s.desc));
      card.onclick = function () { go({ type: 'section', id: s.id }); };
      grid.appendChild(card);
    });
    frag.appendChild(grid);

    var about = el('div', 'about');
    about.appendChild(el('div', null, 'المحتوى مُستخرج من أرشيف تطبيق كنوز: الكتاب المقدس، الأجبية، الخولاجي، القطمارس، السنكسار، التسبحة، الإبصلمودية، السجود، الدلال، الشواهد والمدائح.'));
    about.appendChild(el('div', null, 'النسخة ' + (Native && Native.versionName ? Native.versionName() : '1.0.0')));
    frag.appendChild(about);

    return frag;
  }

  function verseCard() {
    var card = el('div', 'verse-card');
    card.appendChild(el('span', 'lbl', 'آية للتأمل'));
    var body = el('div', null, '…');
    card.appendChild(body);
    Files.json('verses/index.json').then(function (idx) {
      var docs = idx.groups[0].docs;
      var pick = docs[new Date().getDate() % docs.length];
      var day = Math.floor(Date.now() / 86400000);
      return Files.json('verses/' + pick.f, false).then(function (doc) {
        var items = (doc.b || []).filter(function (b) { return b[0] === 'q'; });
        if (!items.length) return;
        body.textContent = items[day % items.length][1];
      }, function () { body.textContent = ''; });
    }).catch(function () { card.classList.add('hidden'); });
    return card;
  }

  function openSynaxarium(cd) {
    getIndex('synaxarium').then(function (idx) {
      var gi = Math.min(cd.month, idx.groups.length - 2);
      var group = idx.groups[gi];
      if (!group) return toast('لا يوجد سنكسار لهذا اليوم');
      var doc = group.docs[cd.day - 1];
      if (!doc) return toast('لا يوجد سنكسار لهذا اليوم');
      go({ type: 'doc', sec: 'synaxarium', file: doc.f, title: doc.t });
    });
  }

  function openDailyKatamars(cd) {
    getIndex('katamars').then(function (idx) {
      var group = null;
      idx.groups.forEach(function (g) { if (g.id === 'days') group = g; });
      if (!group) return toast('لا يوجد قطمارس لهذا اليوم');
      var wanted = cd.name + ' — اليوم ' + cd.day;
      var doc = group.docs.filter(function (d) { return d.t === wanted; })[0];
      if (!doc) return toast('لا توجد قراءات محفوظة لهذا اليوم');
      go({ type: 'doc', sec: 'katamars', file: doc.f, title: doc.t });
    });
  }

  /* ------------------------------------------------------------------ */
  /* section                                                             */
  /* ------------------------------------------------------------------ */
  var PAGE = 70;

  function renderSection(view) {
    return getIndex(view.id).then(function (idx) {
      var meta = sectionMeta(view.id) || { title: idx.title, desc: '' };
      var frag = document.createDocumentFragment();

      var head = el('div', 'sec-head');
      var ic = el('div', 'ic');
      ic.appendChild(icon(meta.icon || 'book'));
      var h = el('div');
      h.appendChild(el('h1', null, meta.title));
      h.appendChild(el('p', null, meta.desc || ''));
      head.appendChild(ic); head.appendChild(h);
      frag.appendChild(head);

      idx.groups.forEach(function (g, gi) {
        var open = view.openGroup ? view.openGroup === g.id : gi === 0;
        var wrap = el('section', 'group' + (open ? ' open' : ''));
        var gh = el('div', 'group-h');
        var ch = el('span', 'ch');
        ch.appendChild(icon('chev', 18));
        gh.appendChild(ch);
        gh.appendChild(el('b', null, g.title));
        gh.appendChild(el('span', 'cnt', fmtCount(g.docs.length)));
        gh.onclick = function () { wrap.classList.toggle('open'); };
        wrap.appendChild(gh);

        var bodyEl = el('div', 'group-b');
        if (g.note) bodyEl.appendChild(el('div', 'note', g.note));
        var shown = 0;
        function showMore() {
          var batch = g.docs.slice(shown, shown + PAGE);
          batch.forEach(function (d) {
            bodyEl.appendChild(docRow(view.id, d));
          });
          shown += batch.length;
          var btn = bodyEl.querySelector('.more');
          if (btn) btn.remove();
          if (shown < g.docs.length) {
            var more = el('button', 'more', 'عرض المزيد (' + fmtCount(g.docs.length - shown) + ')');
            more.onclick = showMore;
            bodyEl.appendChild(more);
          }
        }
        showMore();
        wrap.appendChild(bodyEl);
        frag.appendChild(wrap);
      });

      return frag;
    });
  }

  function docRow(secId, d) {
    var row = el('div', 'row');
    var txt = el('div', 'txt');
    txt.appendChild(el('b', null, d.t));
    if (d.s) txt.appendChild(el('small', null, d.s));
    row.appendChild(txt);
    if (isBookmarked(secId, d.f)) row.appendChild(el('span', 'star', '★'));
    var chev = el('span', 'go');
    chev.appendChild(icon('chev', 16));
    row.appendChild(chev);
    row.onclick = function () { go({ type: 'doc', sec: secId, file: d.f, title: d.t }); };
    return row;
  }

  /* ------------------------------------------------------------------ */
  /* document reader                                                     */
  /* ------------------------------------------------------------------ */
  function isBookmarked(secId, file) {
    return prefs.bookmarks.some(function (b) { return b.sec === secId && b.file === file; });
  }

  function toggleBookmark(secId, file, title, secTitle) {
    var i = -1;
    prefs.bookmarks.forEach(function (b, k) { if (b.sec === secId && b.file === file) i = k; });
    if (i >= 0) prefs.bookmarks.splice(i, 1);
    else prefs.bookmarks.unshift({ sec: secId, file: file, title: title, secTitle: secTitle, ts: Date.now() });
    savePref('bookmarks');
    return i < 0;
  }

  function docPlainText(doc) {
    var out = [];
    if (doc.chs) {
      doc.chs.forEach(function (c) {
        out.push('الإصحاح ' + c.n);
        c.v.forEach(function (v) { out.push(v); });
      });
    } else if (doc.b) {
      doc.b.forEach(function (b) { if (b[1]) out.push(b[1]); });
    }
    return out.join('\n');
  }

  function renderDoc(view) {
    return Promise.all([getIndex(view.sec), getDoc(view.sec, view.file)]).then(function (res) {
      var idx = res[0], doc = res[1];
      var meta = sectionMeta(view.sec) || { title: '' };
      var group = null, docMeta = null;
      idx.groups.forEach(function (g) {
        g.docs.forEach(function (d) { if (d.f === view.file) { group = g; docMeta = d; } });
      });
      view.title = doc.t || (docMeta && docMeta.t) || view.title;

      prefs.last = { sec: view.sec, file: view.file, title: view.title, sectionTitle: meta.title };
      savePref('last');

      var frag = document.createDocumentFragment();

      var head = el('div', 'doc-head');
      head.appendChild(el('h1', null, view.title));
      var m = el('div', 'meta');
      m.appendChild(el('span', null, meta.title));
      if (group) m.appendChild(el('span', null, group.title));
      head.appendChild(m);
      frag.appendChild(head);

      if (doc.chs) {
        frag.appendChild(renderBible(doc, view));
      } else {
        var reader = el('article', 'reader');
        (doc.b || []).forEach(function (b) { appendBlock(reader, b); });
        if (!reader.childNodes.length) reader.appendChild(el('div', 'empty', 'لا توجد نصوص في هذا المستند'));
        frag.appendChild(reader);
      }

      /* prev / next */
      if (group) {
        var pos = group.docs.indexOf(docMeta);
        var nav = el('div', 'docnav');
        var prev = el('button', null, '‹ السابق');
        var next = el('button', null, 'التالي ›');
        if (pos <= 0) prev.disabled = true; else prev.onclick = function () {
          var d = group.docs[pos - 1];
          replace({ type: 'doc', sec: view.sec, file: d.f, title: d.t });
        };
        if (pos < 0 || pos >= group.docs.length - 1) next.disabled = true; else next.onclick = function () {
          var d = group.docs[pos + 1];
          replace({ type: 'doc', sec: view.sec, file: d.f, title: d.t });
        };
        nav.appendChild(prev); nav.appendChild(next);
        frag.appendChild(nav);
      }

      buildToolbar(view, doc);
      return frag;
    });
  }

  function appendBlock(parent, b) {
    var kind = b[0], text = b[1];
    if (kind === 'br') { parent.appendChild(el('div', 'b-br')); return; }
    if (kind === 'h') { parent.appendChild(el('h3', 'b-h', text)); return; }
    if (kind === 'm') { parent.appendChild(el('p', 'b-m', text)); return; }
    if (kind === 't') { parent.appendChild(el('p', 'b-t', text)); return; }
    if (kind === 'c') { parent.appendChild(el('p', 'b-c', text)); return; }
    if (kind === 'e') { parent.appendChild(el('p', 'b-e', text)); return; }
    if (kind === 'q') { parent.appendChild(el('div', 'b-q', text)); return; }
    if (kind === 'l') {
      var row = el('div', 'b-l', text);
      var target = b[2];
      row.onclick = function () {
        var sec = state.view && state.view.sec;
        if (!sec || !target) return;
        go({ type: 'doc', sec: sec, file: target + '.json', title: text });
      };
      parent.appendChild(row);
      return;
    }
    parent.appendChild(el('p', 'b-p', text));
  }

  function renderBible(doc, view) {
    var wrap = el('div');
    var chips = el('div', 'chips');
    var bodyEl = el('article', 'reader');
    var current = view.chapter || 1;
    if (!doc.chs.some(function (c) { return c.n === current; })) current = doc.chs[0].n;

    function paint() {
      clear(bodyEl);
      var ch = null;
      doc.chs.forEach(function (c) { if (c.n === current) ch = c; });
      if (!ch) return;
      ch.v.forEach(function (verse, i) {
        var row = el('div', 'verse-row');
        row.appendChild(el('span', 'verse-num', arNum(i + 1)));
        row.appendChild(el('div', null, verse));
        bodyEl.appendChild(row);
      });
      window.scrollTo(0, 0);
    }

    doc.chs.forEach(function (c) {
      var chip = el('button', 'chip' + (c.n === current ? ' on' : ''), arNum(c.n));
      chip.onclick = function () {
        current = c.n;
        view.chapter = c.n;
        Array.prototype.forEach.call(chips.children, function (x) { x.classList.remove('on'); });
        chip.classList.add('on');
        paint();
        chip.scrollIntoView({ inline: 'center', block: 'nearest' });
      };
      chips.appendChild(chip);
    });

    paint();
    wrap.appendChild(chips);
    wrap.appendChild(bodyEl);
    return wrap;
  }

  function buildToolbar(view, doc) {
    var bar = el('div', 'toolbar');

    var bm = el('button');
    bm.appendChild(icon('heart'));
    var marked = isBookmarked(view.sec, view.file);
    if (marked) bm.classList.add('on');
    bm.onclick = function () {
      var meta = sectionMeta(view.sec) || {};
      var on = toggleBookmark(view.sec, view.file, view.title, meta.title);
      bm.classList.toggle('on', on);
      toast(on ? 'تمت الإضافة إلى محفوظاتي' : 'تمت الإزالة من محفوظاتي');
    };
    bar.appendChild(bm);

    if (doc.toc && doc.toc.length) {
      var tocBtn = el('button');
      tocBtn.appendChild(icon('song'));
      tocBtn.onclick = function () { openToc(doc.toc); };
      bar.appendChild(tocBtn);
    }

    var minus = el('button', null, 'A-');
    minus.style.fontSize = '14px';
    minus.onclick = function () { setFont(prefs.font - 1); };
    var plus = el('button', null, 'A+');
    plus.style.fontSize = '16px';
    plus.onclick = function () { setFont(prefs.font + 1); };
    bar.appendChild(minus); bar.appendChild(plus);

    var th = el('button');
    th.appendChild(icon('star'));
    th.onclick = function () { cycleTheme(); };
    bar.appendChild(th);

    var copy = el('button');
    copy.appendChild(icon('book'));
    copy.onclick = function () {
      var text = view.title + '\n\n' + docPlainText(doc);
      if (Native && Native.copy) { Native.copy(text); toast('تم نسخ النص'); }
      else if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { toast('تم نسخ النص'); });
      else toast('النسخ غير متاح');
    };
    bar.appendChild(copy);

    var share = el('button');
    share.appendChild(icon('guide'));
    share.onclick = function () {
      var text = view.title + '\n\n' + docPlainText(doc).slice(0, 1500) + '…';
      if (Native && Native.share) Native.share(text, view.title);
      else if (navigator.share) navigator.share({ title: view.title, text: text }).catch(function () {});
      else toast('المشاركة غير متاحة');
    };
    bar.appendChild(share);

    document.body.appendChild(bar);
  }

  function setFont(px) {
    prefs.font = Math.max(15, Math.min(30, px));
    savePref('font');
    document.documentElement.style.setProperty('--fs', prefs.font + 'px');
    toast('حجم الخط ' + arNum(prefs.font));
  }

  function cycleTheme() {
    var order = ['light', 'sepia', 'dark'];
    var i = order.indexOf(prefs.theme);
    prefs.theme = order[(i + 1) % order.length];
    savePref('theme');
    applyTheme();
  }

  function applyTheme() {
    document.documentElement.setAttribute('data-theme', prefs.theme);
    document.documentElement.style.setProperty('--fs', prefs.font + 'px');
    document.documentElement.style.setProperty('--lh', prefs.lh);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', prefs.theme === 'dark' ? '#0b1420' : '#0f2b46');
    if (Native && Native.setTheme) Native.setTheme(prefs.theme === 'dark');
  }

  function openToc(toc) {
    var bodyEl = $('#sheetBody');
    clear(bodyEl);
    toc.forEach(function (t, i) {
      var row = el('div', 'toc-item');
      row.appendChild(el('small', null, arNum(i + 1)));
      row.appendChild(el('span', null, t));
      row.onclick = function () {
        closeSheet();
        var hs = document.querySelectorAll('.reader .b-h');
        for (var k = 0; k < hs.length; k++) {
          if (hs[k].textContent === t) { hs[k].scrollIntoView({ behavior: 'smooth', block: 'start' }); break; }
        }
      };
      bodyEl.appendChild(row);
    });
    $('#sheetTitle').textContent = 'الفهرس';
    $('#sheetWrap').classList.remove('hidden');
  }

  function closeSheet() { $('#sheetWrap').classList.add('hidden'); }

  /* ------------------------------------------------------------------ */
  /* search                                                              */
  /* ------------------------------------------------------------------ */
  var searchRun = 0;

  function renderSearch(view) {
    var frag = document.createDocumentFragment();

    var bar = el('div', 'searchbar');
    bar.appendChild(icon('search'));
    var input = el('input');
    input.type = 'search';
    input.placeholder = 'ابحث في النصوص…';
    input.value = view.q || '';
    bar.appendChild(input);
    frag.appendChild(bar);

    var scopes = el('div', 'scopes');
    var scopeAll = el('button', 'scope' + (!view.scope ? ' on' : ''), 'كل المكتبة');
    scopes.appendChild(scopeAll);
    state.catalog.sections.forEach(function (s) {
      var b = el('button', 'scope' + (view.scope === s.id ? ' on' : ''), s.title);
      b.onclick = function () { view.scope = s.id; replace(view); };
      scopes.appendChild(b);
    });
    scopeAll.onclick = function () { view.scope = null; replace(view); };
    frag.appendChild(scopes);

    var progress = el('div', 'progress');
    var pbar = el('i');
    progress.appendChild(pbar);
    progress.classList.add('hidden');
    frag.appendChild(progress);

    var status = el('div', 'empty');
    var results = el('div');
    frag.appendChild(status);
    frag.appendChild(results);

    var timer = null;
    function kick() {
      clearTimeout(timer);
      timer = setTimeout(function () {
        runSearch(view, input.value.trim(), results, status, progress, pbar);
      }, 320);
    }
    input.addEventListener('input', kick);
    setTimeout(function () { input.focus(); kick(); }, 60);

    return frag;
  }

  function findHits(doc, tokens, maxHits) {
    var items = [];
    if (doc.chs) {
      doc.chs.forEach(function (c) {
        c.v.forEach(function (v, i) {
          items.push({ text: v, label: 'الإصحاح ' + c.n + ' — آية ' + (i + 1) });
        });
      });
    } else if (doc.b) {
      doc.b.forEach(function (b) {
        if (b[1] && b[0] !== 'br') items.push({ text: b[1], label: '' });
      });
    }
    var hits = [];
    for (var i = 0; i < items.length && hits.length < maxHits; i++) {
      var text = items[i].text;
      if (text.length < 2) continue;
      var nm = normMap(text);
      var ok = true, first = -1;
      for (var t = 0; t < tokens.length; t++) {
        var idx = nm.n.indexOf(tokens[t]);
        if (idx < 0) { ok = false; break; }
        if (first < 0 || idx < first) first = idx;
      }
      if (!ok) continue;
      var origStart = nm.map[first] || 0;
      var start = Math.max(0, origStart - 80);
      var end = Math.min(text.length, origStart + 200);
      hits.push({
        text: (start > 0 ? '…' : '') + text.slice(start, end) + (end < text.length ? '…' : ''),
        label: items[i].label
      });
    }
    return hits;
  }

  function runSearch(view, q, resultsEl, statusEl, progressEl, pbar) {
    var my = ++searchRun;
    clear(resultsEl);
    progressEl.classList.add('hidden');
    if (!q || tokensOf(q).length === 0) {
      statusEl.textContent = q ? 'اكتب كلمة أطول للبحث' : '';
      return;
    }
    var tokens = tokensOf(q);
    statusEl.textContent = 'جارٍ البحث…';
    progressEl.classList.remove('hidden');
    pbar.style.width = '0%';

    var sections = state.catalog.sections.filter(function (s) {
      return !view.scope || s.id === view.scope;
    });
    var total = sections.reduce(function (a, s) { return a + s.count; }, 0);
    var done = 0, found = 0;
    var MAX = 120;

    function step(si) {
      if (my !== searchRun) return;
      if (si >= sections.length || found >= MAX) {
        progressEl.classList.add('hidden');
        statusEl.textContent = found
          ? (found >= MAX ? 'أول ' + fmtCount(MAX) + ' نتيجة — جرّب كلمة أدق' : 'النتائج (' + fmtCount(found) + ')')
          : 'لا توجد نتائج مطابقة';
        return;
      }
      var sec = sections[si];
      return getIndex(sec.id).then(function (idx) {
        var docs = [];
        idx.groups.forEach(function (g) { g.docs.forEach(function (d) { docs.push({ g: g, d: d }); }); });
        var i = 0;
        function batch() {
          if (my !== searchRun) return;
          if (i >= docs.length || found >= MAX) return step(si + 1);
          var slice = docs.slice(i, i + 6);
          i += slice.length;
          return Promise.all(slice.map(function (x) {
            return getDoc(sec.id, x.d.f).then(function (doc) {
              return { doc: doc, meta: x };
            }, function () { return null; });
          })).then(function (loaded) {
            loaded.forEach(function (item) {
              if (!item || found >= MAX) return;
              var hits = findHits(item.doc, tokens, 2);
              if (!hits.length) return;
              found++;
              resultsEl.appendChild(resultCard(sec, item.meta.g, item.meta.d, hits, view));
            });
            done += slice.length;
            pbar.style.width = Math.min(100, Math.round(done / total * 100)) + '%';
            statusEl.textContent = 'جارٍ البحث… ' + fmtCount(Math.min(done, total)) + ' / ' + fmtCount(total);
            return new Promise(function (r) { setTimeout(r, 0); }).then(batch);
          });
        }
        return batch();
      });
    }

    step(0).catch(function (e) {
      statusEl.textContent = 'حدث خطأ أثناء البحث';
      progressEl.classList.add('hidden');
    });
  }

  function resultCard(sec, group, meta, hits, view) {
    var card = el('div', 'res');
    var top = el('div', 'top');
    top.appendChild(el('b', null, meta.t));
    top.appendChild(el('span', 'where', sec.title + ' · ' + group.title));
    card.appendChild(top);
    hits.forEach(function (h) {
      var p = el('p');
      p.appendChild(highlight(h.text, view.q));
      if (h.label) p.appendChild(el('small', null, ' — ' + h.label));
      card.appendChild(p);
    });
    card.onclick = function () {
      go({ type: 'doc', sec: sec.id, file: meta.f, title: meta.t });
    };
    return card;
  }

  function highlight(text, q) {
    var frag = document.createDocumentFragment();
    var tokens = tokensOf(q);
    if (!tokens.length) { frag.appendChild(document.createTextNode(text)); return frag; }
    var nm = normMap(text);
    for (var i = 0; i < tokens.length; i++) {
      var idx = nm.n.indexOf(tokens[i]);
      if (idx < 0) continue;
      var s = nm.map[idx];
      var e = nm.map[idx + tokens[i].length - 1];
      if (s === undefined || e === undefined) continue;
      frag.appendChild(document.createTextNode(text.slice(0, s)));
      var mark = el('mark', null, text.slice(s, e + 1));
      frag.appendChild(mark);
      frag.appendChild(document.createTextNode(text.slice(e + 1)));
      return frag;
    }
    frag.appendChild(document.createTextNode(text));
    return frag;
  }

  /* ------------------------------------------------------------------ */
  /* bookmarks / settings                                                */
  /* ------------------------------------------------------------------ */
  function renderBookmarks() {
    var frag = document.createDocumentFragment();
    if (!prefs.bookmarks.length) {
      var e = el('div', 'empty');
      e.appendChild(el('div', null, 'لا توجد محفوظات بعد'));
      e.appendChild(el('small', null, 'اضغط ♥ أثناء القراءة لإضافة الصفحة هنا'));
      frag.appendChild(e);
      return frag;
    }
    prefs.bookmarks.forEach(function (b, i) {
      var item = el('div', 'item');
      var t = el('div', 'txt');
      t.appendChild(el('b', null, b.title));
      t.appendChild(el('small', null, b.secTitle || ''));
      item.appendChild(t);
      var del = el('button', 'del', '×');
      del.onclick = function (ev) {
        ev.stopPropagation();
        prefs.bookmarks.splice(i, 1);
        savePref('bookmarks');
        render();
      };
      item.appendChild(del);
      item.onclick = function () {
        go({ type: 'doc', sec: b.sec, file: b.file, title: b.title });
      };
      frag.appendChild(item);
    });
    return frag;
  }

  function renderSettings() {
    var frag = document.createDocumentFragment();
    var card = el('div', 'group open');
    card.appendChild(el('div', 'note', 'المظهر وحجم القراءة'));

    var row1 = el('div', 'setrow');
    var lbl1 = el('div');
    lbl1.appendChild(el('span', null, 'المظهر'));
    lbl1.appendChild(el('small', null, 'فاتح / ورقي / ليلي'));
    row1.appendChild(lbl1);
    var seg = el('div', 'seg');
    [['light', 'فاتح'], ['sepia', 'ورقي'], ['dark', 'ليلي']].forEach(function (p) {
      var b = el('button', prefs.theme === p[0] ? 'on' : '', p[1]);
      b.onclick = function () { prefs.theme = p[0]; savePref('theme'); applyTheme(); render(); };
      seg.appendChild(b);
    });
    row1.appendChild(seg);
    card.appendChild(row1);

    var row2 = el('div', 'setrow');
    var lbl2 = el('div');
    lbl2.appendChild(el('span', null, 'حجم الخط'));
    lbl2.appendChild(el('small', null, 'للقراءة المريحة'));
    row2.appendChild(lbl2);
    var st = el('div', 'stepper');
    var mi = el('button', null, '−');
    var val = el('span', null, arNum(prefs.font));
    var pl = el('button', null, '+');
    mi.onclick = function () { setFont(prefs.font - 1); val.textContent = arNum(prefs.font); };
    pl.onclick = function () { setFont(prefs.font + 1); val.textContent = arNum(prefs.font); };
    st.appendChild(mi); st.appendChild(val); st.appendChild(pl);
    row2.appendChild(st);
    card.appendChild(row2);

    var row3 = el('div', 'setrow');
    var lbl3 = el('div');
    lbl3.appendChild(el('span', null, 'تباعد الأسطر'));
    lbl3.appendChild(el('small', null, 'مضغوط / عادي / واسع'));
    row3.appendChild(lbl3);
    var seg2 = el('div', 'seg');
    [[1.7, 'مضغوط'], [2.02, 'عادي'], [2.35, 'واسع']].forEach(function (p) {
      var b = el('button', Math.abs(prefs.lh - p[0]) < 0.01 ? 'on' : '', p[1]);
      b.onclick = function () { prefs.lh = p[0]; savePref('lh'); applyTheme(); render(); };
      seg2.appendChild(b);
    });
    row3.appendChild(seg2);
    card.appendChild(row3);
    frag.appendChild(card);

    var info = el('div', 'about');
    info.appendChild(el('div', null, 'كنوز — مكتبة الكنيسة القبطية الأرثوذكسية'));
    info.appendChild(el('div', null, 'عدد المستندات: ' + fmtCount(state.catalog.docs)));
    info.appendChild(el('div', null, 'النسخة: ' + (Native && Native.versionName ? Native.versionName() : '1.0.0')));
    info.appendChild(el('div', null, 'التنقل: زر الرجوع في الهاتف يعيدك للصفحة السابقة.'));
    frag.appendChild(info);
    return frag;
  }

  /* ------------------------------------------------------------------ */
  /* boot                                                                */
  /* ------------------------------------------------------------------ */
  function boot() {
    applyTheme();

    $('#btnBack').onclick = function () { back(); };
    $('#btnSearch').onclick = function () { go({ type: 'search', q: '' }); };
    $('#sheetClose').onclick = closeSheet;
    $('#sheetBackdrop').onclick = closeSheet;
    $('#bottomnav').onclick = function (ev) {
      var b = ev.target.closest('button');
      if (!b) return;
      var kind = b.dataset.nav;
      if (kind === 'home') {
        state.stack = [{ type: 'home' }];
        render();
      } else if (kind === 'search') go({ type: 'search', q: '' });
      else if (kind === 'bookmarks') go({ type: 'bookmarks' });
      else if (kind === 'settings') go({ type: 'settings' });
    };

    window.addEventListener('beforeunload', function () {
      if (state.view && state.view.type === 'doc') state.view.scroll = window.scrollY;
    });

    Files.json('catalog.json').then(function (cat) {
      state.catalog = cat;
      state.stack = [{ type: 'home' }];
      $('#boot').classList.add('hidden');
      $('#app').classList.remove('hidden');
      render();
    }).catch(function (err) {
      $('#bootMsg').textContent = 'تعذّر تحميل المحتوى: ' + (err && err.message || err);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
