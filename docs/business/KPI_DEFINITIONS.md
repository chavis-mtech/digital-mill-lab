# KPI Definitions

> Task DML-006. Owner: researcher. Independent concept demo; all values are synthetic. Parameter keys in `code` refer to `docs/business/DOMAIN_PARAMETERS.json`. Every KPI payload must carry the provenance object defined in the build plan (kept private) section 3: `{"kind": "synthetic_actual" | "forecast" | "what_if", "source", "as_of", "model_version"}`.

## 1. Conventions that apply to every KPI

1. **Ratio of sums, never mean of ratios.** OER, KER, energy per tonne, cost per tonne and availability over a window are computed as sum(numerator) / sum(denominator) over the window. Averaging daily percentages weights a 300 t day the same as a 1,100 t day and is wrong.
2. **Units.** Mass in tonnes (t); kg only in raw tickets. Percent values are stored as numbers in percent (18.2), not fractions, unless the field name says `_fraction`. Money in THB.
3. **Time.** Stored UTC; business day = `Asia/Bangkok` (the mill day starts 00:00 local unless the data engine defines a 06:00 shift boundary - document it once and use it everywhere). `as_of` is the selected playback moment; nothing after `as_of` may influence a `synthetic_actual` value.
4. **Provenance mapping.** Values for periods up to `as_of` are `synthetic_actual`; model outputs for later times are `forecast`; scenario simulator output is `what_if`. A card that mixes them must show each part with its own label.
5. **Current vs previous period.** "Previous period" = the immediately preceding window of the same length (e.g. last 7 days vs the 7 days before). Show absolute and relative change; for ratio KPIs show change in percentage points.
6. **Filters.** Date range, period (today / 7 / 30 days / scenario date), unit (plant, production line, equipment group). Aggregation must respect the filter on both numerator and denominator.
7. **Missing data.** If a denominator is zero or the sensor/ticket series is incomplete, return `null` plus a reason code; never 0 or a fabricated value.
8. **Rounding.** Compute at full precision; round only at presentation (OER one decimal in executive cards, two in analytics).
9. **No hardcoded values.** Every KPI is computed from stored records; thresholds come from configuration derived from the parameters (below), not literals in components.

## 2. Logical data entities used below (the architect maps these to tables)

`weighbridge_ticket` (id, supplier_id, truck_id, event, gross_kg, tare_kg, net_kg, deduction_kg, ts) | `ffb_delivery` (supplier, grade, accepted_kg) | `queue_event` (truck_id, type, ts) | `ramp_stock_reading` (ts, tonnes) | `process_shift` / `production_batch` (start, end, ffb_sterilised_t, running_h) | `cpo_tank_reading` (tank, ts, level, temp, density) | `cpo_dispatch` (tanker, gross/tare/net) | `lab_result` (sample_ts, tank/batch, ffa, moisture, dirt, sludge_oil...) | `equipment_state_event` (equipment, state, start, end, reason_code) | `sensor_reading` (sensor, ts, value, quality) | `energy_reading` (kwh_generated, kwh_import, diesel_l, steam_t, water_m3) | `cost_item` | `alert` (id, rule, severity, status, opened_at, resolved_at) | `work_order`.

## 3. KPI catalogue

Group A: executive control tower (SPEC section 4A). Group B: supporting.

| ID | KPI | Formula | Unit | Grain | Provenance kinds |
|---|---|---|---|---|---|
| KPI-01 | FFB Received | sum(accepted net weight of inbound FFB tickets in window) | t | ticket -> day | synthetic_actual |
| KPI-02 | FFB Processed | sum(FFB sterilised) = FFB received + opening ramp stock - closing ramp stock (mass balance), or direct cage/hopper weighing | t | shift -> day | synthetic_actual |
| KPI-03 | CPO Produced | CPO dispatched + (closing tank stock - opening tank stock) | t | day | synthetic_actual, forecast (model) |
| KPI-04 | OER | CPO produced / FFB processed x 100 | % | day, 7-day rolling, window | synthetic_actual, forecast, what_if |
| KPI-05 | KER | palm kernel produced / FFB processed x 100 | % | day, window | synthetic_actual |
| KPI-06 | Throughput | FFB processed / running hours | t/h | shift, day | synthetic_actual, what_if |
| KPI-07 | Capacity utilisation | FFB processed / (design capacity x scheduled hours) x 100 | % | day | synthetic_actual |
| KPI-08 | Equipment availability | (scheduled hours - maintenance downtime hours) / scheduled hours x 100 | % | equipment, plant | synthetic_actual, what_if |
| KPI-09 | Plant downtime | sum(duration of stop events), split planned/unplanned/starved | h | event -> day | synthetic_actual, what_if |
| KPI-10 | Energy per tonne | see section 4.6 (electricity kWh/t, steam t/t, diesel L/t, energy cost THB/t) | mixed | day, window | synthetic_actual, forecast, what_if |
| KPI-11 | Estimated production cost | see section 4.7 | THB/t CPO, THB/t FFB | day, window | synthetic_actual, what_if |
| KPI-12 | Active maintenance alerts | count(alerts with status open, acknowledged or in_review at as_of), by severity | count | snapshot | synthetic_actual |
| KPI-13 | Logistics queue time | mean(weigh-in start - gate arrival) over completed trucks; plus current queue length | min; trucks | truck -> hour/day | synthetic_actual, forecast |
| KPI-14 | Truck turnaround | exit time - gate arrival; mean, median, p90 | min | truck | synthetic_actual |
| KPI-15 | FFB wait-to-process | tonnage-weighted (sterilizer feed time - arrival time), or ramp stock / throughput | h | batch, day | synthetic_actual |
| KPI-16 | CPO FFA and quality | mass-weighted mean FFA, moisture, dirt; off-spec share = CPO mass with FFA > 5.0% or M&I > 0.25% | %, % | tank/batch -> day | synthetic_actual |
| KPI-17 | Total oil loss | sum(stream flow x oil content) / FFB processed x 100; by stream (EFB, condensate, fibre, sludge, other) | % of FFB | lab sample -> day | synthetic_actual |
| KPI-18 | Equipment health state | rule-based state from sensor criteria (section 4.9) | state | equipment, hour | synthetic_actual |
| KPI-19 | Weighbridge / unloading utilisation | arrival rate x service time / servers | fraction | hour | synthetic_actual |
| KPI-20 | Supplier quality score | per supplier: unripe share, deduction %, FFA-at-delivery proxy | %, score | supplier, month | synthetic_actual |
| KPI-21 | Traceability coverage | share of CPO output mass attributable to supplier lots (lot-based) or covered by mass-balance allocation | % | day | synthetic_actual |
| KPI-22 | Maintenance workflow | work-order backlog, mean time to repair (MTTR), mean time between failures (MTBF), PM compliance | count, h, h, % | week | synthetic_actual |

## 4. Detailed definitions and pitfalls

### 4.1 FFB Received (KPI-01)
- **Formula:** sum over inbound FFB tickets of (gross - tare - grading deduction) / 1000, filtered by ticket completion time inside the window.
- **Variants:** *ticket net* (gross - tare) versus *accepted net* (after deductions). The executive KPI uses accepted net; the ticket net is shown in logistics.
- **Pitfalls:** tickets completed after midnight belong to the next business day; a truck in the queue at `as_of` is not received yet; tare estimated from stored tare must be flagged; do not mix kg and t.

### 4.2 FFB Processed (KPI-02)
- **Formula (mass balance):** received + opening ramp stock - closing ramp stock - rejected/diverted. Opening/closing ramp stock come from stock readings at the day boundary.
- **Pitfalls:** processed can exceed received on a day when stock is drawn down; it can never exceed `capacity x scheduled hours` (check CHK-02 in the JSON). Weight loss while waiting (about 0.7% per day, assumption) means processed mass is slightly below ticket mass of the same FFB; state whether the model applies it.

### 4.3 CPO Produced (KPI-03)
- **Formula:** dispatched net mass + (closing stock - opening stock), with stock = tank level volume x density (0.891 t/m3 near 50 C) corrected for temperature.
- **Pitfalls:** tank dips are the largest source of error; level sensor noise of 0.5% on a 1,500 t tank is 7.5 t - as large as the entire effect of a 0.5 pp OER change at 936 t FFB (4.7 t). The KPI must therefore also report a rolling 7-day figure. Do not count CPO bought-in or returned; exclude tank-to-tank transfers.

### 4.4 OER (KPI-04), variants and pitfalls
- **Definition used in the product:** **OER = CPO produced / FFB processed x 100**, CPO and FFB on the mass basis of KPI-02/03. Unit: percent of FFB mass.
- **Why the stock terms matter (calculation example, synthetic):** FFB received 900 t (accepted), ramp stock 120 t at open and 84 t at close -> processed = 900 + 120 - 84 = 936 t. CPO dispatched 160.0 t, tank 1,200.0 t at open and 1,210.4 t at close -> produced = 170.4 t. OER = 170.4 / 936 = **18.2%**. Using FFB received instead of processed gives 18.93% (inflated by 0.7 pp); using dispatched CPO instead of produced gives 17.09% (deflated by 1.1 pp).
- **Variants (label them, do not mix):**
  1. *Process OER* (above) - used for operations.
  2. *Received-basis OER* (CPO / FFB received) - sometimes used for supplier discussions; sensitive to stock changes.
  3. *Gross-ticket OER* (FFB before grading deduction) - lower than accepted-basis by roughly the deduction share: with a 1.5% deduction, 18.2% becomes 17.93%.
  4. *Quality-adjusted OER* - CPO normalised to the M&I limit (0.25%); the effect is small (0.1% of CPO mass is about 0.02 pp OER).
  5. *Thai pricing basis (18% oil content)* - the basis on which FFB prices are quoted (S32). It is a commercial convention and is **not** the mill's measured OER; never display them as the same thing.
  6. *Total oil* (CPO + kernel oil equivalent) - not used.
- **Pitfalls:** (a) process lag: oil from fruit sterilised now appears in the tank 3-6 h later, so shift-level OER needs lag alignment or a longer window; (b) daily noise of about 0.25 pp is normal in the demo, weekly about 0.10 pp; (c) seasonal swing (about +-0.5 pp assumed); (d) moisture and dirt in FFB, ripeness mix and delay all change true yield, which is why OER is a diagnostic to be explained by contributing factors, not a score of operator performance; (e) never compare OER across mills without the same definition.
- **Thresholds (relative, configurable):** green within 0.3 pp of the 28-day baseline, amber 0.3-0.8 pp below, red more than 0.8 pp below, all *[Engineering Assumption]*. The national average 18.2% (2025, S13) is context only, not a target for the fictional mill.

### 4.5 Throughput, capacity utilisation, KER
- **Throughput** = FFB processed / **running** hours (not scheduled hours); **capacity utilisation** = FFB processed / (design capacity x scheduled hours). Both can be below target because of starvation: a 40% utilisation day in February is a supply fact, not a maintenance problem.
- **KER** = kernel produced / FFB processed x 100; kernel mass on a dry-to-spec basis (moisture below about 7%); same pitfalls as OER for stock changes (silo level).

### 4.6 Energy per tonne (KPI-10)
- **Electricity intensity** = (kWh generated + kWh imported - kWh exported) / FFB processed. Baseline 17 kWh/t (range 14-25).
- **Steam intensity** = steam produced (boiler flow meter) / FFB processed. Baseline 0.50 t/t (0.42-0.65).
- **Diesel intensity** = diesel litres (genset + mobile equipment) / FFB processed. Baseline about 0.4 L/t plus genset use.
- **Energy cost per t FFB** = (grid kWh x tariff + diesel L x price + purchased fuel) / FFB processed. Biomass burned from the mill's own fibre and shell has no purchase cost; a variant may charge an opportunity cost at PKS/EFB prices.
- **Normalise for load:** fixed loads make intensity worse at low throughput. Compare against an *expected intensity at the same throughput* (regression on normal days) before calling an abnormal rise; this is the KPI that feeds AI-E02.
- **Pitfalls:** mixing steam flow metering bases (saturated vs superheated), double counting self-consumed electricity, ignoring turbine outages that shift load to diesel.

### 4.7 Estimated Production Cost (KPI-11)
- **Cost per t FFB processed** = (FFB purchase cost + conversion cost + maintenance + energy cost) / FFB processed.
- **Cost per t CPO** = (total cost - by-product credits, mainly kernel) / CPO produced. The credit method must be stated (here: kernel revenue credited at the configured kernel price).
- **Calculation example (synthetic, illustrative prices):** 936 t FFB x 7.5 THB/kg = 7.02 M; conversion 400 THB/t = 0.374 M; maintenance 80 THB/t = 0.075 M; energy about 0.018 M => total about 7.49 M. Kernel credit 48.7 t x 15,000 THB/t = 0.73 M. Net cost 6.76 M / 170.4 t CPO = about **39,670 THB/t CPO** versus an illustrative CPO price of 40,000 THB/t.
- **Interpretation guard:** at these (dated) public price levels the spread is thin: 18.2% x 40,750 THB/t = about 7.4 THB per kg FFB against an FFB price of about 7.45 THB/kg. Conversion cost and kernel/by-product income decide the margin. Label every output *estimated*, *illustrative* and never present it as any company's cost or profit. Prefer showing **deltas** (for example +0.5 pp OER on 936 t FFB = +4.68 t CPO = about 187,000 THB/day at 40,000 THB/t) over absolute margin.
- **Pitfalls:** allocation choice between CPO and kernel; FFB cost basis (ticket vs accepted weight); price date; double counting energy already inside conversion cost.

### 4.8 Alerts (KPI-12)
- **Active** = status in {open, acknowledged, in_review} at `as_of`, derived from alert event history so the count is correct for any past date. Resolved/closed alerts are excluded.
- **Severity** is computed from the rule that fired (health state and risk), not randomly assigned; de-duplicate repeated firings of the same (equipment, rule) within 24 h into one alert with a count.
- **Aging:** report open duration; an alert unattended beyond a configured limit escalates in display only.
- **Pitfall:** an alert is a prompt for human verification, not proof of a fault.

### 4.9 Queue time and truck turnaround (KPI-13/14/15)
- **Timeline per truck:** gate arrival -> queue join -> weigh-in start/end -> inspection -> unloading start/end -> weigh-out -> exit.
- **Queue time** = weigh-in start - gate arrival. **Unloading wait** = unloading start - weigh-in end. **Turnaround** = exit - gate arrival. **Wait-to-process** (FFB, not truck) = sterilizer feed time - arrival, or ramp stock / throughput (Little's law).
- **Statistics:** mean, median, p90, max over *completed* trucks; show *current queue length* separately (trucks waiting at `as_of`). Trucks still in the queue are right-censored: include them in the current-queue count but not in completed-truck averages, and say so.
- **Pitfalls:** peak-hour weighting (average over the day hides afternoon convoys), weekend effects, and treating long dwell as misconduct (it is a flow problem to analyse, never an accusation).
- **Utilisation (KPI-19):** weighbridge rho = arrivals/h x events/trip x service min / 60 / servers; unloading rho = arrivals/h x (payload / unloading rate) / 60 / bays. At normal arrivals (5-9 trucks/h) rho is about 0.2-0.55; above 0.85 the queue grows nonlinearly. The weighbridge is rarely the real bottleneck; unloading and sterilizer feed are.

### 4.10 Equipment availability and downtime (KPI-08/09)
- **Mechanical availability (MA)** = (scheduled hours - downtime caused by breakdown or planned maintenance) / scheduled hours x 100, per asset; plant availability = hours at which the process line could run at >= 90% of the throughput target / scheduled hours.
- **Operational utilisation** = running hours / scheduled hours; includes starvation and operational stops. Do not call it availability.
- **Downtime categories (reason codes):** unplanned equipment, planned maintenance, utility (steam/power/water), operational (cleaning, changeover), **starved (no FFB)**, external (weather, grid). Only the first two reduce mechanical availability.
- **Derived:** MTBF = running hours / failures; MTTR = downtime hours / repairs.
- **Partial operation:** derating (for example a press line at 92%) is not downtime; it appears in throughput and utilisation.
- **Downtime impact (what_if, AI-C06):** lost FFB capacity = downtime h x throughput t/h. If the mill is supply-constrained (ramp stock accumulating), nothing is lost, output is deferred and wait-to-process rises; if capacity-constrained (peak), CPO lost = recoverable fraction of lost FFB x OER. Keep OER-uplift and downtime-recovery on separate FFB bases to avoid double counting in ROI.

### 4.11 Health state (KPI-18)
- Normal / Warning / Critical / Maintenance Required, from explicit criteria: ISO 10816-3 zone of vibration by the equipment's group and support (A/B normal; C warning; D critical), trend (for example +25% in 7 days), bearing temperature versus its own baseline (+10 C), current versus baseline (+10%), plus corroboration rules. "Maintenance Required" is set when a work order is open. Criteria are shown in the UI. Scores are ranking aids, not calibrated failure probabilities.

### 4.12 Supplier quality and traceability (KPI-20/21)
- Supplier quality score from unripe share, overripe share, deduction % and dirt over a rolling 30 days. Traceability coverage depends on the model: **mass-balance** (CPO output allocated pro rata to supplier input mass over a period) or **lot-based** (separate lots kept through a batch). State which applies; with mixing across suppliers lot-level claims are not valid.

## 5. Display status rules (all configurable, all Engineering Assumptions)

| KPI | Green | Amber | Red |
|---|---|---|---|
| OER | within 0.3 pp of baseline | 0.3-0.8 pp below | more than 0.8 pp below |
| Throughput / utilisation | at or above the season's expected utilisation (`capacity_utilisation_*`) | 10-20% below | more than 20% below, excluding starvation |
| Equipment availability | >= 93% | 85-93% | < 85% |
| Electricity per t | <= 18.5 kWh/t at nominal load | 18.5-21 | > 21 |
| Steam per t | <= 0.55 t/t | 0.55-0.62 | > 0.62 |
| CPO FFA | <= 4.0% | 4.0-5.0% | > 5.0% (off-spec) |
| Queue time | <= 15 min | 15-60 | > 60 |
| Truck turnaround | <= 60 min | 60-120 | > 120 |
| Wait-to-process | <= 12 h | 12-24 | > 24 |
| Active critical alerts | 0 | 1 | >= 2 |

## 6. Validation rules for KPI services and tests

1. OER recomputed from raw tickets, tank readings and stock changes equals the KPI payload within 0.01 pp.
2. For any window, sum of daily FFB processed equals the window value; OER over a window equals sum(CPO)/sum(FFB), not the mean of daily OER.
3. FFB processed <= capacity x scheduled hours on every day.
4. Total oil loss by stream sums to the total within rounding; OER_potential - total loss = OER within tolerance.
5. Availability + downtime hours + starved hours + running hours reconcile to scheduled hours.
6. Alert count at a past `as_of` equals the count reconstructed from alert events.
7. Every KPI response contains provenance, units and the filters applied; null with reason when data is missing.
8. The 120-day dataset shows seasonality and scenario effects in the KPIs exactly where `docs/business/PALM_MILL_PROCESS.md` section 5 says they should.
