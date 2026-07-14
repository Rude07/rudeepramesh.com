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
import os, re, json, glob, html, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = os.path.join(ROOT, "content", "projects")
WORK_DIR = os.path.join(ROOT, "work")

# ---- site-level info (name, domain) from content/site.json ----
site = json.load(open(os.path.join(ROOT, "content", "site.json"), encoding="utf-8"))
DOMAIN = site["seo"]["canonical"].rstrip("/")
PERSON = site["schema"]["name"]
ACCENT = site.get("theme", {}).get("accent", "#D43A56")


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def rooted(path):
    """Make an asset path root-relative so it works from /work/<slug>/."""
    if not path:
        return ""
    if path.startswith("http") or path.startswith("/"):
        return path
    return "/" + path.lstrip("./")


def paragraphs(text):
    """Split plain text into <p> blocks on blank lines; single newlines -> <br>."""
    if not text:
        return ""
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        out.append("<p>" + esc(b).replace("\n", "<br>") + "</p>")
    return "\n".join(out)


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900'
         '&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">')

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:#0B0C0E;color:#F4F6F8;font-family:'Archivo',system-ui,sans-serif;line-height:1.6;--ac:__ACCENT__}
a{color:inherit;text-decoration:none}
.wrap{max-width:1040px;margin:0 auto;padding:0 clamp(20px,6vw,80px)}
header{position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;
 padding:18px clamp(20px,5vw,64px);background:linear-gradient(180deg,rgba(11,12,14,.9),rgba(11,12,14,.6));
 backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.06)}
.brand{font-weight:800;font-size:15px;letter-spacing:-.01em}
.brand span{font-family:'Space Mono',monospace;color:var(--ac);font-size:12px;margin-left:8px;letter-spacing:.12em}
nav a{font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.16em;color:#9AA1AA;margin-left:clamp(14px,2.5vw,32px)}
nav a:hover{color:var(--ac)}
.crumbs{font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.12em;color:#6B7280;
 text-transform:uppercase;padding:clamp(28px,5vh,56px) 0 0}
.crumbs a:hover{color:var(--ac)}
h1{font-size:clamp(2.4rem,7vw,5rem);font-weight:900;letter-spacing:-.04em;line-height:.95;
 text-transform:uppercase;margin:14px 0 18px}
.meta{display:flex;flex-wrap:wrap;gap:10px 28px;font-family:'Space Mono',monospace;font-size:12px;
 letter-spacing:.08em;color:#9AA1AA;text-transform:uppercase;margin-bottom:clamp(30px,5vh,52px)}
.meta b{color:var(--ac);font-weight:400}
.hero-media{position:relative;aspect-ratio:16/9;overflow:hidden;border:1px solid rgba(255,255,255,.08);
 background:#0E1013;margin-bottom:clamp(36px,6vh,64px)}
.hero-media img{width:100%;height:100%;object-fit:cover}
.hero-media .play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:74px;height:74px;
 border-radius:50%;background:rgba(11,12,14,.55);border:1px solid var(--ac);display:flex;align-items:center;
 justify-content:center;backdrop-filter:blur(6px)}
.hero-media .play span{width:0;height:0;border-left:16px solid var(--ac);border-top:10px solid transparent;
 border-bottom:10px solid transparent;margin-left:5px}
.watch{display:inline-flex;align-items:center;gap:10px;background:var(--ac);color:#0B0C0E;font-weight:700;
 padding:14px 26px;border-radius:999px;font-size:14px;margin-bottom:clamp(40px,6vh,64px)}
section.block{margin-bottom:clamp(34px,5vh,52px)}
.block h2{font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.2em;color:var(--ac);
 text-transform:uppercase;margin-bottom:14px}
.block p{color:#C2C8CF;font-size:clamp(1rem,1.4vw,1.15rem);margin-bottom:12px;max-width:70ch}
.lede{font-size:clamp(1.25rem,2.4vw,1.9rem);font-weight:600;letter-spacing:-.02em;line-height:1.4;
 color:#F4F6F8;max-width:60ch;margin-bottom:clamp(36px,6vh,60px)}
.tools{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
.tools span{border:1px solid rgba(255,255,255,.16);border-radius:999px;padding:8px 16px;
 font-family:'Space Mono',monospace;font-size:12px;color:#C2C8CF}
.backrow{border-top:1px solid rgba(255,255,255,.1);margin-top:clamp(40px,7vh,72px);
 padding:clamp(30px,5vh,52px) 0;display:flex;justify-content:space-between;flex-wrap:wrap;gap:16px;
 font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#9AA1AA}
.backrow a:hover{color:var(--ac)}
footer{border-top:1px solid rgba(255,255,255,.07);padding:clamp(30px,5vh,48px) 0;
 font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.14em;color:#6B7280;text-transform:uppercase}
/* work index grid */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:clamp(24px,4vw,44px);
 padding:clamp(30px,5vh,56px) 0 clamp(60px,10vh,110px)}
.card{display:block}
.card .m{position:relative;aspect-ratio:16/9;overflow:hidden;border:1px solid rgba(255,255,255,.08);background:#0E1013}
.card img{width:100%;height:100%;object-fit:cover;transition:transform .6s}
.card:hover img{transform:scale(1.05)}
.card h3{font-size:1.3rem;font-weight:800;letter-spacing:-.02em;margin:14px 0 4px}
.card p{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.1em;color:#8A9099;text-transform:uppercase}
.page-head{padding:clamp(50px,10vh,120px) 0 0}
.page-head .k{font-family:'Space Mono',monospace;font-size:12px;letter-spacing:.28em;color:var(--ac);text-transform:uppercase}
""".replace("__ACCENT__", ACCENT)

def header_html():
    return (
        '<header><a class="brand" href="/">RUDEEP RAMESH<span>/ MOTION</span></a>'
        '<nav><a href="/">HOME</a><a href="/work/">WORK</a>'
        '<a href="/#contact">CONTACT</a></nav></header>'
    )


def footer_html():
    yr = datetime.date.today().year
    return ('<footer><div class="wrap">\u00a9 %d %s &nbsp;\u2014&nbsp; '
            'Based in Kannur, Kerala \u2014 Available Worldwide</div></footer>' % (yr, esc(PERSON)))


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
    if p.get("tools"):
        tools = ('<section class="block"><h2>Tools</h2><div class="tools">' +
                 "".join("<span>%s</span>" % esc(t) for t in p["tools"]) + "</div></section>")

    meta_bits = []
    for label, key in [("Client", "client"), ("Role", "role"), ("Year", "year"), ("Type", "category")]:
        if p.get(key):
            meta_bits.append('<div><b>%s</b> &nbsp;%s</div>' % (label, esc(p[key])))
    meta = "".join(meta_bits)

    # JSON-LD: CreativeWork + VideoObject + BreadcrumbList
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
            },
            {
                "@type": "VideoObject",
                "name": title,
                "description": desc,
                "thumbnailUrl": thumb_abs,
                "uploadDate": str(p.get("year", "")) + "-01-01" if p.get("year") else None,
                "contentUrl": p.get("videoUrl"),
                "embedUrl": p.get("videoUrl"),
            },
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
            return [clean(x) for x in o]
        return o
    ld = clean(ld)

    watch = ('<a class="watch" href="%s" target="_blank" rel="noopener">Watch the film '
             '<span style="font-family:Space Mono,monospace">\u2197</span></a>' % esc(p.get("videoUrl", "#")))

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
</head>
<body>
%(header)s
<main class="wrap">
  <div class="crumbs"><a href="/">Home</a> / <a href="/work/">Work</a> / %(title)s</div>
  <h1>%(title)s</h1>
  <div class="meta">%(meta)s</div>
  <div class="hero-media">
    <img src="%(thumb)s" alt="%(title)s \u2014 %(category)s by %(person)s" width="1280" height="720">
    <a class="play" href="%(video)s" target="_blank" rel="noopener" aria-label="Play %(title)s"><span></span></a>
  </div>
  %(watch)s
  <p class="lede">%(summary)s</p>
  %(blocks)s
  %(tools)s
  <div class="backrow"><a href="/work/">\u2190 All work</a><a href="/#contact">Start a project \u2197</a></div>
</main>
%(footer)s
</body>
</html>
""" % {
        "page_title": esc(page_title), "desc": esc(desc), "url": esc(url),
        "og_title": esc(title + " \u2014 " + PERSON), "thumb_abs": esc(thumb_abs),
        "ld": json.dumps(ld, indent=2), "fonts": FONTS, "css": CSS,
        "header": header_html(), "title": esc(title), "meta": meta,
        "thumb": esc(thumb), "category": esc(p.get("category", "")), "person": esc(PERSON),
        "video": esc(p.get("videoUrl", "#")), "watch": watch,
        "summary": esc(p.get("summary", "")), "blocks": blocks, "tools": tools,
        "footer": footer_html(),
    }


def work_index(projects):
    cards = ""
    for slug, p in projects:
        cards += (
            '<a class="card" href="/work/%s/"><div class="m">'
            '<img src="%s" alt="%s \u2014 %s by %s" loading="lazy" width="1280" height="720"></div>'
            '<h3>%s</h3><p>%s \u00b7 %s</p></a>\n'
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
</head>
<body>
%(header)s
<main class="wrap">
  <div class="page-head"><span class="k">Selected Work</span>
  <h1 style="margin-top:14px">Case Studies</h1></div>
  <div class="grid">%(cards)s</div>
</main>
%(footer)s
</body>
</html>
""" % {"person": esc(PERSON), "domain": esc(DOMAIN), "ld": json.dumps(ld, indent=2),
       "fonts": FONTS, "css": CSS, "header": header_html(), "cards": cards, "footer": footer_html()}


def sitemap(projects):
    today = datetime.date.today().isoformat()
    urls = [(DOMAIN + "/", "1.0"), (DOMAIN + "/work/", "0.8")]
    urls += [("%s/work/%s/" % (DOMAIN, slug), "0.7") for slug, _ in projects]
    body = "".join(
        '  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>\n' % (u, today, pr)
        for u, pr in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s</urlset>\n' % body)


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

    print("Built %d project pages + work index + sitemap." % len(projects))
    for slug, p in projects:
        print("  /work/%s/  (%s)" % (slug, p["title"]))


if __name__ == "__main__":
    main()
