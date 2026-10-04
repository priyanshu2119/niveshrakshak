# Competitive Landscape — Investment-Scam Verification (India)

**Research date:** 1 October 2026
**Method:** Direct Google Play listing scrapes (package-ID addressed), iTunes Search API (India storefront), GitHub repository search, primary vendor sites, `sancharsaathi.gov.in`. ~17 fetches.
**Scope question:** Does anyone already do *chat-message-in → payment-destination extraction → SEBI official verification → registry near-miss matching → forwardable verdict card*?

---

## 1. Headline answer

**No product does the full five-part combination.** The whitespace is real, but it is narrower and more fragile than it looks, and the single biggest competitive threat is SEBI itself.

Three findings dominate everything else:

1. **SEBI's own SAARTHI app now has an in-built SEBI Check tab** (added in the 7 May 2026 update — release notes read literally *"In-built SEBI check new tab add"*). 500K+ downloads, free, official brand. It is buggy and manual, but it owns step (c) legitimately.
2. **Every single consumer competitor found is AI/heuristic-only.** Fourteen+ apps, none query an official registry. Not one can produce a registry-grounded factual verdict.
3. **GitHub has zero open-source wrappers of `siportal.sebi.gov.in`.** Search for `sebi check siportal` → **0 repositories**. Search `siportal` → 4 repos, all unrelated. Your reverse-engineered integration is genuinely un-crowdsourced.

---

## 2. Competitor table

### Tier 1 — Named in the brief

| Name | Platform | Downloads | Rating | Last updated | What it verifies | Data source | Free/Paid | URL |
|---|---|---|---|---|---|---|---|---|
| **RakshaLink: Scam Detector** | Android | **10K+** | **4.3** (115) | **28 Sep 2026** (v1.50.0) | Notification previews (WhatsApp/SMS/RCS/Telegram) for digital arrest, KYC fraud, UPI PIN/CVV asks, fake electricity notices, WA pairing codes, "deposit to finish task" jobs, bank lookalike links; Paste & Check (text/links/**UPI IDs**); payment QR; APK signature/permission check; suspicious-call SOS; family alerts | **On-device heuristics/ML only. No SEBI. No registry.** Vendor site contains zero SEBI mentions; "Verify safely" routes the *user* to official channels rather than querying them | Free core, no ads, 8 Indian languages. Optional **Pro** — 1-year, explicitly **non-auto-renewing**: deeper family coordination, recurring-debit insights, monthly reports | [Play](https://play.google.com/store/apps/details?id=in.rakshalink.app) · [rakshalink.in](https://rakshalink.in/) |
| **Phishbowl: AI Scam Detector** | Android | **100K+** | **3.9** (503) | **26 Sep 2026** | Messages, links, **QR codes**, data-breach lookup, social-media search, mobile-app report | **AI-only** | Free + subscription IAP (recent changelog is entirely subscription-reliability work) | [Play](https://play.google.com/store/apps/details?id=com.phishbowl) |
| **UPI Shield: Scam Detector IN** | Android | **100+** | none | 11 Apr 2026 | Tagline only: *"Don't lose money! Check UPI scams before you send payment."* No long description published | **Unverified** — no method disclosed | Free + **ads** | [Play](https://play.google.com/store/apps/details?id=com.codeninja.upishield) |
| **Bitdefender Scamio** | Web + **WhatsApp**/Messenger/Discord bots | n/a | n/a | live | Suspicious email, text, link, **QR code**, image | **AI-only.** No Indian registries, no SEBI, no UPI logic | Free (Bitdefender account unlocks "real-time analysis"); upsell to *Scam Protection Pro* bundled with Premium Security | [scamio.bitdefender.com](https://scamio.bitdefender.com/) · WhatsApp `wa.link/l1kly7` |
| **ScamShield AI – Scam Detector** | iOS | n/a (not public) | **0 ratings** | v2.0, 21 Jun 2026 (released 20 May 2026) | Pasted SMS/WhatsApp/email, **screenshot OCR**, links, scam-trend education, emergency guidance | **AI-only. Malaysia/Singapore-focused** — v2.0 filters scam trends "by Malaysia or Singapore". No India content | Free + Pro subscription (unlimited checks) | [App Store](https://apps.apple.com/in/app/scamshield-ai-scam-detector/id6770247571) |
| **Sanchar Saathi / Chakshu** | Android + iOS | **10M+** (Play badge) — DoT site claims **2.5Cr+** Play, **21L+** iOS ⚠️ discrepancy | **4.5** (190K) | 3 Aug 2026 | **Chakshu is a REPORTING facility, not a verifier** — official title: *"Chakshu – Report Suspected Fraud Communication / UCC (Spam)"*. Sibling services: CEIR (block lost handset), TAFCOP (connections in your name), KYM (handset genuineness), RICWIN (intl call w/ Indian number), KYI (wireline ISP), Trusted Contact Details (FI) | Official **telecom** databases. **No investment, no UPI, no SEBI.** "Beware of Investment Scam" exists only as a static awareness **PDF** | Free | [Play](https://play.google.com/store/apps/details?id=com.dot.app.sancharsaathi) · [sancharsaathi.gov.in/sfc](https://sancharsaathi.gov.in/sfc/) |
| **SAARTHI (SEBI)** | Android | **500K+** | **3.8** (783) | **7 May 2026** | **In-built SEBI Check tab** + investor-awareness resource library | **OFFICIAL SEBI systems** — the only product in this entire set with legitimate registry access | Free (Government app) | [Play](https://play.google.com/store/apps/details?id=com.sebi.invapp) |

**⚠️ SAARTHI quality signal — direct user reviews:**
- 6 Aug 2026: *"Seems like SEBI Check feature has bug? I enter my own personal UPI and it said not valid, I mean I use it daily, linked with valid bank account and everything check. still got 'UPI ID Not Valid'."*
- 13 Sep 2026: *"This is showing invalid UPI ID even entering the correct UPI ID."*

Two independent false-negative reports within six weeks of the feature shipping. This is your most exploitable opening — and your most likely source of a support burden you inherit by proxy.

### Tier 2 — Found during broad Play/App Store sweeps

| Name | Platform | Downloads | Rating | Last updated | What it verifies | Data source | Free/Paid | URL |
|---|---|---|---|---|---|---|---|---|
| **Siren: Scam Safety App** | Android | **100K+** | **4.7** (899) | 19 Sep 2026 | Risky links/websites/messages/spam calls; **OTP-request and screen-share warnings**; unknown-number check; app scan; "fake UPI" | **On-device pattern detection.** Dev reply on record: *"does not record calls, read or store messages… only detects scam patterns on device"* | Free + IAP | [Play](https://play.google.com/store/apps/details?id=com.joinsiren.app) |
| **ScamKavach: Fraud & UPI Safety** | Android | **5+** ⚠️ dead | none | 26 Mar 2026 (v1.0.1) | URL scanner; **UPI ID verification with "RBI lender badge"**; phone checker vs scam DB; paste-based SMS analyzer; QR fraud scanner; Hindi + English; DPDP Act 2023 Privacy Center | **360+ offline scam-DB entries.** No SEBI registry | Free | [Play](https://play.google.com/store/apps/details?id=com.scamkavach.app) |
| **Scam Shield: AI Fake Photo, QR** ("Owl") | iOS | n/a | 5.0 (**1 rating**) | v2.2, 10 Sep 2026 | Links vs **"7 trusted safety sources"**; QR; screenshots; **share from Messages/WhatsApp**; homograph lookalike detection; AI-image detection; breach check; **"Is this UPI request a scam? (India)" — validates payee ID, amount, payment format** | Aggregated third-party safety feeds + AI. **No SEBI, no registry near-miss** | Free (5 AI image checks) + Pro sub | [App Store](https://apps.apple.com/in/app/scam-shield-ai-fake-photo-qr/id6744896851) |
| **ScamShield** (Singapore GovTech) | iOS | n/a | 0 (IN storefront) | v4.3.0, 29 Sep 2026 | Scam-call blocking, SMS filtering, paste link/message/number, **screenshot upload — explicitly "works for SMS, WhatsApp, and Telegram"**, reporting | Singapore govt scam DBs (SPF + NCPC) | Free | [App Store](https://apps.apple.com/in/app/scamshield/id1497144087) |
| **ScamNet: Anti-Scam Suite** | iOS | n/a | 5.0 (5) | v5.2.1, 29 Jun 2026 | Phone numbers, websites, **wallet addresses**, text, images, audio; Visual Intelligence; system-wide Share Sheet; on-device Apple Intelligence | On-device AI + daily-updated offline threat datasets | Free + ScamNet+ sub | [App Store](https://apps.apple.com/in/app/scamnet-anti-scam-suite/id6472626411) |
| **ScamSense Scam & Fraud Checker** | Android | 1K+ | none | 16 Jul 2026 | Messages, **screenshots**, links; **Voice Scan** (speak the message); AI voice coach | AI-only | Free (ad after each scan) + Premium sub | [Play](https://play.google.com/store/apps/details?id=com.scamsense.app) |
| **ScamShield: Phishing & Fraud** | iOS | n/a | 0 | v1.1, 16 Sep 2026 | Text/links/screenshots via on-device OCR → verdict (Safe/Suspicious/Scam/Phishing) + confidence score + severity-rated red flags | **100% offline** pattern & language checks | **₹199 one-time** | [App Store](https://apps.apple.com/in/app/scamshield-phishing-fraud/id6760344064) |
| **ScamShield: Scam & Phishing** | iOS | n/a | 0 | v1.0.4, 24 Jul 2026 | Text/link/SMS/email/QR in **8 languages incl. Hindi**; phone numbers; file scan (70+ AV engines); breach check; share sheet | On-device + AV aggregation + AI | **₹799 one-time** | [App Store](https://apps.apple.com/in/app/scamshield-scam-phishing/id6780233121) |
| **SEBISCORES** | Android | 10K+ | **2.4** (157) | 17 Sep 2026 | Complaint filing (SCORES). **Not a verification tool** | Official SEBI | Free | [Play](https://play.google.com/store/apps/details?id=com.sebi) |
| **Scam Checker India** | Android | **10+** ⚠️ dead | none | 15 Mar 2026 — changelog: *"Test Release"* | Calls, SMS, messages; 22 languages | AI-only | Free | [Play](https://play.google.com/store/apps/details?id=com.birthdaygirl.scamchecker) |
| **Truecaller: Premium Caller ID** | iOS/Android | 500M+ users | **4.40** (885,155 iOS) | v26.38, 29 Sep 2026 | Caller ID, spam/scam-call blocking, Family Plan (4 members), Travel eSIM | Crowd-sourced number DB | Free + Premium sub | [App Store](https://apps.apple.com/in/app/truecaller-premium-caller-id/id448142450) |

**Answer to the Truecaller question:** as of v26.38 (29 Sep 2026), Truecaller's iOS listing contains **no financial-fraud, UPI, or investment-verification feature**. Its expansion vector is Family Plan and eSIM — telecom, not finance. It is not currently a competitor, but it has the distribution to become one overnight.

**Bank/broker apps with built-in verification:** none found. Play search for `sebi registered check` returns only SEBI's own two apps plus broker apps (Groww 4.8★, Upstox 4.3★, Angel One 4.4★, mStock 4.3★, Samco 4.5★, ET Money 4.4★, Univest 4.8★, Ventura 4.6★, SBI Securities 4.3★, Novelty Wealth 4.7★, SAHI 4.5★) — all of which are *themselves* SEBI-registered and have no reason to build a checker. Play search for `upi id verify` returns only payment apps (Paytm, PhonePe, BHIM, BharatPe, MobiKwik, PayZapp, Freecharge, Canara ai1Pe, Navi) and generic KYC/ID-verification vendors (IBM Verify, Idemia, iDenfy, Firmcheck). **No UPI-handle→registry verification tool exists in either search.**

Also present but non-India / non-relevant: ScamAdviser (3.7★, website reputation), Trend Micro ScamCheck (4.2★), Cleared by Sync.ME (4.4★), ScamChecker by Yarra Secure (AU), Scam Scanner by Happy Grandma Senior Tech Support (US), Robokiller (IT), T-Mobile Scam Shield (US carrier), TextShield (US SMS), Scam Detector Secure RO (RO), SIA – Scammer Information App (BD), eScan CERT-In Bot Removal (3.8★, malware removal), Cyber Help Desk (4.8★, helpline directory), ScamDrill, Scampr.ai, ScamGuard/MiniFyn, ScamCheck AI, ScamSecurity/App2Ace, Fraudly, SCAMalicious, ScamHunter, AI Scam Checker, ScamDetect AI, Scam Detector AI/Devolim, Scam Detector/DanSar Tech.

---

## 3. GitHub / open source (item 9)

| Query | Repos | Notable |
|---|---|---|
| `sebi check siportal` | **0** | — |
| `siportal` | 4 | All unrelated: `ravenlntn/PUP-SIPortal` (CSS, 2022, 0★), `kpukarimunteknishukum-boop/siportal` (0★), `animeshy071-web/siportal` (TS, 0★, pushed 18 days ago — **worth a manual look, name-only match**), `s-innovations/SiPortalFrameworkDemos` (1★, 2015, Danish UI framework) |
| `sebi registry` | 3 | **`aryandigital/prospektlab-scraper`** — "ProspektLab SEBI multi-registry scraper", Python, 0★, updated Jun 2026 → implies a **commercial product (ProspektLab)** already ingests multiple SEBI registries. Investigate. Also `tech-cybersigmacs/india-compliance-registry` (0★), `jjf2009/InvestorFinder` (0★) |
| `sebi scam` | 8 | All hackathon-grade, 0–3★. Closest: **`BlueWaves-afk/marketguard.ai`** (3★, Sep 2025) — "browser extension & mobile SDK for real-time **advisor verification**, scam-language detection, deepfake warnings". Also `nihitagarwal2006-cloud/ai-financial-threat-intelligence` ("FinSentinel" — messages, call transcripts, URLs **& screenshots**, 0★), `asthanakat74-astha/financial-Risk-Predictor` (multilingual 0–100 risk score, 0★), `omaggarwal-2006/niveshak` (bilingual HI/EN literacy, 1★), `Devparth7-coder/TrustShield-AI-SEBI-Hack` (0★), `Yasaswini-ch/ET-InvestIQ` (0★), `harshil748/Sentinel-Shield` (1★), `AmartyaRanjan/SEBI_Hackathon--Scam-detection-and-prevention-model` (0★) |
| `upi fraud detection` | 1.7k | **All academic ML on transaction datasets** — `Vatshayan/UPI-Fraud-Detection-Using-Machine-Learning` (55★), `kirthika1307/UPI-Fraud-Detection-using-ML` (48★), `Shabopp/FraudDetectionUsingGAN` (41★), `Skismail57/...` (16★), `rishabhmaurya-04/PayShield` (6★, Android). **None touch a registry.** Different problem class entirely |

**Conclusion:** the SEBI-hackathon ecosystem keeps producing scam-*language* detectors. Nobody has shipped a registry-*grounded* one. `marketguard.ai` is the only repo whose stated intent (advisor verification) overlaps your step (d), and it has 3 stars.

---

## 4. The actual whitespace

### What nobody does

**(c) + (d) together — official SEBI verification *plus* registry-wide near-miss matching.**

Outside SEBI's own SAARTHI app, **no product on any platform queries SEBI's official systems.** And **no product anywhere** does fuzzy near-miss / impersonation matching against the ~23,500-intermediary registry.

This is the structural gap. Every competitor is AI-only, which means every competitor can only ever say:

> *"This message sounds like a scam."*

None of them can say:

> *"This UPI handle resolves to X. The company name claimed in the message is a 2-character near-miss of SEBI-registered intermediary Y (INZ000XXXXX), whose registered contact details do not include this number."*

That is a **factual, falsifiable, registry-grounded verdict**. An LLM-based competitor cannot fake it, cannot hallucinate its way to it, and cannot ship it without doing the same unglamorous scraping work you did. This is the only claim in your stack that is structurally defensible.

### What almost nobody does

**(e) The forwardable verdict card.** Zero products in this entire set produce a screenshot-ready artifact engineered to be sent *back into the originating chat*. Singapore's ScamShield is culturally closest (government-backed, share-oriented, accepts WhatsApp/Telegram screenshots) but emits no card. This matters more than it looks: it is the only component in your stack that **self-propagates**. Everything else is a feature; this is a distribution mechanic.

**(b) Hindi/Devanagari OCR → payment-destination extraction.** ScamShield AI does OCR but for Malaysia/Singapore. ScamKavach is Hindi+English but paste-only, no OCR. RakshaLink supports 8 Indian languages but reads *notification previews*, not images. **Nobody does Hindi OCR → UPI/bank+IFSC extraction → SEBI verification.** Indian investment scams arrive as screenshots in Hindi; this is the actual input modality and it is unserved.

### Ranked competitive threats

| # | Threat | Why it matters | Why it isn't you yet |
|---|---|---|---|
| **1** | **SEBI SAARTHI's SEBI Check tab** | Official, free, SEBI brand, 500K+ installs, and it legitimately owns step (c). If SEBI fixes the UPI false-negatives and adds a share sheet, your core differentiator evaporates overnight | Manual single-field lookup. No message ingestion, no OCR, no QR, no near-miss matching, no verdict card. 3.8★. Two false-negative bug reports in Aug/Sep 2026. Release notes are one line of broken English |
| **2** | **RakshaLink** | **Closest strategic competitor.** Already owns the *notification → warning → family* loop across WhatsApp/Telegram/SMS/RCS. 10K+ installs, 4.3★, 8 Indian languages, no ads, and shipping fast: v1.37→v1.50 in ~5 months added APK checking, Family Protection, alert dedup, and false-positive tuning. Accepts UPI IDs in Paste & Check today | Pure on-device heuristics. No registry. Its "Verify safely" step *sends the user away* to official channels instead of querying them — that hand-off is precisely your product |
| **3** | **Scam Shield / "Owl" (DiGiForces)** | Does (a) screenshot + WhatsApp share, (b) India-specific UPI payee-ID/amount/format validation, and emits a plain-English verdict. Conceptually the nearest thing to your flow | iOS-only, 1 rating, Canadian indie dev. No SEBI, no registry, no near-miss, no forwardable card |
| **4** | **Siren (Inedge)** | Biggest genuine Indian traction in the category: 100K+, 4.7★, 899 reviews, actively maintained | Pure on-device pattern matching. No financial-registry dimension at all. Also carries permission-trust complaints and a data-safety declaration ("shares Messages with third parties") that contradicts its own marketing |
| **5** | **ProspektLab** ⚠️ | A commercial product already scraping **multiple SEBI registries** (evidenced by `aryandigital/prospektlab-scraper`). Unknown scope — could be B2B advisor due-diligence | **Unverified.** Not investigated this session. **Highest-priority follow-up.** |
| — | ScamKavach | Closest feature list on paper: UPI ID + QR + SMS + Hindi/English + India | **5 downloads**, 360-entry offline DB, last updated March. Effectively dead |

---

## 5. Blunt risk assessment

**The moat is thin, and it is not yours.**

- Your step (c) depends entirely on continued access to a **reverse-engineered API behind a WAF that already returns 505 to HEAD requests**. Repo notes confirm datacenter-IP behaviour is *unverified*. If SEBI rotates the endpoint, hardens the WAF, or — most likely and most damaging — simply **improves SAARTHI's SEBI Check tab**, step (c) is gone and you are left with (d) + (e).
- Your step (d) is **replicable in about two weeks** by any competent team. The ~23,500-row registry mirror is public data; the fuzzy-matching logic is not proprietary. The 5.6MB SQLite mirror is an asset, not a moat.
- **RakshaLink is out-executing you on distribution.** They have the notification-listener pathway that requires a native Android build — the exact thing your `docs/ANDROID-CONVERSION.md` blueprint says you still need Capacitor 8 to obtain. They are shipping weekly. If they add one registry lookup, they reach (c)+(d) with a 10K-install head start and better retention mechanics than you.
- **The category problem is trust, not absence.** Fourteen+ low-quality AI-only apps were found, several from developers whose other products are meme sticker packs, palm-reading apps, and MBA-prep quizzes. The barrier is not "no competitor exists" — it is *"why should an Indian user trust yet another scam app with notification access?"* The only credible answer available to you is **SEBI-official verification**, which is the one component you do not control and cannot guarantee.

**Strategic implication:** lead every piece of marketing with (c)+(d) — *"We ask SEBI. We don't guess."* That is the single claim no AI-only competitor can make, and it is the claim that still holds even if the verdict card, the OCR, and the fuzzy matching all get copied. Ship the verdict card because it is your only self-propagating surface, but do not mistake it for the moat.

---

## 6. Unverified / flagged

| Item | Status |
|---|---|
| **Scamio India availability** | ⚠️ **Partially verified.** Global web app + WhatsApp bot, no geo-block observed, reachable from India. But Bitdefender publishes **no India-specific localization or Indian data source**; the site language selector defaulted to *English – United States*. Treat "available in India" as *technically reachable, not localized*. |
| **`siportal.sebi.gov.in` primary source** | ⚠️ **Could not be fetched this session** — consistent with the WAF 505 behaviour already recorded in repo notes. SEBI Check's *current* UI and field set are unverified from primary source. |
| **Sanchar Saathi download count** | ⚠️ **Unreconciled.** Play badge: 10M+. DoT's own site: 2.5Cr+ (25M) Play, 21L+ (2.1M) iOS. Government self-reporting exceeds store badge by 2.5×. |
| **UPI Shield detection method** | ⚠️ **Unverified.** Listing publishes only a tagline; no description, no method, no privacy detail beyond "shares Device IDs with third parties". Developer Grey Root Labs' other apps are Termux utilities, Virat Kohli meme stickers, and arcade games. |
| **ScamKavach "RBI lender badge"** | ⚠️ **Unverified data source.** Listing claims 360+ offline entries; the provenance of the RBI badge is not disclosed. |
| **ProspektLab** | ⚠️ **Not investigated.** Inferred solely from one 0-star scraper repo. Scope, customers, and whether it touches consumer verification are unknown. **Highest-priority follow-up.** |
| **`animeshy071-web/siportal`** | ⚠️ **Not inspected.** TypeScript, 0★, pushed 18 days ago. Name-only match; could be coincidence or could be a live SEBI integration. |
| **RakshaLink legal entity** | ⚠️ **Unverified.** Publishes as "RakshaLink Labs", Bengaluru; X handle `@mohan1411`; support `support@rakshalink.in`. Registered company name not established. Appears to be a solo or very small team. |
| **Play Store search completeness** | ⚠️ Play search results are ranked and personalized. The Tier-2 list is **not exhaustive** — it reflects three query strings (`investment scam checker`, `sebi registered check`, `upi id verify`) plus two (`scam detector india`, `digital arrest scam`). |
| **iOS download counts** | ⚠️ **Not public.** Apple exposes rating counts only. All iOS "downloads" cells are `n/a` by necessity, not by omission. |
| **Android download counts** | ⚠️ Play publishes **buckets** (100+, 1K+, 10K+, 100K+, 10M+), not exact figures. |

---

## 7. Source list

**Google Play** — `in.rakshalink.app`, `com.phishbowl`, `com.codeninja.upishield`, `com.dot.app.sancharsaathi`, `com.sebi.invapp`, `com.sebi`, `com.joinsiren.app`, `com.scamkavach.app`, `com.scamsense.app`, `com.birthdaygirl.scamchecker`; store searches `sebi registered check`, `investment scam checker`, `upi id verify`, `scam detector india`, `digital arrest scam` (all `&hl=en&gl=IN`).
**App Store (India storefront, via iTunes Search API `country=in`)** — ids `6770247571`, `6744896851`, `1497144087`, `6472626411`, `6760344064`, `6780233121`, `448142450`, `1367276365`, `6448859008`, `1022831885`, `6744879291`.
**Vendor / official** — `rakshalink.in`, `scamio.bitdefender.com`, `sancharsaathi.gov.in`.
**GitHub** — repository searches `sebi check siportal`, `siportal`, `sebi registry`, `sebi scam`, `upi fraud detection`.
