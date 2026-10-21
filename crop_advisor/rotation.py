"""Module 5: 6-season rotation by beam search + Soil Health Score.
State = (N index, organic-matter index, pest pressure, previous family), all 0-1."""
from .data import CROPS, SEASONS
from .enrichment import enrich
from .ranking import recommend

FALLOW_VALUE = 0.15
DH_WEIGHT = 0.02          # value of one Soil Health point


def health(st):
    return 100 * (0.4 * st["n"] + 0.3 * st["om"] + 0.3 * (1 - st["pest"]))


def step(st, crop):
    cl = lambda x: max(0.0, min(1.0, x))
    if crop is None:                                  # fallow / green manure
        return {"n": cl(st["n"] + .04), "om": cl(st["om"] + .005), "pest": st["pest"] * .5, "fam": None}
    c = CROPS[crop]
    pest = st["pest"] + .2 if c["family"] == st["fam"] else st["pest"] * .6
    return {"n": cl(st["n"] + c["n_effect"]), "om": cl(st["om"] + c["om_effect"]),
            "pest": cl(pest), "fam": c["family"]}


def plan(farm, profile, start_season, organic_carbon, n_seasons=6, beam=5):
    i0 = SEASONS.index(start_season)
    seasons = [SEASONS[(i0 + i) % 3] for i in range(n_seasons)]
    options = []
    for i, s in enumerate(seasons):
        f, _ = enrich(farm, s, use_measured_weather=(i == 0))
        options.append(recommend(f, profile)[:6])
    s0 = {"n": .5, "om": min(1.0, organic_carbon), "pest": .1, "fam": None}

    def run(choose):
        beams = [(0.0, s0, [])]
        for i in range(n_seasons):
            nxt = []
            for tot, st, path in beams:
                for r in choose(i):
                    ns = step(st, r["crop"] if r else None)
                    val = (r["score"] if r else FALLOW_VALUE) + DH_WEIGHT * (health(ns) - health(st))
                    nxt.append((tot + val, ns, path + [{"season": seasons[i], "crop": r["crop"] if r else "fallow",
                                                         "score": round(r["score"], 3) if r else None,
                                                         "soil_health": round(health(ns), 1)}]))
            beams = sorted(nxt, key=lambda b: b[0], reverse=True)[:beam]
        return beams[0]

    best = run(lambda i: options[i] + [None])
    mono = run(lambda i: options[i][:1] or [None])      # always top crop: baseline
    return {"start_health": round(health(s0), 1), "plan": best[2],
            "final_health": best[2][-1]["soil_health"],
            "baseline_plan": [p["crop"] for p in mono[2]],
            "baseline_final_health": mono[2][-1]["soil_health"]}
