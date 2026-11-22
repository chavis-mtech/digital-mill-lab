---
id: kb-equipment-inspection-procedure
title: Equipment Inspection Procedure (Rotating Equipment, Example)
doc_type: sample
language: en+th
status: "sample — authored for the demo, not a real company document"
sources:
  - docs/business/PALM_MILL_PROCESS.md
  - docs/business/DOMAIN_PARAMETERS.json
  - docs/business/KPI_DEFINITIONS.md
  - S15
  - S16
  - S24
  - S25
  - S29
  - S30
last_reviewed: 2026-11-21
---

# Equipment Inspection Procedure (Rotating Equipment, Example)

## สรุปภาษาไทย

เอกสารนี้เป็นตัวอย่างขั้นตอนการตรวจสอบอุปกรณ์หมุน ได้แก่ เครื่องอัดเกลียว (screw press) ถังย่อย (digester) ปั๊มและมอเตอร์ ปั๊มป้อนหม้อไอน้ำ (boiler feed) และเครื่องหมุนเหวี่ยง (centrifuge) ใช้เพื่อการสาธิต Copilot เท่านั้น เป็นเพียงคำแนะนำเชิงให้ข้อมูล (advisory only) ต้องให้วิศวกรที่มีคุณสมบัติเหมาะสมยืนยันก่อนดำเนินการใด ๆ ระบบไม่ควบคุมเครื่องจักรและไม่ได้เปลี่ยนแปลงบันทึกทางธุรกิจโดยอัตโนมัติ

**Advisory only: verified by a qualified engineer.** This is an example procedure written for the demo. It is not a plant procedure, and it is not any company's procedure. Every step must be checked against the plant's own procedures and equipment manuals by a qualified engineer before use.

## Purpose and scope

This procedure gives a structure for a routine look at rotating equipment in a palm oil mill. It covers the following:

- Screw press (twin-screw press in the pressing stage)
- Digester (steam-jacketed mash vessel with stirring arms)
- Pump and motor (general process pumps and their drive motors)
- Boiler feed system (feed-water pump and its drive)
- Centrifuge (sludge separator, vertical or decanter)

The procedure describes what to look at, which indicators matter, and when to escalate. It is an inspection aid. It does not replace the equipment manufacturer's instructions.

## Fact tags

- [Engineering Assumption]: a modelling or screening threshold with no published plant standard. Adjustable.
- [Industry Practice]: published practice or guidance, with its source.
- [Synthetic Demonstration Data]: the demo scenario values.

## Before the inspection

1. Confirm the equipment ID, the process stage, and the operating state at the time of the walk-round. Use the plant's own equipment register.
2. Review the last 7 days of readings for the same machine. A reading that is normal on its own may still be part of a trend. [Engineering Assumption]
3. Check for open work orders and recent maintenance events on that machine before raising a new concern.
4. Work only within the plant's permit and safe-isolation procedure. This document does not define isolation or lock-out steps. Follow the plant's own procedure.

## Indicators to check

### Vibration (all rotating equipment)

Vibration is measured in mm/s RMS. The demo uses ISO 10816-3 zone boundaries as a reference point. For a machine in Group 2 (15 to 300 kW) with rigid mounting, the zone boundaries are 1.4 (A/B), 2.8 (B/C) and 4.5 (C/D) mm/s RMS. [Industry Practice, S24, medium confidence]

- Zone A and B: normal operation.
- Zone C: warning. Plan an inspection.
- Zone D: critical. Escalate to a qualified engineer promptly.

The source is a secondary summary and a superseded standard (ISO 20816-3 keeps the same limits). Verify against the licensed standard before any real use. Slow-speed machines such as screw presses are not covered well by the standard. Apply the zone logic to the motor and gearbox housings, and say so. [Source: S24]

**Healthy-range references used in the demo (Engineering Assumption):**

| Equipment | Healthy vibration (mm/s RMS, nominal) | Screening range |
|---|---|---|
| Drive motor | 1.0 | 0.4 to 1.4 |
| Screw press gearbox | 1.6 | 0.8 to 2.3 |
| Pump | 1.4 | 0.6 to 2.3 |
| Fan | 2.0 | 1.0 to 2.8 |
| Centrifuge (sludge separator) | 1.8 | 0.8 to 2.8 |

### Bearing temperature

- Normal bearing temperature for rolling bearings: about 62 °C (screening range 45 to 75 °C). [Industry Practice, S25, low confidence]
- Alarm: commonly 75 to 90 °C. Trip: commonly 90 to 100 °C or above. The actual setpoints must come from the commissioning baseline and the OEM rating. [Source: S25, low confidence]
- Warning rule used in the demo: bearing temperature 10 °C or more above its own 7-day baseline, or above 85 °C. [Engineering Assumption]

### Motor current

- Normal: about 72% of full-load current (screening range 50 to 95%). [Engineering Assumption]
- Warning: above 100% of full-load current, or 10% or more above the machine's 7-day baseline. [Engineering Assumption]
- A current rise with no change in vibration can point to an overload from heavy feed. A current rise together with a vibration rise points more toward mechanical wear. [Industry Practice, S16 and process notes]

### Temperature and pressure by equipment

- **Digester.** Mash temperature 93 °C nominal (range 88 to 98). Published practice for atmospheric digestion is 90 to 96 °C. [Industry Practice, S29] Warning below 88 °C or above 100 °C. [Engineering Assumption]
- **Screw press.** Cone pressure about 40 bar (range 25 to 60). Motor load about 80% of full-load current. [Engineering Assumption, no public number found]
- **Boiler feed.** Boiler steam pressure about 21 bar(g) nominal (range 18 to 26). [Industry Practice, S30, low confidence] Warning when steam pressure is more than 10% away from setpoint. [Engineering Assumption]
- **Centrifuge.** Clarifier temperature 90 °C nominal (range 85 to 95), warning below 85 °C. [Industry Practice, S16, Engineering Assumption for the warning limit]

## Step-by-step inspection

1. **Walk around.** Look for leaks (oil, water, steam), loose guards, unusual noise, and smells of burning. Record anything seen.
2. **Vibration.** Take readings at the bearing housings in the same positions each time. Compare with the zone boundaries and the machine's own trend.
3. **Temperature.** Check the bearing and winding temperatures. Compare with the baseline, not only with the absolute limit.
4. **Current and load.** Compare the motor current with its baseline, and check whether the load matches the feed rate.
5. **Process values.** Check the process values for the machine (for example, digester temperature or boiler pressure) against the normal ranges above.
6. **Lubrication.** Check oil level and condition against the maintenance checklist.
7. **Record.** Write the readings, the time, the conditions and the inspector's name in the plant's record system. Do not overwrite earlier records.

## When to escalate

Escalate to a qualified engineer when any of the following is true. Escalation means informing the responsible engineer. It does not mean stopping the machine by default.

- Vibration is in Zone C for two or more consecutive checks, or in Zone D on any check. [Source: S24]
- Bearing temperature is 10 °C or more above baseline, or above 85 °C. [Engineering Assumption]
- Motor current is above 100% of full-load current, or 10% or more above baseline, for more than one shift. [Engineering Assumption]
- A process value is outside its warning limit for the machine (for example, a digester below 88 °C). [Engineering Assumption]
- A trend is rising for several days without an obvious process reason. [Engineering Assumption]
- Any sign of a safety hazard, such as a leak, a loose guard or a smell of burning. In that case, follow the plant's own emergency procedure first.

## What the Copilot may say about this procedure

- It may list the indicators, the thresholds used by the demo and the reasons for escalation.
- It may say that a reading is a possible contributing factor. It must not say that a fault is proven.
- It must not give control instructions, change a work order, or claim a cause without evidence.

Any anomaly score or risk rank in the demo is a ranking aid for human review. It is not a calibrated probability of failure. Anomaly is not proof of cause.

## Example: a press scenario in the demo

In the demo scenario PRESS_VIBRATION_ANOMALY, the gearbox vibration rises over about 14 days from about 1.6 to about 4.8 mm/s RMS. The bearing temperature rises about 10 °C and the motor current rises about 12%. [Synthetic Demonstration Data] An inspector would see the trend first, then check the zone boundary, then escalate. The demo uses this to show the sequence, not as evidence of how a real press fails.

## Limits of this document

- Example procedure only. Advisory only, verified by a qualified engineer.
- Thresholds are screening values. Several are engineering assumptions with low confidence.
- The vibration zones come from a secondary summary. Verify against the licensed standard before any use.
- It contains no lock-out, tag-out or isolation steps. Use the plant's own safe-isolation procedure.
- It is not any company's procedure, and it does not describe any real machine's condition.
