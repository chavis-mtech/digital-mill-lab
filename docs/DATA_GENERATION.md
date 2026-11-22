# Data Generation — synthetic dataset for "Demo Palm Mill A"

> Owner: data-engine. Status: **implemented** (generator, validator, tests). Everything below describes
> **Synthetic Demonstration Data** produced by a model of a *fictional* mill ("Demo Palm Oil Co. (fictional)" /
> "Demo Palm Mill A"). **Synthetic ≠ real plant.** No number here is a measurement of any company, and a model trained on
> it is not validated for any real mill.

## 1. How to build, validate, inspect

```bash
make seed                                   # canonical build -> data/demo.db + data/synthetic/MANIFEST.json
cd apps/ai-api && source .venv/bin/activate
python -m app.seed [--seed N] [--db-url URL] [--days N] [--anchor YYYY-MM-DD] [--if-empty] [--reset] [--no-manifest]
python -m app.seed.validate [--db-url URL] [--json]      # 58 checks, exit 1 on failure
python -m app.seed.report   [--db-url URL] [--out F]     # scenario chain report (focus vs baseline)
DML_FULL_SEED_TEST=1 python -m pytest tests/data          # includes the full 120-day build test
```

* Default behaviour rebuilds from scratch (drop + `create_all` of the frozen schema, then load). `--if-empty` (Docker
  CMD) only builds when `facilities` is empty. `--reset` is accepted for explicitness.
* Relative SQLite URLs resolve from the repo root (app convention); a relative path that would escape the repo (e.g.
  `sqlite:///../../data/dev/x.db` typed from `apps/ai-api`) is resolved from the CWD instead (`app/seed/dburl.py`).
* Wrappers: `scripts/seed/seed.py`, `scripts/validation/validate_dataset.py`, `scripts/simulation/scenario_report.py`;
  `scripts/seed/snapshot_params.py` regenerates the parameter snapshot from `docs/business/DOMAIN_PARAMETERS.json`.
* Opening a scenario (ADR-005/011): read `scenario_runs.focus_ts` and send it as `as_of` (or send `scenario_id`;
  the API resolves it to `focus_ts`). `baseline_ts` is the comparable normal moment for before/after views.

## 2. Determinism, size, runtime (measured 2026-11-21, MacBook, SQLite)

| Item | Value |
|---|---|
| Root seed | `20261120` (`--seed`); per-domain sub-generators `default_rng([seed, crc32(name)])` — no wall clock, no unseeded randomness |
| Window | 120 mill-local days, 2026-07-24 00:00 → 2026-11-21 00:00 Asia/Bangkok (2026-07-23 17:00Z → 2026-11-20 17:00Z), anchor 2026-11-20 |
| Content checksum | sha256 over every owned table ordered by id (`app/seed/writer.content_checksum`), stored in `data/synthetic/MANIFEST.json`; `validate` recomputes it and compares |
| Same seed twice | identical checksum (`34fc4a3750bd3a47...`, verified by `tests/data/test_seed.py` on fresh builds and by the CLI run twice) |
| Rows | 1,569,016 (sensor readings 1,355,288) |
| Runtime | ~10 s total (generate 4.3 s, write 3.6 s, checksum 1.9 s) |
| DB size | 158 MB (SQLite) |

Sensor cadence trade-off: 10-min samples for the presses, feed-water pump, boiler drum/steam flow, BPV header and
sterilizer vessel pressure (the tags the scenarios and tour use); 15 min for other rotating equipment and process
temperatures; 1 h for counters, levels and the genset. 1-min data would be ~15x larger (>2 GB) with no extra
information for hourly KPIs; coarser data would hide the sterilizer cycle shape and the debounce logic of alarms.

## 3. Pipeline (`apps/ai-api/app/seed/`)

| Module | Role |
|---|---|
| `params.py` | frozen snapshot of DOMAIN_PARAMETERS (169 parameters, 5 profiles); test fails on drift |
| `assumptions.py` | `P(key)` sourced values, `DEVIATIONS` (sourced key, different value, reason), `ASSUMED` (engineering assumptions, category, reason) |
| `registry.py` | company, facility, line, 12 stages, 35 equipment, 112 sensors (ISO 10816-3 limits), 12 technicians, 45 suppliers, 89 plantations |
| `episodes.py` | scenario schedule + background abnormalities → *driver* modifiers and `injected_events` labels |
| `calendar.py` | crop seasonality, weekday pattern, rain Markov chain, AR(1) intake noise, OER seasonal/daily noise, illustrative prices |
| `logistics.py` | daily intake → supplier deliveries → trucks (convoys) → gate / weighbridge / grading / unloading queue simulation |
| `mill.py` | hourly mill: ramp FIFO, capacity, start/stop, sterilization, steam balance, oil-loss model, OER/KER, FFA |
| `core.py` | runs the above with the supplier-quota feedback loop (ramp overflow → mill limits deliveries) |
| `energy.py` | equipment electrical state, plant electricity, turbine/grid/diesel, biomass fuel |
| `outputs.py` | rows for logistics, process_hourly, shifts, production batches, batch_inputs, by-products, CPO lots + compositions, lab results, energy |
| `sensors.py` | sensor time series from the same hourly state (+ dropouts, injected sensor faults) |
| `alerts.py` | rule/threshold alerts derived from the stored readings (like a plant alarm system) |
| `maintenance.py` | work orders, status history, maintenance events, seeded audit-log hash chain |
| `writer.py`, `build.py`, `__main__.py` | DB write (Core inserts, SQLite fast path for readings), checksum, manifest, CLI |
| `validate.py`, `report.py` | validator and scenario chain report |

## 4. Model equations

All parameters are `P(key)` from DOMAIN_PARAMETERS unless stated; `[EA]` = Engineering Assumption, `[SDD]` = Synthetic Demonstration Data.

**Supply.** Daily target `T_d = 60 t/h × 20 h × 0.72 × season(d) × weekday(d) × noise_d × rain_d × episode_d × quota_d`.
`season` = damped catchment profile interpolated daily (peak 1.33 in Sep); `noise` = AR(1) (φ 0.5, CV 0.12) [SDD];
rain: heavy day ×0.85, light ×0.95, day after heavy ×1.08 [EA]. Suppliers: 2 own estates, 4 estates, 12 dealers,
27 smallholder groups with persistent quality tier, reliability (delivery probability), harvest-to-mill time and
truck mix; a slow AR(1) random walk per supplier shifts quality over time. Truck payloads per class from
`truck_payload_*`, tare per class [EA], weighbridge resolution 10 kg; arrivals by the hourly profile
(sharpened in the queue episode, shifted to the afternoon on rain days), in convoys of 1–3 trucks.

**Queue (REL-14).** Gate check (lognormal, mean 5 min [EA]) → weigh-in on a 2-bridge pool shared with weigh-out
(2 min/event) → grading (2 graders, 4 min) → unloading (3 bays, 3 min + payload / 1 t/min) → weigh-out → exit.
Interval booking per server; outages are pre-booked busy intervals. Grade A/B/C/reject from ripeness; deduction %
from unripe, long stalk and dirt. Timestamps are censored at the window end.

**Mill (hourly).** FFB unloaded before the hour is available (FIFO cohorts keep supplier, quality, arrival).
`capacity = min(operator rate 56 t/h ± shift/stock adjustments [EA], 60 × thresher availability,
5 vessels × 20 t / ((cycle + 10)/60), Σ press capacity × (1 − derate), steam-limited rate)`; planned (Sunday
05:00–13:00, 8 h/week) and unplanned stops remove minutes; start at ≥ 100 t ramp stock, stop when empty
(starvation ≠ downtime). Ramp stock and wait follow (REL-05/06); CHK-06 holds (4.51 h weighted wait vs 4.52 h
stock/throughput).

**Oil losses (REL-03 extended) and OER (REL-04).**
```
U       = max(0, 1 − p_ster_peak/2.8) + 0.8·max(0, 1 − cycle/80)           (under-cooking index, [EA])
efb     = 0.07·(1 + 8U)          condensate = 0.10·(1 + 3.8U)               (+0.15 pp at U = 0.16 = scn_steam_deviation_extra_loss_pp)
fibre_p = 0.35·(1 + 0.04·max(0, 93 − T_dig))·(1 + 0.857·sev_p)·(1 + wear)·shift,  plant fibre = feed-weighted mean
sludge  = 0.40·(1 + 0.10·max(0, 90 − T_clar))                              (−5 °C → ×1.5 = scn_clarifier_sludge_loss_multiplier)
nut     = 0.08·(1 + 0.25·Σ share_p·sev_p)
OER     = 18.2 + season_pp(d) + (1.00 − total_loss) − 0.08·max(0, unripe − 4) − 0.10·max(0, (delay − 24)/24) + AR daily noise + hourly noise
KER     = 5.2 + daily noise − 0.03·max(0, unripe − 4) + hourly noise
FFA     = 2.4 + 0.03·max(0, delay − 8) + 0.03·max(0, overripe − 8)          (REL-07; delay = harvest-to-mill + ramp wait)
```
`sev_p` = bearing severity of press p (0..1); vibration `= 1.6 + (4.8 − 1.6)·sev`; derate `= 8%·clip((vib − 2.8)/(4.8 − 2.8))`.
CPO = FFB × OER, kernel = FFB × KER per hour; batches, shifts, lots aggregate the same rows (ratio of sums).

**Steam (REL-08).** Demand = processed × 0.48 × (1 + steam_extra) + 2 t/h banking while stopped [EA]; supply = 40 t/h ×
boiler availability (−3% after heavy rain: wet fibre). Operators throttle feed so demand ≤ 1.18 × supply; pressure
deficit `δ = 1 − supply/demand` scales drum (21 bar) and BPV header (3.0 bar) pressure, extends sterilizer cycles by
`15 min × min(1, δ/0.15)` and cools digesters by 6.7 °C per bar of header deficit [EA].

**Electricity (REL-09).** Per motor: `kW = rated × (0.30 + 0.62·load + friction) × health multiplier × running fraction`
(+ 0.30 × rated when left idle-running); plant = Σ motors + 70 kW unmetered base [EA]. Turbine 36 kWh per t steam
while running and steam ≥ 8 t/h [EA]; deficit → grid (≤ 300 kW [EA]) → diesel genset (0.27 L/kWh); loaders
0.4 L/t FFB. Cost = grid × tariff + diesel × price (daily price series). Biomass (REL-10): HHV needed =
steam × 2.2 GJ/t / (0.85 × boiler efficiency); fibre first, shell for the rest.

**Water, by-products.** Water = 1.35 m³/t + 6 m³/h; EFB 22%, fibre 13.5%, shell 5.5%, POME 0.65 t/t of FFB per
batch (±2% noise). The five outputs sum to ~64% (the rest is water/evaporation), never 100%.

**CPO storage (REL-12).** One lot per business day into the receiving tank (3 × 1,500 t); lots dispatched whole at
10:00, oldest first, ≥ 3 days old, keeping ≥ 700 t stock [EA]. Produced = dispatched + closing stock exactly.
Tank level sensors are computed from the lots. There is no dispatch table in the frozen schema: dispatch is
`cpo_output_lots.dispatched_at` (tanker trips = ⌈t/28⌉, not stored).

**Sensors.** Hourly drivers interpolated to the sample time; contiguous running block within an hour; first-order
thermal lags (bearings 40 min, digester 45 min, clarifier/flue 60 min); AR(1) noise; sterilizer vessel pressure
follows a cycle profile (triple-peak deaeration, hold at the achieved peak, blowdown). Dropouts at 0.5% of samples
(`sensor_dropout_rate_pct`); injected flatline/spike/dropout windows are labelled.

**Alerts (rule/threshold, source `rule`).** Sensor beyond warn/crit limit for 3 consecutive samples while the
equipment (process tags: the mill, after a 60-min start-up inhibit) is running; same (sensor, level) within 12 h
merged; resolved after 6 samples back inside. Process rules: 4-h OER > 0.8 pp (medium) / 1.3 pp (high) below the
trailing 28-day baseline; daily kWh/t > 18.5 / steam > 0.55 t/t on days ≥ 1,000 t; queue ≥ 12 / 25 trucks;
truck wait > 60 min; FFB wait-to-process > 12 h; lot FFA > 4.0 / 5.0%. 19 alerts in 120 days.

## 5. Timeline and scenario windows (anchor A = 2026-11-20; local time)

| Scenario | Window (local) | Focus (`as_of`) | Baseline | Primary entity | Drivers (all in `injected_events`) |
|---|---|---|---|---|---|
| ENERGY_EFFICIENCY_DROP | 09-07 → 09-14 | 09-10 15:00 | 08-31 15:00 | BLR-01 | boiler fouling (eff 0.60→0.52, flue +45 °C, ID fan +25%), sterilizer steam-trap leak (+15% steam/t), idle running, compressed-air leak (+75 kW); cleaned at the Sunday stop |
| OER_DEGRADATION | 09-30 → 10-06 | 10-02 16:00 | 09-23 16:00 | CLR-01 | 2 rain days → unripe +8 pp dealers / +5 smallholders / +1.5 estates, harvest-to-mill +12 h; sterilizer cycle 80→66 min; worn press screws (fibre loss +40%, current +4%); clarifier valve stuck (−6 °C) |
| NORMAL_DAY | 10-21 | 10-21 15:00 | = focus | — | none (dry, no noise draw, no breakdowns) |
| STEAM_PRESSURE_DEVIATION | 10-29 04:00 → 22:00 | 10-29 12:00 | 10-22 12:00 | FWP-01 | FWP-01 strainer clog → cavitation → boiler output −55% at peak; wet fibre after overnight rain |
| TRUCK_QUEUE_CONGESTION | 11-12 → 11-16 | 11-14 10:00 | 11-05 10:00 | WB-02 | 2 rain days then surge ×1.6 (×1.12 next day), convoy arrivals; WB-02 out 06:00–14:00 with manual ticketing; unloading bay 3 out 10:00–17:00 |
| PRESS_VIBRATION_ANOMALY | 11-16 → 11-21 (onset 11-06 03:00) | 11-20 15:00 | 11-05 15:00 | PRS-03 | bearing wear: vibration 1.6→4.8 mm/s, bearing temp +24 °C, friction current +12%, derate 8%, cake oil up to 13% dry basis; **no PRS-03 work order** after onset (tour creates it) |

Playback presets: **Today** (11-20) shows PRS-03 in ISO zone D with critical + bearing-temperature alerts; **Last 7 days**
(11-14→11-20) shows the queue focus day and the press degradation; **Last 30 days** adds the steam deviation, NORMAL_DAY,
the CTF-01 imbalance and an idle-running night. **Recommended ML temporal split:** train < 2026-10-15 00:00 local,
test ≥ that. Train side: ENERGY + OER episodes (8 labels), PRS-01 bearing wear (alert → WO → repair), DIG-02
overheating, minor steam dip, supplier quality day, 2 sensor flatlines, weight outliers, breakdowns. Test side:
STEAM, QUEUE, PRESS episodes (5 labels), CTF-01 imbalance (below alarm), idle-running night, PRS-02 spike, CLR-01
dropout, breakdowns. 54 labels total, 41 without a scenario code (background).

## 6. Cross-module chains (focus vs baseline, from `python -m app.seed.report`, file `data/synthetic/scenario_report.json`)

**PRESS_VIBRATION_ANOMALY (11-20 vs 11-05).** PRS-03 vibration max 5.32 vs 1.80 mm/s, bearing temp max 88.5 vs
65.4 °C, motor current mean 129.4 vs 119.6 A (+8%) → plant press-fibre loss 0.424 vs 0.357% FFB, OER 18.20 vs
18.42%, kWh/t 18.51 vs 17.31 → alerts: vibration HIGH 11-15 14:30, HIGH-HIGH (critical) 11-19 10:20, bearing temp HIGH
11-20 11:40 → lowest-OER batches PB-20261120-20 (17.89%), PB-20261120-16 (17.94%) feeding lot CPO-20261120-T1.

**OER_DEGRADATION (10-02 vs NORMAL_DAY 10-21).** Delivered unripe 8.7 vs 3.6%, harvest-to-mill 25.3 vs 18.6 h,
sterilizer cycle 66.2 vs 79.6 min, clarifier min 83.0 vs 89.0 °C, PRS-02 current 127.5 vs 122.6 A → losses: fibre
0.502 vs 0.360, sludge 0.616 vs 0.418, EFB 0.150 vs 0.077% FFB → OER 17.71 vs 18.52% (−0.81 pp), lot
CPO-20261002-T1 FFA 3.16 vs 2.91%, DOBI 2.89 vs 3.09 → alerts: OER below baseline 03:00 and 13:00, clarifier low
temperature 06:15 → lowest batches PB-20261002-18 (17.22%), -14 (17.43%).

**TRUCK_QUEUE_CONGESTION (11-14 vs 11-05).** Trucks wait-to-weigh mean 29.6 vs 5.5 min (max 123 vs 15), turnaround
128.8 vs 34.8 min, ramp stock max 646 vs 319 t → next day FFB wait-to-process 11.2 vs 4.7 h and lot FFA 3.17 vs
2.88% → alerts: truck wait > 60 min 11-14 11:23, queue ≥ 12 trucks 12:10, FFB wait > 12 h 11-15 15:00.

**STEAM_PRESSURE_DEVIATION (10-29 vs 10-22).** FWP-01 vibration max 3.75 vs 1.50 mm/s → drum min 17.5 vs 19.9 bar,
BPV header min 2.54 vs 2.92 bar → deviation hours: sterilizer cycle 93 vs 80 min, OER 18.32 vs 18.50%, digester
min 89.3 °C, turbine load 584 vs 752 kW, grid import 1,980 vs 921 kWh/day → alerts FWP-01 vibration 07:30, drum and
header pressure LOW 13:10.

**ENERGY_EFFICIENCY_DROP (episode week vs prior week).** kWh/t 19.54 vs 17.88 (+9.3%), steam 0.549 vs 0.493 t/t
(+11.5%), idle kWh up; flue gas max 219 vs 187 °C, ID-fan current 235 vs 173 A → alerts: daily kWh/t and steam/t,
flue gas HIGH, ID-fan current HIGH.

## 7. Physical and consistency rules (validated by `app.seed.validate`)

Referential integrity (PRAGMA foreign_key_check); no data outside the window; one process_hourly row per hour; CPO =
FFB × OER and kernel = FFB × KER (hour, batch); throughput ≤ 60 t/h; running + downtime ≤ 60 min; ramp continuity
from opening stock 0; processed ≤ received cumulatively; ramp ≤ 600 t outside the documented congestion episode;
received = unloaded FFB batches; shift/batch totals = hourly; batch_inputs mass = batch FFB and shares sum to 1
(ADR-017 mass balance); lot quantity = Σ compositions; CPO produced = dispatched + stock (CHK-03); tank ≤ 100%;
daily OER/KER in sourced ranges; daily FFB ≤ capacity × 24 (CHK-02); by-product fractions in range; five outputs ≤
75% (CHK-01); oil-loss terms reconcile (CHK-04); steam 0.35–0.80 t/t and 12–30 kWh/t (CHK-05); water in range; FFA,
moisture+dirt, clarifier, digester ranges (CHK-08); Little's law within 15% (CHK-06); net = gross − tare and ≤ class
max × 1.15 (CHK-07); delivery net = ticket net; truck timelines ordered; sensor values bounded; every sensor alert
derivable from a stored reading (CHK-09); alerts are rule alerts only; scenario effects (11 checks); every episode
labelled; audit hash chain verifies; no PRS-03 work order after onset; checksum = manifest. CHK-10 (seasonality) is
reported as info: monthly intake Jul 811 / Aug 952 / Sep 951 / Oct 939 / Nov 911 t/d — the September peak is
flattened by the supplier quota feedback (deliberate, see §8).

## 8. Deviations from the researcher's values (and why)

| Item | Researcher | Used | Reason |
|---|---|---|---|
| `capacity_utilisation_normal` | 0.78 | 0.72 | window spans the crop peak; at 0.78 September intake exceeds daily capacity and the ramp overflows (in range 0.6–0.92) |
| `press_count` / `press_unit_capacity` / `digester_count` | 6 / 10 / 6 | 4 / 15 / 4 | same 60 t/h; smaller sensor table; one press = 25% of feed (all in range) |
| `ramp_buffer_capacity_t` | 300 | 600 | peak-season afternoon arrivals build 300–450 t before the night shift (sourced max) |
| `ffb_supply_daily_cv` | 0.15 | 0.12 (AR φ 0.5) | persistent noise on top of the peak caused multi-day overflows (in range) |
| `scn_press_degradation_extra_fibre_loss_pp` | 0.30 plant-level | 0.10 (≈0.07 measured) | physically one press = 1/4 of feed with cake oil ≤ ~13% dry basis; press-level lab samples show the full effect |
| Press bearing temperature rise (PALM_MILL_PROCESS §5) | +10 °C | +24 °C | REL-15 "critical" needs temperature corroboration at zone D; alarm at 85 °C |
| OER_DEGRADATION unripe shift | +8 pp plant | +8 dealers / +5 smallholders / +1.5 estates (≈ +5 pp plant) | driver per supplier group; total OER drop 0.81 pp (sourced range 0.5–2.0, nominal 1.1) |
| Queue episode | arrivals ×1.8 for ~4 days, waits 3–5 h, wait-to-process 12–30 h, FFA +0.4–1.0 | ×1.6 one day (+1.12 next) + WB-02 outage + bay outage; max wait 2.1 h, mean 30 min; next-day wait-to-process 11.2 h; FFA +0.29 pp | a 4-day ×1.8 surge needs ~2,000 t/d intake vs 1,440 t/d capacity (ramp > 2,000 t) — implausible without refusing trucks; effect sizes are smaller but causal |
| ENERGY effects | steam 0.50→0.575, kWh 17→18.7 | steam +11.5%, kWh +9.3% (week vs week) | emergent from the four drivers |
| STEAM_PRESSURE_DEVIATION OER | "short OER dip" | −0.18 pp in the deviation hours; daily OER not visibly lower | deviation lasts ~8 h of a ~16 h production day |
| Electricity intensity | 17 kWh/t | 18.2 kWh/t window (16.4–22.3 daily) | idle-hour base load (pumps, banked boiler fan, lighting) is counted in the daily denominator (KPI_DEFINITIONS 4.6); in range 14–25 |
| BPV header warning | PALM_MILL_PROCESS: < 2.5 bar | 2.7 bar (−10%) | JSON `steam_pressure_alarm_deviation_pct` = 10% of setpoint |
| FFB weight loss while waiting | 0.7%/day (assumption) | not applied | keeps exact mass balance ticket → batch → batch_inputs; < 0.3% at the ~4.5 h mean wait |

## 9. Assumptions and fact categories

* Sourced: all `P(key)` values (categories per DOMAIN_PARAMETERS: Industry Practice, Historical Public Information,
  Engineering Assumption, Verified Public Fact). Engineering assumptions specific to the generator: `ASSUMED` in
  `assumptions.py` (operator rate, start/stop stock, banking steam, turbine kWh/t, grid limit, base load, fresh-FFB
  FFA, DOBI, loss gains, shift effects, queue service times, batch size, CPO dispatch policy, lab noise).
* Synthetic Demonstration Data: scenario effect sizes, noise levels, supplier traits, background abnormalities.
* Comparison days (scenario focus and baseline days, NORMAL_DAY) get no daily OER/KER noise draw, no intake-noise
  excursion and dry weather, so the contrast reflects the drivers (hourly noise still applies). This is a demo design
  choice, stated here so nobody mistakes it for natural variation.
* Business day = 00:00–24:00 Asia/Bangkok (ADR-016). Shifts: A 06:00–18:00, B 18:00–06:00 (business_date = shift start
  date); the 00:00–06:00 block of the first day belongs to no shift (`shift_id` NULL); the last shift is truncated at
  the window end.
* Cold start: empty ramp and empty CPO tanks at 2026-07-24 00:00 (first day processes less); traceability starts there.
* `process_hourly.ffb_received_t` is physical (ticket net) FFB unloaded; KPI-01 "accepted net" is
  `ffb_deliveries.accepted_kg` (after grading deductions). Rejected loads (~0.2%) are weighed and returned, never processed.
* Supplier quota feedback: when the ramp would exceed ~570 t, the mill limits the same/previous day's deliveries
  (multiplicative quota, ≤ 6 iterations); exempt in the queue episode. Real mills do this in the peak.
* `alerts.source` = `rule` (schema enum); `evidence_json.rule_type = "rule_threshold"`. ML writes `ml_*`/anomaly rows.
* `injected_events` is ground truth for evaluation only — PRIVATE, never exposed by the API, never an ML feature.
* Mutable tables (work orders, status history, maintenance events, audit logs) are seeded with `session_id` NULL
  (shared baseline, ADR-006). Seeded audit rows form a valid hash chain (ADR-013) that runtime writes extend.

## 10. Limits (read before using the data)

* One fictional mill, one line, 120 days; no annual shutdown, no public holidays, no lean season (Feb–Apr).
* Losses, OER and FFA are simple parametric functions with noise; there is no physics of digestion/pressing; lab
  values are model values plus noise, not instrument behaviour.
* Queue model is FIFO-ish interval booking; no driver behaviour, no appointment system.
* Equipment degradation shapes are prescribed curves (power laws), so remaining-useful-life results on this data
  say nothing about real bearings. Risk scores built on it are not calibrated probabilities.
* Prices are an illustrative random walk around sourced nominal values — not market data.
* Because we generated the data, any model can in principle learn the generator; ML must use temporal splits, never
  use `injected_events` or scenario codes as features, and report results as synthetic benchmarks.
