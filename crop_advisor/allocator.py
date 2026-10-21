"""Module 6: land allocation. Greedy marginal allocation in 0.25-acre chunks
(a light stand-in for the LP). Constraints: plot area, irrigation water (m3),
labour (days), max share of total land per crop (diversification)."""
from .enrichment import enrich
from .ranking import recommend


def allocate(farm, profile, season, plots, water_m3, labour_days, max_share=0.6, chunk=0.25, top_n=5):
    options = []
    for p in plots:
        farm_p = {**farm, **{k: p[k] for k in ("soil_type", "ph") if p.get(k) is not None}}
        f, _ = enrich(farm_p, season)
        for r in recommend(f, profile)[:top_n]:
            e = r["econ"]
            cap = profile.get("capital_per_acre")
            if e["profit"] > 0 and not (cap and e["cost"] > cap):      # respect the budget
                # risk-adjusted value: blend expected and pessimistic (p10) profit, scaled by rank score
                value = (0.6 * e["profit"] + 0.4 * e["profit_p10"]) * (0.5 + 0.5 * r["score"])
                if value > 0:
                    options.append((value, p["name"], r))
    options.sort(key=lambda o: o[0], reverse=True)
    left = {p["name"]: float(p["acres"]) for p in plots}
    total = sum(left.values())
    if len({o[2]["crop"] for o in options}) < 2:
        max_share = 1.0
    crop_ac, alloc = {}, {}
    water, labour = water_m3, labour_days
    while True:
        for value, plot, r in options:
            size = min(chunk, left[plot])
            e = r["econ"]
            if (size <= 1e-9 or e["irrigation_m3_per_acre"] * size > water
                    or e["labour_days"] * size > labour
                    or crop_ac.get(r["crop"], 0) + size > max_share * total + 1e-9):
                continue
            alloc[(plot, r["crop"])] = alloc.get((plot, r["crop"]), 0) + size
            crop_ac[r["crop"]] = crop_ac.get(r["crop"], 0) + size
            left[plot] -= size; water -= e["irrigation_m3_per_acre"] * size; labour -= e["labour_days"] * size
            break
        else:
            break
    rows, profit = [], 0.0
    for (plot, crop), ac in alloc.items():
        r = next(o[2] for o in options if o[1] == plot and o[2]["crop"] == crop)
        profit += r["econ"]["profit"] * ac
        rows.append({"plot": plot, "crop": crop, "acres": round(ac, 2),
                     "expected_profit": round(r["econ"]["profit"] * ac)})
    return {"allocation": sorted(rows, key=lambda x: (x["plot"], -x["acres"])),
            "unallocated_acres": {k: round(v, 2) for k, v in left.items() if v > 1e-6},
            "water_used_m3": round(water_m3 - water), "labour_used_days": round(labour_days - labour),
            "expected_total_profit": round(profit)}
