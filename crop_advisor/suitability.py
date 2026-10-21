"""Module 2: crop fit = weighted sum of trapezoid membership scores (0-1).
Probability = softmax of fit over season-eligible crops."""
import math
from .data import CROPS

W = {"temp": .35, "rain": .25, "ph": .20, "soil": .20}
TAU = 0.15            # softmax temperature (lower = more peaked)


def trap(x, a, b, c, d):
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    return (x - a) / (b - a) if x < b else (d - x) / (d - c)


def parts(crop, f):
    c = CROPS[crop]
    rain = trap(f["rainfall"], *c["rain"])
    if f["irrigated"] and f["rainfall"] < c["rain"][1]:
        rain = 1.0                      # irrigation covers a rain shortfall
    soil = 1.0 if f["soil_type"] in c["soil_good"] else .6 if f["soil_type"] in c["soil_ok"] else .25
    return {"temp": trap(f["temp"], *c["temp"]), "rain": rain,
            "ph": trap(f["ph"], *c["ph"]), "soil": soil}


def score_all(f):
    out = {}
    for name, c in CROPS.items():
        p = parts(name, f)
        out[name] = {"fit": sum(W[k] * p[k] for k in W), "parts": p,
                     "eligible": f["season"] in c["seasons"], "prob": 0.0}
    elig = [n for n in out if out[n]["eligible"]]
    z = sum(math.exp(out[n]["fit"] / TAU) for n in elig) or 1
    for n in elig:
        out[n]["prob"] = math.exp(out[n]["fit"] / TAU) / z
    return out
