---
id: kb-industrial-kpi-guide
title: Industrial KPI Guide for a Palm Oil Mill
doc_type: sample
language: en+th
status: "sample — authored for the demo, not a real company document"
sources:
  - docs/business/KPI_DEFINITIONS.md
  - docs/business/PALM_MILL_PROCESS.md
  - docs/business/DOMAIN_PARAMETERS.json
  - docs/SPEC.md
  - docs/architecture/DATABASE_SCHEMA.md
  - S13
  - S14
  - S18
  - S22
  - S26
  - S28
  - S31
  - S40
last_reviewed: 2026-11-21
---

# Industrial KPI Guide for a Palm Oil Mill

## สรุปภาษาไทย

เอกสารนี้อธิบายนิยามและสูตรของ KPI หลักของโรงสกัดน้ำมันปาล์มตัวอย่าง ได้แก่ OER, KER, ปริมาณการผลิต (throughput), ความพร้อมใช้งานของเครื่องจักร (availability), เวลาหยุด, พลังงานต่อตัน, เวลารอคิว, เวลาหมุนเวียนรถ (turnaround) และเวลารอก่อนการผลิต พร้อมข้อควรระวังในการคำนวณ ค่าทั้งหมดในเอกสารเป็นตัวอย่างเพื่อการสาธิต ไม่ใช่ข้อมูลของบริษัทใด ๆ และไม่ได้เป็นเป้าหมายของโรงงานใด

## Purpose

This guide defines each KPI used in the demo: its formula, unit, grain, provenance and the common pitfalls. The demo's Copilot cites this guide when it explains a number. The guide describes the definitions. It does not say that any demo number is a real result.

## Fact tags

- [Industry Practice]: common definition or guidance.
- [Engineering Assumption]: a demo threshold or design choice. Adjustable.
- [Historical Public Information]: a dated public figure, used as context only.
- [Synthetic Demonstration Data]: a value created for the demo.

## Conventions that apply to every KPI

1. **Ratio of sums, never mean of ratios.** Compute OER, KER, energy per tonne, cost per tonne and availability over a window as sum(numerator) / sum(denominator). Averaging daily percentages gives a 300 t day the same weight as a 1,100 t day, which is wrong.
2. **Units.** Mass is in tonnes (t). Use kg only on raw weighbridge tickets. Percent values are stored as numbers (18.2), not fractions. Money is in THB.
3. **Time.** Store UTC. The business day is `Asia/Bangkok`. Nothing after the selected `as_of` may affect a `synthetic_actual` value.
4. **Provenance.** Values up to `as_of` are `synthetic_actual`. Model outputs for later times are `forecast`. Scenario results are `what_if`. A card that mixes them must label each part.
5. **Previous period.** The previous period is the window of the same length immediately before. Show absolute and relative change. For ratios, show the change in percentage points (pp).
6. **Missing data.** If a denominator is zero or a source series is incomplete, return null with a reason code. Never return 0 or an invented value.
7. **Rounding.** Compute at full precision and round only for display. OER uses one decimal on executive cards and two decimals in analytics.
8. **No hard-coded values.** Thresholds come from configuration, not from literals in the interface.

## KPI catalogue

| KPI | Formula (short) | Unit | Grain | Provenance |
|---|---|---|---|---|
| FFB received | Sum of accepted net weight of inbound FFB tickets in the window | t | Ticket, day | `synthetic_actual` |
| FFB processed | FFB sterilised, from mass balance: received + opening ramp stock - closing ramp stock | t | Shift, day | `synthetic_actual` |
| CPO produced | CPO dispatched + (closing tank stock - opening tank stock) | t | Day | `synthetic_actual`, `forecast` |
| OER | CPO produced / FFB processed x 100 | % | Day, rolling 7 days, window | `synthetic_actual`, `forecast`, `what_if` |
| KER | Kernel produced / FFB processed x 100 | % | Day, window | `synthetic_actual` |
| Throughput | FFB processed / running hours | t/h | Shift, day | `synthetic_actual`, `what_if` |
| Capacity utilisation | FFB processed / (design capacity x scheduled hours) x 100 | % | Day | `synthetic_actual` |
| Equipment availability | (scheduled hours - maintenance downtime hours) / scheduled hours x 100 | % | Equipment, plant | `synthetic_actual`, `what_if` |
| Plant downtime | Sum of stop-event durations, split into planned, unplanned and starved | h | Event, day | `synthetic_actual`, `what_if` |
| Energy per tonne | Electricity, steam, diesel and cost per t FFB (see below) | mixed | Day, window | `synthetic_actual`, `forecast`, `what_if` |
| Production cost | Cost per t FFB and cost per t CPO (see below) | THB/t | Day, window | `synthetic_actual`, `what_if` |
| Active alerts | Count of alerts still active at `as_of`, by severity | count | Snapshot | `synthetic_actual` |
| Queue time | Mean of (weigh-in start - gate arrival) over completed trucks; plus current queue length | min; trucks | Truck, hour, day | `synthetic_actual`, `forecast` |
| Truck turnaround | Exit time - gate arrival (mean, median, 90th percentile) | min | Truck | `synthetic_actual` |
| Wait-to-process | Ramp stock / throughput, or tonnage-weighted (sterilizer feed time - arrival time) | h | Batch, day | `synthetic_actual` |
| CPO FFA and quality | Mass-weighted mean FFA, moisture and dirt; off-spec share | %, % | Tank or batch, day | `synthetic_actual` |
| Total oil loss | Sum of (stream flow x oil content) / FFB processed x 100, by stream | % of FFB | Lab sample, day | `synthetic_actual` |

## OER (oil extraction rate)

**Formula.** OER = CPO produced / FFB processed x 100. Both values use the mass basis above. The unit is percent of FFB mass.

**Calculation example (synthetic).** FFB received 900 t. Ramp stock 120 t at open and 84 t at close, so FFB processed = 900 + 120 - 84 = 936 t. CPO dispatched 160.0 t. Tank stock 1,200.0 t at open and 1,210.4 t at close, so CPO produced = 160.0 + 10.4 = 170.4 t. OER = 170.4 / 936 = **18.2%**. [Synthetic Demonstration Data]

**Why the stock terms matter.** Using FFB received instead of FFB processed gives 18.93%, which is inflated by about 0.7 pp. Using dispatched CPO instead of CPO produced gives 17.09%, which is deflated by about 1.1 pp.

**Named variants. Label them and do not mix them.**
1. *Process OER* (the one above), used for operations.
2. *Received-basis OER* (CPO / FFB received), sometimes used in supplier discussions. It is sensitive to stock changes.
3. *Gross-ticket OER* (before grading deduction). It is lower than the accepted-basis value by roughly the deduction share. With a 1.5% deduction, 18.2% becomes about 17.93%. [Engineering Assumption]
4. *Quality-adjusted OER*, normalised to the impurity limit. The effect is small.
5. *Thai pricing basis (18% oil content)*, the basis on which FFB prices are quoted. It is a commercial convention. It is not the mill's measured OER, and the two must never be shown as the same thing. [Historical Public Information, S32]
6. *Total oil* (CPO plus kernel oil equivalent). Not used in the demo.

**Reference values.** The national average OER was 18.2% in 2025, and 17.7% in 2024. [Historical Public Information, S13] The demo's nominal mill value is 18.2%, with a range of 15.8 to 20.5%. [Industry Practice, S13, S18] The national average is context only. It is not a target for the fictional mill.

**Pitfalls.**
- *Process lag.* Oil from fruit sterilised now reaches the tank 3 to 6 hours later. Shift-level OER needs lag alignment or a longer window. [Industry Practice]
- *Noise.* Daily OER noise of about 0.25 pp is normal in the demo. Weekly noise is about 0.10 pp. A smooth constant OER is not realistic. [Synthetic Demonstration Data]
- *Seasonality.* A seasonal swing of about half a percentage point is assumed. [Engineering Assumption]
- *Causes.* Moisture, dirt, ripeness mix and processing delay all change true yield. OER is a diagnostic to be explained by contributing factors. It is not a score of operator performance.
- *Comparison.* Never compare OER across mills unless they use the same definition.

**Status rule (demo, Engineering Assumption).** Green: within 0.3 pp of the 28-day baseline. Amber: 0.3 to 0.8 pp below. Red: more than 0.8 pp below.

## KER (kernel extraction rate)

**Formula.** KER = kernel produced / FFB processed x 100, with kernel mass on a dry-to-spec basis (moisture below about 7%). [Industry Practice, S16]

**Pitfalls.** The same stock-change issues as OER apply to the kernel silo level. Unripe fruit lowers KER. [Industry Practice, S40]

**Reference.** Nominal 5.2% with a range of 4.5 to 6.0%. [Industry Practice, S18]

## Throughput and capacity utilisation

- **Throughput** = FFB processed / running hours. Use running hours, not scheduled hours.
- **Capacity utilisation** = FFB processed / (design capacity x scheduled hours).

Both can read low because of starvation. A day at about 40% utilisation in the lean season is a supply fact, not a maintenance problem. [Industry Practice, S13, S14]

The demo's nominal normal-season utilisation is 78%, with a range of 60 to 92%. Lean-season utilisation is about 50%. Peak-season utilisation is about 95%. [Engineering Assumption, anchored on S13, S14, S26]

## Equipment availability and downtime

- **Mechanical availability** = (scheduled hours - downtime from breakdown or planned maintenance) / scheduled hours x 100, per asset.
- **Operational utilisation** = running hours / scheduled hours. It includes starvation and operational stops. Do not call it availability.
- **Downtime categories.** Unplanned equipment, planned maintenance, utility (steam, power, water), operational (cleaning, changeover), starved (no FFB), and external (weather, grid). Only the first two reduce mechanical availability.
- **Derived values.** MTBF = running hours / failures. MTTR = downtime hours / repairs.
- **Derating.** Running at reduced output (for example, one press at 92%) is not downtime. It shows in throughput and utilisation.

**Status rule (demo, Engineering Assumption).** Green at 93% or above. Amber at 85 to 93%. Red below 85%.

**Pitfall.** Do not count a stop for lack of FFB as equipment downtime. Doing so makes a supply problem look like a machine problem.

**Downtime impact (what-if).** Lost FFB capacity = downtime hours x throughput. If the mill is supply-limited, output is deferred and wait-to-process rises, so little is lost. If it is capacity-limited, lost CPO = recoverable fraction of lost FFB x OER. Keep the OER-uplift and downtime-recovery calculations on separate FFB bases to avoid double counting.

## Energy per tonne

- **Electricity intensity** = (kWh generated + kWh imported - kWh exported) / FFB processed. Baseline 17 kWh/t, range 14 to 25. [Industry Practice, S15, S26, S43]
- **Steam intensity** = steam produced (boiler flow meter) / FFB processed. Baseline 0.50 t/t, range 0.42 to 0.65. [Industry Practice, S15]
- **Diesel intensity** = diesel litres (genset and mobile equipment) / FFB processed. Baseline about 0.4 L/t plus genset use. [Engineering Assumption]
- **Energy cost per t FFB** = (grid kWh x tariff + diesel L x price + purchased fuel) / FFB processed. Biomass from the mill's own fibre and shell has no purchase cost. A variant may charge an opportunity cost at fuel prices.

**Normalise for load.** Fixed loads make intensity worse at low throughput. Compare the intensity with the expected value at the same throughput, from a regression on normal days, before calling a rise abnormal. This is the measure used by the energy anomaly detector.

**Pitfalls.** Mixing steam metering bases (saturated and superheated). Double counting self-consumed electricity. Ignoring turbine outages that move load to diesel.

**Status rules (demo, Engineering Assumption).** Electricity: green at or below 18.5 kWh/t, amber 18.5 to 21, red above 21. Steam: green at or below 0.55 t/t, amber 0.55 to 0.62, red above 0.62.

## Estimated production cost

- **Cost per t FFB** = (FFB purchase cost + conversion cost + maintenance + energy cost) / FFB processed.
- **Cost per t CPO** = (total cost - by-product credits, mainly kernel) / CPO produced. The credit method must be stated. In the demo, kernel revenue is credited at the configured kernel price.

**Calculation example (synthetic, illustrative prices).** 936 t FFB x 7.5 THB/kg = 7.02 million THB. Conversion at 400 THB/t = 0.374 million. Maintenance at 80 THB/t = 0.075 million. Energy about 0.018 million. Total about 7.49 million. Kernel credit 48.7 t x 15,000 THB/t = 0.73 million. Net cost 6.76 million / 170.4 t CPO = about 39,670 THB/t CPO, against an illustrative CPO price of 40,000 THB/t. [Synthetic Demonstration Data using Engineering Assumptions]

**Interpretation guard.** At the public price levels cited, the margin is thin. The FFB price was about 7.45 THB/kg and the CPO price about 40,750 THB/t in April 2026. [Historical Public Information, S31] Conversion cost and by-product income decide the margin. Label every output as *estimated* and *illustrative*. Never present it as a company cost or profit. Prefer showing deltas. For example, +0.5 pp OER on 936 t FFB adds 4.68 t CPO, about 187,000 THB per day at 40,000 THB/t. [Synthetic Demonstration Data]

**Pitfalls.** The allocation method between CPO and kernel. Which FFB weight basis is used (ticket or accepted). The price date. Energy counted twice (inside conversion cost and again as energy cost).

## Queue time, turnaround and wait-to-process

- **Queue time** = weigh-in start - gate arrival.
- **Unloading wait** = unloading start - weigh-in end.
- **Turnaround** = exit - gate arrival.
- **Wait-to-process** (for FFB, not for trucks) = ramp stock / throughput, or sterilizer feed time - arrival time.

**Statistics.** Use the mean, median, 90th percentile and maximum over completed trucks. Show the current queue length separately. Trucks still in the queue are excluded from completed-truck averages but included in the current-queue count. Say so on the card.

**Status rules (demo, Engineering Assumption).** Queue time: green at or below 15 min, amber 15 to 60, red above 60. Turnaround: green at or below 60 min, amber 60 to 120, red above 120. Wait-to-process: green at or below 12 h, amber 12 to 24, red above 24.

**Utilisation.** Weighbridge utilisation = arrivals per hour x events per trip x service minutes / 60 / servers. Unloading utilisation = arrivals per hour x (payload / unloading rate) / 60 / bays. At normal arrivals of 5 to 9 trucks per hour, utilisation is about 0.2 to 0.55. Above about 0.85 the queue grows sharply. The weighbridge is rarely the real bottleneck. Unloading and sterilizer feed usually are. [Engineering Assumption]

**Pitfalls.** Averages over the whole day hide afternoon convoys. Weekend effects. Treating a long wait as misconduct. A long wait is a flow problem to analyse, never an accusation.

**Reference.** Ramps handle about 75 to 80% of smallholder FFB in Thailand, and a special lane is used in peak season. [Historical Public Information, S14] The demo's congestion scenario uses a queue wait of 3 to 5 hours as a design choice. [Synthetic Demonstration Data]

## CPO FFA and off-spec share

- **Mass-weighted mean FFA, moisture and dirt** for the tank or batch, over the day or window.
- **Off-spec share** = CPO mass with FFA above 5.0% or moisture and impurities above 0.25%, divided by total CPO mass. [Industry Practice, S27]

**Status rule (demo, Engineering Assumption).** FFA: green at or below 4.0%, amber 4.0 to 5.0%, red above 5.0% (off-spec).

**Pitfall.** FFA rises with time, temperature and moisture in storage. The demo's FFA drift is about 0.05 pp per day. [Engineering Assumption, direction supported by S28]

## Total oil loss

**Formula.** Sum over streams of (stream flow x oil content) / FFB processed x 100. Streams are EFB, sterilizer condensate, pressed fibre, clarification sludge, and other (nuts, unstripped bunches, decanter cake, spills).

**Reference.** Vendor figures put average total oil loss near 1.0% of FFB, with efficient plants at 0.5 to 0.6%. These are not independent figures. The demo's nominal total is 1.0%, with a range of 0.6 to 1.6%. [Industry Practice, S37, low confidence]

**Pitfall.** The five stream terms must sum to the total within rounding.

## Equipment health and alerts

- **Health state** (Normal, Warning, Critical or Maintenance Required) is set by explicit criteria: a vibration zone from the ISO table, a trend (for example +25% over 7 days), bearing temperature against its own baseline (+10 °C), motor current against its baseline (+10%), and corroboration rules. A state is set to Maintenance Required when a work order is open. [Industry Practice, S24, S25; Engineering Assumption for the thresholds]
- Health scores are **ranking aids, not calibrated failure probabilities**.
- **Active alerts** are counted from the alert history at `as_of`. Resolved or dismissed alerts are excluded. Repeated firings of the same equipment and rule within 24 hours are merged into one alert with a count.
- **Pitfall.** An alert is a prompt for human verification. It is not proof of a fault.

**Status-value note.** The KPI definitions list active statuses as `open`, `acknowledged` and `in_review`. The alerts table in the schema allows `new`, `acknowledged`, `in_progress`, `resolved` and `dismissed`. The schema has no `open` or `in_review` value for alerts. Use the schema values when reading or counting alerts, and reconcile the definition before implementation.

## Supplier quality and traceability

- **Supplier quality score** is built from the unripe share, overripe share, grading deduction and dirt, over a rolling 30 days. [Engineering Assumption on the weighting]
- **Traceability coverage** is the share of CPO output mass that can be attributed to supplier lots (lot-based) or covered by a mass-balance allocation. State which method applies. Under mixing across suppliers, lot-level claims are not valid. [Industry Practice]

## Validation rules for KPI results

1. OER recomputed from raw tickets, tank readings and stock changes matches the KPI within 0.01 pp.
2. For any window, the sum of daily FFB processed equals the window value. OER over a window equals sum(CPO) / sum(FFB), not the mean of daily OER.
3. FFB processed is at most capacity x scheduled hours on every day.
4. Availability, downtime, starved and running hours reconcile to scheduled hours.
5. Every KPI response carries provenance, units and the filters applied. Missing data returns null with a reason.

## Limits of this document

- The formulas and thresholds are definitions for the demo. Thresholds are engineering assumptions and are adjustable.
- The worked examples use synthetic values. They are illustrations, not measured results.
- Price figures are dated public levels used only as context. The demo's prices are illustrative.
- Some terms in the KPI definitions do not match the current schema names. The data dictionary lists them.
- Nothing here is a target, cost or performance figure of any company, and the national averages are context only.
