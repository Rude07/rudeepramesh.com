/* site.js — behaviour only.

   All page CONTENT is prerendered into index.html by build.py from
   content/site.json. This file never writes copy, never fetches site.json
   and never re-renders a section: it only does things that need a live
   browser — scroll spy, reveal-on-scroll, parallax, hover states, lazy
   thumbnails, the cursor-proximity hero, and measuring the brands marquee.

   If you need to change a word, change content/site.json (or /admin).
   If you need to change markup, change the <template> blocks in index.html. */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };


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









  /* ---------- brands marquee ----------
     The tiles themselves are written into the tracks by build.py from
     content/site.json. This only repeats one set until it is wider than the
     viewport and sets the loop duration — it is measurement, not content. */
  var brandSets = null;
  function setupBrands() {
    var trackA = $('brandsTrackA'), trackB = $('brandsTrackB');
    if (!trackA || !trackB) return;
    if (!brandSets) brandSets = { a: trackA.innerHTML, b: trackB.innerHTML };
    if (!brandSets.a.trim()) {
      var s = $('brands');
      if (s) s.style.display = 'none';
      return;
    }
    function fillTrack(track, oneSet, durVar, baseSpeedPxPerSec) {
      track.innerHTML = oneSet;                 // measure one set
      var vw = window.innerWidth || 1200;
      var guard = 0;
      while (track.scrollWidth < vw * 1.2 && guard < 12) {
        track.innerHTML += oneSet; guard++;
      }
      var oneWidth = track.scrollWidth;
      track.innerHTML = track.innerHTML + track.innerHTML;  // duplicate for -50% loop
      var dur = Math.max(18, Math.round(oneWidth / baseSpeedPxPerSec));
      track.style.setProperty(durVar, dur + 's');
    }
    function fillBoth() {
      fillTrack(trackA, brandSets.a, '--durA', 70);
      fillTrack(trackB, brandSets.b, '--durB', 48);
    }
    fillBoth();
    // Logo images affect widths as they load; re-measure once they're all done.
    var imgs = [].slice.call(document.querySelectorAll('#brands img'));
    var pending = imgs.filter(function (im) { return !im.complete; }).length;
    if (pending) {
      var done = 0;
      function check() { if (++done >= pending) fillBoth(); }
      imgs.forEach(function (im) {
        if (im.complete) return;
        im.addEventListener('load', check); im.addEventListener('error', check);
      });
    }
  }

  var spyLinks = [], spySections = [];
  function setupScrollSpy() {
    var nav = document.querySelector('header nav');
    if (!nav) return;
    spyLinks = []; spySections = [];
    [].slice.call(nav.querySelectorAll('a')).forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var id = a.getAttribute('data-spy') || (href.charAt(0) === '#' ? href.slice(1) : null);
      if (!id) return;
      var sec = document.getElementById(id) || (id === 'top' ? document.body : null);
      if (!sec) return;
      spyLinks.push(a); spySections.push(sec);
    });
    onScrollSpy();
  }
  function onScrollSpy() {
    if (!spyLinks.length) return;
    var pos = window.scrollY + (window.innerHeight * 0.32);
    var activeIdx = -1;
    for (var i = 0; i < spySections.length; i++) {
      var sec = spySections[i];
      if (sec && sec.offsetTop <= pos) activeIdx = i;
    }
    // near bottom => last link (contact)
    if ((window.innerHeight + window.scrollY) >= document.body.scrollHeight - 4)
      activeIdx = spyLinks.length - 1;
    spyLinks.forEach(function (a, i) { a.classList.toggle('is-active', i === activeIdx); });
  }

  /* ---------- hero name: cursor-proximity variable font weight ----------
     Letters individually morph their `wght` axis based on distance to the
     cursor. Ported from a React/Framer component to vanilla JS, with cached
     letter positions (measured on scroll/resize/font-load rather than every
     frame) and an idle-stopping rAF loop. Requires the variable Archivo
     requested in index.html (wght@100..900). */
  var HP = {
    from: 900,   // resting weight (matches the current bold hero)
    to: 300,     // weight at the cursor
    reach: 280,  // px radius of influence
    tau: 0.28    // ramp smoothing (seconds); higher = softer
  };
  var hpLetters = [], hpRunning = false, hpLastT = 0, hpBound = false, hpQueued = false;
  var hpMouse = { x: -99999, y: -99999 };

  function hpEnabled() {
    if (!window.matchMedia || !('fontVariationSettings' in document.documentElement.style)) return false;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
    // pointer-driven effect: desktop only, skip touch devices
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  }

  function initHeroProximity() {
    if (!hpEnabled()) return;
    hpLetters = [];
    ['heroFirst', 'heroLast'].forEach(function (id) {
      var el = $(id);
      if (!el) return;
      var text = (el.textContent || '').trim();
      if (!text) return;
      el.textContent = '';
      // keep the full word available to screen readers
      var sr = document.createElement('span');
      sr.textContent = text;
      sr.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;' +
                         'clip:rect(0,0,0,0);white-space:nowrap;';
      el.appendChild(sr);
      for (var i = 0; i < text.length; i++) {
        var s = document.createElement('span');
        s.setAttribute('aria-hidden', 'true');
        s.textContent = text.charAt(i);
        s.style.display = 'inline-block';
        s.style.fontVariationSettings = "'wght' " + HP.from;
        el.appendChild(s);
        hpLetters.push({ el: s, f: 0, cx: 0, cy: 0 });
      }
    });
    if (!hpLetters.length) return;
    hpMeasure();
    if (!hpBound) {
      hpBound = true;
      window.addEventListener('mousemove', function (e) {
        hpMouse.x = e.clientX; hpMouse.y = e.clientY; hpStart();
      }, { passive: true });
      window.addEventListener('scroll', hpQueueMeasure, { passive: true });
      window.addEventListener('resize', hpQueueMeasure);
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(hpMeasure).catch(function () {});
      }
    }
  }

  function hpQueueMeasure() {
    if (hpQueued) return;
    hpQueued = true;
    requestAnimationFrame(function () { hpQueued = false; hpMeasure(); });
  }

  function hpMeasure() {
    for (var i = 0; i < hpLetters.length; i++) {
      var r = hpLetters[i].el.getBoundingClientRect();
      hpLetters[i].cx = r.left + r.width / 2;
      hpLetters[i].cy = r.top + r.height / 2;
    }
  }

  function hpStart() {
    if (hpRunning) return;
    hpRunning = true; hpLastT = 0;
    requestAnimationFrame(hpTick);
  }

  function hpTick(now) {
    var dt = hpLastT ? Math.min(0.1, (now - hpLastT) / 1000) : 0.016;
    hpLastT = now;
    var a = 1 - Math.exp(-dt / HP.tau);
    var active = false;
    for (var i = 0; i < hpLetters.length; i++) {
      var L = hpLetters[i];
      var dx = hpMouse.x - L.cx, dy = hpMouse.y - L.cy;
      var target = 1 - Math.sqrt(dx * dx + dy * dy) / HP.reach;
      if (target < 0) target = 0; else if (target > 1) target = 1;
      L.f += (target - L.f) * a;
      if (L.f < 0.002) {
        if (L.f !== 0) { L.f = 0; L.el.style.fontVariationSettings = "'wght' " + HP.from; }
      } else {
        active = true;
        L.el.style.fontVariationSettings =
          "'wght' " + Math.round(HP.from + (HP.to - HP.from) * L.f);
      }
      if (target > 0.002) active = true;
    }
    if (active) requestAnimationFrame(hpTick); else hpRunning = false;
  }


  /* ---------- boot ---------- */

  document.addEventListener('DOMContentLoaded', function () {
    // parallax
    var hero = $('heroPar');
    window.addEventListener('scroll', function () {
      var y = window.scrollY || 0;
      if (hero) hero.style.transform = 'translateY(' + (y * 0.22) + 'px)';
      onScrollSpy();
    }, { passive: true });

    setupScrollSpy();
    initHeroProximity();

    // back-to-top button (in the footer)
    var btt = $('backToTop');
    if (btt) {
      btt.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    // keep the brands loop seamless if the window is resized
    var lastW = window.innerWidth, rt;
    window.addEventListener('resize', function () {
      if (Math.abs(window.innerWidth - lastW) < 80) return;  // ignore mobile URL-bar jitter
      lastW = window.innerWidth;
      clearTimeout(rt);
      rt = setTimeout(setupBrands, 200);
    });

    // Smooth-scroll anchor links WITHOUT putting #section in the URL
    document.addEventListener('click', function (e) {
      var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
      if (!a) return;
      var id = a.getAttribute('href').slice(1);
      var target = id === 'top' ? document.body : document.getElementById(id);
      if (!target) return;
      e.preventDefault();
      window.scrollTo({ top: id === 'top' ? 0 : target.offsetTop - 70, behavior: 'smooth' });
      if (window.history && history.replaceState) history.replaceState(null, '', window.location.pathname);
    });

    setupBrands();
    bindHover(document);
    setupReveal();
    hydrateThumbs(document);
  });
})();
