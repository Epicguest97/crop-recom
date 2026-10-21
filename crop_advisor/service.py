"""Service layer: validates a request dict, runs the advisor, returns JSON-safe results
plus a WhatsApp-ready text message. No web code here, so it is easy to test."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .data import REGIONS, CROPS, season_of
from .enrichment import enrich
from .ranking import recommend
from . import rotation, allocator, scheduler

SOILS = {"sandy", "loam", "clay", "red", "black", "silt"}
RISK = {"low", "medium", "high"}
TZ = ZoneInfo("Asia/Kolkata")
DEFAULT_CAPITAL = 40000   # Rs/acre assumed when the farmer gives no budget


class ValidationError(ValueError):
    pass


def _num(d, key, lo, hi, default=None):
    v = d.get(key)
    if v in (None, ""):
        return default
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"'{key}' must be a number")
    if not lo <= v <= hi:
        raise ValidationError(f"'{key}' must be between {lo} and {hi}")
    return v


def _bool(v, default=False):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "yes", "y", "1", "haan"):
        return True
    if s in ("false", "no", "n", "0", "nahi"):
        return False
    raise ValidationError("'irrigated' must be true/false or yes/no")


def parse(payload):
    """Turn a raw request body into (farm, profile, sowing_date, extras)."""
    if not isinstance(payload, dict):
        raise ValidationError("body must be a JSON object")
    state = str(payload.get("state", "")).strip()
    if not state:
        raise ValidationError("'state' is required (e.g. Karnataka)")
    soil = payload.get("soil_type")
    if soil not in (None, ""):
        soil = str(soil).strip().lower()
        if soil not in SOILS:
            raise ValidationError(f"'soil_type' must be one of {sorted(SOILS)}")
    else:
        soil = None
    risk = str(payload.get("risk_tolerance", "medium")).strip().lower()
    if risk not in RISK:
        raise ValidationError("'risk_tolerance' must be low, medium or high")

    today = datetime.now(TZ).date()
    sd = payload.get("sowing_date")
    if sd in (None, ""):
        sowing = today
    else:
        try:
            sowing = datetime.strptime(str(sd), "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError("'sowing_date' must be YYYY-MM-DD")

    farm = {"state": state, "soil_type": soil,
            "ph": _num(payload, "ph", 3.5, 10),
            "organic_carbon": _num(payload, "organic_carbon", 0.05, 3),
            "temp": _num(payload, "temp", -5, 50),
            "rainfall": _num(payload, "rainfall", 0, 5000),
            "irrigated": _bool(payload.get("irrigated"))}
    profile = {"risk_tolerance": risk,
               "capital_per_acre": _num(payload, "capital_per_acre", 1000, 1e7, DEFAULT_CAPITAL)}
    extras = {"acres": _num(payload, "acres", 0.1, 10000, 1.0),
              "water_m3": _num(payload, "water_m3", 0, 1e9, 1e9),
              "labour_days": _num(payload, "labour_days", 0, 1e9, 1e9),
              "plots": payload.get("plots"), "today": today}
    return farm, profile, sowing, extras


def _clean(r):
    e = r["econ"]
    return {"crop": r["crop"], "score": round(r["score"], 3), "fit": round(r["fit"], 3),
            "yield_quintal_per_acre": round(e["yield_q"], 1),
            "profit_per_acre": round(e["profit"]), "profit_low": round(e["profit_p10"]),
            "profit_high": round(e["profit_p90"]), "water_gap_mm": round(e["water_deficit_mm"]),
            "risk_index": round(e["risk"], 2), "why": r["why"], "cautions": r["notes"]}


def whatsapp_text(ranked, season, state, tags):
    if not ranked:
        return "Sorry, no crop suits these conditions right now. Please try a different sowing date."
    est = [k for k in ("temp", "rainfall", "ph", "soil_type") if tags[k] == "estimated"]
    lines = [f"*Crop advice - {state.title()}, {season} season*", ""]
    medals = ["1.", "2.", "3."]
    for m, r in zip(medals, ranked[:3]):
        e = r["econ"]
        lines.append(f"{m} *{r['crop'].title()}*  - est. profit Rs {e['profit']:,.0f}/acre "
                     f"(range {e['profit_p10']:,.0f} to {e['profit_p90']:,.0f})")
        if r["why"]:
            lines.append("   Why: " + "; ".join(r["why"]))
        for c in r["notes"]:
            lines.append("   Note: " + c)
        lines.append("")
    lines.append(f"Best choice: *{ranked[0]['crop'].title()}*")
    if est:
        lines.append("(Estimated from regional averages: " + ", ".join(est) + ". Share them for better accuracy.)")
    return "\n".join(lines)


def get_recommendation(payload):
    farm, profile, sowing, _ = parse(payload)
    season = season_of(sowing.month)
    f, tags = enrich(farm, season)
    ranked = recommend(f, profile)
    return {"season": season, "best_crop": ranked[0]["crop"] if ranked else None,
            "ranking": [_clean(r) for r in ranked[:5]],
            "features": {k: {"value": f[k], "source": tags[k]} for k in f},
            "message": whatsapp_text(ranked, season, farm["state"], tags)}


def get_full_plan(payload):
    farm, profile, sowing, x = parse(payload)
    season = season_of(sowing.month)
    f, tags = enrich(farm, season)
    ranked = recommend(f, profile)
    if not ranked:
        raise ValidationError("no suitable crop for these conditions")
    plots = x["plots"] or [{"name": "Farm", "acres": x["acres"]}]
    for p in plots:
        if not isinstance(p, dict) or "name" not in p or "acres" not in p:
            raise ValidationError("each plot needs 'name' and 'acres'")
    rot = rotation.plan(farm, profile, season, f["organic_carbon"])
    alloc = allocator.allocate(farm, profile, season, plots, x["water_m3"], x["labour_days"])
    area = {}
    for r in alloc["allocation"]:
        area[r["crop"]] = area.get(r["crop"], 0) + r["acres"]
    main = max(area, key=area.get) if area else ranked[0]["crop"]
    sched = scheduler.build_schedule(main, f, sowing)
    upcoming = [{"date": str(t["date"]), "task": t["task"]} for t in sched["tasks"]
                if t["date"] >= x["today"]][:10]
    return {"season": season, "best_crop": ranked[0]["crop"],
            "ranking": [_clean(r) for r in ranked[:5]], "rotation": rot, "allocation": alloc,
            "schedule": {"crop": main, "stages": {k: str(v) for k, v in sched["stages"].items()},
                         "next_tasks": upcoming},
            "message": whatsapp_text(ranked, season, farm["state"], tags)}


def meta():
    return {"states": sorted(k for k in REGIONS if k != "default"),
            "soil_types": sorted(SOILS), "crops": sorted(CROPS)}
