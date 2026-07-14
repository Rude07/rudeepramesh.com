# rudeepramesh.com — Deploy & Edit Guide

Your portfolio as a fast static site + Decap CMS editing panel at `/admin`.
Total running cost: just the domain (~₹1,000/yr). Hosting is free.

---

## How it works (30 seconds)

- **`index.html`** — the whole site, pre-rendered (great for Google).
- **`content/site.json`** — every editable thing: name, bio, films, reels,
  thumbnails, links, colors, SEO, schema. **This is the only file the CMS edits.**
- **`js/site.js`** — reads site.json and updates the page, including the
  Person schema (JSON-LD) Google uses for your Knowledge Panel.
- **`admin/`** — the editing panel. Open `rudeepramesh.com/admin` → log in
  with GitHub → friendly forms → Save → site updates in ~1 minute.

---

## Go live — step by step (≈30 minutes)

### 1. Create a GitHub account + repo
1. Sign up at github.com (free) if you haven't.
2. Create a **new repository**, e.g. `rudeepramesh.com`. Keep it **Public**
   (or Private — both work).

### 2. Push this folder to the repo
On your Mac, in Terminal, inside this site folder:

```bash
git init
git add .
git commit -m "Portfolio v1"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/rudeepramesh.com.git
git push -u origin main
```

### 3. Deploy on Netlify (free)
1. Sign up at netlify.com **with your GitHub account**.
2. **Add new site → Import an existing project → GitHub** → pick your repo.
3. Build command: *leave empty*. Publish directory: `.` → **Deploy**.
4. You get a live URL like `rudeep.netlify.app` immediately.

### 4. Wire up the CMS login (one-time, ~5 min)
Netlify's old "Identity" login is deprecated, so we use GitHub login directly:

1. Open `admin/config.yml` and change
   `repo: YOUR_GITHUB_USERNAME/YOUR_REPO` to your real repo,
   e.g. `repo: rudeepramesh/rudeepramesh.com`. Commit & push.
2. On GitHub: **Settings → Developer settings → OAuth Apps → New OAuth App**
   - Application name: `Rudeep Site CMS`
   - Homepage URL: `https://YOUR-SITE.netlify.app` (or your domain later)
   - Authorization callback URL: `https://api.netlify.com/auth/done`
   - Register → copy the **Client ID**, generate a **Client Secret**.
3. On Netlify: **Site configuration → Access & security → OAuth →
   Install provider → GitHub** → paste Client ID + Secret.
4. Visit `https://YOUR-SITE.netlify.app/admin` → **Login with GitHub** → done.

*(Alternative if you ever want email/password login instead of GitHub:
decapbridge.com is a free service built for this — its site gives you 4 lines
to paste into config.yml.)*

### 5. Connect your domain
1. Buy `rudeepramesh.com` (Cloudflare Registrar is cheapest, ~₹900/yr;
   Namecheap/GoDaddy also fine).
2. Netlify: **Domain management → Add a domain** → follow the DNS
   instructions (usually add 2 records at your registrar).
3. HTTPS certificate is automatic. Done — you're live on rudeepramesh.com.

### 6. Tell Google you exist (the SEO part)
1. **Google Search Console** (search.google.com/search-console):
   add property `rudeepramesh.com`, verify (Netlify DNS or HTML tag),
   then **Sitemaps → submit** `https://rudeepramesh.com/sitemap.xml`.
2. In `/admin` → **Identity / Schema** → replace the placeholder Instagram
   and YouTube URLs in **sameAs** with your real profiles. Add Behance,
   Wikidata, anything else you have.
3. Update your **Wikidata** entry: add *official website =
   rudeepramesh.com*, occupation = motion designer, and your social profile
   properties. Wikidata ↔ your schema ↔ your profiles pointing at each
   other is what builds Knowledge-Panel trust.
4. Put `rudeepramesh.com` in the website field of your LinkedIn, Instagram
   and YouTube bios.
5. Rich Results Test (search.google.com/test/rich-results): paste your URL,
   confirm the **Person** schema is detected.

---

## Editing the site day-to-day

- Go to `rudeepramesh.com/admin`, log in, edit, **Save/Publish**.
  Netlify redeploys automatically (~1 min).
- **Add a film/reel:** Films or Reels section → *Add item* → fill title,
  link, upload a thumbnail (drag & drop). New uploads land in
  `images/uploads/`.
- **Change your photo:** About → Portrait photo → upload.
- **Change accent color / grain:** Theme section.
- **Everything Google sees** (title, description, schema, social links):
  SEO & Search + Identity/Schema sections.

### Editing locally on your Mac (no login needed)
```bash
cd your-site-folder
npx decap-server        # terminal 1
npx serve               # terminal 2
# open http://localhost:3000/admin
```
Edits write straight to your local files; `git push` when happy.

---

## Costs

| Item | Cost |
|---|---|
| Domain .com / year | ₹800–1,300 |
| Netlify hosting, SSL, CDN | ₹0 |
| Decap CMS | ₹0 |
| **Total** | **~₹1,000/yr** |

## Later upgrades worth doing
1. Replace Google Drive video links with YouTube (unlisted is fine) —
   Drive links can break and look less professional.
2. A real OG/social image (1200×630) — set it in SEO & Search.
3. Individual project pages for your biggest 3–4 works (more Google surface).
4. Get credited by name on the EBS site + 1–2 design-community features —
   these external mentions are what eventually trigger the Knowledge Panel.
