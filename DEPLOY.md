# Running the API on a server

## 1. Install & start (Linux server, Python 3.9+)
    unzip crop_advisor_project.zip && cd crop_advisor_project
    python3 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    export API_KEY="put-a-long-random-string-here"
    gunicorn -w 2 -b 0.0.0.0:8000 --timeout 30 server:app
Test:  `API_KEY=k python test_api.py`

## 2. Or with Docker
    docker build -t crop-api .
    docker run -d --restart always -p 8000:8000 -e API_KEY="your-secret" crop-api

## 3. Keep it running (systemd) - /etc/systemd/system/crop-api.service
    [Unit]
    Description=Crop API
    After=network.target
    [Service]
    WorkingDirectory=/home/ubuntu/crop_advisor_project
    Environment=API_KEY=your-secret
    ExecStart=/home/ubuntu/crop_advisor_project/venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 server:app
    Restart=always
    [Install]
    WantedBy=multi-user.target
Then: `sudo systemctl enable --now crop-api`. Put nginx/Caddy in front for HTTPS
(Meta requires HTTPS for webhooks; your bot server calls this API, so keep this API private
or at least protected by the API key).

## 4. Endpoints  (header `X-API-Key: <key>` on all except /health)
| Method | Path | Purpose |
|---|---|---|
| GET | /health | liveness check |
| GET | /options | valid states, soil types, crops |
| POST | /recommend | best crop + top 3 + ready-to-send WhatsApp `message` |
| POST | /plan | adds 6-season rotation, land allocation, dated task list |

Request body (only `state` is required):
    {"state":"Karnataka","soil_type":"red","ph":6.4,"organic_carbon":0.6,
     "temp":24,"rainfall":150,"irrigated":true,"sowing_date":"2026-11-10",
     "risk_tolerance":"medium","capital_per_acre":30000,
     "acres":5,"water_m3":6000,"labour_days":300}
Unknown values are estimated from the state's regional averages (reported in `features`).
Errors: 400 = bad input (message says which field), 401 = bad key, 500 = server error.

## 5. How your bot calls it (Python example)
    import requests
    r = requests.post("https://YOUR-SERVER/recommend",
        headers={"X-API-Key": KEY}, timeout=15,
        json={"state": "Karnataka", "soil_type": "red", "irrigated": True})
    if r.ok: send_whatsapp_text(user_number, r.json()["message"])
    else:    send_whatsapp_text(user_number, "Sorry: " + r.json().get("error", "try again"))
Node: `fetch(url,{method:"POST",headers:{"X-API-Key":KEY,"Content-Type":"application/json"},body:JSON.stringify(data)})`
