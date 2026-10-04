# Backend deployment — Oracle Cloud VPS

**Status: 🟢 LIVE** (deployed 2026-10-02)

| | |
|---|---|
| Host | `hermes` → `ubuntu@144.24.100.113` (ssh alias in `~/.ssh/config`) |
| Box | Oracle Always Free A1 · **aarch64** · Ubuntu 24.04.5 · 2 OCPU / 11 GB / 71 GB free |
| Neighbour | `omniroute` + `omniroute-redis` containers — **resource caps below exist to protect them** |
| Container | `niveshrakshak` · image `niveshrakshak:latest` · `127.0.0.1:8300` (loopback only) |
| Public URL | Cloudflare quick tunnel → `https://<random>.trycloudflare.com` (systemd `nr-tunnel.service`) |
| Registry | **23,513 rows**, seeded from the local mirror |
| SEBI Check | **`state: ok`, `fails: 0`** — verified live from this box |

## The SEBI reachability question is settled 🟢

The single biggest project risk was whether siportal.sebi.gov.in's WAF blocks
datacenter IPs. There was no public evidence either way. **Verified directly:**

```
GET  /intermediary/sebi-check          → 200, sets CA_SESSIONID
POST /intermediary/sebi-check/validate.html
     {ctype=upi-check, upi=test123@ybl}
     → {"status":"error","message":"UPI Id is not valid!",
        "errorCode":"UPI_ID_INVALID",
        "transactionId":"TXN-MUQNTFOQ-HTQ3"}     ← real TXN id = WAF accepted the POST
```

Latency from this box to siportal: **~112 ms** (Cloudflare edge for the tunnel
reports `location=bom06` = Mumbai). No fallback needed.

⚠️ Use **GET/POST only** — siportal's WAF answers `HEAD` with a non-standard
`505 BLOCKED`, which looks like an IP block but is method-based.

## Commands

```bash
./deploy/deploy.sh            # rsync + rebuild + restart + wait for health
./deploy/deploy.sh --seed     # also push the local registry mirror into the volume
sudo bash deploy/setup-timers.sh   # install the maintenance timers (once per box)
./deploy/pull-backup.sh       # pull the VPS-side DB backup to THIS machine
```

### 🔴 Scheduling uses systemd timers, NOT cron

`apt-cache policy cron` on this image returns **`Installed: (none)`** — the Oracle
Ubuntu 24.04 ARM image is systemd-timers-only. A file dropped in `/etc/cron.d` is
**silently ignored**, which is exactly what happened here: the anti-idle and backup
jobs never ran for two days, leaving the instance exposed to Oracle's idle
reclamation with no backups at all.

Installed by `deploy/setup-timers.sh` (which also deletes the dead cron.d file):

| Unit | Schedule | Notes |
|---|---|---|
| `nr-anti-idle.timer` | `OnBootSec=6min`, `OnUnitActiveSec=4h` | `Persistent=true` replays missed runs on boot |
| `nr-backup.timer` | `OnCalendar=*-*-* 03:30:00` | `Persistent=true` |

**Always verify a scheduled job actually FIRED** — `systemctl list-timers 'nr-*'`,
`journalctl -u nr-backup.service`, or `/var/log/nr-anti-idle.log`. "The unit file is
in place" proves nothing. The symptom that exposed this was a stale `as_of`
timestamp in `/api/health`.

Ad-hoc:
```bash
ssh hermes 'cd ~/niveshrakshak && sudo -n docker compose logs -f --tail=50'
ssh hermes 'curl -sS http://127.0.0.1:8300/api/health | python3 -m json.tool'
ssh hermes 'sudo -n systemctl status nr-tunnel'
```

## 🔴 Four things that will bite you

**1. Never terminate or resize the instance.**
Oracle silently halved Always Free ARM on **2026-06-15**: 4 OCPU/24 GB →
**2 OCPU/12 GB**. Your existing instance is grandfathered, but the docs say a
terminated instance *"may not be possible to recreate above the updated limit."*

**2. Idle reclamation is permanent.**
Oracle deletes an Always Free instance whose 95th-percentile CPU, network **and**
memory all stay below 10% over 7 days. A 30–40-tester app can trip that in a
quiet week — and it would take `omniroute` down with it. `deploy/anti-idle.sh`
runs every 4 h via the `nr-anti-idle.timer` systemd unit to stay above the
thresholds (tesseract warm-up + GETs to both SEBI hosts + the daily registry
refresh).

⚠️ This mitigation is only real if the timer is actually active — see the cron
warning above. Check with `systemctl list-timers 'nr-*'`.

**3. `--proxy-headers` is load-bearing.**
Behind the tunnel, `request.client.host` is the proxy's address. Without
`--proxy-headers --forwarded-allow-ips='*'` the per-IP token bucket in
`server/app.py` (30 checks / 10 min) collapses into **one global bucket** and
locks out every tester after 30 checks. It is set in the Dockerfile CMD. Safe to
trust unconditionally because compose publishes to `127.0.0.1` only.

**4. The volume directory must be owned by UID 10001, not just the DB file.**
SQLite runs in WAL mode and must **create** `nr.sqlite-wal` / `nr.sqlite-shm`
alongside the database. A root-owned directory with a 10001-owned file fails at
startup with `sqlite3.OperationalError: attempt to write a readonly database`.
`deploy.sh --seed` now does `chown -R`; if you seed by hand, do the same.

## Public URL — current state and the permanent fix

### Now: Cloudflare quick tunnel
`nr-tunnel.service` runs `cloudflared tunnel --url http://127.0.0.1:8300`.

Why a tunnel and not an open port: **Oracle's VCN Security List on this instance
allows only TCP 22 and 20128** (20128 is omniroute). Probed from outside —
443, 8300, 9119, 20129 are all blocked, and that is a *console-level* rule which
cannot be changed over SSH. A tunnel is outbound-only, so it needs no ingress
rule at all, and it gives valid HTTPS for free.

🔴 **The quick-tunnel hostname is regenerated on every restart.** Recover it with:
```bash
ssh hermes 'grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /var/log/nr-tunnel.log | tail -1'
```
Then update `web/api-config.js` and rebuild the app. Fine for testing; not fine
for 40 testers over weeks.

### Permanent: named tunnel (recommended — needs any domain, ~₹800/yr)
1. Add the domain to Cloudflare's **free** plan (nameserver change).
2. `cloudflared tunnel login` → creates `~/.cloudflared/cert.pem`.
3. `cloudflared tunnel create niveshrakshak` → a tunnel UUID + credentials JSON.
4. `config.yml`:
   ```yaml
   tunnel: <UUID>
   credentials-file: /home/ubuntu/.cloudflared/<UUID>.json
   ingress:
     - hostname: api.yourdomain.tld
       service: http://127.0.0.1:8300
     - service: http_status:404
   ```
5. `cloudflared tunnel route dns niveshrakshak api.yourdomain.tld`
6. Point `nr-tunnel.service` at `cloudflared tunnel run niveshrakshak`.
7. Set `REMOTE_API` in `web/api-config.js` to `https://api.yourdomain.tld`.

The URL is then stable forever, survives reboots, and still needs **no** VCN change.

### Alternative: open the VCN + DuckDNS + Caddy
Oracle Console → Networking → Virtual cloud networks → your VCN → Security Lists →
Add Ingress Rules: TCP 80 and 443 from `0.0.0.0/0`. Then a free
`*.duckdns.org` name + Caddy for automatic Let's Encrypt. More moving parts and
it exposes the box directly, so the named tunnel is preferable.

## Resource caps (protecting the neighbour project)

`docker-compose.yml` sets `cpus: 1.5`, `mem_limit: 2g`, `mem_reservation: 512m`.
The box has 2 OCPU and ~7.5 GB available; a tesseract OCR burst is the only real
spike and these caps keep it from starving `omniroute`.

## Backups

`deploy/backup-db.sh` runs nightly at 03:30 UTC via `nr-backup.timer` →
`~/backups/niveshrakshak/nr-*.sqlite.gz`, mode 0600, keeps 14. The registry half
is regenerable (it re-downloads from sebi.gov.in); the `checks` audit log is not.

How it snapshots: Python's `sqlite3` **online backup API** run *inside* the
container (`docker exec -i`). That is WAL-safe, needs no volume name, and needs no
extra packages — `python:3.11-slim` has no `sqlite3` CLI, and mounting the compose
volume by hand is a trap because compose prefixes it with the project name
(`niveshrakshak_nr-data`, not `nr-data`). The script then self-verifies with
`gzip -t` plus a SQLite magic-byte check and **deletes the archive if either fails**,
because a corrupt backup is worse than none — it is only discovered when needed.

⚠️ **An on-box backup does not survive instance reclamation.** Run
`./deploy/pull-backup.sh` from your laptop periodically so a copy exists off-box.
It lands in `~/backups/niveshrakshak-vps/`. Verify a copy is genuinely restorable
at least once:
```bash
zcat ~/backups/niveshrakshak-vps/nr-*.sqlite.gz | head -c 100 | xxd | head -1   # "SQLite format 3"
```

## Unrelated thing noticed while auditing the box

`redis` is listening on `0.0.0.0:6379`. That belongs to `omniroute-redis`, not to
this project, but an internet-facing Redis is a well-known cryptomining target.
Worth binding to `127.0.0.1` or enabling `requirepass` when convenient.
