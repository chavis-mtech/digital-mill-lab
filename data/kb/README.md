# data/kb: sample knowledge-base documents

These six Markdown documents are **sample documents written for the demo** of the Industrial Operations Copilot. The Copilot retrieves from them (RAG) and cites them. They are not real company documents. Digital Mill Lab is an independent portfolio demo and is not an official system of any company.

## Documents

| File | Purpose |
|---|---|
| `palm-oil-process-overview.md` | Generic palm oil mill process, stage by stage, with parameters, failure symptoms and loss mechanisms. |
| `equipment-inspection-procedure.md` | Example inspection procedure for rotating equipment (screw press, digester, pump and motor, boiler feed, centrifuge). Advisory only, verified by a qualified engineer. |
| `maintenance-checklist.md` | Example checklists for bearings, lubrication, alignment, sensor verification and motor checks. Points to the plant's own safe-isolation procedure. |
| `example-production-report.md` | Template for a daily production report, with field definitions and KPI formulas. Example values are illustrative only. |
| `demo-data-dictionary.md` | Field dictionary for the demo database, written from the generated schema. Lists the main tables, units, provenance and session scope. |
| `industrial-kpi-guide.md` | Definitions, formulas, status rules and pitfalls for the mill KPIs (OER, KER, throughput, availability, downtime, energy per tonne, queue time, turnaround and others). |

Each file has YAML front matter (`id`, `title`, `doc_type: sample`, `language: en+th`, `status`, `sources`, `last_reviewed`), a short Thai summary, and a "Limits of this document" section.

## Rules

1. **Sample documents stay separate from real company documents.** Nothing in this folder is, or may be presented as, any company's procedure, data, policy or performance. Real company documents must never be placed here or indexed alongside these samples.
2. **Sources.** Content is drawn from the research documents in `docs/business/` and the schema in `docs/architecture/DATABASE_SCHEMA.md`. Source IDs (for example `S16`) refer to the source register. Statements must not go beyond those sources. Where a number is an assumption, it is labelled as one.
3. **Fact tags.** Business and domain statements carry a tag such as Industry Practice, Engineering Assumption, Historical Public Information or Synthetic Demonstration Data.
4. **Example values.** Numbers in examples are illustrations for the fictional "Demo Palm Mill A". They are not measurements.
5. **Advisory only.** Procedures and checklists are aids for qualified people. They do not control equipment and do not replace the plant's own procedures.
6. **Editing.** Only the KB author or the Copilot owner changes these files. After editing, re-index the retrieval store so citations stay accurate.
