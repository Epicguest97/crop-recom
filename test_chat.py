"""Unit tests for the rule-based regex chat engine."""
from datetime import date
from crop_advisor import chat_parser

def test_entity_extraction():
    # 1. Complex sentence
    text = "I have 5 acres of red soil in Karnataka, irrigated with borewell, sowing in November, budget 30k"
    e = chat_parser.extract_entities(text, today=date(2026, 10, 21))
    assert e.get("state") == "Karnataka", e
    assert e.get("soil_type") == "red", e
    assert e.get("irrigated") is True, e
    assert e.get("acres") == 5.0, e
    assert e.get("capital_per_acre") == 30000.0, e
    assert "2026-11-10" in e.get("sowing_date", ""), e

    # 2. Punjab with low risk and canal
    text2 = "Farm in Punjab, 10 acres, loam soil, canal water, low risk, capital 40000"
    e2 = chat_parser.extract_entities(text2, today=date(2026, 10, 21))
    assert e2.get("state") == "Punjab", e2
    assert e2.get("acres") == 10.0, e2
    assert e2.get("soil_type") == "loam", e2
    assert e2.get("irrigated") is True, e2
    assert e2.get("risk_tolerance") == "low", e2
    assert e2.get("capital_per_acre") == 40000.0, e2

    # 3. Rainfed black soil in UP
    text3 = "I am in UP with 2.5 acre rainfed black soil"
    e3 = chat_parser.extract_entities(text3, today=date(2026, 10, 21))
    assert e3.get("state") == "Uttar Pradesh", e3
    assert e3.get("acres") == 2.5, e3
    assert e3.get("soil_type") == "black", e3
    assert e3.get("irrigated") is False, e3

    # 4. Hectares to acres
    text4 = "2 hectares in Tamil Nadu, dryland"
    e4 = chat_parser.extract_entities(text4, today=date(2026, 10, 21))
    assert e4.get("state") == "Tamil Nadu", e4
    assert round(e4.get("acres", 0)) == 5, e4
    assert e4.get("irrigated") is False, e4

    # 5. pH and Organic Carbon
    text5 = "pH is 6.8 and temp is 28c with 600mm rainfall"
    e5 = chat_parser.extract_entities(text5)
    assert e5.get("ph") == 6.8, e5
    assert e5.get("temp") == 28.0, e5
    assert e5.get("rainfall") == 600.0, e5

    # 6. Specific user test: "i have land in goa"
    text6 = "i have land in goa"
    e6 = chat_parser.extract_entities(text6)
    assert e6.get("state") == "Goa", e6

    # 7. Test all 28 Indian States
    all_28_states = [
        ("andhra pradesh", "Andhra Pradesh"),
        ("arunachal pradesh", "Arunachal Pradesh"),
        ("assam", "Assam"),
        ("bihar", "Bihar"),
        ("chhattisgarh", "Chhattisgarh"),
        ("goa", "Goa"),
        ("gujarat", "Gujarat"),
        ("haryana", "Haryana"),
        ("himachal pradesh", "Himachal Pradesh"),
        ("jharkhand", "Jharkhand"),
        ("karnataka", "Karnataka"),
        ("kerala", "Kerala"),
        ("madhya pradesh", "Madhya Pradesh"),
        ("maharashtra", "Maharashtra"),
        ("manipur", "Manipur"),
        ("meghalaya", "Meghalaya"),
        ("mizoram", "Mizoram"),
        ("nagaland", "Nagaland"),
        ("odisha", "Odisha"),
        ("punjab", "Punjab"),
        ("rajasthan", "Rajasthan"),
        ("sikkim", "Sikkim"),
        ("tamil nadu", "Tamil Nadu"),
        ("telangana", "Telangana"),
        ("tripura", "Tripura"),
        ("uttar pradesh", "Uttar Pradesh"),
        ("uttarakhand", "Uttarakhand"),
        ("west bengal", "West Bengal"),
    ]
    for phrase, expected in all_28_states:
        extracted = chat_parser.extract_entities(f"I have land in {phrase}")
        assert extracted.get("state") == expected, f"Failed for {phrase}: got {extracted.get('state')}"

    print("test_entity_extraction PASSED (including Goa and all 28 states)")


def test_dialog_flow():
    # Turn 1: Greeting / Partial input
    p = {}
    r1 = chat_parser.handle_chat("Hello, I want advice for 4 acres", p, today=date(2026, 10, 21))
    assert r1["intent"] == "need_state"
    assert p["acres"] == 4.0
    assert "state" not in p

    # Turn 2: Providing state
    r2 = chat_parser.handle_chat("My farm is in Karnataka", p, today=date(2026, 10, 21))
    assert r2["intent"] == "recommendation"
    assert p["state"] == "Karnataka"
    assert r2["recommendation"]["best_crop"] is not None

    # Turn 3: Adding soil and irrigation
    r3 = chat_parser.handle_chat("Soil is black and irrigated with borewell", p, today=date(2026, 10, 21))
    assert r3["intent"] == "recommendation"
    assert p["soil_type"] == "black"
    assert p["irrigated"] is True

    # Turn 4: Asking for full plan
    r4 = chat_parser.handle_chat("Show full plan", p, today=date(2026, 10, 21))
    assert r4["intent"] == "full_plan"
    assert r4["plan"] is not None
    assert "rotation" in r4["plan"]
    assert "schedule" in r4["plan"]

    # Turn 5: Specific crop query
    r5 = chat_parser.handle_chat("Can I grow maize?", p, today=date(2026, 10, 21))
    assert r5["intent"] == "crop_query"
    assert "maize" in r5["reply"].lower()

    # Turn 6: Reset
    r6 = chat_parser.handle_chat("Reset everything", p, today=date(2026, 10, 21))
    assert r6["intent"] == "reset"
    assert len(p) == 0

    print("test_dialog_flow PASSED")


def test_state_defaults_and_overrides():
    # 1. Goa baseline
    p1 = {}
    r1 = chat_parser.handle_chat("i have land in goa", p1, today=date(2026, 10, 21))
    assert p1["state"] == "Goa"
    assert p1["soil_type"] == "red"
    assert p1["irrigated"] is False
    assert "Goa default" in p1.get("soil_type_source", "")
    assert r1["recommendation"]["best_crop"] is not None

    # 2. Overriding soil & irrigation explicitly with regex
    r2 = chat_parser.handle_chat("my soil is black and I have borewell irrigation", p1, today=date(2026, 10, 21))
    assert p1["soil_type"] == "black"
    assert p1["irrigated"] is True
    assert p1.get("soil_type_source") == "user specified"
    assert p1.get("irrigated_source") == "user specified"

    # 3. Punjab baseline (fresh) - adopts Punjab defaults (loam, irrigated)
    p3 = {}
    r3 = chat_parser.handle_chat("i have land in punjab", p3, today=date(2026, 10, 21))
    assert p3["state"] == "Punjab"
    assert p3["soil_type"] == "loam"
    assert p3["irrigated"] is True
    assert "Punjab default" in p3.get("soil_type_source", "")

    # 4. Rajasthan baseline (fresh) - adopts Rajasthan defaults (sandy, rainfed)
    p4 = {}
    r4 = chat_parser.handle_chat("i have land in rajasthan", p4, today=date(2026, 10, 21))
    assert p4["state"] == "Rajasthan"
    assert p4["soil_type"] == "sandy"
    assert p4["irrigated"] is False
    assert "Rajasthan default" in p4.get("soil_type_source", "")

    # 5. Maharashtra baseline (fresh) - adopts Maharashtra defaults (black soil)
    p5 = {}
    r5 = chat_parser.handle_chat("i have land in maharashtra", p5, today=date(2026, 10, 21))
    assert p5["state"] == "Maharashtra"
    assert p5["soil_type"] == "black"
    assert "Maharashtra default" in p5.get("soil_type_source", "")

    print("test_state_defaults_and_overrides PASSED")


if __name__ == "__main__":
    test_entity_extraction()
    test_dialog_flow()
    test_state_defaults_and_overrides()
    print("ALL CHAT PARSER TESTS PASSED")
