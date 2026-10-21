"""Module 3: yield, price, profit, water deficit (FAO-56 style) and profit spread.
Yield stress uses FAO-33:  1 - Ya/Ym = Ky * (1 - ETa/ETc)."""
import math
from .data import CROPS

M3_PER_MM_ACRE = 4.047
EFFECTIVE_RAIN = 0.8        # share of rain the crop can use
IRRIGATION_COST_PER_M3 = 2.0  # Rs, pumping / canal charges
Z90 = 1.28


def evaluate(crop, f, fit):
    c = CROPS[crop]
    etc = c["water_mm"]
    deficit = max(0.0, etc - EFFECTIVE_RAIN * f["rainfall"])
    if f["irrigated"]:
        eta_ratio, irr_mm = 1.0, deficit
    else:
        eta_ratio, irr_mm = (etc - deficit) / etc, 0.0
    stress = max(0.1, 1 - c["ky"] * (1 - eta_ratio))
    yld = c["base_yield"] * (0.4 + 0.6 * fit) * stress           # quintal / acre
    revenue = yld * c["price"]
    irr_m3 = irr_mm * M3_PER_MM_ACRE
    cost = c["cost"] + irr_m3 * IRRIGATION_COST_PER_M3
    profit = revenue - cost
    sd = revenue * math.sqrt(c["price_cv"] ** 2 + c["yield_cv"] ** 2)
    cv = math.sqrt(c["price_cv"] ** 2 + c["yield_cv"] ** 2)
    risk = min(1.0, cv * 2 + (1 - eta_ratio) * 0.5)
    return {"yield_q": yld, "price": c["price"], "revenue": revenue, "cost": cost,
            "profit": profit, "profit_p10": profit - Z90 * sd, "profit_p90": profit + Z90 * sd,
            "profit_spread": 2 * Z90 * sd, "water_deficit_mm": deficit, "etc_mm": etc,
            "irrigation_m3_per_acre": irr_m3, "water_stress_factor": stress,
            "risk": risk, "labour_days": c["labour"]}
