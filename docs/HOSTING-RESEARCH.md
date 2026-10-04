# Hosting Research — Oracle Cloud Always Free vs Alternatives (Oct 2026)

Research date: 2026-10-02. Method: 11 web searches + 2 page scrapes (Firecrawl). Scope: hosting the NiveshRakshak FastAPI service (tesseract + zbar + ~6MB SQLite, outbound HTTPS to sebi.gov.in / siportal.sebi.gov.in, 30–40 testers) on an existing Oracle Cloud Always Free VPS vs paid alternatives.

---

## 1. Oracle Cloud Always Free — status in 2026 (MAJOR CHANGE)

**Oracle halved the Always Free ARM allocation effective June 15, 2026, with no public announcement.**

| Resource | Before Jun 2026 | Now (Oct 2026) |
|---|---|---|
| Ampere A1 (VM.Standard.A1.Flex) | 3,000 OCPU-hrs + 18,000 GB-hrs/mo = **4 OCPU / 24 GB** | 1,500 OCPU-hrs + 9,000 GB-hrs/mo = **2 OCPU / 12 GB** |
| AMD micro (VM.Standard.E2.1.Micro) | 2× VMs, 1/8 OCPU (burstable), 1 GB each | **unchanged** |
| Block volume storage | 200 GB total Always Free | **unchanged** |
| Free trial | $300 / 30 days | unchanged |

Sources:
- Oracle docs (current text): "All tenancies get the first 1,500 OCPU hours and 9,000 GB hours per month for free… equivalent to 2 OCPUs and 12 GB of memory" — https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- InfoQ, Jul 3 2026: "Oracle Quietly Halves Free Tier Ampere A1 Compute Limits with No Public Announcement" — https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/
- terminalbytes.com, Jun 26 2026 (before/after table; "AMD micro instances and the 200 GB of storage are untouched"; enforcement "isn't consistent" — many still run 4/24 at $0) — https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/
- Linuxiac: https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/
- Reddit (Oracle-support confirmation thread): https://www.reddit.com/r/oraclecloud/comments/1ubk2qy/new_always_free_tier_limits_21june2026_update/

Key fine print and consequences:
- **"Always Free" is still unlimited-duration** (Oracle Free Tier FAQ: "The Always Free services are available for an unlimited period of time") — https://www.oracle.com/cloud/free/faq/
- **Grandfathering trap**: existing 4/24 instances keep running (enforcement inconsistent as of mid-2026), but Oracle's docs say: *"If an existing resource is terminated, it may not be possible to recreate resources above the updated Always Free limit."* → **Do not terminate or resize the existing instance casually.**
- Free-only accounts: instances exceeding new limits "are shut down until the user manually resizes" (InfoQ). PAYG accounts: Reddit reports Oracle Support confirmed new limits apply to PAYG too (overage may be billed); InfoQ says PAYG "may still use 4 OCPUs and 24 GB at no charge" — **contradictory, unverified**.

### Idle reclamation (official policy, unchanged)
- Oracle docs: "Idle Always Free compute instances may be reclaimed by Oracle." Idle criteria over a 7-day window: **95th-percentile CPU < 10% AND network < 10% AND memory < 10% (A1 shapes only)** — https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm + https://stackoverflow.com/questions/71209485
- Reclaimed = **permanently deleted, unrecoverable** (Oracle FAQ).
- Multiple user reports of actual reclamation: https://www.reddit.com/r/oraclecloud/comments/12blebo/ , https://lowendtalk.com/discussion/184161/oracle-may-reclaim-your-idle-vps
- Historical workaround: upgrade to Pay-As-You-Go (PAYG accounts were exempt from idle reclamation). Whether PAYG still gets favorable treatment after the June 2026 change is **unverified/contradictory**.
- A low-traffic service for 30–40 testers **can plausibly trip the idle criteria** in quiet weeks → active mitigation needed (see §6).

## 2. India regions and ARM capacity

- India regions: **Mumbai (ap-mumbai-1)** and **Hyderabad (ap-hyderabad-1)**. Home region is fixed at signup; Always Free resources live in the home region.
- **Chronic "Out of capacity" error for A1.Flex on free accounts is well documented through 2025–2026** (all regions, not India-specific in the sources found):
  - wirywolf.com, May 7 2025: https://wirywolf.com/2025/05/oracle-cloud-ampere-instances-out-of-capacity
  - Ampere community forum thread: https://community.amperecomputing.com/t/how-to-get-around-the-out-of-capacity-error-on-the-always-free-tier-of-oci/3432
  - Retry-script workaround: https://github.com/hitrov/oci-arm-host-capacity
  - Reddit (2025–26): "it's almost impossible to get anything on the free tier even with scripts, and the solution is to upgrade to PAYG" — https://www.reddit.com/r/oraclecloud/comments/1pyoqwb/
  - YouTube, Apr 2026: "Fix Oracle Cloud Out of Host Capacity Error for Free Tier (2026)" — Oracle "often reserves its limited ARM and AMD capacity for Pay-As-You-Go customers" — https://www.youtube.com/watch?v=jXFdB45rn6k
- **Mumbai/Hyderabad-specific 2025–26 reports: NOT found in this pass (flagged unverified).** The general scarcity is proven; India regions are commonly believed to be among the tightest, but no direct citation was captured.
- Practical implication: since the developer **already has the instance**, capacity only matters for creating NEW instances or after a termination — and post-June-2026 a terminated 4/24 instance likely cannot be recreated at the old size (§1).

## 3. arm64 (aarch64) suitability for tesseract/zbar/Python

- **tesseract-ocr**: official Ubuntu arm64 builds exist (e.g. tesseract-ocr 5.3.0-1 arm64 on Launchpad: https://code.launchpad.net/ubuntu/lunar/arm64/tesseract-ocr/5.3.0-1); pkgs.org lists aarch64 packages for Debian/Ubuntu/Alpine/Void: https://pkgs.org/download/tesseract-ocr
- **zbar-tools**: Debian package built for all architectures incl. arm64: https://packages.debian.org/zbar-tools
- **Docker**: standard base images (debian/ubuntu/python) are multi-arch arm64 → `apt-get install tesseract-ocr zbar-tools` works natively on A1.
- **Pillow**: ships official aarch64 manylinux wheels (the oft-cited issue https://github.com/python-pillow/Pillow/issues/5202 is from 2020 and concerns self-compiled wheels in Docker builds, not current PyPI wheels).
- **rapidfuzz**: ships aarch64 manylinux wheels (PyPI files list — low risk; verify at build time).
- The repo bundles its own tessdata (`server/tessdata/eng+hin.traineddata`) — architecture-independent.
- Performance: Ampere A1 cores handle tesseract fine; OCR is bursty CPU work. 2 OCPU is adequate for 30–40 testers (a few OCR requests/min at peak).
- Verdict: **no arm64 blockers found.**

## 4. Network reachability of SEBI portals from cloud IPs — THE critical unknown

**Direct evidence that sebi.gov.in / siportal.sebi.gov.in block cloud or non-Indian IPs: NONE found.** Equally, no evidence they allow them. Summary of what exists:

1. **siportal WAF is real, custom, and aggressive.** Independent security analysis (published 2026-06-05, disclosed to CERT-In + NCIIPC): *"The SI Portal (siportal.sebi.gov.in) returns HTTP 505 BLOCKED for all requests — an unusual response that suggests a custom security layer rather than standard WAF behavior."* — https://nanobot.srik.me/blog/sebi-security-analysis/ . The analysis says nothing about IP-range or geo blocking.
2. **Own probe (residential IP, 2026-10-01, repo memory):** HEAD → 505, GET → 200 with plain curl UA; www.sebi.gov.in is plain Apache. → The 505 is **method/UA-triggered from residential IPs**, not necessarily IP-reputation-triggered. The nanobot analyst likely got 505 on "all requests" because their tooling used blocked methods/UAs.
3. **Indian financial sites DO block datacenter IPs in general.** Documented for NSE: "Why my program to scrape NSE website gets blocked in servers but works locally" — https://stackoverflow.com/questions/67010968 (related questions). Pattern: exchange/regulator-adjacent sites block AWS/GCP/Azure ranges.
4. **SEBI's regulatory posture is hostile to dynamic cloud IPs** in the trading-API context: SEBI's static-IP mandate is live; brokers reject API calls from unregistered IPs — https://www.quotaguard.com/blog/sebis-static-ip-mandate-is-live-fix-your-cloud-trading-bot-now (about broker APIs, NOT the sebi.gov.in website — do not conflate).
5. **Oracle Cloud IPs are commonly blocklisted by WAFs generally.** Cloudflare community: "Aggressively blocking Oracle IPs… this public IP prefix is blocklisted in some way by Cloudflare. A lot of websites using Cloudflare [block it]" — https://community.cloudflare.com/t/aggressively-blocking-oracle-ips/634438 . Oracle publishes its full public IP ranges as JSON (trivial for any WAF to block by CIDR/ASN): https://docs.oracle.com/en-us/iaas/Content/General/Concepts/addressranges.htm . OCI free-tier ranges also carry spam/abuse reputation.

**Conclusion:** the blocking question cannot be answered from public sources. It is a **day-one empirical test**: from the actual Oracle instance, `curl` a GET to siportal.sebi.gov.in (correct UA, no HEAD) and to www.sebi.gov.in registry endpoints, and compare against the residential result. If siportal blocks the Oracle IP, the product's primary check dies on that host — this single fact outweighs all pricing considerations. Note: moving to Fly.io/DO/Vultr does **not** automatically fix it — those are datacenter IPs too (Indian DC IPs may fare better only if the filter is geo-based; unknown).

## 5. Alternatives (small always-on Docker service, persistent disk, India-preferred, <$10/mo)

| Provider | India region | Realistic config for this app | Est. $/mo | Notes |
|---|---|---|---|---|
| **Fly.io** | Mumbai (BOM) historically; **not present in the compute-pricing region dropdown scraped 2026-10-01 — verify** | shared-cpu-2x/512MB or 4x/1GB + 1GB volume | **$4.05–7.95** | Official prices (https://fly.io/pricing/): 1x/256MB $1.94, 2x/512MB $3.89, 4x/1GB $7.78; volumes $0.15/GB/mo; egress India in premium tier (~$0.04+/GB, row truncated). 256MB is too small for tesseract — budget ≥512MB. **Free tier contradictory:** runxbuild.com (2026) says free Hobby = 3×256MB + 3GB volumes; expresstech.io (2026) says free tier removed for new customers (legacy only). Official page shows unit pricing only → assume PAYG. |
| **DigitalOcean** | **Bangalore (BLR1)** — only India region, since 2016 (official FAQ) | 1GB basic droplet | **~$6** (2GB ~$12) | Official: bundled plans "from $4/mo"; per-second billing from Jan 1 2026 — https://www.digitalocean.com/pricing/droplets . Exact current 1GB/2GB India prices not captured — verify. |
| **Vultr** | **Mumbai, Delhi, Bengaluru** (3 India regions) | 1GB IPv4 | **~$5–6** | From $2.50/mo (IPv6-only) — https://northflank.com/blog/best-digitalocean-alternatives-2026 ; cloudpe.com (2026) confirms 3 India regions. |
| **Linode/Akamai** | "Reportedly Mumbai" per cloudpe — **likely Chennai; verify** | Nanode 1GB | **$5** | https://northflank.com/blog/best-digitalocean-alternatives-2026 |
| **Hetzner** | **No India region** (EU/US/Singapore) | CX-series 2GB | **from €3.79** | Cheapest quality option; Singapore ≈ 100–120ms to India; foreign DC IP — worst case for the SEBI geo-blocking unknown. |
| **AWS** | Mumbai (ap-south-1) | t4g.micro etc. | **$0 for ≤6 months, then paid** | **Free tier replaced Jul 15 2025**: new accounts get $100 (+up to $100 earned) credits; Free plan expires after **6 months or credit exhaustion, then account closes automatically**; no more 12-month free EC2 — https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html , https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits/ . Not viable for a perpetual free VPS. |
| **E2E Networks** | India (Delhi/NCR etc.) | small VPS | **unverified** | India-based, GPU/AI-focused; pricing not captured this pass. |
| Indian budget resellers (e.g. CloudPe) | Mumbai/Pune/Delhi/Bengaluru | — | ~₹1,182/mo claimed | Source is CloudPe's own marketing blog — treat with caution: https://www.cloudpe.com/blog/digitalocean-alternatives-india/ |

## 6. Two projects on one Always Free Oracle instance

- **RAM/CPU**: Even at the NEW 2 OCPU / 12 GB limit, this is ample: FastAPI+uvicorn ≈ 100–200 MB, tesseract ≈ 200–400 MB per OCR burst (single-threaded, seconds), SQLite ≈ nothing, 30–40 testers ≈ negligible concurrency. An existing grandfathered 4/24 instance is luxurious. The AMD micros (1 GB) would NOT be enough.
- **Isolation**: run as two separate Docker containers (or two compose projects), each with `mem_limit`/`cpus` caps so OCR bursts can't starve the other project; or two systemd services if native. Keep the SQLite file on the block volume (persistent across reboots/stops).
- **Real risks are not contention — they are platform risks:**
  1. **Idle reclamation** (§1): a lightly-used box can hit <10% 95th-percentile CPU/net/mem over 7 days → permanent deletion. Mitigate: the two projects together probably suffice; add a periodic real workload (e.g. nightly registry refresh — the repo already has `tools/refresh_registry.py` — plus a small OCR self-test) to keep utilization honest. Or upgrade to PAYG (historically exempt from idle reclamation; post-Jun-2026 treatment unverified).
  2. **No-recreate trap**: if the instance is ever reclaimed/terminated, recreating at 4/24 may be impossible (§1). Keep off-box backups (the 6MB SQLite + registry are trivial to back up to object storage/GitHub nightly).
  3. **Capacity** only bites on new creates/resizes in India regions (§2).

---

## Recommendation

**Keep the existing Oracle VPS as the primary host — conditionally.** Rationale: it already exists (capacity problem solved), 2/12 GB post-cut is still enough for FastAPI + tesseract + the other project, it's $0, and if it's in Mumbai/Hyderabad it has an *Indian* IP — plausibly the best-case datacenter IP for the SEBI portals. The June 2026 cut does not break this workload.

Conditions / action list:
1. **Day-one reachability test from the instance itself** (the single decisive unknown, §4): GET (never HEAD) to siportal.sebi.gov.in with the working curl UA, plus the www.sebi.gov.in registry URLs. Compare with residential results. If blocked → fall back immediately.
2. **Never terminate/resize the existing instance** without accepting a probable downgrade to 2/12 on recreate.
3. **Idle-reclamation insurance**: ensure sustained >10% utilization signals (nightly registry refresh + OCR self-test cron), and take **nightly off-box backups** of the SQLite/registry.
4. **Pre-built fallback** (deployable in <1 day, Docker image is portable): Fly.io at $4–8/mo (verify Mumbai region availability for new machines) or DigitalOcean Bangalore 1GB (~$6/mo) or Vultr Mumbai (~$5–6/mo). Remember: these are datacenter IPs too — if siportal blocks Oracle's ranges specifically, an Indian DC IP (DO/Vultr) is the best next bet; if it blocks all DC IPs, only a residential-proxy path for the SEBI leg works.
5. Skip AWS (6-month credit model, then account closure) and Hetzner (no India region) for this use case.

## Unverified / flagged
- Mumbai/Hyderabad-specific ARM capacity reports (general scarcity proven; India-specific anecdote not captured).
- Fly.io: Mumbai region current availability for new machines; free-tier status for new accounts (sources contradict); exact India egress rate (table row truncated).
- Exact current DO/Vultr/Linode 1–2GB India-tier prices (third-party figures); Linode India region city (Mumbai vs Chennai).
- E2E Networks pricing.
- Whether PAYG accounts remain exempt from idle reclamation and/or can run 4/24 free after Jun 15 2026 (contradictory reports).
- siportal.sebi.gov.in behavior from ANY datacenter IP — zero public evidence either way; empirical test required.
