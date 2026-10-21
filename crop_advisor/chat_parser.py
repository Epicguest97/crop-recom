"""Rule-based Chat and Natural Language Regex Parser for Crop Advisor.
Pure Python standard library only - NO AI, NO external ML or LLM APIs.
Extracts entities using regex patterns and keyword matching, maintains
conversation state across turns, and generates rich recommendations and plans.
"""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, Any, Tuple, Optional, List

from .data import REGIONS, CROPS, season_of
from .service import get_recommendation, get_full_plan, ValidationError, SOILS, RISK

TZ = ZoneInfo("Asia/Kolkata")

# All 28 Indian States, 8 Union Territories, major cities, and aliases
STATE_PATTERNS = [
    # 28 States
    (r"\b(andhra\s*pradesh|andhra|amaravati|visakhapatnam|vizag|vijayawada|tirupati|guntur)\b", "Andhra Pradesh"),
    (r"\b(arunachal\s*pradesh|arunachal|itanagar)\b", "Arunachal Pradesh"),
    (r"\b(assam|asom|guwahati|dispur|silchar|dibrugarh|jorhat)\b", "Assam"),
    (r"\b(bihar|patna|gaya|bhagalpur|muzaffarpur|darbhanga)\b", "Bihar"),
    (r"\b(chhattisgarh|chattisgarh|raipur|bilaspur|durg|bhilai|korba)\b", "Chhattisgarh"),
    (r"\b(goa|panaji|panjim|margao|madgaon|vasco(?:\s*da\s*gama)?|mapusa|ponda)\b", "Goa"),
    (r"\b(gujarat|gujrat|ahmedabad|surat|vadodara|baroda|rajkot|gandhinagar|bhavnagar|jamnagar)\b", "Gujarat"),
    (r"\b(haryana|gurgaon|gurugram|faridabad|panipat|ambala|karnal|rohtak|hisar|sonipat)\b", "Haryana"),
    (r"\b(himachal\s*pradesh|himachal|shimla|manali|dharamshala|mandi|solan|kullu)\b", "Himachal Pradesh"),
    (r"\b(jharkhand|ranchi|jamshedpur|dhanbad|bokaro|deoghar|hazaribagh)\b", "Jharkhand"),
    (r"\b(karnataka|karnatka|bengaluru|bangalore|mysore|mysuru|hubli|belgaum|belagavi|mangalore|mangaluru|gulbarga|kalaburagi|dharwad)\b", "Karnataka"),
    (r"\b(kerala|kochi|cochin|thiruvananthapuram|trivandrum|kozhikode|calicut|thrissur|kannur|kollam|alappuzha|palakkad)\b", "Kerala"),
    (r"\b(madhya\s*pradesh|madhyapradesh|bhopal|indore|gwalior|jabalpur|ujjain|sagar|rewa)\b", "Madhya Pradesh"),
    (r"\b(maharashtra|maharastra|mumbai|bombay|pune|nagpur|nashik|aurangabad|chhatrapati\s*sambhajinagar|solapur|kolhapur|thane|amravati|nanded)\b", "Maharashtra"),
    (r"\b(manipur|imphal)\b", "Manipur"),
    (r"\b(meghalaya|shillong)\b", "Meghalaya"),
    (r"\b(mizoram|aizawl)\b", "Mizoram"),
    (r"\b(nagaland|kohima|dimapur)\b", "Nagaland"),
    (r"\b(odisha|orissa|bhubaneswar|cuttack|rourkela|puri|sambalpur|berhampur)\b", "Odisha"),
    (r"\b(punjab|ludhiana|amritsar|jalandhar|patiala|bathinda|mohali|pathankot)\b", "Punjab"),
    (r"\b(rajasthan|rajastan|jaipur|jodhpur|udaipur|kota|bikaner|ajmer|bhilwara|alwar)\b", "Rajasthan"),
    (r"\b(sikkim|gangtok)\b", "Sikkim"),
    (r"\b(tamil\s*nadu|tamilnadu|chennai|madras|coimbatore|madurai|salem|trichy|tiruchirappalli|tirunelveli|erode|vellore)\b", "Tamil Nadu"),
    (r"\b(telangana|hyderabad|secunderabad|warangal|nizamabad|karimnagar|khammam)\b", "Telangana"),
    (r"\b(tripura|agartala)\b", "Tripura"),
    (r"\b(uttar\s*pradesh|uttarpradesh|lucknow|kanpur|varanasi|banaras|kashi|agra|meerut|prayagraj|allahabad|noida|ghaziabad|bareilly|aligarh|moradabad|gorakhpur)\b", "Uttar Pradesh"),
    (r"\b(uttarakhand|uttaranchal|dehradun|haridwar|rishikesh|haldwani|roorkee|nainital)\b", "Uttarakhand"),
    (r"\b(west\s*bengal|bengal|kolkata|calcutta|howrah|darjeeling|siliguri|asansol|durgapur|bardhaman)\b", "West Bengal"),

    # Union Territories
    (r"\b(delhi|new\s*delhi)\b", "Delhi"),
    (r"\b(jammu\s*(?:and|&)?\s*kashmir|j&k|kashmir|srinagar)\b", "Jammu and Kashmir"),
    (r"\b(ladakh|leh|kargil)\b", "Ladakh"),
    (r"\b(puducherry|pondicherry)\b", "Puducherry"),
    (r"\b(chandigarh)\b", "Chandigarh"),
    (r"\b(andaman(?:\s*(?:and|&)?\s*nicobar)?|port\s*blair)\b", "Andaman and Nicobar Islands"),
    (r"\b(daman|diu|dadra|silvassa)\b", "Dadra and Nagar Haveli and Daman and Diu"),
    (r"\b(lakshadweep|kavaratti)\b", "Lakshadweep"),

    # Contextual abbreviations (e.g. "in UP", "state GA", "from MP")
    (r"\b(?:in|state|from|at|near|around|of)\s+(up|mh|ka|pb|tn|ap|ts|mp|gj|hr|rj|wb|dl|jk|uk|hp|ga|jh|cg|br|kl|or|od)\b",
     lambda m: {
         "up": "Uttar Pradesh", "mh": "Maharashtra", "ka": "Karnataka", "pb": "Punjab", "tn": "Tamil Nadu",
         "ap": "Andhra Pradesh", "ts": "Telangana", "mp": "Madhya Pradesh", "gj": "Gujarat", "hr": "Haryana",
         "rj": "Rajasthan", "wb": "West Bengal", "dl": "Delhi", "jk": "Jammu and Kashmir", "uk": "Uttarakhand",
         "hp": "Himachal Pradesh", "ga": "Goa", "jh": "Jharkhand", "cg": "Chhattisgarh", "br": "Bihar",
         "kl": "Kerala", "or": "Odisha", "od": "Odisha"
     }.get(m.group(1).lower(), m.group(1).upper())),
    (r"\b(up|mh|ka|pb|tn|ap|ts|mp|gj|hr|rj|wb|dl|jk|uk|hp|ga|jh|cg|br|kl|or|od)\s+state\b",
     lambda m: {
         "up": "Uttar Pradesh", "mh": "Maharashtra", "ka": "Karnataka", "pb": "Punjab", "tn": "Tamil Nadu",
         "ap": "Andhra Pradesh", "ts": "Telangana", "mp": "Madhya Pradesh", "gj": "Gujarat", "hr": "Haryana",
         "rj": "Rajasthan", "wb": "West Bengal", "dl": "Delhi", "jk": "Jammu and Kashmir", "uk": "Uttarakhand",
         "hp": "Himachal Pradesh", "ga": "Goa", "jh": "Jharkhand", "cg": "Chhattisgarh", "br": "Bihar",
         "kl": "Kerala", "or": "Odisha", "od": "Odisha"
     }.get(m.group(1).lower(), m.group(1).upper())),
]

# Soil types and normalization
SOIL_PATTERNS = [
    (r"\bblack(?:\s*cotton)?(?:\s*soil)?\b", "black"),
    (r"\bred(?:\s*soil)?\b", "red"),
    (r"\b(loam|loamy|alluvial)(?:\s*soil)?\b", "loam"),
    (r"\bclay(?:ey)?(?:\s*soil)?\b", "clay"),
    (r"\bsilt(?:y)?(?:\s*soil)?\b", "silt"),
    (r"\bsand(?:y)?(?:\s*soil)?\b", "sandy"),
    (r"\blaterite(?:\s*soil)?\b", "red"),
]

# Irrigation patterns
NEG_IRRIGATION = re.compile(
    r"\b(rain[\s-]?fed|dry[\s-]?land|unirrigated|non[\s-]?irrigated|"
    r"no\s+(?:irrigation|water|borewell|canal|tubewell)|"
    r"without\s+irrigation|lacking\s+water|water\s+scarcity)\b",
    re.IGNORECASE
)
POS_IRRIGATION = re.compile(
    r"\b(irrigated|irrigation\s*(?:is\s*)?(?:yes|available|there|present|good)|"
    r"bore[\s-]?well|tube[\s-]?well|canal|drip|sprinkler|well\s*water|"
    r"have\s+(?:water|irrigation)|with\s+irrigation)\b",
    re.IGNORECASE
)

# Month names mapping
MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
}


def extract_entities(text: str, today: Optional[date] = None) -> Dict[str, Any]:
    """Extract agricultural parameters using pure regular expressions and keywords."""
    if today is None:
        today = datetime.now(TZ).date()
    t = text.lower()
    res: Dict[str, Any] = {}

    # 1. State extraction
    for pat, st in STATE_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            res["state"] = st(m) if callable(st) else st
            break

    # 2. Soil type
    for pat, sl in SOIL_PATTERNS:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            res["soil_type"] = sl
            break

    # 3. Irrigation
    if NEG_IRRIGATION.search(t):
        res["irrigated"] = False
    elif POS_IRRIGATION.search(t):
        res["irrigated"] = True

    # 4. Land size / Acres
    m_acres = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:acres?|acre|ac)\b", t)
    if m_acres:
        res["acres"] = float(m_acres.group(1))
    else:
        m_ha = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hectares?|ha)\b", t)
        if m_ha:
            res["acres"] = round(float(m_ha.group(1)) * 2.471, 2)
        else:
            m_bigha = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:bigha|bighas)\b", t)
            if m_bigha:
                res["acres"] = round(float(m_bigha.group(1)) * 0.4, 2)
            else:
                m_land = re.search(r"\b(?:land|farm|area|plot)(?:\s*size)?\s*(?:is|of|:|=)?\s*(\d+(?:\.\d+)?)\s*(?:acres?|ac)?\b", t)
                if m_land:
                    val = float(m_land.group(1))
                    if 0.1 <= val <= 10000:
                        res["acres"] = val

    # 5. Capital / Budget per acre
    bud_patterns = [
        # "budget 30k", "capital 40000", "investment Rs. 25,000"
        r"(?:budget|capital|investment|cost|spend)(?:\s*(?:is|of|per\s*acre|:|=))?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|thousand|lakh|lac)?\b",
        # "Rs 30,000 per acre", "₹40k budget"
        r"(?:rs\.?|inr|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|thousand|lakh|lac)?(?:\s*(?:per\s*acre|\/acre|budget|capital))?\b",
        # "40000 capital", "30k per acre"
        r"\b(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|thousand|lakh|lac)?\s*(?:per\s*acre|\/acre|budget|capital|investment)\b",
    ]
    for pat in bud_patterns:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            raw_val = float(m.group(1).replace(",", ""))
            unit = m.group(2).lower() if (len(m.groups()) >= 2 and m.group(2)) else ""
            if unit in ("k", "thousand"):
                raw_val *= 1000
            elif unit in ("lakh", "lac"):
                raw_val *= 100000
            elif raw_val < 500:  # e.g. "budget 30" meaning 30k
                raw_val *= 1000
            if 1000 <= raw_val <= 1e7:
                res["capital_per_acre"] = raw_val
                break

    # 6. Risk Tolerance
    if re.search(r"\b(low[\s-]risk|safe|conservative|minimum\s*risk|no\s*risk)\b", t) or re.search(r"\brisk(?:\s*tolerance)?\s*(?:is|=|:)?\s*low\b", t):
        res["risk_tolerance"] = "low"
    elif re.search(r"\b(high[\s-]risk|aggressive|maximum\s*profit|risky)\b", t) or re.search(r"\brisk(?:\s*tolerance)?\s*(?:is|=|:)?\s*high\b", t):
        res["risk_tolerance"] = "high"
    elif re.search(r"\b(medium[\s-]risk|moderate|balanced)\b", t) or re.search(r"\brisk(?:\s*tolerance)?\s*(?:is|=|:)?\s*medium\b", t):
        res["risk_tolerance"] = "medium"

    # 7. Sowing Date / Season
    # ISO YYYY-MM-DD
    m_iso = re.search(r"\b(20\d\d-[0-1]?\d-[0-3]?\d)\b", t)
    if m_iso:
        res["sowing_date"] = m_iso.group(1)
    else:
        # DD/MM/YYYY or DD-MM-YYYY
        m_dmy = re.search(r"\b([0-3]?\d)[/-]([0-1]?\d)[/-](20\d\d)\b", t)
        if m_dmy:
            day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            res["sowing_date"] = f"{year:04d}-{month:02d}-{day:02d}"
        elif re.search(r"\b(today|now)\b", t):
            res["sowing_date"] = today.isoformat()
        elif re.search(r"\btomorrow\b", t):
            res["sowing_date"] = (today + timedelta(days=1)).isoformat()
        elif re.search(r"\bnext\s*week\b", t):
            res["sowing_date"] = (today + timedelta(days=7)).isoformat()
        elif re.search(r"\bnext\s*month\b", t):
            res["sowing_date"] = (today + timedelta(days=30)).isoformat()
        elif re.search(r"\b(rabi|winter)\b", t):
            yr = today.year if today.month <= 11 else today.year + 1
            res["sowing_date"] = f"{yr}-11-10"
        elif re.search(r"\b(kharif|monsoon)\b", t):
            yr = today.year if today.month <= 7 else today.year + 1
            res["sowing_date"] = f"{yr}-07-01"
        elif re.search(r"\b(zaid|summer)\b", t):
            yr = today.year if today.month <= 4 else today.year + 1
            res["sowing_date"] = f"{yr}-04-15"
        else:
            # Month name pattern
            month_pat = r"\b(?:sowing\s*(?:in\s*)?|in\s*|month\s*(?:of\s*)?)?(" + "|".join(MONTHS.keys()) + r")\b"
            m_mo = re.search(month_pat, t)
            if m_mo:
                mo_name = m_mo.group(1)
                mo_num = MONTHS[mo_name]
                yr = today.year if mo_num >= today.month else today.year + 1
                res["sowing_date"] = f"{yr:04d}-{mo_num:02d}-10"

    # 8. Soil pH
    m_ph = re.search(r"\b(?:ph\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*ph)\b", t)
    if m_ph:
        v = float(m_ph.group(1) or m_ph.group(2))
        if 3.5 <= v <= 10.0:
            res["ph"] = v

    # 9. Temperature
    m_temp = re.search(r"\b(?:temp(?:erature)?\s*(?:is|=|:)?\s*(-?\d+(?:\.\d+)?)\s*(?:°?c|deg)?|(-?\d+(?:\.\d+)?)\s*(?:°?c|deg(?:rees?)?)\s*(?:temp(?:erature)?)?)\b", t)
    if m_temp:
        v = float(m_temp.group(1) or m_temp.group(2))
        if -5 <= v <= 50:
            res["temp"] = v

    # 10. Rainfall
    m_rain = re.search(r"\b(?:rain(?:fall)?\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:mm)?|(\d+(?:\.\d+)?)\s*(?:mm)?\s*rain(?:fall)?)\b", t)
    if m_rain:
        v = float(m_rain.group(1) or m_rain.group(2))
        if 0 <= v <= 5000:
            res["rainfall"] = v

    # 11. Organic carbon
    m_oc = re.search(r"\b(?:organic\s*carbon|oc)\s*(?:is|=|:)?\s*(\d+(?:\.\d+)?)\b", t)
    if m_oc:
        v = float(m_oc.group(1))
        if 0.05 <= v <= 3.0:
            res["organic_carbon"] = v

    return res


def detect_intent(text: str) -> Tuple[str, Optional[str]]:
    """Determine user intent and identify target crop if mentioned."""
    t = text.lower().strip()

    # Reset
    if re.search(r"\b(reset|clear|restart|start\s*over|new\s*chat|new\s*farm|clean)\b", t):
        return "reset", None

    # Help
    if re.search(r"\b(help|how\s*to\s*use|guide|commands|what\s*can\s*you\s*do|instructions|examples)\b", t) and len(t.split()) <= 6:
        return "help", None

    # Full Plan
    if re.search(r"\b(full\s*plan|detailed\s*plan|6[\s-]season|rotation|schedule|land\s*allocation|tasks|view\s*plan)\b", t):
        return "full_plan", None

    # Specific crop inquiry
    crop_match = re.search(r"\b(?:can\s*i\s*(?:grow|plant|sow)|what\s*about|is\s*(?:it\s*good\s*to\s*grow)?|how\s*is|why\s*(?:not)?)\s+(rice|wheat|maize|cotton|soybean|chickpea|groundnut|mustard|tomato|ragi)\b", t)
    if crop_match:
        return "crop_query", crop_match.group(1)

    # General crop recommendation request
    if re.search(r"\b(recommend(?:ation)?|suggest|what\s*(?:should|can)\s*i\s*(?:grow|plant|sow)|best\s*crop|options|what\s*to\s*grow)\b", t):
        return "recommend", None

    # Greetings
    if re.search(r"^(hi|hello|hey|namaste|greetings|good\s*(?:morning|afternoon|evening)|hola)\b", t) and len(t.split()) <= 4:
        return "greeting", None

    # Default: conversational input
    return "update", None


def format_currency(val: float) -> str:
    return f"₹{val:,.0f}"


def format_crop_card_html(crop: Dict[str, Any], rank: int) -> str:
    """Format single crop recommendation card for web UI."""
    is_top = rank == 1
    badge_color = "#16a34a" if is_top else "#0284c7"
    card_bg = "#f0fdf4" if is_top else "#f8fafc"
    card_border = "#86efac" if is_top else "#e2e8f0"
    rank_icon = "🏆 Best Choice" if is_top else f"#{rank}"

    why_tags = "".join(f'<span class="badge badge-why">✓ {w}</span>' for w in crop.get("why", []))
    cautions = "".join(f'<div class="caution-item">⚠️ {c}</div>' for c in crop.get("cautions", []))
    if not cautions:
        cautions = ""

    html = f"""
    <div class="crop-card" style="background:{card_bg}; border: 1px solid {card_border}; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="background:{badge_color}; color:white; font-size:12px; font-weight:700; padding:3px 8px; border-radius:12px;">{rank_icon}</span>
          <strong style="font-size:17px; text-transform:capitalize; color:#0f172a;">{crop['crop']}</strong>
        </div>
        <div style="text-align:right;">
          <span style="font-size:15px; font-weight:700; color:#15803d;">{format_currency(crop['profit_per_acre'])}</span>
          <span style="font-size:11px; color:#64748b;">/acre</span>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; font-size:12px; background:rgba(255,255,255,0.7); padding:8px; border-radius:6px; margin-bottom:8px;">
        <div><span style="color:#64748b;">Fit Score:</span> <strong>{int(crop['fit']*100)}%</strong></div>
        <div><span style="color:#64748b;">Yield:</span> <strong>{crop['yield_quintal_per_acre']} q/ac</strong></div>
        <div><span style="color:#64748b;">Water Gap:</span> <strong>{crop['water_gap_mm']} mm</strong></div>
      </div>

      <div style="margin-bottom:6px; display:flex; flex-wrap:wrap; gap:4px;">
        {why_tags}
      </div>
      {cautions}
    </div>
    """
    return html


def format_recommendation_html(rec: Dict[str, Any], state: str, updated_fields: List[str], profile: Optional[Dict[str, Any]] = None) -> str:
    """Format recommendation into rich HTML for chat with state-adjusted baseline highlights."""
    if profile is None:
        profile = {}
    season = rec.get("season", "rabi").title()
    ranking = rec.get("ranking", [])
    if not ranking:
        return "<p>No suitable crop found for these exact conditions. Please try a different sowing season or soil type.</p>"

    # State baseline information
    feats = rec.get("features", {})
    soil_val = profile.get("soil_type") or feats.get("soil_type", {}).get("value", "loam")
    soil_src = profile.get("soil_type_source", "state default")
    irrig_val = "Irrigated 💧" if profile.get("irrigated") else "Rainfed 🌧️"
    irrig_src = profile.get("irrigated_source", "state default")
    ph_val = profile.get("ph") or (feats.get("ph", {}).get("value") if isinstance(feats.get("ph"), dict) else 7.0)
    rain_val = profile.get("rainfall") or (feats.get("rainfall", {}).get("value") if isinstance(feats.get("rainfall"), dict) else "N/A")

    # Updated notice
    updated_html = ""
    if updated_fields:
        fields_str = ", ".join(f"<strong>{f.replace('_', ' ').title()}</strong>" for f in updated_fields)
        updated_html = f'<div class="update-banner" style="background:#e0f2fe; color:#0369a1; padding:8px 12px; border-radius:6px; font-size:13px; margin-bottom:12px;">📝 Regex Matched: {fields_str}</div>'

    # State baselines card
    state_card = f"""
    <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px; margin-bottom:12px; font-size:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <strong style="color:#166534; font-size:13px;">📍 {state.title()} Regional Agronomic Defaults Applied</strong>
        <span style="font-size:10px; background:#dcfce7; color:#15803d; padding:2px 7px; border-radius:10px; font-weight:700;">STATE TUNED</span>
      </div>
      <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:6px; color:#334155;">
        <div>🌱 Soil: <strong style="text-transform:uppercase;">{soil_val}</strong> <span style="font-size:10px; color:#64748b;">({soil_src})</span></div>
        <div>💧 Water: <strong>{irrig_val}</strong> <span style="font-size:10px; color:#64748b;">({irrig_src})</span></div>
        <div>🧪 Soil pH: <strong>{ph_val}</strong></div>
        <div>🌧️ Rainfall: <strong>{rain_val} mm</strong> ({season})</div>
      </div>
      <div style="font-size:11px; color:#15803d; margin-top:6px;">
        <em>💡 Defaults tailored for {state.title()}. Type your exact soil or irrigation anytime to override!</em>
      </div>
    </div>
    """

    cards_html = "".join(format_crop_card_html(crop, i + 1) for i, crop in enumerate(ranking[:3]))

    html = f"""
    {updated_html}
    {state_card}
    <div style="margin-bottom:10px;">
      <h3 style="margin:0 0 4px 0; font-size:16px; color:#1e293b;">🌾 Recommended Crops for {state.title()} ({season} Season)</h3>
      <p style="margin:0; font-size:12px; color:#64748b;">Calculated with rule-based agronomy formulas (soil fit, expected yield, mandi price, and weather deficit).</p>
    </div>
    {cards_html}
    """
    return html


def format_plan_html(plan: Dict[str, Any], state: str) -> str:
    """Format full 6-season rotation and plot allocation plan into rich HTML."""
    season = plan.get("season", "rabi").title()
    rot = plan.get("rotation", {})
    sched = plan.get("schedule", {})
    alloc = plan.get("allocation", {})

    # Rotation timeline
    rot_rows = ""
    for step in rot.get("plan", []):
        rot_rows += f"""
        <tr style="border-bottom:1px solid #f1f5f9;">
          <td style="padding:6px 8px; font-weight:600; color:#334155;">{step['season'].title()}</td>
          <td style="padding:6px 8px; text-transform:capitalize; font-weight:700; color:#15803d;">{step['crop']}</td>
          <td style="padding:6px 8px; color:#64748b;">{step['soil_health']} / 100</td>
        </tr>
        """

    # Upcoming tasks
    task_rows = ""
    for t in sched.get("next_tasks", [])[:6]:
        task_rows += f"""
        <li style="margin-bottom:6px; font-size:12px; color:#334155;">
          <strong>{t['date']}:</strong> {t['task']}
        </li>
        """

    # Land allocation
    alloc_rows = ""
    for a in alloc.get("allocation", []):
        alloc_rows += f"""
        <div style="background:#f8fafc; border-left:3px solid #16a34a; padding:6px 10px; margin-bottom:6px; font-size:12px;">
          <span style="font-weight:700; text-transform:capitalize;">{a['crop']}</span>: <strong>{a['acres']} acres</strong> on {a['plot']} (Est. Profit: {format_currency(a['expected_profit'])})
        </div>
        """

    html = f"""
    <div>
      <h3 style="margin:0 0 6px 0; font-size:16px; color:#1e293b;">📋 Complete Agricultural Plan for {state.title()}</h3>
      <p style="font-size:12px; color:#64748b; margin-top:0;">Optimized for profit stability, water conservation, and long-term soil health.</p>

      <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:10px; margin-bottom:12px;">
        <h4 style="margin:0 0 6px 0; font-size:13px; color:#166534;">🔄 6-Season Crop Rotation & Soil Health</h4>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">
          <thead>
            <tr style="text-align:left; color:#64748b; border-bottom:1px solid #cbd5e1;">
              <th style="padding:4px 8px;">Season</th>
              <th style="padding:4px 8px;">Crop</th>
              <th style="padding:4px 8px;">Health Index</th>
            </tr>
          </thead>
          <tbody>
            {rot_rows}
          </tbody>
        </table>
        <div style="font-size:11px; color:#166534; margin-top:6px;">
          Starting Health: <strong>{rot.get('start_health')}</strong> ➔ Final Projected: <strong>{rot.get('final_health')}</strong>
        </div>
      </div>

      <div style="margin-bottom:12px;">
        <h4 style="margin:0 0 6px 0; font-size:13px; color:#1e293b;">📐 Land & Plot Allocation ({alloc.get('total_acres', '')} acres)</h4>
        {alloc_rows}
        <div style="font-size:11px; color:#64748b; margin-top:4px;">
          Total Expected Profit: <strong style="color:#15803d;">{format_currency(alloc.get('expected_total_profit', 0))}</strong> | Water: {alloc.get('water_used_m3', 0)} m³
        </div>
      </div>

      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px;">
        <h4 style="margin:0 0 6px 0; font-size:13px; color:#1e293b;">📅 Upcoming Agronomic Schedule ({sched.get('crop', '').title()})</h4>
        <ul style="margin:0; padding-left:18px;">
          {task_rows}
        </ul>
      </div>
    </div>
    """
    return html


def handle_chat(user_message: str, profile: Optional[Dict[str, Any]] = None, today: Optional[date] = None) -> Dict[str, Any]:
    """Main dialogue handler: parses user input with regex, maintains profile state,
    and returns recommendations or plans without AI."""
    if today is None:
        today = datetime.now(TZ).date()

    if profile is None:
        profile = {}

    intent, target_crop = detect_intent(user_message)

    # Handle Reset Intent
    if intent == "reset":
        profile.clear()
        reply_text = "🔄 Conversation and farm profile have been reset. Tell me about your farm! (e.g. 'I have 5 acres in Karnataka with red soil and borewell')"
        reply_html = f"""
        <div style="padding:8px 0;">
          <p>🔄 <strong>Reset Complete.</strong> All previous farm parameters have been cleared.</p>
          <p>Please share your farm details to get fresh recommendations, for example:</p>
          <div style="display:flex; flex-direction:column; gap:6px; margin-top:8px;">
            <button class="chip-btn" onclick="sendSuggestion('5 acres in Punjab, irrigated, rabi season')">🌾 5 acres in Punjab, irrigated, rabi season</button>
            <button class="chip-btn" onclick="sendSuggestion('Karnataka, 4 acres red soil, borewell')">🌱 Karnataka, 4 acres red soil, borewell</button>
            <button class="chip-btn" onclick="sendSuggestion('Maharashtra, black soil, rainfed, low risk')">🌧️ Maharashtra, black soil, rainfed, low risk</button>
          </div>
        </div>
        """
        return {
            "reply": reply_text,
            "reply_html": reply_html,
            "profile": profile,
            "extracted": {},
            "intent": "reset",
            "quick_replies": [
                "5 acres in Punjab, irrigated",
                "Karnataka, red soil, borewell",
                "Maharashtra, black soil, rainfed"
            ],
            "recommendation": None,
            "plan": None
        }

    # Handle Help Intent
    if intent == "help":
        reply_text = (
            "🌾 Crop Advisor Help:\n"
            "You can type your farm details naturally. We use regular expressions to extract:\n"
            "- State: Karnataka, Punjab, Maharashtra, Tamil Nadu, Uttar Pradesh, etc.\n"
            "- Soil: Black, Red, Loam, Clay, Sandy, Silt\n"
            "- Irrigation: Irrigated / Borewell / Canal OR Rainfed / Dryland\n"
            "- Land size: e.g. 5 acres, 2.5 acre, 10 bigha, 2 hectares\n"
            "- Budget: e.g. ₹30,000 / acre, 40k budget, capital 25k\n"
            "- Risk tolerance: Low, Medium, High\n"
            "- Season / Date: Rabi, Kharif, Zaid, or month name like November\n\n"
            "Commands: 'full plan' for 6-season rotation, 'reset' to start over."
        )
        reply_html = """
        <div style="font-size:13px; line-height:1.5;">
          <h4 style="margin:0 0 8px 0; color:#15803d;">🌾 How to Use Crop Advisor</h4>
          <p>This is a <strong>100% deterministic, rule-based</strong> advisory system. No AI or external ML is used.</p>
          <p>You can tell me your farm details in plain English, and our regex engine will detect:</p>
          <ul style="padding-left:18px; margin:6px 0;">
            <li><strong>State:</strong> Karnataka, Punjab, Maharashtra, Tamil Nadu, Uttar Pradesh, etc.</li>
            <li><strong>Soil Type:</strong> Black, Red, Loam, Clay, Sandy, Silt</li>
            <li><strong>Irrigation:</strong> Borewell, canal, drip (Irrigated) vs. Rainfed/Dryland</li>
            <li><strong>Land Area:</strong> e.g. <code>5 acres</code>, <code>2.5 acre</code>, <code>3 hectares</code></li>
            <li><strong>Budget:</strong> e.g. <code>₹30,000 / acre</code>, <code>budget 40k</code></li>
            <li><strong>Risk Tolerance:</strong> <code>Low</code>, <code>Medium</code>, <code>High</code></li>
            <li><strong>Sowing Season / Date:</strong> <code>Rabi</code>, <code>Kharif</code>, <code>Zaid</code>, <code>November</code>, or <code>YYYY-MM-DD</code></li>
          </ul>
          <p style="margin-top:8px;">💡 Try typing: <em>"I have 4 acres of loam soil in Punjab with canal irrigation for rabi season"</em></p>
        </div>
        """
        return {
            "reply": reply_text,
            "reply_html": reply_html,
            "profile": profile,
            "extracted": {},
            "intent": "help",
            "quick_replies": [
                "5 acres in Punjab, irrigated",
                "Karnataka, red soil, low risk",
                "Show full plan"
            ],
            "recommendation": None,
            "plan": None
        }

    # Extract entities from user message
    extracted = extract_entities(user_message, today=today)
    updated_fields = list(extracted.keys())

    # Track which parameters were explicitly typed / matched via regex
    explicit_keys = set(profile.get("explicit_keys", []))
    for k in extracted.keys():
        explicit_keys.add(k)
    profile["explicit_keys"] = list(explicit_keys)

    # Merge newly extracted entities into profile
    profile.update(extracted)

    # Check if State is known
    state = profile.get("state")

    # If state is known, adopt state-specific agronomic defaults for parameters
    # that were NOT explicitly regex-matched by the user.
    if state:
        state_key = state.lower().strip()
        state_defaults = REGIONS.get(state_key, REGIONS["default"])

        # 1. Soil type: adopt state's dominant soil if not explicitly specified
        if "soil_type" not in explicit_keys:
            profile["soil_type"] = state_defaults["soil"]
            profile["soil_type_source"] = f"{state} default"
        else:
            profile["soil_type_source"] = "user specified"

        # 2. Irrigation: adopt state's baseline irrigation if not explicitly specified
        if "irrigated" not in explicit_keys:
            profile["irrigated"] = state_defaults.get("irrigated", False)
            profile["irrigated_source"] = f"{state} default"
        else:
            profile["irrigated_source"] = "user specified"
    if not state:
        known_details = []
        if "acres" in profile:
            known_details.append(f"{profile['acres']} acres")
        if "soil_type" in profile:
            known_details.append(f"{profile['soil_type']} soil")
        if "irrigated" in profile:
            known_details.append("irrigated" if profile["irrigated"] else "rainfed")

        known_str = f" (Noted: {', '.join(known_details)})" if known_details else ""
        reply_text = (
            f"I have recorded your details{known_str}. Which state is your farm located in? "
            "(e.g. Goa, Karnataka, Punjab, Maharashtra, Tamil Nadu, Uttar Pradesh, etc.)"
        )
        reply_html = f"""
        <div>
          <p>🌱 <strong>Almost there!</strong>{f" I noted {', '.join(known_details)}." if known_details else ""}</p>
          <p>Which <strong>state</strong> is your farm located in? (All 28 Indian states supported):</p>
          <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
            <button class="chip-btn" onclick="sendSuggestion('Goa')">📍 Goa</button>
            <button class="chip-btn" onclick="sendSuggestion('Punjab')">📍 Punjab</button>
            <button class="chip-btn" onclick="sendSuggestion('Karnataka')">📍 Karnataka</button>
            <button class="chip-btn" onclick="sendSuggestion('Maharashtra')">📍 Maharashtra</button>
            <button class="chip-btn" onclick="sendSuggestion('Uttar Pradesh')">📍 Uttar Pradesh</button>
          </div>
        </div>
        """
        return {
            "reply": reply_text,
            "reply_html": reply_html,
            "profile": profile,
            "extracted": extracted,
            "intent": "need_state",
            "quick_replies": ["Goa", "Punjab", "Karnataka", "Maharashtra", "Uttar Pradesh"],
            "recommendation": None,
            "plan": None
        }

    # Handle Crop Query
    if intent == "crop_query" and target_crop:
        try:
            rec = get_recommendation(profile)
            found = next((r for r in rec.get("ranking", []) if r["crop"].lower() == target_crop.lower()), None)
            if found:
                rank_idx = [r["crop"].lower() for r in rec.get("ranking", [])].index(target_crop.lower()) + 1
                reply_text = (
                    f"Analysis for {target_crop.title()}:\n"
                    f"Ranks #{rank_idx} for your conditions with {int(found['fit']*100)}% fit.\n"
                    f"Est. profit: Rs {found['profit_per_acre']:,.0f}/acre (range {found['profit_low']:,.0f} to {found['profit_high']:,.0f}).\n"
                    f"Water gap: {found['water_gap_mm']} mm.\n"
                    f"Reasons: {'; '.join(found['why']) if found['why'] else 'Suitable'}"
                )
                reply_html = f"""
                <div style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:12px;">
                  <h4 style="margin:0 0 6px 0; color:#1e293b;">🌾 Crop Inquiry: <strong>{target_crop.title()}</strong></h4>
                  <p style="margin:0 0 8px 0; font-size:13px; color:#475569;">
                    Ranks <strong>#{rank_idx}</strong> among candidates for your farm in <strong>{state}</strong> ({rec.get('season','').title()} season).
                  </p>
                  {format_crop_card_html(found, rank_idx)}
                </div>
                """
                return {
                    "reply": reply_text,
                    "reply_html": reply_html,
                    "profile": profile,
                    "extracted": extracted,
                    "intent": "crop_query",
                    "quick_replies": ["Show all recommendations", "Show full plan", "Low risk mode"],
                    "recommendation": rec,
                    "plan": None
                }
            else:
                reply_text = f"Crop '{target_crop}' is not currently suitable or not recommended for the selected season in {state}."
                reply_html = f"<p>⚠️ <strong>{target_crop.title()}</strong> is not recommended for this season or conditions in <strong>{state}</strong>.</p>"
                return {
                    "reply": reply_text,
                    "reply_html": reply_html,
                    "profile": profile,
                    "extracted": extracted,
                    "intent": "crop_query",
                    "quick_replies": ["Show best recommendations", "Show full plan"],
                    "recommendation": None,
                    "plan": None
                }
        except ValidationError as e:
            return {
                "reply": f"Could not analyze crop: {e}",
                "reply_html": f"<p style='color:#dc2626;'>Error: {e}</p>",
                "profile": profile,
                "extracted": extracted,
                "intent": "error",
                "quick_replies": ["Reset", "Help"],
                "recommendation": None,
                "plan": None
            }

    # Handle Full Plan request
    if intent == "full_plan":
        try:
            plan = get_full_plan(profile)
            reply_text = f"Complete agricultural plan generated for {state}. 6-Season rotation and upcoming schedule ready."
            reply_html = format_plan_html(plan, state)
            return {
                "reply": reply_text,
                "reply_html": reply_html,
                "profile": profile,
                "extracted": extracted,
                "intent": "full_plan",
                "quick_replies": [
                    "Show recommendations",
                    "Change to low risk",
                    "Set irrigated",
                    "Reset"
                ],
                "recommendation": None,
                "plan": plan
            }
        except ValidationError as e:
            return {
                "reply": f"Unable to generate plan: {e}",
                "reply_html": f"<p style='color:#dc2626;'>Error generating plan: {e}</p>",
                "profile": profile,
                "extracted": extracted,
                "intent": "error",
                "quick_replies": ["Help", "Reset"],
                "recommendation": None,
                "plan": None
            }

    # Standard Recommendation flow
    try:
        rec = get_recommendation(profile)
        reply_text = rec.get("message", "Here are your crop recommendations.")
        reply_html = format_recommendation_html(rec, state, updated_fields, profile)

        quick_replies = ["Show full 6-season plan"]
        if profile.get("irrigated"):
            quick_replies.append("Set to rainfed")
        else:
            quick_replies.append("Set to borewell irrigated")
        
        current_soil = profile.get("soil_type", "")
        if current_soil != "black":
            quick_replies.append("Try black soil")
        elif current_soil != "red":
            quick_replies.append("Try red soil")
        if profile.get("risk_tolerance") != "low":
            quick_replies.append("Low risk mode")

        return {
            "reply": reply_text,
            "reply_html": reply_html,
            "profile": profile,
            "extracted": extracted,
            "intent": "recommendation",
            "quick_replies": quick_replies[:4],
            "recommendation": rec,
            "plan": None
        }
    except ValidationError as e:
        return {
            "reply": f"Validation Error: {e}",
            "reply_html": f"<p style='color:#dc2626;'>⚠️ {e}</p>",
            "profile": profile,
            "extracted": extracted,
            "intent": "error",
            "quick_replies": ["Help", "Reset"],
            "recommendation": None,
            "plan": None
        }
