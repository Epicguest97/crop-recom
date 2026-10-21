"""Run: ALLOW_NO_AUTH=1 python test_api.py"""
import os
os.environ.setdefault("API_KEY", "k")
from server import app

c = app.test_client()
h = {"X-API-Key": "k"}
assert c.get("/health").status_code == 200
assert c.post("/recommend", json={"state": "Karnataka"}).status_code == 401
r = c.post("/recommend", headers=h, json={"state": "Karnataka", "irrigated": "yes", "sowing_date": "2026-11-10"})
assert r.status_code == 200, r.data
d = r.get_json(); print(d["message"]); assert d["best_crop"]
assert c.post("/recommend", headers=h, json={"state": "Karnataka", "ph": 99}).status_code == 400
assert c.post("/recommend", headers=h, json={}).status_code == 400
assert c.post("/recommend", headers=h, data="x").status_code == 400
p = c.post("/plan", headers=h, json={"state": "Punjab", "acres": 5, "sowing_date": "2026-11-05", "irrigated": True})
assert p.status_code == 200, p.data
j = p.get_json(); print(j["best_crop"], j["allocation"]["allocation"], j["schedule"]["next_tasks"][:2])
print("ALL TESTS PASSED")
