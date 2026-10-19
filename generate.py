"""Bygger docs/aarch.ics ud fra Moodle kalenderen og config.json.

Kør lokalt:  python generate.py            (bruger kun den gemte cache)
GitHub:      MOODLE_URL sættes som hemmelighed (secret).
"""
import json, os, re, urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TZ = ZoneInfo(CFG["tidszone"])
CACHE = ROOT / "data" / "moodle_cache.json"
OUT = ROOT / "docs" / "aarch.ics"
UTC = timezone.utc


# ---------- Moodle ----------
def parse_ics(text):
    text = text.replace("\r\n", "\n")
    lines = []
    for l in text.split("\n"):
        if l[:1] in (" ", "\t") and lines:
            lines[-1] += l[1:]
        else:
            lines.append(l)
    out, cur = [], None
    for l in lines:
        if l == "BEGIN:VEVENT":
            cur = {}
        elif l == "END:VEVENT":
            if cur:
                out.append(cur)
            cur = None
        elif cur is not None and ":" in l:
            k, v = l.split(":", 1)
            cur[k.split(";")[0]] = v.strip()
    return out


def to_dt(v):
    if v.endswith("Z"):
        return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if "T" in v:
        return datetime.strptime(v, "%Y%m%dT%H%M%S").replace(tzinfo=TZ)
    return datetime.combine(datetime.strptime(v, "%Y%m%d").date(), time(0), TZ)


def slim(e):
    """Gem kun det nødvendige: tider og to flag. Ingen titler eller lokaler."""
    s = e.get("SUMMARY", "").replace("\\", "").lower()
    return {
        "start": to_dt(e["DTSTART"]).astimezone(UTC).isoformat(),
        "slut": to_dt(e.get("DTEND", e["DTSTART"])).astimezone(UTC).isoformat(),
        "unit": "unitmøde" in s,
        "afslutning": s if "afslutning" in s else "",
    }


def update_cache():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    url = os.environ.get("MOODLE_URL")
    if not url:
        print("Ingen MOODLE_URL, bruger cache")
        return cache
    req = urllib.request.Request(url, headers={"User-Agent": "aarch-kalender"})
    text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    feed = {e["UID"]: slim(e) for e in parse_ics(text) if "UID" in e and "DTSTART" in e}
    if feed:
        days = [datetime.fromisoformat(v["start"]).astimezone(TZ).date() for v in feed.values()]
        lo, hi = min(days), max(days)
        # Aflyste aftaler inden for feedets periode fjernes, resten bevares som historik
        for uid in list(cache):
            d = datetime.fromisoformat(cache[uid]["start"]).astimezone(TZ).date()
            if lo <= d <= hi and uid not in feed:
                del cache[uid]
        cache.update(feed)
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    print(f"Moodle: {len(feed)} aftaler i feed, {len(cache)} i cache")
    return cache


# ---------- hjælpere ----------
D = date.fromisoformat
hm = lambda s: time.fromisoformat(s)
local = lambda d, t: datetime.combine(d, t, TZ)


def weekdays(a, b):
    d = a
    while d <= b:
        if d.weekday() < 5:
            yield d
        d += timedelta(1)


def fmt(dt_):
    return dt_.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    b, out = line.encode("utf-8"), []
    while len(b) > 75:
        cut = 75 if not out else 74
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode())
        b = b[cut:]
    out.append(b.decode())
    return "\r\n ".join(out)


# ---------- byg ----------
def build():
    cache = update_cache()
    moodle = [(datetime.fromisoformat(v["start"]), datetime.fromisoformat(v["slut"]), v) for v in cache.values()]
    mdays = [a.astimezone(TZ).date() for a, _, _ in moodle]
    horizon = max(mdays) if mdays else date.min

    events = []  # (sortkey, props, alarm_days)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    # Faste begivenheder
    busy_timed, blocked_days = [], set()
    for i, b in enumerate(CFG["begivenheder"]):
        fra = D(b["fra"]); til = D(b.get("til", b["fra"]))
        p = [("UID", f"aarch-fast-{fra:%Y%m%d}-{i}@kalender"), ("SUMMARY", b["navn"])]
        if "start" in b:
            s, e = local(fra, hm(b["start"])), local(fra, hm(b["slut"]))
            p += [("DTSTART", fmt(s)), ("DTEND", fmt(e))]
            busy_timed.append((s, e, {"unit": False}))
        else:
            p += [("DTSTART;VALUE=DATE", f"{fra:%Y%m%d}"), ("DTEND;VALUE=DATE", f"{til + timedelta(1):%Y%m%d}")]
            d = fra
            while d <= til:
                blocked_days.add(d)
                d += timedelta(1)
        p.append(("TRANSP", "TRANSPARENT" if b.get("ledig") else "OPAQUE"))
        events.append((p[2][1], p, b.get("paamindelse_dage")))

    day_end_t, no_start_t = hm(CFG["dag_slut"]), hm(CFG["ingen_start_efter"])
    nomoodle_t = hm(CFG["dag_start_uden_moodle"])
    gap_min = timedelta(minutes=CFG["min_hul_minutter"])
    gap_unit = timedelta(minutes=CFG["min_hul_ved_unitmoede_minutter"])

    for f in CFG["faser"]:
        navn, key = f["navn"], f.get("afslutning", f["navn"]).lower()
        band = []
        for d in weekdays(D(f["fra"]), D(f["til"])):
            if d in blocked_days:
                continue
            if d > horizon:  # Moodle har endnu ikke aftaler så langt frem
                band.append(d)
                continue
            day = sorted(x for x in moodle + busy_timed if x[0].astimezone(TZ).date() == d)
            end = local(d, day_end_t)
            stop = False
            for a, _, v in day:
                if key in v.get("afslutning", ""):
                    end, stop = min(end, a), True
            if day:
                first = day[0][0]
                cur = max(b for a, b, _ in day if a == first)
                prev_unit = any(v["unit"] for a, _, v in day if a == first)
            else:
                cur, prev_unit = local(d, nomoodle_t), False
            gaps = []
            for a, b, v in day:
                if b <= cur:
                    prev_unit = prev_unit or v["unit"]
                    continue
                if a > cur:
                    gaps.append((cur, a, prev_unit or v["unit"]))
                cur, prev_unit = max(cur, b), v["unit"]
            gaps.append((cur, end, False))
            for a, b, unit in gaps:
                b = min(b, end)
                if b <= a or a.astimezone(TZ).time() >= no_start_t:
                    continue
                if b - a < (gap_unit if unit else gap_min):
                    continue
                events.append((fmt(a), [("UID", f"aarch-fase-{fmt(a)}@kalender"), ("SUMMARY", navn),
                               ("DTSTART", fmt(a)), ("DTEND", fmt(b)), ("TRANSP", "TRANSPARENT")], None))
            if stop:
                break
        # dage uden Moodle data: heldagsbånd pr. uge
        weeks = {}
        for d in band:
            weeks.setdefault(d.isocalendar()[:2], []).append(d)
        for ds in weeks.values():
            events.append((f"{ds[0]:%Y%m%d}", [("UID", f"aarch-baand-{ds[0]:%Y%m%d}@kalender"), ("SUMMARY", navn),
                           ("DTSTART;VALUE=DATE", f"{ds[0]:%Y%m%d}"),
                           ("DTEND;VALUE=DATE", f"{ds[-1] + timedelta(1):%Y%m%d}"), ("TRANSP", "TRANSPARENT")], None))

    events.sort(key=lambda x: x[0])
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AARCH 1. aar//DA", "CALSCALE:GREGORIAN",
           "METHOD:PUBLISH", f"X-WR-CALNAME:{CFG['kalendernavn']}", f"X-WR-TIMEZONE:{CFG['tidszone']}",
           "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    for _, p, alarm in events:
        out.append("BEGIN:VEVENT")
        out.append(f"DTSTAMP:{stamp}")
        for k, v in p:
            out.append(fold(f"{k}:{esc(v) if k == 'SUMMARY' else v}"))
        if alarm:
            out += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Påmindelse", f"TRIGGER:-P{alarm}D", "END:VALARM"]
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\r\n".join(out) + "\r\n", encoding="utf-8", newline="")
    (OUT.parent / "sidst_opdateret.txt").write_text(datetime.now(TZ).isoformat(timespec="minutes") + "\n")
    print(f"Skrev {len(events)} begivenheder til {OUT}")


if __name__ == "__main__":
    build()
