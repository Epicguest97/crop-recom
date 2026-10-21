"""Crop knowledge base. All numbers are ILLUSTRATIVE defaults - replace them with
local agronomy / mandi / cost-of-cultivation data before real use.

Trapezoid tuples = (abs_min, optimum_low, optimum_high, abs_max).
"""
SEASONS = ["kharif", "rabi", "zaid"]          # Jun-Oct, Nov-Mar, Apr-May


def season_of(month):
    return "kharif" if 6 <= month <= 10 else "rabi" if (month >= 11 or month <= 3) else "zaid"


def _c(family, seasons, temp, rain, ph, good, ok, etc, dur, yld, price, cost, pcv, ycv,
       labour, n_eff, om_eff, base, ky, irr_int, legume=False):
    return dict(family=family, seasons=seasons, temp=temp, rain=rain, ph=ph,
                soil_good=good, soil_ok=ok, water_mm=etc, duration=dur,
                base_yield=yld, price=price, cost=cost, price_cv=pcv, yield_cv=ycv,
                labour=labour, n_effect=n_eff, om_effect=om_eff, gdd_base=base,
                ky=ky, irr_interval=irr_int, legume=legume,
                gdd_total=dur * (((temp[1] + temp[2]) / 2) - base))


CROPS = {
 #            family    seasons            temp              rain                  pH
 "rice":      _c("cereal", ["kharif"],        (15,22,32,38), (500,900,1600,2400), (4.5,5.5,7.5,8.8),
               ["clay","silt"], ["loam","black","red"], 1100,120,22,2300,28000,.05,.10,40,-.12,.010,10,1.10,5),
 "wheat":     _c("cereal", ["rabi"],          (3,12,23,32),  (50,150,400,700),    (5.5,6.2,7.5,8.5),
               ["loam","silt"], ["black","clay","red"], 450,120,18,2400,20000,.05,.10,20,-.12,.010,5,1.00,18),
 "maize":     _c("cereal", ["kharif","rabi"], (12,20,30,38), (350,500,900,1400), (5.0,5.8,7.5,8.5),
               ["loam","red","silt"], ["black","sandy"], 500,105,25,2100,22000,.12,.15,22,-.15,.010,10,1.25,12),
 "cotton":    _c("fibre",  ["kharif"],        (16,21,32,39), (400,600,1000,1500), (5.5,6.0,8.0,9.0),
               ["black"], ["loam","red","clay"], 700,170,7,7000,32000,.15,.20,55,-.12,-.010,15,.85,14),
 "soybean":   _c("legume", ["kharif"],        (15,20,30,36), (350,500,900,1300),  (5.0,6.0,7.5,8.5),
               ["black","loam"], ["red","clay"], 450,100,8,4600,14000,.15,.20,18,.12,.020,10,.85,15,True),
 "chickpea":  _c("legume", ["rabi"],          (5,15,26,33),  (50,100,400,700),    (5.5,6.0,8.0,9.0),
               ["black","loam"], ["red","clay","sandy"], 280,105,6,5500,12000,.12,.20,15,.12,.020,5,.60,25,True),
 "groundnut": _c("legume", ["kharif","rabi","zaid"], (15,22,30,37), (350,500,900,1300), (5.0,5.8,7.0,8.0),
               ["sandy","red","loam"], ["black"], 500,110,8,6300,24000,.14,.18,35,.10,.015,10,.70,12,True),
 "mustard":   _c("oilseed",["rabi"],          (5,12,25,32),  (30,80,300,600),     (5.5,6.0,7.8,8.8),
               ["loam","silt"], ["red","black","sandy"], 300,110,6,5600,13000,.12,.18,15,-.06,.005,5,.85,20),
 "tomato":    _c("vegetable",["rabi","zaid"], (10,18,27,35), (200,400,900,1400),  (5.0,6.0,7.0,8.0),
               ["loam","red"], ["black","sandy"], 600,120,80,1500,80000,.45,.25,120,-.12,-.010,10,1.05,6),
 "ragi":      _c("cereal", ["kharif","rabi"], (14,20,30,36), (250,400,800,1200),  (4.5,5.0,7.5,8.5),
               ["red","loam"], ["sandy","black"], 350,110,8,4200,12000,.08,.15,25,-.08,.010,10,.80,18),
}

# Regional climate / soil defaults used to fill gaps (temp C seasonal mean, rain mm per season)
REGIONS = {
 "karnataka":     dict(soil="red",   ph=6.3, oc=.60, kharif=(25,600), rabi=(22,120), zaid=(27,100)),
 "punjab":        dict(soil="loam",  ph=7.8, oc=.50, kharif=(31,500), rabi=(15,80),  zaid=(33,60)),
 "maharashtra":   dict(soil="black", ph=7.8, oc=.55, kharif=(27,750), rabi=(23,60),  zaid=(31,40)),
 "tamil nadu":    dict(soil="red",   ph=7.0, oc=.50, kharif=(29,350), rabi=(26,450), zaid=(30,120)),
 "uttar pradesh": dict(soil="loam",  ph=7.6, oc=.45, kharif=(30,800), rabi=(17,70),  zaid=(32,50)),
 "default":       dict(soil="loam",  ph=7.0, oc=.50, kharif=(28,650), rabi=(21,100), zaid=(31,70)),
}
