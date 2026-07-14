/* Rudeep Ramesh — portfolio renderer.
   Reads content/site.json (edited via /admin Decap CMS) and syncs the whole page,
   including <title>, meta description and the Person JSON-LD schema. */
(function () {
  'use strict';

  var esc = function (s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };
  var $ = function (id) { return document.getElementById(id); };
  var setText = function (id, v) { var el = $(id); if (el && v != null) el.textContent = v; };
  var setHTML = function (id, v) { var el = $(id); if (el && v != null) el.innerHTML = v; };

  function fill(tplId, data) {
    var html = $(tplId).innerHTML;
    Object.keys(data).forEach(function (k) {
      html = html.split('%%' + k + '%%').join(esc(data[k]));
    });
    var box = document.createElement('div');
    box.innerHTML = html;
    return box.firstElementChild;
  }

  /* ---------- interactions (faithful to the original design) ---------- */

  function hoverCard(c, on) {
    c.style.transform = on ? 'translateY(-5px)' : 'translateY(0)';
    var img = c.querySelector('[data-img]');
    if (img) img.style.transform = (on && img.style.opacity !== '0') ? 'scale(1.06)' : 'scale(1)';
    var play = c.querySelector('[data-play]');
    if (play) {
      play.style.opacity = on ? '1' : '0';
      play.style.transform = 'translate(-50%,-50%) scale(' + (on ? '1' : '.82') + ')';
    }
    var ov = c.querySelector('[data-ov]');
    if (ov) ov.style.opacity = on ? '1' : '0';
    var media = c.querySelector('[data-media]');
    if (media) media.style.borderColor = on ? 'var(--ac)' : 'rgba(255,255,255,.08)';
  }
  function hoverRow(r, on) {
    r.style.paddingLeft = on ? '24px' : '6px';
    r.style.background = on ? 'rgba(255,255,255,.03)' : 'transparent';
    var a = r.querySelector('[data-arrow]');
    if (a) a.style.transform = on ? 'translate(6px,-6px)' : 'none';
  }
  function hoverPortrait(p, on) {
    var img = p.querySelector('[data-portrait]');
    if (!img) return;
    img.style.filter = on ? 'grayscale(0) contrast(1.04) brightness(1)'
                          : 'grayscale(.55) contrast(1.04) brightness(.92)';
    img.style.transform = on ? 'scale(1.04)' : 'scale(1)';
  }
  function bindHover(root) {
    root.querySelectorAll('[data-hover]').forEach(function (el) {
      if (el.dataset.hoverBound) return;
      el.dataset.hoverBound = '1';
      var kind = el.dataset.hover;
      var fn = kind === 'card' ? hoverCard : kind === 'row' ? hoverRow : hoverPortrait;
      el.addEventListener('mouseenter', function () { fn(el, true); });
      el.addEventListener('mouseleave', function () { fn(el, false); });
    });
  }

  var io = null;
  function setupReveal() {
    var els = document.querySelectorAll('[data-reveal]');
    if (!('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.style.opacity = '1'; el.style.transform = 'none'; });
      return;
    }
    if (!io) {
      io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.style.opacity = '1';
            en.target.style.transform = 'none';
            io.unobserve(en.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    }
    els.forEach(function (el) {
      if (!el.dataset.revObserved) { el.dataset.revObserved = '1'; io.observe(el); }
    });
  }

  function hydrateThumbs(root) {
    root.querySelectorAll('img[data-src]').forEach(function (img) {
      var url = img.getAttribute('data-src');
      if (!url) return;
      if (img.getAttribute('src') === url) { img.style.opacity = '1'; return; }
      img.onload = function () { img.style.opacity = '1'; };
      img.onerror = function () { img.style.opacity = '0'; };
      img.setAttribute('src', url);
    });
  }

  /* ---------- render from JSON ---------- */

  function renderMarquee(items) {
    function build() {
      var out = '';
      items.forEach(function (it, i) {
        var outline = (i % 2 === 1)
          ? ' color:transparent; -webkit-text-stroke:1px rgba(255,255,255,.5);' : '';
        out += '<span style="padding:0 28px;' + outline + '">' + esc(it) + '</span>' +
               '<span style="color:var(--ac);">\u2726</span>';
      });
      return out;
    }
    setHTML('mqA', build());
    setHTML('mqB', build());
  }

  function renderFilms(films) {
    var grid = $('filmsGrid');
    grid.querySelectorAll(':scope > a').forEach(function (n) { n.remove(); });
    films.forEach(function (f) {
      grid.appendChild(fill('tpl-film', f));
    });
  }

  function renderReels(reels) {
    var grid = $('reelsGrid');
    grid.querySelectorAll(':scope > a').forEach(function (n) { n.remove(); });
    reels.forEach(function (r) {
      var node = fill('tpl-reel', r);
      if (!r.highlight) {
        var hl = node.querySelector('[data-hl]');
        if (hl) hl.remove();
      }
      grid.appendChild(node);
    });
  }

  function renderExperience(items) {
    var list = $('expList');
    list.querySelectorAll(':scope > div').forEach(function (n) { n.remove(); });
    items.forEach(function (e, i) {
      var node = fill('tpl-exp', e);
      if (!e.linkHref || !e.linkLabel) {
        var link = node.querySelector('[data-exp-link]');
        if (link) link.remove();
      }
      if (i === items.length - 1) node.style.borderBottom = '1px solid rgba(255,255,255,.1)';
      list.appendChild(node);
    });
  }

  function renderSkills(sk) {
    var topline = '';
    sk.topline.forEach(function (t, i) {
      if (i > 0) topline += '<span style="color:var(--ac); font-size:1.4rem;">/</span>';
      var outline = (i > 0 && i % 2 === 0)
        ? ' color:transparent; -webkit-text-stroke:1px rgba(255,255,255,.55);' : '';
      topline += '<span style="font-size:clamp(1.7rem,4vw,3rem); font-weight:800; letter-spacing:-.03em;' +
                 outline + '">' + esc(t) + '</span>';
    });
    setHTML('skillsTop', topline);

    var groups = $('skillGroups');
    groups.querySelectorAll(':scope > div').forEach(function (n) { n.remove(); });
    sk.groups.forEach(function (g, i) {
      var node = fill('tpl-skillgroup', { title: g.title });
      node.style.transitionDelay = (i * 0.08) + 's';
      var ul = node.querySelector('ul');
      ul.innerHTML = g.items.map(function (it) { return '<li>' + esc(it) + '</li>'; }).join('');
      groups.appendChild(node);
    });

    setText('aiTitle', sk.aiTitle);
    setHTML('aiTools', sk.aiTools.map(function (t) {
      return '<span style="border:1px solid rgba(255,255,255,.16); border-radius:999px; padding:9px 18px; ' +
             "font-family:'Space Mono',monospace; font-size:12px; letter-spacing:.04em; color:#C2C8CF;\">" +
             esc(t) + '</span>';
    }).join(''));
  }

  function renderContact(c) {
    setHTML('contactHead', esc(c.headingLine1) + '<br>' + esc(c.headingLine2) +
      ' <span style="color:var(--ac);">' + esc(c.headingAccent) + '</span>');
    var box = $('contactLinks');
    box.querySelectorAll(':scope > a').forEach(function (n) { n.remove(); });
    c.links.forEach(function (l, i) {
      var node = fill('tpl-contact', l);
      node.style.transitionDelay = (i * 0.06) + 's';
      if (/^https?:/.test(l.href)) {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener');
      }
      box.appendChild(node);
    });
  }

  function renderSchema(d) {
    var s = d.schema, seo = d.seo;
    document.title = seo.title;
    var md = document.querySelector('meta[name="description"]');
    if (md) md.setAttribute('content', seo.description);
    var ld = {
      '@context': 'https://schema.org',
      '@type': 'Person',
      '@id': (seo.canonical || '') + '/#person',
      name: s.name,
      alternateName: s.alternateName,
      url: seo.canonical,
      image: (seo.canonical || '') + '/' + (seo.ogImage || ''),
      jobTitle: s.jobTitle,
      worksFor: { '@type': 'Organization', name: s.worksFor },
      address: {
        '@type': 'PostalAddress',
        addressLocality: s.locality,
        addressRegion: s.region,
        addressCountry: s.country
      },
      email: 'mailto:' + s.email,
      description: s.description,
      knowsAbout: s.knowsAbout,
      sameAs: (s.sameAs || []).filter(function (u) { return u && u.indexOf('REPLACE_WITH') === -1; })
    };
    var el = $('person-jsonld');
    if (el) el.textContent = JSON.stringify(ld, null, 2);
  }

  function apply(d) {
    // theme
    var root = $('top');
    root.style.setProperty('--ac', d.theme.accent || '#D43A56');
    var grain = $('grain');
    if (grain) grain.style.display = d.theme.filmGrain ? '' : 'none';

    // nav + hero
    setText('navName', d.nav.name);
    setText('navSub', d.nav.suffix);
    setHTML('heroRole', String(d.hero.role || '').replace(/&/g, '&amp;').replace(/</g, '&lt;'));
    setText('heroFirst', d.hero.firstName);
    setText('heroLast', d.hero.lastName);
    setText('heroTagline', d.hero.tagline);

    renderMarquee(d.marquee);

    // featured
    var f = d.featured;
    $('featLink').setAttribute('href', f.href);
    setText('featFrame', f.frame);
    var fi = $('featImg');
    fi.setAttribute('data-src', f.thumb);
    setText('featBadgeL', f.badgeLeft);
    setText('featBadgeR', f.badgeRight);
    setText('featName', f.title);
    setText('featSub', ' ' + f.subtitle);
    setText('featByline', f.byline);

    renderFilms(d.films);
    renderReels(d.reels);

    // about
    var a = d.about;
    $('aboutPortrait').setAttribute('src', a.portrait);
    setText('aboutCapName', a.captionName);
    setText('aboutCapLoc', a.captionLocation);
    setHTML('aboutBio', a.bio); // intentionally HTML (accent spans)
    setText('factBasedIn', a.basedIn);
    setText('factLanguages', a.languages);
    setText('factAlso', a.also);
    if (a.stats[0]) { setText('s1v', a.stats[0].value); setText('s1l', a.stats[0].label); }
    if (a.stats[1]) { setText('s2v', a.stats[1].value); setText('s2l', a.stats[1].label); }

    renderExperience(d.experience);
    renderSkills(d.skills);
    renderContact(d.contact);

    setText('footCopy', d.footer.copyright);
    setText('footLoc', d.footer.location);

    renderSchema(d);

    // re-bind behaviour on the fresh DOM
    bindHover(document);
    setupReveal();
    hydrateThumbs(document);
  }

  /* ---------- boot ---------- */

  document.addEventListener('DOMContentLoaded', function () {
    // parallax
    var hero = $('heroPar');
    window.addEventListener('scroll', function () {
      var y = window.scrollY || 0;
      if (hero) hero.style.transform = 'translateY(' + (y * 0.22) + 'px)';
    }, { passive: true });

    // static fallback behaviour first (works even if fetch fails)
    bindHover(document);
    setupReveal();
    hydrateThumbs(document);

    fetch('content/site.json?v=' + Date.now())
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(apply)
      .catch(function (err) { console.warn('site.json not loaded, using static content', err); });
  });
})();
