"""Module 7: dated task list from crop calendar + Growing Degree Days (GDD).
Re-run build_schedule every day with the observed weather so far; stage dates
and irrigation dates shift automatically. today_tasks() applies weather rules."""
from datetime import timedelta
from .data import CROPS

STAGES = [("emergence", .06), ("vegetative", .30), ("flowering", .55), ("late_stage", .78), ("maturity", 1.0)]


def build_schedule(crop, f, sowing, observed=None):
    c, observed = CROPS[crop], observed or {}
    stage, gdd, d, si = {}, 0.0, sowing, 0
    while si < len(STAGES) and (d - sowing).days < 400:
        o = observed.get(d)
        t = (o["tmax"] + o["tmin"]) / 2 if o else f["temp"]
        gdd += max(0.0, min(t, 35) - c["gdd_base"])
        while si < len(STAGES) and gdd >= STAGES[si][1] * c["gdd_total"]:
            stage[STAGES[si][0]] = d
            si += 1
        d += timedelta(days=1)
    for n, fr in STAGES:                                   # fallback if GDD never reached
        stage.setdefault(n, sowing + timedelta(days=round(c["duration"] * fr)))
    T = []
    add = lambda d, kind, txt: T.append({"date": d, "kind": kind, "task": txt})
    add(sowing - timedelta(days=7), "land", "Land preparation; apply FYM/compost and basal fertilizer")
    add(sowing, "sowing", f"Sow {crop} (treat seed; use recommended spacing)")
    add(stage["emergence"], "scout", "Check germination and fill gaps")
    add(stage["vegetative"] - timedelta(days=5), "weeding", "First weeding")
    if not c["legume"]:
        add(stage["vegetative"], "fertilizer", "Top-dress nitrogen (split dose)")
    add(stage["flowering"] - timedelta(days=5), "spray", "Scout for pests/disease; spray only if threshold crossed")
    add(stage["flowering"], "scout", "Flowering: most water-sensitive stage - do not let the crop dry out")
    add(stage["late_stage"], "scout", "Reduce irrigation; watch for late disease")
    add(stage["maturity"], "harvest", f"Harvest {crop} (check maturity signs, dry before storage)")
    if f["irrigated"]:
        last, d = sowing, sowing + timedelta(days=1)
        while d <= stage["late_stage"]:
            o = observed.get(d)
            if o and o.get("rain_mm", 0) >= 10:
                last = d
            elif (d - last).days >= c["irr_interval"]:
                add(d, "irrigation", "Irrigate"); last = d
            d += timedelta(days=1)
    return {"crop": crop, "sowing": sowing, "stages": stage,
            "tasks": sorted(T, key=lambda t: t["date"])}


def today_tasks(sched, today, forecast):
    fc = {x["date"]: x for x in forecast}
    rain0 = fc.get(today, {}).get("rain_mm", 0)
    rain1 = fc.get(today + timedelta(days=1), {}).get("rain_mm", 0)
    out = []
    for t in sched["tasks"]:
        if t["date"] != today:
            continue
        if t["kind"] == "irrigation" and (rain0 >= 8 or rain1 >= 10):
            out.append("Skip irrigation - rain expected/received")
        elif t["kind"] in ("spray", "fertilizer") and (rain0 >= 5 or rain1 >= 10):
            out.append(f"Postpone: {t['task']} (rain would wash it off)")
        else:
            out.append(t["task"])
    tmax = fc.get(today, {}).get("tmax")
    if tmax and tmax >= CROPS[sched["crop"]]["temp"][3] - 3:
        out.append("Heat alert: light evening irrigation, avoid spraying in midday")
    return out
