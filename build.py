#!/usr/bin/env python3
"""
build.py — generates project (case-study) pages from content/projects/*.json.

Runs with only the Python standard library, so it works on Netlify with no
install step. Outputs:
  - work/<slug>/index.html   (one real page per project, full SEO + schema)
  - work/index.html          (index listing all projects)
  - sitemap.xml              (homepage + every project page)

Safe to run repeatedly. Does NOT touch index.html, admin/, assets/, js/.
"""
import os, re, json, glob, html, math, datetime, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.join(ROOT, "content", "projects")
WORK_DIR = os.path.join(ROOT, "work")

# ---- site-level info (name, domain) from content/site.json ----
site = json.load(open(os.path.join(ROOT, "content", "site.json"), encoding="utf-8"))
DOMAIN = site["seo"]["canonical"].rstrip("/")
PERSON = site["schema"]["name"]
ACCENT = site.get("theme", {}).get("accent") or "#242de8"


def accent_ink(accent, surface="#121519", target=5.2):
    """Text-safe tint of the accent: same OKLCH hue, lightness raised in 0.01
    steps until it reaches `target` contrast on `surface` (the lightest dark
    surface accent text sits on). The raw accent stays for fills and buttons;
    this one is for small text, which needs 4.5:1. Target 5.2 leaves headroom
    for the 11-12px mono labels. #242de8 -> #5b81fe."""
    def lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    def unlin(c): return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    def rgb(h):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    def lum(c):
        r, g, b = [lin(x) for x in c]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    def contrast(a, b):
        a, b = lum(a), lum(b)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)
    def oklch(c):
        r, g, b = [lin(x) for x in c]
        l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
        m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
        s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
        L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
        A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
        B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
        return L, math.hypot(A, B), math.atan2(B, A)
    def srgb(L, C, h):
        while True:  # shed chroma until the colour is inside sRGB
            A, B = C * math.cos(h), C * math.sin(h)
            l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
            m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
            s = (L - 0.0894841775 * A - 1.2914855480 * B) ** 3
            c = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                 -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                 -0.0041960771 * l - 0.7034186147 * m + 1.7076147010 * s]
            if all(-1e-6 <= x <= 1 + 1e-6 for x in c) or C <= 0:
                return [min(1, max(0, unlin(min(1, max(0, x))))) for x in c]
            C -= 0.002
    base, bg = rgb(accent), rgb(surface)
    if contrast(base, bg) >= target:
        return accent
    L, C, h = oklch(base)
    while L < 1:
        L = round(L + 0.01, 2)
        c = srgb(L, C, h)
        if contrast(c, bg) >= target:
            return "#" + "".join("%02x" % round(x * 255) for x in c)
    return "#ffffff"


ACCENT_INK = accent_ink(ACCENT)


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def rooted(path):
    """Make an asset path root-relative so it works from /work/<slug>/."""
    if not path:
        return ""
    if path.startswith("http") or path.startswith("/"):
        return path
    return "/" + path.lstrip("./")


YT_ID = re.compile(r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#]*&)?v=|embed/|shorts/|live/))([\w-]{11})")


def youtube_id(url):
    """The 11-char video id from any YouTube URL form, or None."""
    m = YT_ID.search(str(url or ""))
    return m.group(1) if m else None


def _iso_upload_date(v):
    """CMS date -> ISO 8601 with a timezone (IST when only a date is given)."""
    v = str(v or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return v + "T00:00:00+05:30"
    return v or None


def _iso_duration(v):
    """'7:55', '1:02:03' or seconds -> ISO 8601 duration (PT7M55S)."""
    parts = [x for x in str(v or "").strip().split(":") if x.strip()]
    if not parts or not all(x.strip().isdigit() for x in parts) or len(parts) > 3:
        return None
    secs = 0
    for x in parts:
        secs = secs * 60 + int(x)
    h, rem = divmod(secs, 3600)
    m, sec = divmod(rem, 60)
    return "PT" + ("%dH" % h if h else "") + ("%dM" % m if m else "") + ("%dS" % sec if sec or not (h or m) else "")


def paragraphs(text):
    """Split plain text into <p> blocks on blank lines; single newlines -> <br>."""
    if not text:
        return ""
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        out.append("<p>" + esc(b).replace("\n", "<br>") + "</p>")
    return "\n".join(out)


# Self-hosted (assets/fonts, SIL OFL), same files as the homepage
FONTS = ('<link rel="preload" href="/assets/fonts/archivo-100-900-latin.woff2" as="font" type="font/woff2" crossorigin>'
         '<link rel="stylesheet" href="/assets/fonts/fonts.css">')

# Case-study pages share the homepage's header, buttons, play disc, footer and
# atmosphere so the whole site reads as one. The header/menu behaviour comes
# from the same js/site.js. Keep these rules in step with index.html.
GRAIN_BG = 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'140\' height=\'140\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'2\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\'/%3E%3C/svg%3E")'
EASE = "cubic-bezier(.16,1,.3,1)"
FILMGRAIN = '@keyframes filmgrain{0%{transform:translate(0,0);}10%{transform:translate(-2%,-3%);}20%{transform:translate(-4%,2%);}30%{transform:translate(2%,-4%);}40%{transform:translate(-1%,3%);}50%{transform:translate(-3%,1%);}60%{transform:translate(3%,2%);}70%{transform:translate(-2%,-1%);}80%{transform:translate(1%,-3%);}90%{transform:translate(-3%,2%);}100%{transform:translate(0,0);}}'

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-padding-top:88px}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
:root{--ac:__ACCENT__;--ac-ink:__ACCENT_INK__}
body{background:#0B0C0E;color:#F4F6F8;font-family:'Archivo',system-ui,sans-serif;line-height:1.6}
::selection{background:var(--ac);color:#fff}
a{color:inherit;text-decoration:none}
.wrap{max-width:1040px;margin:0 auto;padding:0 clamp(20px,6vw,80px)}
main.wrap{padding-top:clamp(104px,15vh,150px)}

/* atmosphere: grain animates on desktop pointers only, static on touch */
#grain{position:fixed;inset:-20%;z-index:60;pointer-events:none;opacity:.06;background-image:__GRAIN_CSS__}
__FILMGRAIN__
@media (hover:hover) and (pointer:fine) and (prefers-reduced-motion:no-preference){#grain{animation:filmgrain .7s steps(2) infinite}}
.vignette{position:fixed;inset:0;z-index:55;pointer-events:none;
 background:radial-gradient(ellipse 120% 100% at 50% 50%,transparent 55%,rgba(0,0,0,.6) 100%)}

/* header + primary nav (same as the homepage) */
.site-header{position:fixed;top:0;left:0;right:0;z-index:50;display:flex;justify-content:space-between;
 align-items:center;gap:16px;padding:18px clamp(20px,5vw,64px);
 backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
 background:linear-gradient(180deg,rgba(11,12,14,.82),rgba(11,12,14,0));border-bottom:1px solid rgba(255,255,255,.05)}
.site-name{font-weight:800;letter-spacing:-.01em;font-size:15px;white-space:nowrap}
.site-nav{display:flex;gap:clamp(16px,2.5vw,40px);font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.18em}
.site-nav a{color:#9AA1AA;transition:color .2s __EASE__}
.site-nav a:hover{color:#F4F6F8}
.site-nav a.is-active{color:var(--ac-ink)}
.nav-toggle{display:none}
.site-nav a:focus-visible,.nav-toggle:focus-visible,.site-name:focus-visible{outline:2px solid var(--ac-ink);outline-offset:4px}
@media (hover:none){
  .site-header{backdrop-filter:none;-webkit-backdrop-filter:none;
    background:linear-gradient(180deg,rgba(11,12,14,.94),rgba(11,12,14,.72))}
}
@keyframes navIn{from{opacity:0;transform:translateY(-8px)}}
@media (max-width:900px){
  .site-header{padding:12px 20px}
  .js .nav-toggle{display:inline-flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;
    padding:0 18px;background:transparent;border:1px solid rgba(255,255,255,.22);border-radius:999px;
    color:#F4F6F8;font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.16em;text-transform:uppercase;cursor:pointer;
    transition:transform .12s __EASE__}
  .js .nav-toggle:active{transform:scale(.97)}
  .js .site-nav{display:flex;flex-direction:column;gap:0;position:absolute;top:100%;left:0;right:0;
    padding:4px 20px 16px;background:#0B0C0E;border-bottom:1px solid rgba(255,255,255,.08);font-size:13px;
    visibility:hidden;opacity:0;transform:translateY(-4px);pointer-events:none;
    transition:opacity .12s __EASE__,transform .12s __EASE__,visibility 0s linear .12s}
  .js .site-header.nav-open .site-nav{visibility:visible;opacity:1;transform:none;pointer-events:auto;
    animation:navIn .18s __EASE__;transition:opacity .18s __EASE__,transform .18s __EASE__,visibility 0s}
  .js .site-header::before{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;background:#0B0C0E;
    opacity:0;transition:opacity .12s __EASE__}
  .js .site-header.nav-open::before{opacity:1;transition-duration:.18s}
  .js .site-nav a{display:flex;align-items:center;min-height:48px;border-top:1px solid rgba(255,255,255,.06)}
  html:not(.js) .site-header{flex-wrap:wrap}
  html:not(.js) .site-nav{flex-wrap:wrap;gap:0 18px}
  html:not(.js) .site-nav a{display:inline-flex;align-items:center;min-height:44px}
}

/* buttons (same system as the homepage) */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:52px;padding:0 26px;
 border-radius:999px;border:1px solid transparent;cursor:pointer;white-space:nowrap;
 font:600 15px/1 'Archivo',system-ui,sans-serif;letter-spacing:.01em;
 transition:background-color .2s __EASE__,border-color .2s __EASE__,color .2s __EASE__,transform .12s __EASE__}
.btn svg{width:18px;height:18px;flex:none;fill:currentColor;transition:transform .2s __EASE__}
.btn:active{transform:scale(.97)}
.btn:focus-visible{outline:2px solid var(--ac-ink);outline-offset:4px}
.btn-primary{background:var(--ac);color:#fff}
.btn-secondary{background:transparent;border-color:rgba(255,255,255,.22);color:#F4F6F8}
@media (hover:hover) and (pointer:fine){
  .btn-primary:hover{background:color-mix(in oklab,var(--ac) 86%,#fff)}
  .btn-secondary:hover{border-color:#F4F6F8;background:rgba(255,255,255,.06)}
  .btn:hover svg{transform:translateX(3px)}
  .btn:hover svg.ext{transform:translate(2px,-2px)}
}

/* case study */
.crumbs{font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.12em;color:#8A9099;text-transform:uppercase}
.crumbs a{transition:color .2s __EASE__;display:inline-block;padding:14px 4px;margin:-14px -4px}
.crumbs a:hover{color:var(--ac-ink)}
h1{font-size:clamp(2.4rem,7vw,5rem);font-weight:900;letter-spacing:-.04em;line-height:.95;
 text-transform:uppercase;margin:16px 0 22px}
.meta{display:flex;flex-wrap:wrap;gap:16px 40px;margin-bottom:clamp(30px,5vh,48px)}
.meta div{display:flex;flex-direction:column;gap:3px}
.meta dt{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ac-ink)}
.meta dd{font-size:1rem;color:#E6E9ED}
.hero-media{position:relative;aspect-ratio:16/9;overflow:hidden;border:1px solid rgba(255,255,255,.08);
 background:#0E1013;margin-bottom:24px}
.hero-media img{width:100%;height:100%;object-fit:cover;display:block}
.hero-media iframe{position:absolute;inset:0;width:100%;height:100%;border:0;display:block}
.play-disc{position:absolute;left:50%;top:50%;width:74px;height:74px;margin:-37px 0 0 -37px;border-radius:50%;
 background:var(--ac);display:flex;align-items:center;justify-content:center;
 transition:background-color .2s __EASE__,transform .12s __EASE__}
.play-disc span{width:0;height:0;border-left:17px solid #fff;border-top:11px solid transparent;
 border-bottom:11px solid transparent;margin-left:5px}
.play-disc:active{transform:scale(.97)}
.play-disc:focus-visible{outline:2px solid #fff;outline-offset:4px}
@media (hover:hover) and (pointer:fine){.play-disc:hover{background:color-mix(in oklab,var(--ac) 86%,#fff)}}
@media (max-width:560px){.play-disc{width:58px;height:58px;margin:-29px 0 0 -29px}}
.actions{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:clamp(40px,6vh,64px)}
.lede{font-size:clamp(1.25rem,2.4vw,1.9rem);font-weight:600;letter-spacing:-.02em;line-height:1.4;
 color:#F4F6F8;max-width:60ch;margin-bottom:clamp(40px,6vh,64px)}
section.block{margin-bottom:clamp(36px,5vh,56px)}
.block h2{font-size:clamp(1.4rem,2.6vw,2rem);font-weight:800;letter-spacing:-.025em;line-height:1.1;
 color:#F4F6F8;margin-bottom:14px}
.block p{color:#C2C8CF;font-size:clamp(1rem,1.4vw,1.15rem);line-height:1.65;margin-bottom:12px;max-width:68ch}
.tools{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
.tools span{border:1px solid rgba(255,255,255,.16);border-radius:999px;padding:8px 16px;
 font-family:'Space Mono',monospace;font-size:12px;color:#C2C8CF}
.backrow{border-top:1px solid rgba(255,255,255,.1);margin-top:clamp(40px,7vh,72px);
 padding:clamp(30px,5vh,52px) 0 clamp(56px,9vh,96px);display:flex;justify-content:space-between;align-items:center;
 flex-wrap:wrap;gap:16px}
.back-link{display:inline-flex;align-items:center;min-height:44px;font-family:'Space Mono',monospace;font-size:12px;
 letter-spacing:.12em;text-transform:uppercase;color:#9AA1AA;transition:color .2s __EASE__}
.back-link:hover{color:var(--ac-ink)}
.back-link:focus-visible{outline:2px solid var(--ac-ink);outline-offset:4px}

/* footer (same as the homepage) */
.site-footer{padding:clamp(40px,6vh,64px) clamp(20px,6vw,96px);border-top:1px solid rgba(255,255,255,.07)}
.site-footer .row{max-width:1340px;margin:0 auto;display:flex;flex-wrap:wrap;justify-content:space-between;
 align-items:center;gap:18px;font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.14em;
 color:#8A9099;text-transform:uppercase}
.site-footer .loc{color:#8A9099}
.btt{flex:none;width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;
 background:transparent;border:1px solid rgba(255,255,255,.22);color:#F4F6F8;cursor:pointer;
 transition:border-color .2s __EASE__,background-color .2s __EASE__,transform .12s __EASE__}
.btt svg{width:16px;height:16px}
.btt svg{fill:currentColor}
.back-link svg{width:14px;height:14px;fill:currentColor;margin-right:8px}
.btt:active{transform:scale(.97)}
.btt:focus-visible{outline:2px solid var(--ac-ink);outline-offset:4px}
@media (hover:hover) and (pointer:fine){.btt:hover{border-color:#F4F6F8;background:rgba(255,255,255,.06)}}

/* case-study index */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:clamp(28px,4vw,48px);
 padding:clamp(34px,5vh,56px) 0 clamp(64px,10vh,112px)}
.card{display:block;transition:translate .25s __EASE__}
.card .m{position:relative;aspect-ratio:16/9;overflow:hidden;border:1px solid rgba(255,255,255,.08);background:#0E1013;
 transition:border-color .25s __EASE__,transform .18s __EASE__}
.card img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .55s __EASE__}
.card h2{font-size:1.35rem;font-weight:800;letter-spacing:-.02em;line-height:1.2;margin:16px 0 4px}
.card p{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.1em;color:#8A9099;text-transform:uppercase}
.card:focus-visible{outline:2px solid var(--ac-ink);outline-offset:6px}
@media (hover:hover) and (pointer:fine){
  .card:hover{translate:0 -5px}
  .card:hover .m{border-color:var(--ac)}
  .card:hover img{transform:scale(1.05)}
}
@media (hover:none){.card:active .m{transform:scale(.98)}}

/* reduced motion: no loops, no movement; colour changes stay */
@media (prefers-reduced-motion:reduce){
  #grain{animation:none!important}
  .js .site-nav,.js .site-header.nav-open .site-nav{transform:none;animation:none}
  .btn,.btn svg,.btt,.play-disc,.card,.card .m,.card img,.js .nav-toggle{transition-property:color,background-color,border-color,opacity}
  .btn:active,.btt:active,.play-disc:active,.js .nav-toggle:active,.btn:hover svg,.card:active .m,.card:hover img{transform:none!important}
  .card:hover{translate:none!important}
}
""".replace("__ACCENT_INK__", ACCENT_INK).replace("__ACCENT__", ACCENT).replace("__EASE__", EASE) \
   .replace("__GRAIN_CSS__", GRAIN_BG).replace("__FILMGRAIN__", FILMGRAIN)

# Phosphor Icons (bold weight, MIT), the same glyphs index.html uses
ARROW_RIGHT = ('<svg viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
               '<path d="M224.49,136.49l-72,72a12,12,0,0,1-17-17L187,140H40a12,12,0,0,1,0-24H187L135.51,64.48a12,12,0,0,1,17-17l72,72A12,12,0,0,1,224.49,136.49Z"/></svg>')
ARROW_EXT = ('<svg class="ext" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
             '<path d="M204,64V168a12,12,0,0,1-24,0V93L72.49,200.49a12,12,0,0,1-17-17L163,76H88a12,12,0,0,1,0-24H192A12,12,0,0,1,204,64Z"/></svg>')
ARROW_LEFT = ('<svg viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
              '<path d="M228,128a12,12,0,0,1-12,12H69l51.52,51.51a12,12,0,0,1-17,17l-72-72a12,12,0,0,1,0-17l72-72a12,12,0,0,1,17,17L69,116H216A12,12,0,0,1,228,128Z"/></svg>')
ARROW_UP = ('<svg viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<path d="M208.49,120.49a12,12,0,0,1-17,0L140,69V216a12,12,0,0,1-24,0V69L64.49,120.49a12,12,0,0,1-17-17l72-72a12,12,0,0,1,17,0l72,72A12,12,0,0,1,208.49,120.49Z"/></svg>')

# site.js reads the .js class (set before paint) and drives the menu + back-to-top
PAGE_SCRIPTS = ('<script>document.documentElement.classList.add(\'js\')</script>\n'
                '<script src="/js/site.js" defer></script>')


def header_html(active="studies"):
    nav = [("/#work", "WORK", None), ("/work/", "CASE STUDIES", "studies"),
           ("/#about", "ABOUT", None), ("/#experience", "EXPERIENCE", None), ("/#contact", "CONTACT", None)]
    links = "".join(
        '<a href="%s"%s>%s</a>' % (href, ' class="is-active" aria-current="page"' if key == active else "", label)
        for href, label, key in nav)
    return ('<div id="grain" aria-hidden="true"%s></div><div class="vignette" aria-hidden="true"></div>\n'
            '<header id="siteHeader" class="site-header">'
            '<a href="/" class="site-name">%s</a>'
            '<button id="navToggle" class="nav-toggle" type="button" aria-expanded="false" aria-controls="siteNav">Menu</button>'
            '<nav id="siteNav" class="site-nav" aria-label="Primary">%s</nav></header>'
            % ('' if site.get("theme", {}).get("filmGrain", True) else ' style="display:none"',
               esc(site.get("nav", {}).get("name") or PERSON.upper()), links))


def footer_html():
    f = site.get("footer", {})
    return (('<footer class="site-footer"><div class="row">'
             '<span>%s</span><span class="loc">%s</span>'
             '<button class="btt" id="backToTop" type="button" aria-label="Back to top">')
            + ARROW_UP + '</button></div></footer>') % (
               esc(f.get("copyright") or "© %d %s" % (datetime.date.today().year, PERSON)),
               esc(f.get("location", "")))


def project_page(slug, p):
    url = "%s/work/%s/" % (DOMAIN, slug)
    thumb = rooted(p.get("thumb", ""))
    thumb_abs = DOMAIN + thumb if thumb.startswith("/") else thumb
    title = p["title"]
    desc = p.get("summary") or (p.get("overview", "")[:150])
    page_title = "%s \u2014 %s | %s" % (title, p.get("category", "Project"), PERSON)

    blocks = ""
    for label, key in [("Overview", "overview"), ("The Challenge", "challenge"),
                       ("Approach", "approach"), ("Outcome", "results")]:
        if p.get(key):
            blocks += '<section class="block"><h2>%s</h2>%s</section>\n' % (label, paragraphs(p[key]))

    tools = ""
    tool_list = [t for t in (p.get("tools") or []) if str(t).strip()]  # skip blank CMS entries
    if tool_list:
        tools = ('<section class="block"><h2>Tools</h2><div class="tools">' +
                 "".join("<span>%s</span>" % esc(t) for t in tool_list) + "</div></section>")

    meta_bits = []
    for label, key in [("Client", "client"), ("Role", "role"), ("Year", "year"), ("Type", "category")]:
        if p.get(key):
            meta_bits.append('<div><dt>%s</dt><dd>%s</dd></div>' % (label, esc(p[key])))
    meta = "".join(meta_bits)

    # JSON-LD: CreativeWork + VideoObject + BreadcrumbList
    vid = youtube_id(p.get("videoUrl"))
    # VideoObject only for a film actually playable on this page (embedded
    # YouTube), with real dates: a guessed uploadDate is worse than none.
    video = None
    if vid:
        upload = _iso_upload_date(p.get("videoUploadDate"))
        if not upload:
            print('  ! %s: no "Video upload date" set, so Google may skip the video' % slug)
        video = {
            "@type": "VideoObject",
            "@id": url + "#video",
            "name": title,
            "description": desc,
            "thumbnailUrl": thumb_abs,
            "uploadDate": upload,
            "duration": _iso_duration(p.get("videoDuration")),
            "embedUrl": "https://www.youtube.com/embed/%s" % vid,
            "creator": {"@id": DOMAIN + "/#person"},
            "mainEntityOfPage": url,
        }
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CreativeWork",
                "@id": url + "#work",
                "name": title,
                "url": url,
                "description": desc,
                "genre": p.get("category"),
                "image": thumb_abs,
                "creator": {"@type": "Person", "@id": DOMAIN + "/#person", "name": PERSON},
                "author": {"@type": "Person", "@id": DOMAIN + "/#person", "name": PERSON},
                "dateCreated": p.get("year"),
                "video": {"@id": url + "#video"} if video else None,
            },
            video,
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": DOMAIN + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Work", "item": DOMAIN + "/work/"},
                    {"@type": "ListItem", "position": 3, "name": title, "item": url},
                ],
            },
        ],
    }
    # strip null values
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if v is not None}
        if isinstance(o, list):
            return [clean(x) for x in o if x is not None]
        return o
    ld = clean(ld)

    if vid:
        # play the film on the page itself; the thumbnail stays as og:image
        media = ('<iframe src="https://www.youtube.com/embed/%s?rel=0" title="%s, %s by %s" '
                 'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
                 'referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>'
                 % (vid, esc(title), esc(p.get("category", "")), esc(PERSON)))
    else:
        media = ('<img src="%s" alt="%s, %s by %s" width="1280" height="720" fetchpriority="high" decoding="async">\n'
                 '    <a class="play-disc" href="%s" target="_blank" rel="noopener" aria-label="Play %s"><span></span></a>'
                 % (esc(thumb), esc(title), esc(p.get("category", "")), esc(PERSON),
                    esc(p.get("videoUrl", "#")), esc(title)))

    watch = ('<a class="btn btn-primary" href="%s" target="_blank" rel="noopener">%s%s</a>'
             % (esc(p.get("videoUrl", "#")), "Watch on YouTube" if vid else "Watch the film", ARROW_EXT))

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(page_title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(url)s">
<meta property="og:type" content="article">
<meta property="og:title" content="%(og_title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(url)s">
<meta property="og:image" content="%(thumb_abs)s">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
%(ld)s
</script>
%(fonts)s
<style>%(css)s</style>
%(scripts)s
</head>
<body>
%(header)s
<main class="wrap">
  <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a> / <a href="/work/">Case studies</a> / %(title)s</nav>
  <h1>%(title)s</h1>
  <dl class="meta">%(meta)s</dl>
  <div class="hero-media">
    %(media)s
  </div>
  <div class="actions">%(watch)s</div>
  <p class="lede">%(summary)s</p>
  %(blocks)s
  %(tools)s
  <div class="backrow"><a class="back-link" href="/work/">%(arrow_left)sAll case studies</a><a class="btn btn-secondary" href="/#contact">Get in touch%(arrow)s</a></div>
</main>
%(footer)s
</body>
</html>
""" % {
        "page_title": esc(page_title), "desc": esc(desc), "url": esc(url),
        "og_title": esc(title + " \u2014 " + PERSON), "thumb_abs": esc(thumb_abs),
        "ld": _ld_json(ld), "fonts": FONTS, "css": CSS,
        "header": header_html(), "title": esc(title), "meta": meta,
        "media": media, "watch": watch,
        "summary": esc(p.get("summary", "")), "blocks": blocks, "tools": tools,
        "footer": footer_html(), "scripts": PAGE_SCRIPTS, "arrow": ARROW_RIGHT, "arrow_left": ARROW_LEFT,
    }


def work_index(projects):
    cards = ""
    for slug, p in projects:
        cards += (
            '<a class="card" href="/work/%s/"><div class="m">'
            '<img src="%s" alt="%s, %s by %s" loading="lazy" decoding="async" width="1280" height="720"></div>'
            '<h2>%s</h2><p>%s \u00b7 %s</p></a>\n'
            % (slug, esc(rooted(p.get("thumb", ""))), esc(p["title"]), esc(p.get("category", "")),
               esc(PERSON), esc(p["title"]), esc(p.get("category", "")), esc(p.get("year", "")))
        )
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "Work \u2014 " + PERSON, "url": DOMAIN + "/work/",
        "about": {"@type": "Person", "@id": DOMAIN + "/#person", "name": PERSON},
    }
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Work \u2014 Selected Projects | %(person)s</title>
<meta name="description" content="Selected motion design, film and brand work by %(person)s \u2014 case studies across testimonial films, ad films and short films.">
<link rel="canonical" href="%(domain)s/work/">
<meta property="og:title" content="Work \u2014 %(person)s">
<meta property="og:url" content="%(domain)s/work/">
<script type="application/ld+json">
%(ld)s
</script>
%(fonts)s
<style>%(css)s</style>
%(scripts)s
</head>
<body>
%(header)s
<main class="wrap">
  <h1>Case studies</h1>
  <div class="grid">%(cards)s</div>
</main>
%(footer)s
</body>
</html>
""" % {"person": esc(PERSON), "domain": esc(DOMAIN), "ld": _ld_json(ld),
       "fonts": FONTS, "css": CSS, "header": header_html(), "cards": cards, "footer": footer_html(),
       "scripts": PAGE_SCRIPTS}


def _last_changed(*paths):
    """Date (YYYY-MM-DD) of the last commit touching any of these files, or
    None when git or its history is unavailable. A wrong date is worse than
    none: Google stops trusting lastmod that changes on every build."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--"] + list(paths),
                             cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    return out if re.match(r"^\d{4}-\d{2}-\d{2}$", out) else None


def sitemap(projects):
    proj_files = ["content/projects/%s.json" % slug for slug, _ in projects]
    urls = [(DOMAIN + "/", _last_changed("content/site.json")),
            (DOMAIN + "/work/", _last_changed(*proj_files) if proj_files else None)]
    urls += [("%s/work/%s/" % (DOMAIN, slug), _last_changed(f))
             for (slug, _), f in zip(projects, proj_files)]
    body = "".join(
        "  <url><loc>%s</loc>%s</url>\n" % (u, "<lastmod>%s</lastmod>" % d if d else "")
        for u, d in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % body)


# ---------------------------------------------------------------------------
# index.html prerendering
#
# content/site.json is the single source of truth for every word on the home
# page. This section bakes it into index.html at build time, reusing the very
# same <template> blocks that js/site.js used to use, so there is exactly one
# copy of the markup and exactly one copy of the content.
#
# Anything you hand-edit inside a generated container (filmsGrid, reelsGrid,
# expList, skillGroups, contactLinks, the hero, the about block, the head
# metas, the JSON-LD) is overwritten on the next build. Edit the <template>
# blocks for markup; edit content/site.json (or /admin) for content.
# ---------------------------------------------------------------------------

TPL_RE = r'<template id="%s">(.*?)</template>'


def _template(markup, tpl_id):
    m = re.search(TPL_RE % re.escape(tpl_id), markup, re.S)
    if not m:
        raise SystemExit("build: missing <template id=\"%s\"> in index.html" % tpl_id)
    return m.group(1).strip()


def _fill(tpl, data):
    """Same contract as fill() in js/site.js: %%key%% -> escaped value."""
    out = tpl
    for k, v in data.items():
        out = out.replace("%%" + k + "%%", esc(v))
    return out


def _drop_tag(markup, tag, marker):
    """Remove a single non-nesting <tag ... marker ...>...</tag>."""
    return re.sub(r"<%s\b[^>]*\b%s\b.*?</%s>" % (tag, marker, tag), "", markup, flags=re.S)


VOID = {"img", "br", "hr", "input", "meta", "link", "source", "track", "wbr", "area", "col"}


def _inner_span(markup, el_id):
    """Return (start, end) of the inner HTML of the element carrying id=el_id,
    matching nested same-name tags properly (a naive `.*?</div>` does not)."""
    m = re.search(r'<([a-zA-Z0-9]+)\b[^>]*\bid="%s"[^>]*?>' % re.escape(el_id), markup)
    if not m:
        raise SystemExit('build: no element with id=%s in index.html' % el_id)
    tag = m.group(1).lower()
    start = m.end()
    if tag in VOID or m.group(0).rstrip().endswith("/>"):
        return start, start
    depth = 1
    tok = re.compile(r"<(/?)%s\b([^>]*)>" % re.escape(tag), re.I)
    pos = start
    while depth:
        t = tok.search(markup, pos)
        if not t:
            raise SystemExit("build: unbalanced <%s> around id=%s" % (tag, el_id))
        if t.group(1):
            depth -= 1
            if depth == 0:
                return start, t.start()
        elif not t.group(2).rstrip().endswith("/"):
            depth += 1
        pos = t.end()
    return start, start


def _swap_el(markup, el_id, new_inner):
    """Replace a container's inner HTML, preserving any <template> children.

    js/site.js removed only the item elements (`:scope > a`, `:scope > div`)
    and left the <template> blocks in place; some of them live inside the
    container they feed, so they must survive the swap here too."""
    a, b = _inner_span(markup, el_id)
    kept = "".join(re.findall(r"<template\b.*?</template>", markup[a:b], re.S))
    return markup[:a] + new_inner + ("\n" + kept if kept else "") + markup[b:]


def _swap_meta(markup, selector, value):
    pat = re.compile(r'(<meta[^>]*%s[^>]*\bcontent=")([^"]*)(")' % selector, re.S)
    new, n = pat.subn(lambda m: m.group(1) + esc(value) + m.group(3), markup, count=1)
    if not n:
        print("  ! index.html: no meta matching %s (skipped)" % selector)
    return new


def _alt_tag(tag):
    return str(tag or "").replace(" \u00b7 ", ", ")


EXT_ATTRS = ' target="_blank" rel="noopener"'
# the card's "WATCH <arrow>" label; the arrow is index.html's .ico svg
CARD_LABEL = re.compile(r'(?:WATCH|CASE STUDY) (<svg class="ico"[^>]*><path d=")[^"]*("/></svg>)')
PATH_EXT = re.search(r'<path d="([^"]*)"', ARROW_EXT).group(1)
PATH_RIGHT = re.search(r'<path d="([^"]*)"', ARROW_RIGHT).group(1)


def _study_slug(item, studies, slugs):
    """Case-study slug a homepage card should link to, or None.

    The CMS "Link to case study" setting on each card decides:
      auto (default) - link when a case study uses the same YouTube video
      manual         - link to the case study picked in the CMS
      off            - always open the video link"""
    mode = item.get("caseStudyLink") or "auto"
    if mode == "off":
        return None
    if mode == "manual":
        pick = item.get("caseStudy")
        if pick in slugs:
            return pick
        print('  ! "%s": case study "%s" not found, matching by video instead'
              % (item.get("title", "").strip(), pick or ""))
    return studies.get(youtube_id(item.get("href")))


def _card_link(node, slug):
    """Point a rendered card at its case study (same tab), or off-site."""
    if slug:
        node = node.replace(EXT_ATTRS, "", 1)
        return CARD_LABEL.sub(lambda m: "CASE STUDY " + m.group(1) + PATH_RIGHT + m.group(2), node, count=1)
    return CARD_LABEL.sub(lambda m: "WATCH " + m.group(1) + PATH_EXT + m.group(2), node, count=1)


def _render_films(markup, films, studies, slugs):
    tpl = _template(markup, "tpl-film")
    out = []
    for f in films:
        d = dict(f)
        d["alt_tag"] = _alt_tag(f.get("tag"))
        slug = _study_slug(f, studies, slugs)
        if slug:
            d["href"] = "/work/%s/" % slug
        out.append(_card_link(_fill(tpl, d), slug))
    return "\n".join(out)


def _render_reels(markup, reels):
    tpl = _template(markup, "tpl-reel")
    out = []
    for r in reels:
        d = dict(r)
        d["alt_tag"] = _alt_tag(r.get("tag"))
        node = _fill(tpl, d)
        if not r.get("highlight"):
            node = _drop_tag(node, "span", "data-hl")
        out.append(node)
    return "\n".join(out)


def _render_experience(markup, items):
    tpl = _template(markup, "tpl-exp")
    out = []
    last = len(items) - 1
    for i, e in enumerate(items):
        node = _fill(tpl, e)
        if not (e.get("linkHref") and e.get("linkLabel")):
            node = _drop_tag(node, "a", "data-exp-link")
        if i == last:
            # js/site.js set this inline on the last row to close the list
            node = node.replace(
                "border-top:1px solid rgba(255,255,255,.1);",
                "border-top:1px solid rgba(255,255,255,.1); "
                "border-bottom:1px solid rgba(255,255,255,.1);",
                1,
            )
        out.append(node)
    return "\n".join(out)


def _render_skill_groups(markup, groups):
    tpl = _template(markup, "tpl-skillgroup")
    out = []
    for i, g in enumerate(groups):
        node = _fill(tpl, {"title": g.get("title", "")})
        lis = "".join("<li>" + esc(it) + "</li>" for it in g.get("items", []))
        node = re.sub(r"(<ul\b[^>]*>)(\s*)(</ul>)",
                      lambda m: m.group(1) + lis + m.group(3), node, count=1, flags=re.S)
        out.append(node)
    return "\n".join(out)


def _render_skills_topline(topline):
    out = []
    for i, t in enumerate(topline):
        if i > 0:
            out.append('<span style="color:var(--ac-ink); font-size:1.4rem;">/</span>')
        out.append('<span style="font-size:clamp(1.7rem,4vw,3rem); font-weight:800; '
                   'letter-spacing:-.03em;">' + esc(t) + '</span>')
    return "".join(out)


def _render_ai_tools(tools):
    return "".join(
        '<span style="border:1px solid rgba(255,255,255,.16); border-radius:999px; '
        'padding:9px 18px; font-family:\'Space Mono\',monospace; font-size:12px; '
        'letter-spacing:.04em; color:#C2C8CF;">' + esc(t) + '</span>'
        for t in tools
    )


def _render_contact_links(markup, links):
    tpl = _template(markup, "tpl-contact")
    out = []
    for i, l in enumerate(links):
        node = _fill(tpl, l)
        if re.match(r"^https?:", str(l.get("href", ""))):
            node = node.replace("<a href=", '<a target="_blank" rel="noopener" href=', 1)
        out.append(node)
    return "\n".join(out)


def _render_marquee(items):
    out = []
    for i, it in enumerate(items):
        outline = (' color:transparent; -webkit-text-stroke:1px rgba(255,255,255,.5);'
                   if i % 2 == 1 else '')
        out.append('<span style="padding:0 28px;' + outline + '">' + esc(it) + '</span>'
                   '<span style="color:var(--ac-ink);">\u2726</span>')
    return "".join(out)


def _render_brand_tiles(brands):
    def tile(b):
        if b.get("logo"):
            return ('<div class="brand"><img src="' + esc(b["logo"]) + '" alt="' +
                    esc(b.get("name", "")) + '" decoding="async"></div>')
        return '<div class="brand"><span class="txt">' + esc(b.get("name", "")) + '</span></div>'
    half = -(-len(brands) // 2)
    rotated = brands[half:] + brands[:half]
    return "".join(tile(b) for b in brands), "".join(tile(b) for b in rotated)


REEL_FRAMES = 5  # index.html's reelFade keyframes are timed for exactly five


def _video_type(src):
    ext = os.path.splitext(str(src).split("?")[0])[1].lower()
    return {".webm": "video/webm", ".mov": "video/quicktime"}.get(ext, "video/mp4")


def _hero_stills(site):
    """CMS stills, or else the films that have a local thumbnail. The featured
    film is left out on purpose: its thumbnail is a title card whose lettering
    fights the hero name (YouTube stills are skipped for their letterbox bars)."""
    reel = site.get("hero", {}).get("reel") or {}
    pool = [x for x in (reel.get("stills") or []) if x]
    if not pool:
        pool = [f["thumb"] for f in site.get("films", [])
                if f.get("thumb") and not re.match(r"^https?:", f["thumb"])]
    if not pool and site.get("featured", {}).get("thumb"):
        pool = [site["featured"]["thumb"]]
    return pool


def _hero_reel_on(site):
    """CMS switch: off leaves the plain dark hero with only the glows."""
    reel = site.get("hero", {}).get("reel") or {}
    return reel.get("enabled", True) is not False


def _render_hero_reel(site):
    """The full-bleed hero background (CMS: Hero > Hero reel).

    With a video: a muted, looping <video> showing the poster until js/site.js
    starts it (it stays on the poster for reduced-motion / save-data visitors
    and pauses off-screen). Without one: five stills cross-fading in CSS."""
    reel = site.get("hero", {}).get("reel") or {}
    if not _hero_reel_on(site):
        return ""
    pool = _hero_stills(site)
    video = (reel.get("video") or "").strip()
    if video:
        poster = (reel.get("poster") or (pool[0] if pool else "")).strip()
        return ('<video muted loop playsinline preload="none" disablepictureinpicture%s>'
                '<source src="%s" type="%s"></video>'
                % (' poster="%s"' % esc(poster) if poster else "", esc(video), _video_type(video)))
    if not pool:
        return ""
    out = []
    for i in range(REEL_FRAMES):
        load = 'fetchpriority="high"' if i == 0 else 'loading="lazy"'
        out.append('<img src="%s" alt="" %s decoding="async" width="1280" height="720" style="--i:%d">'
                   % (esc(pool[i % len(pool)]), load, i))
    return "".join(out)


def _render_hero_play(site):
    """'Watch showreel' button, only when the CMS link points off-site (a
    YouTube/Vimeo showreel). The default #work is already the View work CTA."""
    reel = site.get("hero", {}).get("reel") or {}
    link = (reel.get("link") or "").strip()
    if not _hero_reel_on(site) or not re.match(r"^https?:", link):
        return ""
    return ('<a class="hero-play" href="%s" target="_blank" rel="noopener">'
            '<span class="disc" aria-hidden="true"><span></span></span>Watch showreel'
            '<span class="sr-only"> (opens in a new tab)</span></a>' % esc(link))


def _ld_json(ld):
    """JSON for a <script type="application/ld+json"> block. Script contents
    are not HTML-decoded, so &amp; would reach Google literally; escape only
    what could close the tag, as JSON unicode escapes."""
    return (json.dumps(ld, indent=2, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e"))


def _render_jsonld(site):
    s, seo = site["schema"], site["seo"]
    canonical = seo.get("canonical", "").rstrip("/")
    home = canonical + "/"
    person = {
        "@type": "Person",
        "@id": canonical + "/#person",
        "name": s.get("name"),
        "alternateName": s.get("alternateName"),
        "url": canonical + "/",
        "image": canonical + "/" + (seo.get("ogImage") or ""),
        "jobTitle": s.get("jobTitle"),
        "worksFor": {k: v for k, v in (("@type", "Organization"), ("name", s.get("worksFor")),
                                        ("url", s.get("worksForUrl"))) if v},
        "address": {
            "@type": "PostalAddress",
            "addressLocality": s.get("locality"),
            "addressRegion": s.get("region"),
            "addressCountry": s.get("country"),
        },
        "email": "mailto:" + str(s.get("email", "")),
        "description": s.get("description"),
        "knowsAbout": s.get("knowsAbout"),
        "sameAs": [u for u in (s.get("sameAs") or []) if u and "REPLACE_WITH" not in u],
    }
    # WebSite names the site (Google's site name in results); ProfilePage
    # says the homepage is a profile whose subject is the Person above
    website = {
        "@type": "WebSite",
        "@id": canonical + "/#website",
        "url": home,
        "name": s.get("name"),
        "alternateName": s.get("alternateName"),
        "publisher": {"@id": canonical + "/#person"},
        "inLanguage": "en",
    }
    profile = {
        "@type": "ProfilePage",
        "@id": canonical + "/#profilepage",
        "url": home,
        "name": seo.get("title"),
        "isPartOf": {"@id": canonical + "/#website"},
        "mainEntity": {"@id": canonical + "/#person"},
        "inLanguage": "en",
    }
    return _ld_json({"@context": "https://schema.org", "@graph": [person, website, profile]})


def prerender_index(site, projects):
    path = os.path.join(ROOT, "index.html")
    h = open(path, encoding="utf-8").read()

    # homepage cards can link to these case studies (see _study_slug)
    slugs = {slug for slug, _ in projects}
    studies = {youtube_id(p.get("videoUrl")): slug for slug, p in projects}
    studies.pop(None, None)

    hero = site["hero"]
    about = site["about"]
    seo = site["seo"]
    feat = site["featured"]
    sk = site["skills"]
    c = site["contact"]

    # ---- head ----
    h = re.sub(r"(<title>)(.*?)(</title>)",
               lambda m: m.group(1) + esc(seo["title"]) + m.group(3), h, count=1, flags=re.S)
    h = _swap_meta(h, r'name="description"', seo["description"])
    h = _swap_meta(h, r'property="og:title"', seo["title"])
    h = _swap_meta(h, r'property="og:description"', seo["description"])
    h = _swap_meta(h, r'property="og:url"', DOMAIN + "/")
    h = re.sub(r'(<link rel="canonical" href=")([^"]*)(")',
               lambda m: m.group(1) + esc(DOMAIN + "/") + m.group(3), h, count=1)
    h = _swap_el(h, "person-jsonld", _render_jsonld(site))


    # ---- theme (baked, so the pre-paint localStorage hack is not needed) ----
    theme = site.get("theme", {})
    accent = theme.get("accent") or "#242de8"
    # --ac is the brand colour for fills/buttons; --ac-ink is its text-safe tint
    h = re.sub(r"<style>:root\{--ac:[^}]*\}</style>",
               lambda m: "<style>:root{--ac:%s;--ac-ink:%s}</style>" % (accent, accent_ink(accent)),
               h, count=1)
    h = re.sub(r"<script>\s*/\* pre-paint.*?</script>\n?", "", h, count=1, flags=re.S)
    if not theme.get("filmGrain", True):
        h = re.sub(r'(<div id="grain"[^>]*style=")', r"\1display:none; ", h, count=1)

    # ---- nav ----
    h = _swap_el(h, "navName", esc(site["nav"]["name"]))
    h = _swap_el(h, "navSub", esc(site["nav"]["suffix"]))

    # ---- hero ----
    h = _swap_el(h, "heroRole", esc(hero["role"]))
    h = _swap_el(h, "heroFirst", esc(hero["firstName"]))
    h = _swap_el(h, "heroLast", esc(hero["lastName"]))
    h = _swap_el(h, "heroTagline", esc(hero["tagline"]))
    if 'id="heroReel"' in h:
        h = _swap_el(h, "heroReel", _render_hero_reel(site))
    h = re.sub(r'<section class="hero[^"]*">',
               '<section class="hero%s">' % ("" if _hero_reel_on(site) else " hero--plain"), h, count=1)
    if 'id="heroPlay"' in h:
        h = _swap_el(h, "heroPlay", _render_hero_play(site))

    # ---- marquee ----
    # The skills marquee band was removed from the page (the logo strip is
    # the one marquee); keep filling it if it is ever put back.
    if 'id="mqA"' in h:
        mq = _render_marquee(site.get("marquee", []))
        h = _swap_el(h, "mqA", mq)
        h = _swap_el(h, "mqB", mq)

    # ---- brands (one set each; js repeats + measures at runtime) ----
    setA, setB = _render_brand_tiles(site.get("brands", []))
    h = _swap_el(h, "brandsTrackA", setA)
    h = _swap_el(h, "brandsTrackB", setB)

    # ---- featured ----
    feat_slug = _study_slug(feat, studies, slugs)
    feat_href = "/work/%s/" % feat_slug if feat_slug else feat["href"]
    h = re.sub(r'(<a[^>]*\bid="featLink"[^>]*\bhref=")([^"]*)(")',
               lambda m: m.group(1) + esc(feat_href) + m.group(3), h, count=1)
    # same-tab for the case study, new tab for an off-site video
    h = re.sub(r'<a\b[^>]*\bid="featLink"[^>]*>',
               lambda m: m.group(0).replace(EXT_ATTRS, "").replace(
                   'id="featLink"', 'id="featLink"' + ("" if feat_slug else EXT_ATTRS), 1),
               h, count=1)
    a, b = _inner_span(h, "featLink")
    h = h[:a] + _card_link(h[a:b], feat_slug) + h[b:]
    # src and data-src must match, or the browser fetches the stale src first
    # and site.js then swaps in data-src: two downloads for one image
    h = re.sub(r'(<img[^>]*\bid="featImg"[^>]*\bdata-src=")([^"]*)(")',
               lambda m: m.group(1) + esc(feat["thumb"]) + m.group(3), h, count=1)
    h = re.sub(r'(<img[^>]*\bid="featImg"[^>]*\ssrc=")([^"]*)(")',
               lambda m: m.group(1) + esc(feat["thumb"]) + m.group(3), h, count=1)
    # loading-text and thumbnail badges were removed from the design; the
    # CMS fields still exist, so fill them only if the markup comes back
    for el_id, key in (("featFrame", "frame"), ("featBadgeL", "badgeLeft"), ("featBadgeR", "badgeRight")):
        if 'id="%s"' % el_id in h:
            h = _swap_el(h, el_id, esc(feat.get(key, "")))
    h = _swap_el(h, "featName", esc(feat["title"]))
    h = _swap_el(h, "featSub", " " + esc(feat["subtitle"]))
    h = _swap_el(h, "featByline", esc(feat["byline"]))

    # ---- work grids ----
    h = _swap_el(h, "filmsGrid", _render_films(h, site["films"], studies, slugs))
    h = _swap_el(h, "reelsGrid", _render_reels(h, site["reels"]))

    # ---- about ----
    h = re.sub(r'(<img[^>]*\bid="aboutPortrait"[^>]*\bsrc=")([^"]*)(")',
               lambda m: m.group(1) + esc(about["portrait"]) + m.group(3), h, count=1)
    # the caption overlaid on the portrait was removed from the design; the
    # CMS fields still exist, so fill them only if the markup comes back
    if 'id="aboutCapName"' in h:
        h = _swap_el(h, "aboutCapName", esc(about["captionName"]))
        h = _swap_el(h, "aboutCapLoc", esc(about["captionLocation"]))
    # intentionally raw HTML (accent spans); point those spans at the text-safe tint
    h = _swap_el(h, "aboutBio", re.sub(r"(?<![\w-])color:\s*var\(--ac\)",
                                       "color:var(--ac-ink)", about["bio"]))
    h = _swap_el(h, "factBasedIn", esc(about["basedIn"]))
    h = _swap_el(h, "factLanguages", esc(about["languages"]))
    h = _swap_el(h, "factAlso", esc(about["also"]))
    stats = about.get("stats", [])
    if len(stats) > 0:
        h = _swap_el(h, "s1v", esc(stats[0]["value"]))
        h = _swap_el(h, "s1l", esc(stats[0]["label"]))
    if len(stats) > 1:
        h = _swap_el(h, "s2v", esc(stats[1]["value"]))
        h = _swap_el(h, "s2l", esc(stats[1]["label"]))

    # ---- experience / skills / contact / footer ----
    h = _swap_el(h, "expList", _render_experience(h, site["experience"]))
    h = _swap_el(h, "skillsTop", _render_skills_topline(sk["topline"]))
    h = _swap_el(h, "skillGroups", _render_skill_groups(h, sk["groups"]))
    h = _swap_el(h, "aiTitle", esc(sk["aiTitle"]))
    h = _swap_el(h, "aiTools", _render_ai_tools(sk["aiTools"]))
    h = _swap_el(h, "contactHead",
                 esc(c["headingLine1"]) + "<br>" + esc(c["headingLine2"]) +
                 ' <span style="color:var(--ac-ink);">' + esc(c["headingAccent"]) + "</span>")
    h = _swap_el(h, "contactLinks", _render_contact_links(h, c["links"]))
    h = _swap_el(h, "footCopy", esc(site["footer"]["copyright"]))
    h = _swap_el(h, "footLoc", esc(site["footer"]["location"]))

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(h)
    print("Prerendered index.html from content/site.json "
          "(%d films, %d reels, %d roles, %d brands)."
          % (len(site["films"]), len(site["reels"]),
             len(site["experience"]), len(site.get("brands", []))))


def main():
    files = sorted(glob.glob(os.path.join(PROJ_DIR, "*.json")))
    projects = []
    for f in files:
        slug = os.path.splitext(os.path.basename(f))[0]
        p = json.load(open(f, encoding="utf-8"))
        projects.append((slug, p))
    # sort by 'order' then title
    projects.sort(key=lambda sp: (sp[1].get("order", 999), sp[1].get("title", "")))

    for slug, p in projects:
        d = os.path.join(WORK_DIR, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(project_page(slug, p))

    os.makedirs(WORK_DIR, exist_ok=True)
    with open(os.path.join(WORK_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(work_index(projects))
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write(sitemap(projects))

    prerender_index(site, projects)

    print("Built %d project pages + work index + sitemap." % len(projects))
    for slug, p in projects:
        print("  /work/%s/  (%s)" % (slug, p["title"]))


if __name__ == "__main__":
    main()
