"""Module 4: weighted score + plain-language reasons.
Reasons are a SHAP-like attribution: each criterion's weighted contribution is
compared with the average of the other candidates."""
from . import suitability, economics

MIN_FIT = 0.25
WEIGHTS = {   # fit, profit, water, risk   (by farmer risk tolerance)
    "low":    {"fit": .30, "profit": .20, "water": .15, "risk": .35},
    "medium": {"fit": .30, "profit": .35, "water": .15, "risk": .20},
    "high":   {"fit": .25, "profit": .50, "water": .10, "risk": .15},
}
GOOD = {
    "fit":    lambda r: f"climate, soil and pH are a strong match (suitability {r['fit']:.0%})",
    "profit": lambda r: f"expected profit is high (about Rs {r['econ']['profit']:,.0f}/acre)",
    "water":  lambda r: f"needs little water beyond rainfall ({r['econ']['water_deficit_mm']:.0f} mm)",
    "risk":   lambda r: f"income is fairly stable (risk index {r['econ']['risk']:.2f})",
}
BAD = {
    "fit":    lambda r: "conditions are only a partial match",
    "profit": lambda r: "profit is lower than the other options",
    "water":  lambda r: f"needs {r['econ']['water_deficit_mm']:.0f} mm of water beyond rainfall",
    "risk":   lambda r: f"prices/yield swing a lot (risk index {r['econ']['risk']:.2f})",
}


def recommend(f, profile):
    suit = suitability.score_all(f)
    rows = []
    for name, s in suit.items():
        if not s["eligible"] or s["fit"] < MIN_FIT:
            continue
        rows.append({"crop": name, "fit": s["fit"], "prob": s["prob"],
                     "econ": economics.evaluate(name, f, s["fit"])})
    if not rows:
        return []
    w = WEIGHTS[profile.get("risk_tolerance", "medium")]
    p = [r["econ"]["profit"] for r in rows]
    lo, hi = min(p), max(p)
    for r in rows:
        e = r["econ"]
        r["comp"] = {"fit": r["fit"],
                     "profit": (e["profit"] - lo) / (hi - lo) if hi > lo else .5,
                     "water": 1 - min(1, e["water_deficit_mm"] / e["etc_mm"]),
                     "risk": 1 - e["risk"]}
        r["score"] = sum(w[k] * r["comp"][k] for k in w)
        r["notes"] = []
        cap = profile.get("capital_per_acre")
        if cap and e["cost"] > cap:
            r["score"] *= 0.75
            r["notes"].append(f"costs Rs {e['cost']:,.0f}/acre, above your budget of Rs {cap:,.0f}")
        if e["profit_p10"] < 0 and profile.get("risk_tolerance", "medium") != "high":
            r["score"] *= 0.65 if profile.get("risk_tolerance") == "low" else 0.8
            r["notes"].append(f"in a bad season you could lose up to Rs {-e['profit_p10']:,.0f}/acre")
    mean = {k: sum(r["comp"][k] for r in rows) / len(rows) for k in w}
    for r in rows:
        delta = {k: w[k] * (r["comp"][k] - mean[k]) for k in w}
        order = sorted(delta, key=delta.get, reverse=True)
        r["why"] = [GOOD[k](r) for k in order[:2] if delta[k] > 0.005]
        worst = order[-1]
        if delta[worst] < -0.03:
            r["notes"].append(BAD[worst](r))
    return sorted(rows, key=lambda r: r["score"], reverse=True)
