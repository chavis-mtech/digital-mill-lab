---
id: kb-palm-oil-process-overview
title: Palm Oil Mill Process Overview
doc_type: sample
language: en+th
status: "sample — authored for the demo, not a real company document"
sources:
  - docs/business/PALM_MILL_PROCESS.md
  - docs/business/DOMAIN_PARAMETERS.json
  - docs/business/KPI_DEFINITIONS.md
  - S13
  - S14
  - S15
  - S16
  - S17
  - S20
  - S22
  - S24
  - S28
  - S29
  - S30
  - S37
  - S40
  - S42
last_reviewed: 2026-11-21
---

# Palm Oil Mill Process Overview

## สรุปภาษาไทย

เอกสารนี้อธิบายกระบวนการของโรงสกัดน้ำมันปาล์มแบบทั่วไป ตั้งแต่การรับผลปาล์มสด (FFB) จนถึงการเก็บน้ำมันปาล์มดิบ (CPO) ใช้สำหรับการสาธิตระบบค้นคืนข้อมูล (RAG) ของ Industrial Operations Copilot เท่านั้น เป็นเอกสารตัวอย่างที่เขียนขึ้นสำหรับเดโม ไม่ใช่เอกสารหรือข้อมูลของ บริษัทใด ๆ และตัวเลขทั้งหมดเป็นช่วงอ้างอิงหรือสมมติฐาน

## Purpose of this document

This sample describes a generic palm oil mill as it is used in the demo. The demo mill is the fictional **Demo Palm Mill A** with a design capacity of 60 t FFB per hour. It is an independent concept demo. It is **not** a description of any company's facility, and no number here is a measurement from any real plant.

The document covers each stage from fresh fruit bunch (FFB) reception to crude palm oil (CPO) storage and dispatch, with the main parameters, typical failure symptoms, and loss mechanisms for each stage.

## Fact tags used in this document

Each statement is tagged with one of these categories:

- [Verified Public Fact]: confirmed public statistic, used with its source.
- [Historical Public Information]: dated public information, such as a national average or a price level.
- [Industry Practice]: common practice or published guidance from literature or vendors.
- [Engineering Assumption]: a modelling choice with no reliable public figure. Treat as adjustable.
- [Synthetic Demonstration Data]: a design choice made for the demo scenarios.

Source IDs (for example S16) refer to the source register in `docs/business/PALM_MILL_PROCESS.md` and `docs/business/DOMAIN_PARAMETERS.json`.

## Mill flow at a glance

FFB arrives by truck, usually through a collection ramp, and is weighed in. It is graded, unloaded to a ramp buffer, and fed to the sterilizers. The cooked bunches are threshed to separate the fruitlets from the empty bunch (EFB). The fruitlets are digested (heated and mashed) and pressed. The crude oil is clarified, purified and dried, then stored in CPO tanks until dispatch. The press cake goes to kernel recovery, where the fibre, nuts, shells and kernels are separated. Fibre and shell fuel the boiler, which drives a back-pressure turbine for electricity and supplies exhaust steam to the process. Liquid effluent (POME) leaves as sterilizer condensate, clarification sludge and hydrocyclone water.

## Reference day (calculation example, not a measurement)

At nominal parameters the demo mill processes **936 t FFB per day**. This follows from 60 t/h design capacity x 20 running hours x 0.78 utilisation, which gives 46.8 t/h while running. [Engineering Assumption] for the hours and utilisation, [Industry Practice] for the design size.

| Output | Rule (parameter) | Value per day (example) |
|---|---|---|
| CPO | OER 18.2% | 170.4 t (about six tanker loads of 28 t) |
| Palm kernel | KER 5.2% | 48.7 t |
| EFB | 22% of FFB | 205.9 t |
| Fibre | 13.5% of FFB | 126.4 t |
| Shell | 5.5% of FFB | 51.5 t |
| POME | 0.65 t per t FFB | about 608 t |
| Steam | 0.50 t per t FFB | 468 t (23.4 t/h, about 58% of 40 t/h installed boiler capacity) |
| Electricity | 17 kWh per t FFB | 15.9 MWh (about 796 kW average while running) |
| Water | 1.4 m3 per t FFB | 1,310 m3 |

CPO, kernel, EFB, fibre and shell together are about **64% of FFB mass**. The rest leaves as water (evaporation, condensate, POME) and dissolved solids. Outputs must not be forced to sum to 100% of FFB. [Source: S15, S16, S18, S38]

## Stage 1: Weighbridge and reception

**Purpose.** Record the legal-for-trade weight of each truck and the supplier, vehicle and time. Net weight = gross weight - tare weight.

**Equipment.** One to three platform weighbridges with load cells, an indicator, a ticket printer and a gate. [Engineering Assumption] for the count.

**Key parameters.**
- Service time about 2 minutes per weighing event, two events per trip. [Engineering Assumption]
- Typical truck payload classes: 6-wheel about 8 t, 10-wheel about 15 t, trailer about 25 t (means, not limits). [Engineering Assumption, S36 for legal gross limits]

**Typical failure symptoms.**
- Load-cell drift: a repeat supplier's tare readings shift systematically.
- Indicator fault or communication loss.
- Queue spill-back onto the public road.

**Data-quality flags (never accusations).** A net weight outside the payload class, a tare that changes unexpectedly, or a very long dwell time is a data-quality flag to review. It is not evidence of wrongdoing.

**Loss mechanism.** None directly, but the weighing queue delays the FFB.

## Stage 2: Ramp, grading and unloading

**Purpose.** Inspect and grade bunches, apply the deduction, unload the bunches to the ramp or hopper, and feed the sterilizer cages.

**Equipment.** A grading bay, unloading bays with hydraulic tipping or ramps, a ramp buffer, loaders, and the cage loading system.

**Key parameters.**
- Unloading bays: 3 (range 2 to 6). Unloading rate about 1.0 t per minute per bay. [Engineering Assumption]
- Ramp buffer capacity: 300 t (range 100 to 600). [Engineering Assumption]
- Unripe share of intake: 4% nominal (range 0 to 15). Overripe share: 8% nominal (range 2 to 25). [Engineering Assumption, S40]
- Grading deduction: about 1.5% of weight (range 0.5 to 4.0). [Engineering Assumption, S40]
- Dirt or trash: about 1% of weight (range 0.3 to 3.0). [Engineering Assumption]
- Harvest-to-sterilizer target: 24 hours (range 12 to 48). [Industry Practice, S16, S44]

**Wait-to-process.** Wait-to-process time is ramp stock divided by throughput. This is how a logistics queue turns into a production problem. [Industry Practice, Little's law]

**Typical failure symptoms.**
- Tipping hydraulics or chain stoppage: unloading rate falls, ramp stock climbs.
- Loader unavailability: wait-to-process time grows.
- A peak-season convoy: a long queue, longer wait-to-process time and a rising free fatty acid (FFA) level.

**Loss mechanism.** FFA rises with delay after harvest. A laboratory study measured FFA rising from 2.96% at 0 h to 5.14% at 48 h, which is a single low-reliability study, not mill conditions. [Source: S22, low reliability] The demo uses about 0.03 percentage points per hour beyond an 8-hour free period. [Engineering Assumption]

## Stage 3: Sterilization

**Purpose.** Steam-cook the bunches to stop lipase activity, loosen the fruit from the bunch, soften the mesocarp and condition the nuts.

**Equipment.** Horizontal autoclaves (sterilizer vessels) with doors, steam inlet and exhaust valves, condensate traps and a cage tipper. The demo uses 5 vessels of 8 cages each, with 2.5 t of FFB per cage. [Engineering Assumption, Industry Practice S16]

**Key parameters.**
- Peak steam pressure: about 2.8 bar(g) nominal (range 2.5 to 3.2). About 40 psig. [Industry Practice, S16, S30]
- Cycle time: about 80 minutes nominal (range 60 to 90). [Industry Practice, S16]
- Steam temperature at the peak: about 140 °C (range 130 to 145). [Industry Practice, S16]
- Steam use: about 200 kg per t FFB nominal (range 140 to 224). Values above 224 kg per t suggest leaks or poor cycle control. [Industry Practice, S16]
- Triple-peak cycles step the pressure, with a low first peak of about 1.0 to 1.5 bar and then high peaks of about 2.8 to 3.0 bar. The exact staging values are [Engineering Assumption].

**Typical failure symptoms.**
- Steam leak or door seal failure: the peak pressure is not reached and the cycle extends.
- Failed condensate trap: slow heat-up and high condensate.
- Valve actuator fault: a stuck phase in the cycle.
- Low boiler or header pressure: all vessels slow down together. This is the cross-module chain used in the STEAM_PRESSURE_DEVIATION scenario.

**Loss mechanism.** Under-cooked bunches strip poorly and leave oil in the EFB and nuts. Over-long cycles waste steam. Condensate carries about 0.1% of FFB as oil. [Industry Practice, S16, low confidence on exact figure]

**Warning rules used in the demo (Engineering Assumption).** Peak pressure below 2.5 bar(g), or a cycle longer than 95 minutes, raises a warning.

## Stage 4: Threshing

**Purpose.** Separate the fruitlets from the cooked bunches. The empty bunch (EFB, about 22% of FFB) leaves the line.

**Equipment.** Drum thresher, EFB conveyors and a fruit elevator.

**Key parameters.**
- EFB: about 22% of FFB (range 20 to 25). [Industry Practice, S15]
- Unstripped bunches: about 1% (range 0.3 to 3.0). [Engineering Assumption]

**Typical failure symptoms.** Rising vibration in the thresher bearings, motor current spikes, drum or chain damage, conveyor jams. A high share of unstripped bunches in the EFB points to under-cooking or a mechanical fault.

**Loss mechanism.** Oil on the EFB is about 0.07% of FFB. [Engineering Assumption, derived from an unverified excerpt]

## Stage 5: Digestion

**Purpose.** Heat and mash the fruitlets so that the oil cells rupture and the oil can be pressed.

**Equipment.** Steam-jacketed digesters with stirring arms. The demo uses 6 digesters, each driven by a motor of about 37 kW. [Engineering Assumption]

**Key parameters.**
- Mash temperature: 93 °C nominal (range 88 to 98). Published practice for atmospheric digestion is about 90 to 96 °C. [Industry Practice, S29]
- Residence time: about 25 minutes (range 15 to 40). [Engineering Assumption]

**Typical failure symptoms.**
- Worn stirring arms: poor mashing, with lower motor current.
- Low steam: mash temperature falls below about 88 °C.
- Bearing or gearbox faults.

**Loss mechanism.** Poorly digested fruit leaves more oil in the fibre and nuts, which lowers OER.

**Warning rules used in the demo (Engineering Assumption).** Warning below 88 °C or above 100 °C.

## Stage 6: Pressing

**Purpose.** Squeeze the crude oil out of the digested mash. The remaining press cake (fibre and nuts) goes to kernel recovery.

**Equipment.** Twin-screw presses, with 6 units of about 10 t FFB per hour each in the demo. Drive motors of about 55 kW. [Engineering Assumption] Gearboxes and cone or back-pressure control.

**Key parameters.**
- Motor load: about 80% of full-load current (range 55 to 95%). [Engineering Assumption]
- Cone pressure: about 40 bar (range 25 to 60). [Engineering Assumption, no public number found]
- Residual oil in pressed fibre: 7% of dry matter nominal (range 5 to 11). [Industry Practice, S17]
- That residual oil is about 0.35% of FFB nominal (range 0.25 to 0.55). [Industry Practice, S17]
- Pressed-fibre moisture: about 36% (range 30 to 45). [Industry Practice, S17]

**Sensors commonly kept.** Motor current, gearbox and motor vibration, bearing temperature, hydraulic cone pressure, crude oil flow.

**Typical failure symptoms.**
- Worn screw or cage: current rises or becomes erratic, vibration rises, more oil stays in the fibre, more nuts break.
- Bearing or gearbox damage: vibration and temperature rise, usually over weeks of drift before failure.
- Overload from heavy feed: current rises without a change in vibration.

**Loss mechanism.** Higher pressure lowers the oil in the fibre but raises broken nuts and kernel loss. A worn press loses on both sides. This is the physical basis of the PRESS_VIBRATION_ANOMALY demo scenario. [Synthetic Demonstration Data for the size of the effect]

**Vibration zones.** The demo uses ISO 10816-3 zone boundaries as a reference (Group 2 rigid: 1.4, 2.8 and 4.5 mm/s RMS for the A/B, B/C and C/D boundaries). The source table is a secondary summary, and ISO 10816-3 is superseded by ISO 20816-3 with the same limits. Verify against the licensed standard before any real use. [Source: S24, medium confidence]

## Stage 7: Clarification and purification

**Purpose.** Separate the oil from water, sludge and fine solids, and dry the oil.

**Equipment.** Vibrating crude-oil screens, a crude-oil tank, a continuous clarification tank, sludge separators (vertical centrifuges or a decanter), an oil purifier, a vacuum dryer, a sludge tank and oil recovery from the sludge.

**Key parameters.**
- Clarifier temperature: 90 °C nominal (range 85 to 95). [Industry Practice, S16]
- Retention time: 2 hours nominal (range 1 to 3). [Industry Practice, S16]
- Oil lost in sludge: about 0.4% of FFB (range 0.25 to 0.8). [Industry Practice, vendor figure, low confidence]
- After drying, moisture about 0.15% and dirt about 0.04%. [Engineering Assumption]

**Typical failure symptoms.** A cold clarifier (steam shortage) raises sludge oil loss. Separator imbalance or a bearing fault shows as vibration and trips. Foaming or emulsions, a sludge pump failure, and dryer vacuum loss (higher moisture) are also common.

**Loss mechanism.** Clarification is the main route by which operating discipline (temperature, dilution, retention) moves OER by tenths of a percentage point. [Industry Practice]

**Warning rule used in the demo (Engineering Assumption).** Clarifier temperature below 85 °C.

## Stage 8: CPO storage

**Purpose.** Buffer and hold CPO until dispatch. The tanks are heated to about 50 °C so the oil does not solidify, but excess heat speeds up the rise in FFA.

**Equipment.** Three storage tanks of about 1,500 t each in the demo. [Engineering Assumption] Heating coils, level transmitters, temperature probes and sampling points.

**Key parameters.**
- Storage temperature: 50 °C nominal (range 35 to 55). [Industry Practice, S28, S41]
- CPO density: 0.891 t/m3 near 50 °C. Level readings are converted to mass with this value. [Engineering Assumption]
- FFA: 3.2% nominal (range 2.0 to 5.0). The Malaysian-standard maximum used in the demo is 5.0%. [Industry Practice, S27, S28]
- Moisture and impurities maximum: 0.25%. [Industry Practice, S27]
- FFA drift in storage: about 0.05 percentage points per day (range 0 to 0.3). [Engineering Assumption, direction supported by S28]

**Typical failure symptoms.** Heating failure (solid fat, pumping problems), a level sensor error (which causes a stock mismatch and affects OER), or contamination.

**Loss mechanism.** FFA drifts up with time, temperature and moisture. The stock-change error is the largest pitfall when computing the daily OER. See the KPI guide.

## Stage 9: Dispatch

**Purpose.** Load CPO tankers (about 28 t each) and weigh them out. Issue the delivery documents.

**Data kept.** Tanker gross and tare weights, seal numbers, sample ID, FFA and moisture at loading, time in and out.

**Typical failure symptoms.** Pump or hose fault, a weighbridge queue, or quality rejection by the buyer.

**Link to OER.** Dispatched mass plus the change in tank stock equals CPO produced, which is the numerator of OER.

## Support: Kernel recovery

**Process.** Press cake passes through a depericarper, which separates the fibre from the nuts. The nuts are conditioned in a silo, cracked, and the shell is separated from the kernel (winnowing or hydrocyclone). The kernel is dried to below about 7% moisture and stored in a silo. [Industry Practice, S16]

**Key parameters.** Kernel extraction rate (KER) 5.2% nominal (range 4.5 to 6.0). [Industry Practice, S18] Shell about 5.5% of FFB (range 5.0 to 7.0). Fibre about 13.5% of FFB (range 12 to 15). [Industry Practice, S15]

**Typical failure symptoms.** Cracker wear (kernels left in the shell, or broken kernels), poor separation (shell in the kernel), dryer fault (high moisture, FFA rising in the kernel).

**Loss mechanism.** Kernel lost in the shell and fibre. Unripe fruit lowers KER. [Industry Practice, S40]

## Support: Boiler and steam

**Process.** Fibre and shell (sometimes EFB) are burned in a water-tube boiler. The high-pressure steam drives a back-pressure turbine. The exhaust steam, at about 1.5 to 3.5 bar(g), feeds the sterilizers, digesters and clarifiers. [Industry Practice, S30]

**Key parameters.**
- Steam use: 0.50 t per t FFB nominal (range 0.42 to 0.65). [Industry Practice, S15]
- Boiler pressure: about 21 bar(g) nominal (range 18 to 26). [Industry Practice, S30, low confidence]
- Installed boiler capacity: 40 t/h (range 30 to 60). [Engineering Assumption]
- Boiler efficiency: about 60% (range 55 to 75%). [Industry Practice, S15, low confidence]
- Overall steam-to-electricity efficiency: about 12%. [Industry Practice, S15, low confidence]

**Fuel check.** Fibre and shell provide roughly 2.6 GJ higher heating value per tonne FFB. After moisture losses and 60% boiler efficiency, they roughly cover the steam need with a surplus of about 20%. A 15% rise in steam intensity would leave only about 4% surplus. In that case, topping up with EFB becomes plausible. [Derived from S15, Engineering Assumption for the margin]

**Typical failure symptoms.** Boiler tube leak (feed-water flow rises, drum level unstable). Fan bearing or imbalance (vibration). Wet fuel (pressure sags, flue O2 swings). Feed-pump failure. A pressure drop spreads to the sterilizer cycle time, the digester and clarifier temperatures, and then to OER.

**Warning rule used in the demo (Engineering Assumption).** Boiler steam pressure more than 10% away from setpoint.

## Support: Power, water and POME

**Power.** A turbine generator covers most of the mill's electricity. The demo uses about 1.5 MW installed, and a standby diesel genset of about 800 kW for start-up and outages. [Engineering Assumption] Electricity use is about 17 kWh per t FFB (range 14 to 25). [Industry Practice, S15, S26, S43] Most self-sufficient mills import little grid power. [Source: S26, low confidence]

**Water.** About 1.4 m3 per t FFB (range 1.0 to 2.5). [Industry Practice, S38] Failure modes include low supply in dry months, softener breakthrough (boiler scaling) and pump faults.

**POME.** Raw effluent of about 0.65 t per t FFB (range 0.5 to 0.9). [Industry Practice, S16] It comes from sterilizer condensate, clarification sludge and hydrocyclone water. Typical treatment is oil traps, cooling, and anaerobic ponds or covered lagoons. [Industry Practice]

**Biogas (what-if only).** Biogas yield is about 28 m3 per m3 POME (range 20 to 33) at about 60% methane. [Industry Practice, S39, low confidence] The demo treats biogas as a project or what-if option, not as an installed asset, unless the data is modelled explicitly.

## Cross-stage links the demo must keep

- Logistics queue leads to longer wait-to-process time, which leads to a higher FFA and a small OER effect.
- Press wear leads to lower throughput and lower OER.
- Steam pressure deviation leads to sterilizer, digester and clarifier problems, then to OER and energy per tonne.
- Energy efficiency drop leads to a higher energy cost per tonne.
- Work orders must change the later data after a repair. Otherwise a what-if result is not coherent.

## Loss mechanisms in one table

| Mechanism | Where | Direction | Order of magnitude |
|---|---|---|---|
| FFB delay raises FFA | Reception, ramp | FFA up | About +0.03 pp per hour beyond 8 h [Engineering Assumption, S22 low confidence] |
| Unripe bunches | Harvest, grading | OER, KER and quality down | About -0.08 pp OER per pp unripe [Engineering Assumption, S40 direction only] |
| Sterilizer under- or over-cooking | Sterilizer | Oil left in EFB, nuts or condensate | Condensate about 0.1% of FFB [Industry Practice, S16] |
| Poor digestion | Digester | More oil in fibre | Within the fibre loss range 0.25 to 0.55% [Industry Practice, S17] |
| Press wear | Press | Oil in fibre, broken nuts | Up to about +0.3 pp [Synthetic Demonstration Data] |
| Cold clarifier or short retention | Clarifier | Sludge oil loss | About 0.4% of FFB, up to 1.5 times [Industry Practice low, Synthetic Demonstration Data] |
| EFB oil | Thresher, sterilizer | Small loss | About 0.07% of FFB [Engineering Assumption] |
| CPO storage heat or moisture | Tanks | FFA drifts up | About 0.05 pp per day [Engineering Assumption, S28 direction] |
| Measurement error | Tank dips, ticket weights | Apparent OER noise | Daily standard deviation about 0.25 pp [Synthetic Demonstration Data] |

## Upstream: plantation, harvest and transport (brief)

- Plantation yield follows the season. In a Surat Thani study, monthly yield peaked in September and fell to a trough in February. [Historical Public Information, S20, single site and small sample]
- Yield responds to rainfall with lags of months up to about two years. [Source: S20, S21]
- Harvest should be delivered the same day. Transport from harvest to the mill should not exceed about 8 hours. [Industry Practice, S42, low confidence]
- In Thailand, about 75 to 80% of smallholder FFB passes through collection ramps. [Historical Public Information, S14]
- Bunch weight averages about 19.7 kg in the Surat Thani sample. [Historical Public Information, S20]

## Limits of this document

- This is a generic sample for the demo. It does not describe any company or any specific mill.
- Most sensor thresholds and many parameter ranges are engineering assumptions with low confidence. The source register lists them. Do not treat them as plant standards.
- The reference-day figures are calculation examples at nominal parameters. They are not measured data.
- Vibration boundaries come from a secondary summary and must be checked against the licensed standard.
- Real plants vary in instrumentation. Many have only local gauges and paper logs for parts of the line. What any plant actually measures is a discovery question.
- This document does not give operating instructions. Any change to a plant's process must follow the plant's own procedures and be approved by qualified staff.
