"""Test suite for the Web Chat interface and routes."""
import os
os.environ.setdefault("API_KEY", "test-secret-key")
from server import app

def test_web_routes():
    c = app.test_client()

    # 1. Health check
    assert c.get("/health").status_code == 200

    # 2. Main website page (unauthorized access allowed for browser UI)
    r_index = c.get("/")
    assert r_index.status_code == 200
    assert b"AgroAdvisor Chat" in r_index.data
    assert b"100% Deterministic Regex" in r_index.data

    # 3. Chat endpoint with no API key header
    r_chat1 = c.post("/chat", json={"message": "Hello, I have 4 acres in Punjab"})
    assert r_chat1.status_code == 200
    d1 = r_chat1.get_json()
    assert d1["profile"]["state"] == "Punjab"
    assert d1["profile"]["acres"] == 4.0
    assert d1["recommendation"] is not None
    assert d1["recommendation"]["best_crop"] is not None

    # 4. Multi-turn chat
    profile = d1["profile"]
    r_chat2 = c.post("/chat", json={
        "message": "It is loam soil and canal irrigated, low risk",
        "profile": profile
    })
    assert r_chat2.status_code == 200
    d2 = r_chat2.get_json()
    assert d2["profile"]["soil_type"] == "loam"
    assert d2["profile"]["irrigated"] is True
    assert d2["profile"]["risk_tolerance"] == "low"

    # 5. Full plan request
    r_chat3 = c.post("/chat", json={
        "message": "Show full 6-season plan",
        "profile": d2["profile"]
    })
    assert r_chat3.status_code == 200
    d3 = r_chat3.get_json()
    assert d3["plan"] is not None
    assert "rotation" in d3["plan"]
    assert "schedule" in d3["plan"]

    # 6. Chat reset
    r_reset = c.post("/chat/reset")
    assert r_reset.status_code == 200
    d_reset = r_reset.get_json()
    assert d_reset["intent"] == "reset"
    assert len(d_reset["profile"]) == 0

    print("ALL WEB CHAT ENDPOINT TESTS PASSED")

if __name__ == "__main__":
    test_web_routes()
