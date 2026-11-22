---
id: kb-maintenance-checklist
title: Maintenance Checklists (Example)
doc_type: sample
language: en+th
status: "sample — authored for the demo, not a real company document"
sources:
  - docs/business/PALM_MILL_PROCESS.md
  - docs/business/DOMAIN_PARAMETERS.json
  - docs/architecture/DATABASE_SCHEMA.md
  - S24
  - S25
last_reviewed: 2026-11-21
---

# Maintenance Checklists (Example)

## สรุปภาษาไทย

เอกสารนี้เป็นรายการตรวจสอบการบำรุงรักษาตัวอย่าง ครอบคลุมลูกปืน การหล่อลื่น การจัดแนวศูนย์ (alignment) และการตรวจสอบเซนเซอร์ รวมถึงการเตือนให้ใช้ขั้นตอนการปลดแยกความปลอดภัยของโรงงานเอง เอกสารนี้ไม่ได้กำหนดมาตรฐาน lock-out/tag-out และไม่ใช่ขั้นตอนของ บริษัทใด ๆ ใช้สำหรับการสาธิตเท่านั้น

**Example checklist for the demo. Not a plant procedure.** Intervals, torques and tolerances must come from the equipment manufacturer and the plant's own maintenance system. This document does not invent them.

## How to use these checklists

- Each checklist is a prompt for a qualified technician. It is not a sign-off.
- Record each completed item in the plant's own maintenance record. In the demo, a completed item is a `maintenance_events` or work-order record, and only a human can confirm it.
- Where a value is needed (interval, torque, tolerance), the checklist says "per OEM" and does not give a number.

## Fact tags

- [Engineering Assumption]: a demo design choice.
- [Industry Practice]: published guidance, with source.

## Safe isolation (pointer only)

Before any work on rotating equipment, follow the plant's own safe-isolation and permit-to-work procedure. This document does not describe a lock-out or tag-out method, does not set isolation standards, and does not replace the plant's procedure. If the plant has no written procedure, the work must not start until one is in place. [Engineering Assumption on governance]

## Checklist 1: Rolling bearings

- [ ] Confirm the bearing ID, the position and the OEM part number against the equipment register.
- [ ] Check bearing temperature against its own commissioning baseline, not only against an absolute number. [Industry Practice, S25]
- [ ] Compare the alarm and trip setpoints with the OEM rating. Published guidance for rolling bearings is commonly an alarm at 75 to 90 °C and a trip at 90 to 100 °C or above, but the plant's own setpoints govern. [Source: S25, low confidence]
- [ ] Measure vibration at the housing in the same position each time. Compare with the zone boundaries and the trend. [Source: S24]
- [ ] Listen and look for noise, heat marks, or grease leakage at the seals.
- [ ] Record any change in bearing temperature or vibration over the last 7 days.
- [ ] If a warning limit is reached, raise a work order for inspection. Do not change the setpoints to clear an alarm.

## Checklist 2: Lubrication

- [ ] Confirm the lubricant grade and quantity against the OEM lubrication chart.
- [ ] Check the oil level or grease fill point. Do not overfill.
- [ ] Check the lubricant for contamination: water, dirt, or colour change.
- [ ] Confirm that the lubrication interval follows the OEM schedule. Do not use an interval from this document.
- [ ] Log each lubrication event with the date, grade and quantity. A logged event is a `maintenance_events` record of type `lubrication` in the demo.
- [ ] Note any leak at the seals.

## Checklist 3: Alignment and coupling

- [ ] Confirm the alignment check follows the OEM tolerance. Do not use a tolerance from this document.
- [ ] Check after any coupling change, foundation work, or a rise in vibration at the motor or gearbox.
- [ ] Check the coupling guard and fasteners.
- [ ] Check soft-foot before the alignment reading.
- [ ] Record the readings and the tool used.

## Checklist 4: Sensor verification

- [ ] Confirm the sensor code, the unit and the measurement range against the sensor register.
- [ ] Check the calibration date of the sensor or the instrument. Record it.
- [ ] Compare the sensor reading with a reference reading taken by a separate, calibrated instrument, where one is available.
- [ ] For a load cell (weighbridge), check the zero reading and a known test weight. A drifting zero or a repeat-supplier tare shift is a data-quality flag. The calibration method is per the OEM and national requirements.
- [ ] Check for stuck, flat or missing readings. A sensor that stops changing is a data-quality issue, not normal stable operation.
- [ ] Record any sensor replaced or recalibrated. In the demo this is a traceable record, and it must not be overwritten.

## Checklist 5: Motor and drive

- [ ] Check motor current against its full-load current and its baseline. [Engineering Assumption on the warning level, above 100% of full-load current]
- [ ] Check winding and bearing temperatures against the OEM rating.
- [ ] Check cable connections and terminal temperatures during an isolated inspection.
- [ ] Check guards and cooling fans.

## Checklist 6: Close-out

- [ ] Confirm the work is complete and the equipment is returned to service by the responsible person, following the plant's procedure.
- [ ] Update the work order with the actions taken and the readings before and after the work.
- [ ] Note any follow-up checks, with a date.
- [ ] Do not mark a work order resolved without the human sign-off required by the plant. In the demo, changes to records are confirmed by a person before they are saved.

## Limits of this document

- Example only. Not a plant procedure and not any company's.
- No numeric intervals, torques or tolerances are given. Use the OEM and the plant's system.
- No lock-out, tag-out or isolation standard is defined here. Use the plant's own safe-isolation procedure.
- The alarm and trip values for bearings are from a low-confidence vendor excerpt. Use the commissioning baseline and OEM rating.
- The checklist does not diagnose any fault. Any finding needs a qualified engineer.
