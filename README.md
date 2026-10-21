# Crop Advisor (formula-based, no ML, standard library only)

## 🌐 Web Chat Interface (Clean & Rule-Based)
Launch the interactive web chat:
```bash
ALLOW_NO_AUTH=1 python server.py
# Or with virtual environment:
./venv/bin/python server.py
```
Then open your browser at **http://localhost:8000**

- **Chat Interface**: Type farm descriptions in conversational English (e.g. *"I have 5 acres of red soil in Karnataka with borewell"*).
- **100% Deterministic Regex**: Uses pure Python `re` pattern matching to extract farm location, soil type, irrigation status, acreage, budget, risk preference, and season.
- **NO AI/LLM Required**: Zero black-box AI; recommendations are calculated using agronomic suitability formulas, regional climate defaults, and market price models.
- **Live Farm HUD**: Displays real-time parsed slots and a regex inspector.
- **Full Plans**: Type *"Show full plan"* to see a 6-season rotation, plot allocation, and dated farming tasks.

## 💻 CLI Run
    python run.py --input sample_input.json
    python run.py --input sample_input.json --today 2026-11-12   # simulate a later day (re-plans schedule)
Needs Python 3.8+. Full results are saved to report.json.

## Files
| File | Module | Formula |
|---|---|---|
| crop_advisor/enrichment.py | 1 Enrichment | Missing values filled from regional table; each tagged measured/estimated |
| crop_advisor/suitability.py | 2 Suitability | fit = .35*temp + .25*rain + .20*pH + .20*soil (trapezoid scores); prob = softmax(fit/0.15) |
| crop_advisor/economics.py | 3 Yield/profit/water/risk | yield = base*(0.4+0.6*fit)*(1-Ky*(1-ETa/ETc)); deficit = ETc - 0.8*rain; profit = yield*price - cost - irrigation; p10/p90 = profit -/+ 1.28*sd |
| crop_advisor/ranking.py | 4 Ranking | score = w_fit*fit + w_profit*minmax(profit) + w_water*(1-deficit/ETc) + w_risk*(1-risk); weights depend on risk tolerance; reasons = each criterion vs. candidate average |
| crop_advisor/rotation.py | 5 Rotation | N/organic matter/pest state transitions; Soil Health = 100*(.4N + .3OM + .3(1-pest)); beam search over 6 seasons |
| crop_advisor/allocator.py | 6 Allocation | Greedy 0.25-acre chunks by risk-adjusted profit under area, water, labour, budget, max-share limits |
| crop_advisor/scheduler.py | 7 Scheduler | GDD = max(0, Tmean - Tbase) accumulates to stage dates; irrigation interval resets on rain; rain/heat rules |
| crop_advisor/data.py | | Crop table + regional defaults (**illustrative numbers - replace with local data**) |

## Customising
- Add a crop: add one `_c(...)` row in data.py. Add a state: add a row in `REGIONS`.
- Real weather/soil: replace `_estimate()` in enrichment.py with an API call.
- Daily updates: run the scheduler each morning with observed weather in `forecast`.
- Change priorities: edit `WEIGHTS` in ranking.py or `W` in suitability.py.
- Exact optimiser: swap allocator.py's greedy loop for a PuLP LP (same inputs/outputs).
