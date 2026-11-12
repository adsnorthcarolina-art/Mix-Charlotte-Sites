# Mix Charlotte Sites

Static sites for locksmith clients in the "gold header / dark hero" style.

- `data/<domain>.json` – everything about one business (NAP, hours, services with prices, areas, reviews, photos, redirects).
- `assets/site.css`, `assets/site.js` – shared style and behaviour (menu, tracking events, lead form).
- `scripts/build.py <domain>` – generates `sites/<domain>/` (plain HTML, sitemap, robots, `_redirects`, 404).

```
python3 scripts/build.py locksmithsmatthews.com
```

Deploy `sites/<domain>` as the output directory (for example a Cloudflare Pages project per site, no build command).

Notes
- Services, prices and service areas must match the Google Business Profile.
- Lead form: set `web3forms_key` in the data file; without it pages show phone/email instead of a form.
- Tracking: set `gtm` in the data file, or `ga4` (measurement id) to load gtag.js directly when there is no GTM container. `site.js` pushes `phone_call`, `sms_click`, `whatsapp_click`, `lead_form_submit` to `dataLayer`.
- Photos are currently loaded from the business's Google profile photo URLs (`photo_base` + id). Replace with local files under `assets/<domain>/img/` when the originals are available.
