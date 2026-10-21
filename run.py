"""Usage: python run.py --input sample_input.json [--today 2026-10-21]"""
import argparse, json
from datetime import date, datetime, timedelta
from crop_advisor.data import season_of
from crop_advisor.enrichment import enrich
from crop_advisor.ranking import recommend
from crop_advisor import rotation, allocator, scheduler

ap = argparse.ArgumentParser()
ap.add_argument("--input", default="sample_input.json")
ap.add_argument("--today", default=None)
ap.add_argument("--out", default="report.json")
a = ap.parse_args()

cfg = json.load(open(a.input))
farm, profile = cfg["farmer"], cfg.get("profile", {})
today = datetime.strptime(a.today, "%Y-%m-%d").date() if a.today else date.today()
sowing = datetime.strptime(cfg.get("sowing_date", str(today)), "%Y-%m-%d").date()
season = season_of(sowing.month)

# 1 enrichment
f, tags = enrich(farm, season)
print(f"\n=== 1. FEATURES for {season} season ===")
for k in f:
    print(f"  {k:15s} {str(f[k]):10s} [{tags[k]}]")

# 2-4 suitability, economics, ranking
ranked = recommend(f, profile)
print("\n=== 2-4. RANKED CROPS ===")
for i, r in enumerate(ranked, 1):
    e = r["econ"]
    print(f"{i}. {r['crop'].upper():10s} score {r['score']:.2f} | fit {r['fit']:.0%} (prob {r['prob']:.0%}) | "
          f"yield {e['yield_q']:.1f} q/ac | profit Rs {e['profit']:,.0f} "
          f"(p10 {e['profit_p10']:,.0f} .. p90 {e['profit_p90']:,.0f}) | water gap {e['water_deficit_mm']:.0f} mm")
    print("     why: " + ("; ".join(r["why"]) or "balanced option"))
    for n in r["notes"]:
        print("     careful: " + n)

# 5 rotation
rot = rotation.plan(farm, profile, season, f["organic_carbon"])
print(f"\n=== 5. 6-SEASON ROTATION (soil health now {rot['start_health']}) ===")
for p in rot["plan"]:
    print(f"  {p['season']:7s} {p['crop']:10s} soil health after: {p['soil_health']}")
print(f"  final soil health {rot['final_health']}  vs  repeating top crop {rot['baseline_final_health']} "
      f"({', '.join(rot['baseline_plan'][:3])}...)")

# 6 allocation
res = cfg.get("resources", {})
alloc = allocator.allocate(farm, profile, season, cfg["plots"], res.get("water_m3", 1e9), res.get("labour_days", 1e9))
print("\n=== 6. LAND ALLOCATION ===")
for r in alloc["allocation"]:
    print(f"  {r['plot']:12s} {r['crop']:10s} {r['acres']:5.2f} acres  expected profit Rs {r['expected_profit']:,}")
print(f"  water used {alloc['water_used_m3']} m3, labour {alloc['labour_used_days']} days, "
      f"total expected profit Rs {alloc['expected_total_profit']:,}, unallocated {alloc['unallocated_acres'] or 'none'}")

# 7 scheduler for the biggest-area crop
crops = {}
for r in alloc["allocation"]:
    crops[r["crop"]] = crops.get(r["crop"], 0) + r["acres"]
main_crop = max(crops, key=crops.get) if crops else ranked[0]["crop"]
forecast = [{**x, "date": datetime.strptime(x["date"], "%Y-%m-%d").date()} for x in cfg.get("forecast", [])]
observed = {x["date"]: x for x in forecast if x["date"] < today}
sched = scheduler.build_schedule(main_crop, f, sowing, observed)
print(f"\n=== 7. SCHEDULE for {main_crop} (sowing {sowing}) ===")
print("  stage dates: " + ", ".join(f"{k} {v}" for k, v in sched["stages"].items()))
for d in range(35):
    day = today + timedelta(days=d)
    for t in scheduler.today_tasks(sched, day, forecast):
        print(f"  {day}  {t}")

json.dump({"features": f, "tags": tags, "ranking": ranked, "rotation": rot, "allocation": alloc,
           "schedule": [{**t, "date": str(t["date"])} for t in sched["tasks"]]},
          open(a.out, "w"), indent=2, default=str)
print(f"\nFull report saved to {a.out}")
