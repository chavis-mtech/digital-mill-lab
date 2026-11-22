---
id: kb-example-production-report
title: Daily Production Report (Template with Example Values)
doc_type: sample
language: en+th
status: "sample — authored for the demo, not a real company document"
sources:
  - docs/business/KPI_DEFINITIONS.md
  - docs/business/PALM_MILL_PROCESS.md
  - docs/business/DOMAIN_PARAMETERS.json
  - docs/architecture/DATABASE_SCHEMA.md
  - S16
  - S18
last_reviewed: 2026-11-21
---

# Daily Production Report (Template with Example Values)

## สรุปภาษาไทย

เอกสารนี้เป็นแม่แบบรายงานการผลิตรายวันของโรงสกัดน้ำมันปาล์มตัวอย่าง พร้อมฟิลด์ที่ต้องกรอก และวิธีคำนวณ KPI แต่ละตัว ตัวเลขทั้งหมดในเอกสารเป็น **ค่าตัวอย่างเพื่ออธิบายเท่านั้น (example values only, not from the demo database or any real plant)** ไม่ได้มาจากฐานข้อมูลสาธิตหรือจากโรงงานจริง

> **Example values only. Not from the demo database or any real plant.** Every number in the example columns is an illustration of the calculation. It is not a measurement, not a target, and not any company's result.

## Purpose

A daily production report gives one business day's mill results in a fixed layout. It shows the inputs (fruit), the outputs (CPO and kernel), the yields, the running time, the energy use, and the main exceptions. The layout below is the template the demo's reports and the Copilot's explanations should follow.

## Reporting rules

1. **Business day.** Use the mill business day in `Asia/Bangkok`. Store times in UTC. State the shift boundary used, once, in the header. [Engineering Assumption on the boundary]
2. **Units.** Mass in tonnes (t). Use kg only on raw weighbridge tickets. Percentages are stored as numbers in percent (for example 18.2), not fractions.
3. **Ratio of sums.** Compute daily and period yields as the sum of the numerator divided by the sum of the denominator. Never average daily percentages.
4. **Missing data.** If a denominator is zero or a source series is incomplete, report the value as null with a reason. Do not show 0 or a made-up figure.
5. **Provenance.** Label each number as `synthetic_actual` (up to the report date), `forecast` (model output) or `what_if` (scenario). A report that mixes them must show each part with its own label.
6. **Advisory.** The report describes what happened. It does not assign blame. Low OER is a prompt for analysis, not proof of an operator's fault.

## Header fields

| Field | Description | Example value |
|---|---|---|
| Report date | Mill business date | 2026-11-20 (example) |
| Facility | Mill name | Demo Palm Mill A (fictional) |
| Design capacity | Nameplate FFB per hour | 60 t/h |
| Scheduled hours | Hours the mill was scheduled to run | 20 h (example) |
| Provenance | Label for the whole report | `synthetic_actual` |
| Prepared by | Person or role | (example) Production Engineer |

## Section 1: Intake (fruit)

| Field | Meaning | Calculation | Example value |
|---|---|---|---|
| FFB received (t) | Accepted net weight of the day's inbound FFB | Sum of (gross - tare - grading deduction) over completed tickets in the day | 900 t (example) |
| Ramp stock at open (t) | Ramp stock at the start of the day | Stock reading at the day boundary | 120 t (example) |
| Ramp stock at close (t) | Ramp stock at the end of the day | Stock reading at the day boundary | 84 t (example) |
| FFB processed (t) | FFB sent to the sterilizers | Received + opening stock - closing stock (mass balance) | 936 t (example) |

The mass balance gives 900 + 120 - 84 = 936 t. [KPI definition, calculation example]

## Section 2: Output (CPO and kernel)

| Field | Meaning | Calculation | Example value |
|---|---|---|---|
| CPO dispatched (t) | Net mass of CPO sent out | Sum of tanker net weights | 160.0 t (example) |
| Tank stock at open (t) | CPO stock at the start of the day | Level x density, corrected for temperature | 1,200.0 t (example) |
| Tank stock at close (t) | CPO stock at the end of the day | Same method | 1,210.4 t (example) |
| CPO produced (t) | CPO made in the day | Dispatched + (close - open) | 170.4 t (example) |
| Kernel produced (t) | Kernel made in the day | Kernel weighed out of the silo, plus any change in silo stock | 48.7 t (example, from the nominal KER of 5.2%) |

Tank dips are the largest source of error. A level sensor noise of 0.5% on a 1,500 t tank is about 7.5 t, which is as large as a 0.5 percentage point change in OER over 936 t. A daily CPO figure should therefore be read together with a rolling 7-day figure. [Engineering Assumption on the noise level, Synthetic Demonstration Data]

## Section 3: Yields and running performance

| KPI | Formula | Example value | Status (demo rule) |
|---|---|---|---|
| OER (%) | CPO produced / FFB processed x 100 | 170.4 / 936 = 18.2% | Compare with the 28-day baseline, see KPI guide |
| KER (%) | Kernel produced / FFB processed x 100 | 48.7 / 936 = 5.2% | Within the nominal range |
| Throughput (t/h) | FFB processed / running hours | 936 / 20 = 46.8 t/h (example, running hours assumed equal to scheduled hours) | Compare with the season's expected level |
| Capacity utilisation (%) | FFB processed / (design capacity x scheduled hours) x 100 | 936 / (60 x 20) = 78% | Compare with the season's expected level |
| Equipment availability (%) | (scheduled hours - maintenance downtime hours) / scheduled hours x 100 | (example) | Green at 93% or above |
| Plant downtime (h) | Sum of stop-event hours, split planned, unplanned and starved | (example) | Starved hours are not equipment downtime |

Only the first two rows are KPI values in the demo. The other values are placeholders for the reader to fill from the day's records. Do not fill them from this example.

## Section 4: Energy

| Field | Calculation | Example value |
|---|---|---|
| Electricity intensity (kWh/t FFB) | (kWh generated + kWh imported - kWh exported) / FFB processed | 17 kWh/t (example, equal to the nominal baseline) |
| Electricity total (MWh) | Intensity x FFB processed | 17 x 936 = 15.9 MWh (example) |
| Steam intensity (t/t FFB) | Steam produced (boiler flow meter) / FFB processed | 0.50 t/t (example) |
| Diesel intensity (L/t FFB) | Diesel litres (genset and mobile equipment) / FFB processed | (example) |
| Water (m3/t FFB) | Water used / FFB processed | 1.4 m3/t (example) |

Electricity and steam are normalised for load. A fixed load makes intensity worse at low throughput, so compare with the expected intensity at the same throughput before calling an increase abnormal. [Engineering Assumption on the method]

## Section 5: Quality and losses

| Field | Calculation | Example value |
|---|---|---|
| CPO FFA (%) | Mass-weighted mean of lab results for the day's tank or lot | (example) |
| CPO moisture and dirt (%) | Mass-weighted mean | (example) |
| Off-spec CPO (t) | Mass of CPO with FFA above 5.0% or moisture and impurities above 0.25% | (example) |
| Total oil loss (% of FFB) | Sum of (stream flow x oil content) / FFB processed x 100 | Nominal total about 1.0% (range 0.6 to 1.6). [Industry Practice, vendor figure, low confidence] |

## Section 6: Logistics and queue

| Field | Calculation | Example value |
|---|---|---|
| Trucks received (count) | Completed inbound trips | (example) |
| Mean queue time (min) | Mean of (weigh-in start - gate arrival) over completed trucks | (example) |
| Current queue (trucks) | Trucks still waiting at the report time | (example) |
| Wait-to-process (h) | Ramp stock / throughput | (example) |

Trucks still in the queue are excluded from completed-truck averages and counted only in the current-queue figure. [KPI definition]

## Section 7: Alerts and exceptions

| Field | Meaning |
|---|---|
| Active alerts by severity | Count of alerts still open at the report time |
| Notable events | Short factual list: stops, scenario flags, sensor data gaps |
| Items for human review | Anomalies or flags that need a person to verify. The report does not state a proven cause. |

## Section 8: Sign-off

- Prepared by: (name and role)
- Reviewed by: (name and role)
- Records changed after sign-off: none, or a list with the reason for each change. Changes to a business record require a person's confirmation.

## Limits of this document

- Template with example values only. The numbers in the example columns are illustrations, not data from the demo database or any real plant.
- The example uses the synthetic calculation from the KPI definitions, so the numbers are internally consistent but not measured.
- The report does not define an official format for any company. It is a demo template.
- The status rules are engineering assumptions, which are adjustable.
