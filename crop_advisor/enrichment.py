"""Module 1: fill missing inputs and tag every value measured / estimated.
To use real APIs, replace `_estimate` with calls to a weather/soil service."""
from .data import REGIONS


def _estimate(region, key, season):
    r = REGIONS.get(region, REGIONS["default"])
    if key == "temp":
        return r[season][0]
    if key == "rainfall":
        return r[season][1]
    return {"soil_type": r["soil"], "ph": r["ph"], "organic_carbon": r["oc"], "irrigated": r.get("irrigated", False)}[key]


def enrich(farm, season, use_measured_weather=True):
    """Returns (values, tags). Farmer-given climate numbers only apply to the
    season they were measured for (use_measured_weather)."""
    region = str(farm.get("state", "")).strip().lower()
    if region not in REGIONS:
        region = "default"
    values, tags = {"season": season}, {"season": "measured"}
    for key in ("temp", "rainfall", "ph", "soil_type", "organic_carbon", "irrigated"):
        v = farm.get(key)
        weather = key in ("temp", "rainfall")
        if v is not None and (use_measured_weather or not weather):
            values[key], tags[key] = v, "measured"
        else:
            values[key], tags[key] = _estimate(region, key, season), "estimated"
    return values, tags
