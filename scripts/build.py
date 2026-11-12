#!/usr/bin/env python3
"""Mix Charlotte Sites - static site generator.

Usage:  python3 scripts/build.py <domain>
Reads   data/<domain>.json  and  assets/site.css, assets/site.js
Writes  sites/<domain>/   (plain HTML, one folder per page)

With FETCH_PHOTOS=1 the photos are downloaded into sites/<domain>/img/ and the
pages use those local files (used as the Cloudflare Pages build command, where
the network is available). Without it the pages load the photos from photo_base.
A failed photo download stops the build, so a broken deploy never goes live.
"""
import html
import json
import os
import shutil
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E = html.escape


def main(domain):
    d = json.loads((ROOT / "data" / f"{domain}.json").read_text(encoding="utf-8"))
    out = ROOT / "sites" / domain
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    for f in ("site.css", "site.js"):
        shutil.copy(ROOT / "assets" / f, out / "assets" / f)
    site = Site(d, out)
    site.build()
    print(f"built {len(site.pages)} pages -> {out}")


class Site:
    def __init__(self, d, out):
        self.d, self.out, self.pages = d, out, []
        self.base = d["base_url"].rstrip("/")
        self.tel = "tel:" + d["phone_e164"]
        self.loc = f'{d["city"]}, {d["st"]}'
        self.cats = {c["slug"]: c for c in d["categories"]}
        self.year = date.today().year
        self.local = os.environ.get("FETCH_PHOTOS") == "1"
        self.needed = {}
        import hashlib
        self.ver = {f: hashlib.sha1((ROOT / "assets" / f).read_bytes()).hexdigest()[:8] for f in ("site.css", "site.js")}

    # ---------- helpers ----------
    def photo(self, name, pid, size):
        """URL of a photo: local file when FETCH_PHOTOS=1, else the remote one."""
        remote = f'{self.d["photo_base"]}{pid}=s{size}'
        if not self.local:
            return remote
        fn = f"{name}-{size}.jpg"
        self.needed[fn] = remote + "-rj"
        return f"/img/{fn}"

    def img(self, key, size=800):
        return self.photo(key, self.d["photos"][key], size)

    def absurl(self, u):
        return self.base + u if u.startswith("/") else u

    def fetch_photos(self):
        dest = self.out / "img"
        dest.mkdir(parents=True, exist_ok=True)
        for fn, url in sorted(self.needed.items()):
            data = b""
            for attempt in range(4):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site build)"})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        data = r.read()
                    if len(data) > 2000:
                        break
                except Exception as e:  # noqa: BLE001
                    print(f"  retry {fn}: {e}")
                time.sleep(2 + attempt * 2)
            if len(data) <= 2000:
                sys.exit(f"photo download failed: {fn} <- {url}")
            (dest / fn).write_bytes(data)
        print(f"downloaded {len(self.needed)} photos -> {dest}")

    def logo(self, width=150, pad=4):
        """Business logo as a cropped background image (logo_box = x1,y1,x2,y2,source size)."""
        d = self.d
        if not d.get("logo_box"):
            return ""
        x1, y1, x2, y2, size = d["logo_box"]
        s = width / (x2 - x1)
        w, h = round(width + 2 * pad), round((y2 - y1) * s + 2 * pad)
        style = (f'width:{w}px;height:{h}px;background-image:url({self.photo("logo", d["logo_photo"], size)});'
                 f'background-size:{size * s:.1f}px {size * s:.1f}px;background-position:{pad - x1 * s:.1f}px {pad - y1 * s:.1f}px')
        return f'<span class="logo" role="img" aria-label="{E(d["business"])} logo" style="{style}"></span>'

    def write(self, path, title, desc, body, schema=None, hero=""):
        """path like '/' or '/services/car-lockout/'"""
        d = self.d
        url = self.base + path
        nav = [("/", "Home"), ("/automotive/", "Automotive"), ("/commercial/", "Commercial"),
               ("/emergency/", "Emergency"), ("/residential/", "Residential"), ("/services/", "Services"),
               ("/areas/", "Areas"), ("/about/", "About"), ("/reviews/", "Reviews"), ("/contact/", "Contact Us")]
        cur = ' aria-current="page"'
        nav_html = "".join(f'<a href="{h}"{cur if h == path else ""}>{t}</a>' for h, t in nav)
        nav_html += f'<a class="call" href="{self.tel}">Call: {d["phone"]}</a>'
        schemas = [self.business_schema()] + (schema or [])
        ld = "".join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in schemas)
        gtm_head = gtm_body = ""
        if d.get("gtm"):
            gtm_head = ("<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});"
                        "var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;"
                        "j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);"
                        f"}})(window,document,'script','dataLayer','{d['gtm']}');</script>")
            gtm_body = (f'<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={d["gtm"]}" height="0" width="0" '
                        'style="display:none;visibility:hidden"></iframe></noscript>')
        elif d.get("ga4"):
            gtm_head = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={d["ga4"]}"></script>'
                        "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                        f"gtag('js',new Date());gtag('config','{d['ga4']}');</script>")
        soc = d["social"]
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{self.absurl(self.img('hero', 1200))}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{'' if self.local else '<link rel="preconnect" href="https://lh3.googleusercontent.com">'}
<link rel="stylesheet" href="/assets/site.css?v={self.ver['site.css']}">
{gtm_head}{ld}
</head>
<body>
{gtm_body}<header class="top"><div class="wrap">
<a class="brand" href="/" aria-label="{E(d['business'])} home">{self.logo(150) or E(d['business'])}</a>
<button class="burger" aria-label="Menu" aria-expanded="false" aria-controls="nav"><span></span><span></span><span></span></button>
<nav class="nav" id="nav" aria-label="Main">{nav_html}</nav>
</div></header>
<main>
{hero}
{body}
</main>
<footer><div class="wrap">
<div class="cols2">
<div>{self.logo(190)}<h2>More Information</h2>
<p><strong>{E(d['legal_name'])}</strong><br>24 Hour Locksmith<br>Monday through Sunday, all day<br>
Mobile service from {E(self.loc)} {d['zip']}<br>
Email: <a href="mailto:{d['email']}">{d['email']}</a><br>
Phone: <a href="{self.tel}">{d['phone']}</a><br>
<a href="{self.base}/">{self.base.replace('https://', '')}</a></p>
<p>We accept: {E(', '.join(d['payments']))}</p>
<p><a href="{soc['facebook']}" rel="noopener">Facebook</a> · <a href="{soc['instagram']}" rel="noopener">Instagram</a> · <a href="{soc['x']}" rel="noopener">X</a> · <a href="{soc['youtube']}" rel="noopener">YouTube</a> · <a href="{soc['tiktok']}" rel="noopener">TikTok</a></p></div>
<div><h2>Main Navigation</h2>
<p class="navlinks">{''.join(f'<a href="{h}">{t}</a>' for h, t in nav)}<a href="/book/">Book a Locksmith</a></p>
<h2>Service Areas</h2>
<p class="navlinks">{''.join(f'<a href="/areas/{a["slug"]}/">{E(a["name"])}</a>' for a in d['areas'])}</p></div>
</div>
<p class="copy">&copy; Copyright {self.year} {E(d['business'])}. All Rights Reserved.</p>
</div></footer>
<div class="callbar"><a class="c1" href="{self.tel}">Call {d['phone']}</a><a class="c2" href="/book/">Book Online</a></div>
<button class="totop" aria-label="Back to top">&#9650;</button>
<script src="/assets/site.js?v={self.ver['site.js']}" defer></script>
</body>
</html>
"""
        target = self.out / path.strip("/") / "index.html" if path != "/" else self.out / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        self.pages.append(path)

    def business_schema(self):
        d = self.d
        return {
            "@context": "https://schema.org", "@type": "Locksmith", "@id": self.base + "/#business",
            "name": d["legal_name"], "alternateName": d["business"], "url": self.base + "/",
            "telephone": d["phone_e164"], "email": d["email"], "image": self.absurl(self.img("hero", 1200)),
            "logo": self.absurl(self.photo("logo", d["logo_photo"], d.get("logo_box", [0, 0, 0, 0, 512])[4])), "priceRange": "$$",
            "foundingDate": str(d["since"]),
            "address": {"@type": "PostalAddress", "addressLocality": d["city"], "addressRegion": d["st"],
                        "postalCode": d["zip"], "addressCountry": "US"},
            "geo": {"@type": "GeoCoordinates", "latitude": d["geo"]["lat"], "longitude": d["geo"]["lng"]},
            "openingHoursSpecification": [{"@type": "OpeningHoursSpecification",
                                           "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                                           "opens": "00:00", "closes": "23:59"}],
            "areaServed": [{"@type": "City", "name": f'{a["name"]}, {d["st"]}'} for a in d["areas"]],
            "sameAs": list(d["social"].values()) + [f'https://www.google.com/maps?cid={d["cid"]}'],
            "paymentAccepted": ", ".join(d["payments"]),
        }

    def crumbs_schema(self, trail):
        return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": self.base + p} for i, (p, n) in enumerate(trail)]}

    def small_hero(self, h1, sub, trail):
        crumbs = " &rsaquo; ".join(f'<a href="{p}">{E(n)}</a>' for p, n in trail[:-1])
        crumbs += (" &rsaquo; " if crumbs else "") + E(trail[-1][1])
        return (f'<section class="hero small" style="background-image:url({self.img("hero", 1200)})"><div class="wrap">'
                f'<p class="crumbs">{crumbs}</p><h1>{E(h1)}</h1><p>{E(sub)}</p>'
                f'<p style="margin-top:14px"><a class="btn gold" href="{self.tel}">Call {self.d["phone"]}</a></p></div></section>')

    def service_card(self, s):
        return (f'<article class="card"><a href="/services/{s["slug"]}/"><img loading="lazy" src="{self.img(s["photo"], 600)}" '
                f'alt="{E(s["name"])} in {E(self.loc)}" width="600" height="450"></a><div class="in">'
                f'<h3><a href="/services/{s["slug"]}/">{E(s["name"])}</a></h3><p class="price">From ${s["price"]}</p>'
                f'<p>{E(s["short"])}</p><p class="more"><a href="/services/{s["slug"]}/">Learn more &rarr;</a></p></div></article>')

    def cta(self, text=None):
        d = self.d
        text = text or f"Need a locksmith in {self.loc}? We are mobile and open 24/7."
        return (f'<section class="sec cream"><div class="wrap center"><h2>{E(text)}</h2>'
                f'<p><a class="btn" href="{self.tel}">Call us today: {d["phone"]}</a></p>'
                f'<p>Free estimate before any work starts.</p></div></section>')

    def reviews_block(self, limit=None):
        d = self.d
        revs = d["reviews"][:limit] if limit else d["reviews"]
        items = "".join(f'<div class="rev"><b>{E(r["name"])}</b><span class="stars" aria-label="5 out of 5 stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> {E(r["date"])}'
                        f'<p>{E(r["text"])}</p></div>' for r in revs)
        return items

    def review_urls(self):
        pid = self.d["place_id"]
        return (f"https://search.google.com/local/reviews?placeid={pid}",
                f"https://search.google.com/local/writereview?placeid={pid}")

    def form(self, heading="Request a locksmith"):
        d = self.d
        if not d.get("web3forms_key"):
            return (f'<div class="note"><p><strong>{E(heading)}</strong></p><p>The fastest way to reach us is by phone: '
                    f'<a href="{self.tel}">{d["phone"]}</a>, 24 hours a day. You can also email '
                    f'<a href="mailto:{d["email"]}">{d["email"]}</a>.</p></div>')
        opts = "".join(f'<option>{E(s["name"])}</option>' for s in d["services"])
        return f"""<h2>{E(heading)}</h2>
<form class="lead-form" action="https://api.web3forms.com/submit" method="POST">
<input type="hidden" name="access_key" value="{d['web3forms_key']}">
<input type="hidden" name="subject" value="New lead - {E(d['business'])} ({d['domain']})">
<input type="hidden" name="from_name" value="{E(d['business'])} website">
<input type="checkbox" name="botcheck" class="hp" tabindex="-1" autocomplete="off">
<label>Name<input name="name" required autocomplete="name"></label>
<label>Phone<input name="phone" type="tel" required autocomplete="tel"></label>
<label>Service<select name="service"><option value="">Choose a service</option>{opts}</select></label>
<label>Address or ZIP<input name="address" autocomplete="street-address"></label>
<label>What do you need?<textarea name="message" rows="4"></textarea></label>
<button class="btn" type="submit">Send request</button>
<p class="form-status" role="status"></p>
</form>"""

    # ---------- pages ----------
    def build(self):
        self.home()
        for c in self.d["categories"]:
            self.category(c)
        self.services_index()
        for s in self.d["services"]:
            self.service(s)
        self.areas_index()
        for a in self.d["areas"]:
            self.area(a)
        self.about()
        self.reviews()
        self.contact()
        self.book()
        self.extras()
        if self.local:
            self.fetch_photos()

    def home(self):
        d = self.d
        soc = d["social"]
        tiles = "".join(
            f'<a class="tile" href="/{c["slug"]}/"><img src="{self.img(c["photo"], 500)}" alt="{E(c["name"])} in {E(self.loc)}" width="500" height="400">'
            f'<span>{E(c["name"].replace(" Locksmith", ""))}<br>Locksmith</span></a>' for c in d["categories"])
        pay = "".join(f"<li>{E(p)}</li>" for p in d["payments"])
        hero = f"""<section class="hero" style="background-image:url({self.img('hero', 1200)})">
<p class="tag">A mobile locksmith company</p>
<p class="tel">Call Today: <a href="{self.tel}">{d['phone']}</a></p>
<ul class="pay" aria-label="Payment methods">{pay}</ul>
<ul class="soc" aria-label="Social profiles">
<li><a href="{soc['facebook']}" rel="noopener" aria-label="Facebook">f</a></li>
<li><a href="{soc['instagram']}" rel="noopener" aria-label="Instagram">IG</a></li>
<li><a href="{soc['x']}" rel="noopener" aria-label="X">X</a></li>
<li><a href="{soc['youtube']}" rel="noopener" aria-label="YouTube">YT</a></li>
<li><a href="{soc['tiktok']}" rel="noopener" aria-label="TikTok">TT</a></li>
</ul>
<div class="tiles">{tiles}</div>
<svg class="curve" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true"><path d="M0 10 L0 6 Q50 -4 100 6 L100 10 Z" fill="#fff"/></svg>
</section>"""
        by_cat = {}
        for s in d["services"]:
            by_cat.setdefault(s["cat"], []).append(s)
        cat_secs = ""
        for i, c in enumerate(d["categories"]):
            items = [s for s in d["services"] if s["cat"] == c["slug"] or (c["slug"] == "emergency" and s.get("emergency"))]
            lis = "".join(f'<li><a href="/services/{s["slug"]}/">{E(s["name"])}</a> <span class="price">from ${s["price"]}</span></li>' for s in items)
            cat_secs += (f'<section class="sec{" alt" if i % 2 == 0 else ""}"><div class="wrap">'
                         f'<h2>{E(d["city"])} {E(c["name"])} Services</h2><p>{E(c["lead"])}</p>'
                         f'<ul class="ticks">{lis}</ul>'
                         f'<p class="center"><a class="btn" href="/{c["slug"]}/">More about {E(c["name"].lower())} service</a></p></div></section>')
        dcards = "".join(f'<div class="dcard"><h3><a href="/{c["slug"]}/" style="color:inherit;text-decoration:none">{E(c["name"].replace(" Locksmith", ""))} Services</a></h3><p>{E(c["summary"])}</p></div>'
                         for c in d["categories"])
        areas = "".join(f'<li><a href="/areas/{a["slug"]}/">{E(a["name"])}, {d["st"]}</a></li>' for a in d["areas"])
        faq = "".join(f'<details><summary>{E(f["q"])}</summary><p>{E(f["a"])}</p></details>' for f in d["faq"])
        read_url, write_url = self.review_urls()
        years = self.year - d["since"]
        body = f"""<section class="sec"><div class="wrap">
<h1>{E(d['business'])} &ndash; We Are Mobile!</h1>
<p class="lead">Serving {E(self.loc)} {d['zip']} and nearby towns, 24 hours a day.</p>
<img class="float" src="{self.img('van', 500)}" alt="Car key and remote made by {E(d['business'])}" width="500" height="500">
<p>Need a mobile locksmith? {E(d['legal_name'])} is a local, veteran-owned company that has worked in {E(d['city'])} since {d['since']}. Our technicians come to your home, your business or your vehicle with the tools, locks and key blanks already on the van, so most jobs are finished in one visit.</p>
<p>We handle car keys and lockouts, house and business locks, and commercial door hardware. You get a free estimate before any work starts.</p>
<p class="center"><a class="btn" href="{self.tel}">Call us today: {d['phone']}</a></p>
<ul class="ticks">
<li>Open 24/7, including weekends and holidays</li>
<li>Mobile service across {E(d['city'])}, Mint Hill, Stallings, Indian Trail and beyond</li>
<li>Serving the area for {years}+ years</li>
<li>Rated {d['rating']['value']} on Google from {d['rating']['count']} reviews</li>
<li>Upfront starting prices for every service</li>
</ul>
</div></section>
{cat_secs}
<section class="sec"><div class="wrap"><h2>Starting Prices</h2>
<p>Every job starts with a free estimate. These are our starting prices; the final price depends on the lock or vehicle and is confirmed before work begins.</p>
<table class="prices"><thead><tr><th>Service</th><th>From</th></tr></thead><tbody>
{''.join(f'<tr><td><a href="/services/{s["slug"]}/">{E(s["name"])}</a></td><td>${s["price"]}</td></tr>' for s in d['services'])}
</tbody></table></div></section>
<section class="sec dark"><div class="wrap"><h2>Reviews</h2>
{self.reviews_block(4)}
<p class="center" style="margin-top:22px"><a class="btn gold" href="/reviews/">Click here for more customer reviews &gt;&gt;</a></p>
<h2 style="margin-top:34px;color:#fff;font-family:var(--mono);font-weight:400">{E(d['business'])} Services</h2>
{dcards}
</div></section>
<section class="sec"><div class="wrap"><h2>Areas We Serve</h2>
<p>We are based in {E(self.loc)} and drive to these towns:</p>
<ul class="cols">{areas}</ul></div></section>
<section class="sec alt" id="faq"><div class="wrap"><h2>Frequently Asked Questions</h2>{faq}</div></section>
{self.cta()}"""
        faq_schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in d["faq"]]}
        self.write("/", f'{d["business"]} | 24/7 Mobile Locksmith in {self.loc} | {d["phone"]}',
                   f'{d["business"]} is a mobile locksmith in {self.loc} {d["zip"]}, open 24/7. Car keys, lockouts, rekeying, lock changes and commercial hardware. Call {d["phone"]}.',
                   body, [faq_schema], hero)

    def category(self, c):
        d = self.d
        items = [s for s in d["services"] if s["cat"] == c["slug"] or (c["slug"] == "emergency" and s.get("emergency"))]
        trail = [("/", "Home"), (f'/{c["slug"]}/', c["name"])]
        hero = self.small_hero(f'{c["name"]} in {self.loc}', c["lead"], trail)
        body = f"""<section class="sec"><div class="wrap">
<h2>{E(c['name'])} services we offer</h2>
<div class="grid">{''.join(self.service_card(s) for s in items)}</div>
</div></section>
<section class="sec alt"><div class="wrap"><h2>How it works</h2>
<ul class="ticks"><li>Call {d['phone']} and tell us what is going on</li><li>We give you a free estimate and an arrival window</li><li>A mobile technician comes to you in {E(d['city'])} or a nearby town</li><li>The price is confirmed before the work starts</li></ul>
{self.form()}</div></section>
{self.cta()}"""
        self.write(f'/{c["slug"]}/', f'{c["name"]} in {self.loc} | {d["business"]}',
                   f'{c["name"]} in {self.loc}: {c["summary"].replace(" and more...", "")}. Mobile service, open 24/7. Call {d["phone"]}.',
                   body, [self.crumbs_schema(trail)], hero)

    def services_index(self):
        d = self.d
        trail = [("/", "Home"), ("/services/", "Services")]
        hero = self.small_hero(f'Locksmith Services in {self.loc}', f'{len(d["services"])} services for cars, homes and businesses, each with a starting price.', trail)
        secs = ""
        for c in d["categories"]:
            items = [s for s in d["services"] if s["cat"] == c["slug"]]
            secs += f'<h2><a href="/{c["slug"]}/" style="color:inherit">{E(c["name"])}</a></h2><div class="grid" style="margin-bottom:30px">{"".join(self.service_card(s) for s in items)}</div>'
        self.write("/services/", f'Locksmith Services in {self.loc} | {d["business"]}',
                   f'All locksmith services from {d["business"]} in {self.loc} with starting prices: car keys, lockouts, rekeying, lock changes, access control and more.',
                   f'<section class="sec"><div class="wrap">{secs}</div></section>{self.cta()}', [self.crumbs_schema(trail)], hero)

    def service(self, s):
        d = self.d
        c = self.cats[s["cat"]]
        trail = [("/", "Home"), (f'/{c["slug"]}/', c["name"]), (f'/services/{s["slug"]}/', s["name"])]
        hero = self.small_hero(f'{s["name"]} in {self.loc}', s["short"], trail)
        related = [x for x in d["services"] if x["cat"] == s["cat"] and x["slug"] != s["slug"]][:3]
        if len(related) < 3:
            related += [x for x in d["services"] if x["cat"] != s["cat"]][: 3 - len(related)]
        areas = ", ".join(f'<a href="/areas/{a["slug"]}/">{E(a["name"])}</a>' for a in d["areas"][:10])
        body = f"""<section class="sec"><div class="wrap">
<img class="photo" src="{self.img(s['photo'], 900)}" alt="{E(s['name'])} by {E(d['business'])} in {E(self.loc)}" width="900" height="675">
<h2>{E(s['name'])} from ${s['price']}</h2>
<p>{E(s['body'])}</p>
<h3>What is included</h3>
<ul class="ticks">{''.join(f'<li>{E(i)}</li>' for i in s['includes'])}</ul>
<p class="note"><strong>Starting price: ${s['price']}.</strong> The final price depends on the lock or vehicle and is confirmed with you before any work begins. The estimate is free.</p>
<p class="center"><a class="btn" href="{self.tel}">Call us today: {d['phone']}</a></p>
</div></section>
<section class="sec alt"><div class="wrap"><h2>Where we offer {E(s['name'].lower())}</h2>
<p>We are a mobile locksmith based in {E(self.loc)}. This service is available 24/7 in {areas} and the <a href="/areas/">rest of our service area</a>.</p>
{self.form(f'Request {s["name"].lower()}')}</div></section>
<section class="sec"><div class="wrap"><h2>Related services</h2><div class="grid">{''.join(self.service_card(x) for x in related)}</div></div></section>
{self.cta()}"""
        schema = {"@context": "https://schema.org", "@type": "Service", "name": s["name"], "serviceType": s["name"],
                  "description": s["short"], "provider": {"@id": self.base + "/#business"},
                  "areaServed": [{"@type": "City", "name": f'{a["name"]}, {d["st"]}'} for a in d["areas"]],
                  "offers": {"@type": "Offer", "priceCurrency": "USD",
                             "priceSpecification": {"@type": "PriceSpecification", "minPrice": s["price"], "priceCurrency": "USD"}},
                  "url": self.base + f'/services/{s["slug"]}/'}
        self.write(f'/services/{s["slug"]}/', f'{s["name"]} in {self.loc} | From ${s["price"]} | {d["business"]}',
                   f'{s["short"]} Mobile service in {self.loc}, open 24/7, from ${s["price"]}. Call {d["phone"]}.',
                   body, [self.crumbs_schema(trail), schema], hero)

    def areas_index(self):
        d = self.d
        trail = [("/", "Home"), ("/areas/", "Service Areas")]
        hero = self.small_hero(f'{d["business"]} Service Areas', f'Mobile locksmith service in {len(d["areas"])} towns around {self.loc}.', trail)
        cards = "".join(f'<div class="card"><div class="in"><h3><a href="/areas/{a["slug"]}/">Locksmith in {E(a["name"])}, {d["st"]}</a></h3>'
                        f'<p>{E(a["county"])} &middot; ZIP {E(a["zips"])}</p><p>{E(a["note"])}</p></div></div>' for a in d["areas"])
        self.write("/areas/", f'Service Areas | {d["business"]} | {self.loc}',
                   f'{d["business"]} serves {", ".join(a["name"] for a in d["areas"][:8])} and more. Mobile locksmith, open 24/7. Call {d["phone"]}.',
                   f'<section class="sec"><div class="wrap"><div class="grid">{cards}</div></div></section>{self.cta()}', [self.crumbs_schema(trail)], hero)

    def area(self, a):
        d = self.d
        home = a["slug"] == d["areas"][0]["slug"]
        trail = [("/", "Home"), ("/areas/", "Service Areas"), (f'/areas/{a["slug"]}/', a["name"])]
        hero = self.small_hero(f'Locksmith in {a["name"]}, {d["st"]}', f'24/7 mobile locksmith service for {a["name"]}, {a["county"]} (ZIP {a["zips"]}).', trail)
        idx = d["areas"].index(a)
        n = len(d["services"])
        feat = [d["services"][(idx * 3 + k * 7) % n] for k in range(6)]
        seen, featured = set(), []
        for s in feat + d["services"]:
            if s["slug"] not in seen:
                seen.add(s["slug"]); featured.append(s)
            if len(featured) == 6:
                break
        near = [d["areas"][(idx + k) % len(d["areas"])] for k in (1, 2, 3, 4)]
        where = (f'We are based right here in {E(a["name"])}' if home else f'We are based in {E(self.loc)} and drive to {E(a["name"])}')
        body = f"""<section class="sec"><div class="wrap">
<h2>Mobile locksmith for {E(a['name'])} homes, cars and businesses</h2>
<p>{E(a['note'])}</p>
<p>{where} with a fully stocked van, so lockouts, new car keys, rekeys and lock changes are done on site. We answer the phone 24 hours a day, 7 days a week, and you get a free estimate before any work starts.</p>
<p class="center"><a class="btn" href="{self.tel}">Call us today: {d['phone']}</a></p>
<h2>Popular services in {E(a['name'])}</h2>
<div class="grid">{''.join(self.service_card(s) for s in featured)}</div>
<p class="center" style="margin-top:20px"><a class="btn gold" href="/services/">See all {n} services</a></p>
</div></section>
<section class="sec alt"><div class="wrap"><h2>All services available in {E(a['name'])}, {d['st']}</h2>
<ul class="cols">{''.join(f'<li><a href="/services/{s["slug"]}/">{E(s["name"])}</a></li>' for s in d['services'])}</ul>
<h3>Nearby areas</h3>
<p>{' &middot; '.join(f'<a href="/areas/{x["slug"]}/">{E(x["name"])}</a>' for x in near)} &middot; <a href="/areas/">all areas</a></p>
{self.form(f'Request a locksmith in {a["name"]}')}</div></section>
{self.cta(f'Locked out in {a["name"]}? Call now, we are open 24/7.')}"""
        self.write(f'/areas/{a["slug"]}/', f'Locksmith in {a["name"]}, {d["st"]} | 24/7 Mobile Service | {d["business"]}',
                   f'Mobile locksmith in {a["name"]}, {d["st"]} ({a["zips"]}). Car keys, lockouts, rekeying and lock changes, open 24/7. Call {d["phone"]}.',
                   body, [self.crumbs_schema(trail)], hero)

    def about(self):
        d = self.d
        trail = [("/", "Home"), ("/about/", "About Us")]
        hero = self.small_hero(f'About {d["business"]}', f'A local, mobile locksmith company serving {self.loc} since {d["since"]}.', trail)
        body = f"""<section class="sec"><div class="wrap">
<p class="center">{self.logo(240, 8)}</p>
<h2>Who we are</h2>
<p>{E(d['legal_name'])} is a mobile locksmith company based in {E(self.loc)}. We opened in {d['since']} and have been helping drivers, homeowners and business owners in {E(d['city'])} and the surrounding towns ever since.{' The business is veteran-owned.' if d.get('veteran_owned') else ''}</p>
<p>We do not run a storefront. Instead, our vans carry the locks, keys, remotes and machines needed to finish the job where you are, whether that is a driveway, an office or a parking lot.</p>
<h2>What you can expect</h2>
<ul class="ticks">
<li>A person answers the phone 24 hours a day, 7 days a week</li>
<li>A free estimate before any work starts, with a starting price for every service</li>
<li>Technicians who explain the options, for example rekeying instead of replacing</li>
<li>Service for cars, homes and commercial properties</li>
<li>Payment by {E(', '.join(d['payments'][:-1]))} or {E(d['payments'][-1].lower())}</li>
</ul>
<h2>Our customers</h2>
<p>{d['rating']['count']} customers have reviewed us on Google, with an average rating of {d['rating']['value']} out of 5. <a href="/reviews/">Read some of their reviews</a>.</p>
</div></section>{self.cta()}"""
        self.write("/about/", f'About Us | {d["business"]} | {self.loc}',
                   f'About {d["legal_name"]}: a mobile, veteran-owned locksmith company serving {self.loc} since {d["since"]}, open 24/7. Call {d["phone"]}.',
                   body, [self.crumbs_schema(trail)], hero)

    def reviews(self):
        d = self.d
        trail = [("/", "Home"), ("/reviews/", "Reviews")]
        read_url, write_url = self.review_urls()
        hero = self.small_hero(f'{d["business"]} Reviews', f'Rated {d["rating"]["value"]} out of 5 on Google from {d["rating"]["count"]} customer reviews.', trail)
        body = f"""<section class="sec dark"><div class="wrap"><h2>What customers say</h2>
<p class="center">These reviews were written by customers on our Google Business Profile.</p>
{self.reviews_block()}
<p class="center" style="margin-top:24px"><a class="btn gold" href="{read_url}" rel="noopener">Read all reviews on Google</a></p>
<p class="center"><a class="btn gold" href="{write_url}" rel="noopener">Write a review</a></p>
</div></section>{self.cta()}"""
        self.write("/reviews/", f'Reviews | {d["business"]} | {self.loc}',
                   f'Customer reviews of {d["business"]} in {self.loc}. Rated {d["rating"]["value"]} on Google from {d["rating"]["count"]} reviews. Call {d["phone"]}.',
                   body, [self.crumbs_schema(trail)], hero)

    def contact(self):
        d = self.d
        trail = [("/", "Home"), ("/contact/", "Contact Us")]
        hero = self.small_hero(f'Contact {d["business"]}', f'Call, email or send a request. We answer 24 hours a day.', trail)
        body = f"""<section class="sec"><div class="wrap">
<h2>Get in touch</h2>
<ul class="ticks">
<li>Phone: <a href="{self.tel}">{d['phone']}</a> (24/7)</li>
<li>Email: <a href="mailto:{d['email']}">{d['email']}</a></li>
<li>Hours: {E(d['hours_text'])}</li>
<li>Service area: {E(self.loc)} {d['zip']} and <a href="/areas/">nearby towns</a>. We are a mobile service and come to you.</li>
</ul>
{self.form()}
<h2 style="margin-top:30px">Find us on Google Maps</h2>
<p><a class="btn gold" href="https://www.google.com/maps?cid={d['cid']}" rel="noopener">Open {E(d['legal_name'])} in Google Maps</a></p>
</div></section>"""
        self.write("/contact/", f'Contact {d["business"]} | {d["phone"]} | {self.loc}',
                   f'Contact {d["business"]} in {self.loc}: call {d["phone"]} any time, 24/7, or send a service request.',
                   body, [self.crumbs_schema(trail)], hero)

    def book(self):
        d = self.d
        trail = [("/", "Home"), ("/book/", "Book a Locksmith")]
        hero = self.small_hero('Book a Locksmith', f'Schedule a visit in {self.loc} or a nearby town. For emergencies, please call.', trail)
        body = f"""<section class="sec"><div class="wrap">
<p>For lockouts and anything urgent, call <a href="{self.tel}">{d['phone']}</a>. We answer 24/7. For planned work such as rekeying, new locks or a spare car key, send the details and we will call you back to set a time.</p>
{self.form('Book your appointment')}
</div></section>{self.cta()}"""
        self.write("/book/", f'Book a Locksmith in {self.loc} | {d["business"]}',
                   f'Book a mobile locksmith in {self.loc}. Rekeying, lock changes, car keys and more. For emergencies call {d["phone"]}, 24/7.',
                   body, [self.crumbs_schema(trail)], hero)

    def extras(self):
        d, out = self.d, self.out
        today = date.today().isoformat()
        urls = "".join(f"<url><loc>{self.base}{p}</loc><lastmod>{today}</lastmod></url>" for p in self.pages)
        (out / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', encoding="utf-8")
        (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {self.base}/sitemap.xml\n", encoding="utf-8")
        (out / "favicon.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#e8b548"/>'
            '<path d="M22 28v-6a10 10 0 0 1 20 0v6" fill="none" stroke="#190b04" stroke-width="5"/>'
            '<rect x="16" y="28" width="32" height="24" rx="4" fill="#190b04"/><circle cx="32" cy="39" r="4" fill="#e8b548"/></svg>', encoding="utf-8")
        red = "".join(f"{a} {b} 301\n" for a, b in d.get("redirects", []))
        (out / "_redirects").write_text(red, encoding="utf-8")
        (out / "_headers").write_text("/assets/*\n  Cache-Control: public, max-age=604800\n/img/*\n  Cache-Control: public, max-age=2592000\n", encoding="utf-8")
        nf = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
              f'<title>Page not found | {E(d["business"])}</title><meta name="robots" content="noindex"><link rel="stylesheet" href="/assets/site.css"></head>'
              f'<body><header class="top"><div class="wrap"><a class="brand" href="/">{E(d["business"])}</a></div></header>'
              f'<main><section class="sec"><div class="wrap center"><h1>Page not found</h1><p>The page you were looking for has moved.</p>'
              f'<p><a class="btn" href="/">Go to the home page</a></p><p>Or call <a href="{self.tel}">{d["phone"]}</a>, 24/7.</p></div></section></main></body></html>')
        (out / "404.html").write_text(nf, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 scripts/build.py <domain>")
    main(sys.argv[1])
