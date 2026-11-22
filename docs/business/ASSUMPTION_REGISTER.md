# Assumption and Fact Register

> Task DML-002. Owner: researcher. Retrieved: **2026-11-21** (all sources unless a row says otherwise). Companion: the public-facts research (kept private) (facts about the target organisation and the Thai industry), `docs/business/DOMAIN_PARAMETERS.json` (machine-readable parameters).

**Independent concept demo.** Nothing here is internal company data, and nothing turns an assumption into a company fact. Where public information is thin, this register says so.

## How to read this register

Every statement used by the product carries one tag from the fact taxonomy in `docs/SPEC.md`:

| Tag | Meaning in this register |
|---|---|
| Verified Public Fact | Stated in a public source we read; still dated as of that source |
| Historical Public Information | A public statement or number that is dated and may no longer hold (website pages 2013-2021, 2026 price quotes, research periods) |
| Industry Practice | Generally reported practice or typical value in the palm oil literature |
| Engineering Assumption | Our own judgement or derivation, used where no reliable public number was found; numeric values are always confidence low (a few definitional rules about meaning, e.g. AR-005, are marked high because they are rules, not estimates) |
| Synthetic Demonstration Data | A choice made for the fictional mill or for a scenario; not a measurement |
| Proposed Future Capability | Something the demo only sketches; nothing exists |

**Confidence**: high = primary/authoritative and consistent; med = credible secondary or consistent multiple sources; low = single weak source, excerpt only, vendor claim, or our assumption.

**Used-by codes**: DATA (synthetic data engine), MILL (Palm Mill Production Intelligence), EXEC (Executive Control Tower), MAINT (Predictive Maintenance), LOG (Logistics & Weighbridge), ENERGY (Energy & Sustainability), SCEN (Scenario Simulator), ROI (Business Impact / ROI), TRACE (Supplier Traceability), TWIN (Digital Twin Lite), KPI (KPI service), COPILOT (Industrial AI Copilot), ML (model cards and evaluation), IT (integration/security docs).

**Rule for downstream agents:** if you use a number from the JSON file in code, keep its `key` in a comment and keep the confidence label visible in docs. Do not quote a `low` row as a fact in UI copy.

Counts: 169 parameters (50 med, 119 low, 0 high - the honest picture of public information on mill-level numbers).

## A. Demo framing and honesty assumptions

| ID | Statement | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-001 | The company 'Demo Palm Oil Co. (fictional)' and the mill 'Demo Palm Mill A' are fictional. No generated value maps 1:1 to any company's facility. | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | high | ALL |
| AR-002 | Every number shown in the application is labelled synthetic_actual, forecast or what_if. None is a measurement from a real plant, and synthetic benchmarks are not factory measurements. | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | high | ALL |
| AR-003 | The demo mill is sized at 60 t FFB/h because 45 and 60 t/h are common Thai design sizes. a Thai palm oil operator's public RSPO notice also lists 60 t/h for its mill, but demo behaviour is not a claim about that mill's performance or even that it is operating. | Engineering Assumption | [S18](https://bsigroup.com/siteassets/pdf/en/about-us/rspo/rspo-pc-public-summary-report-univanich-topi-siam-lamthap-mill-asa1-2.pdf), [S10](https://rspo.org/wp-content/uploads/RSPO-PC-PC14-Public-Announcement-EN-PC-V2_PC-Palm_Rev.01_TM-Approved.pdf) | 2026-11-21 | med | DATA, MILL, TWIN |
| AR-004 | The 120-day dataset ends 2026-11-20, so it covers the Thai peak-supply months (Aug-Oct) and the November decline; congestion and waiting-time effects are therefore plausible in the window. | Synthetic Demonstration Data | [S20](https://ph03.tci-thaijo.org/index.php/kaset_rbruj/article/download/3071/2483/15597) | 2026-11-21 | med | DATA, LOG, MILL |
| AR-005 | Risk and anomaly scores are ranking aids, not calibrated failure probabilities, because the demo has no real failure ground truth. Anomaly does not equal proven cause; logistics anomaly is not an accusation. | Engineering Assumption | A00 (judgement) | 2026-11-21 | high | MAINT, MILL, LOG, COPILOT |
| AR-006 | Model metrics measured on synthetic data (whose structure we wrote) will look better than any real-plant result and must be reported as synthetic benchmarks; if a model loses to its naive baseline that is shown truthfully. | Engineering Assumption | A00 (judgement) | 2026-11-21 | high | ML docs, MILL, MAINT |
| AR-007 | ROI figures are an illustrative business scenario built on adjustable assumptions, not verified financial results of any company. | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | high | ROI, SCEN, EXEC |
| AR-008 | Illustrative prices (CPO, FFB, diesel, electricity) use dated 2026 public quotes as starting values only; users can change them and no forecast is implied. | Historical Public Information | [S31](https://www.thansettakij.com/economy/trade-agriculture/656721), [S32](https://www.nationthailand.com/business/economy/40065331), [S33](https://www.pptvhd36.com/news/Wealth/287289), [S34](https://www.khaosod.co.th/economics/news_10334424) | 2026-11-21 | med | ROI, SCEN, ENERGY |

## B. Industry practice and public-context statements

| ID | Statement | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-010 | Mills aim to sterilise FFB within about 24 h of harvest; longer waits raise free fatty acid (FFA) and can degrade quality. | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/), [S44](https://www.krungsri.com/getmedia/de09fc89-060d-4545-ac44-1fe91709c640/IO_Oil_), [S22](https://repository.unsri.ac.id/72064/2/RAMA_41231_05091003007_0005076402_0031105601_01_front_ref.pdf), [S23](https://agris.fao.org/search/en/records/647391e368b4c299a3f9e659) | 2026-11-21 | med | MILL, LOG, DATA |
| AR-011 | Crude palm oil is traded mainly on FFA and moisture-and-impurities content (common contract limits 5.0% and 0.25%). | Industry Practice | [S27](https://agris.fao.org/search/en/records/647391e168b4c299a3f9e57f), [S28](https://pmc.ncbi.nlm.nih.gov/articles/PMC9198255/) | 2026-11-21 | med | MILL, KPI, TRACE |
| AR-012 | Palm oil mills are generally energy self-sufficient: fibre and shell (sometimes EFB) fire the boilers; back-pressure steam serves sterilisation and process heating; most electricity is self-generated. | Industry Practice | [S15](https://edepot.wur.nl/288880), [S16](https://www.aocs.org/resource/palm-oil/), [S26](https://cuir.car.chula.ac.th/dspace/bitstream/123456789/69113/6/Orathai_ch_ch5_p.pdf) | 2026-11-21 | med | ENERGY, DATA, SCEN |
| AR-013 | Roughly 75-80% of Thai smallholder FFB reaches mills via ramps (collection points); Thailand had about 149 CPO mills and 2,274 ramps in 2022. | Historical Public Information | [S14](https://rspo.org/wp-content/uploads/Oil-Palm-Development-in-Thailand-Trends-and-Progress-of-Sustainability-Efforts-in-Palm-Oil-Production-and-Procurement.pdf) | 2026-11-21 | med | LOG, TRACE, DATA |
| AR-014 | Quoted Thai FFB prices are stated on an 18% oil-content basis; this is a pricing convention and is not the mill's measured OER. | Historical Public Information | [S32](https://www.nationthailand.com/business/economy/40065331) | 2026-11-21 | med | KPI, ROI |
| AR-015 | Mixed-supplier RSPO supply chains in Thailand commonly use the mass-balance model rather than identity preservation; the traceability module will therefore be mass-balance first and lot-based where supplier lots are kept separate. | Industry Practice | [S18](https://bsigroup.com/siteassets/pdf/en/about-us/rspo/rspo-pc-public-summary-report-univanich-topi-siam-lamthap-mill-asa1-2.pdf) | 2026-11-21 | med | TRACE |
| AR-016 | Tonnage deductions for unripe or poor bunches at reception are practice in Malaysia; exact Thai practice and rates were not found publicly. | Industry Practice | [S40](https://ir.uitm.edu.my/38188/1/38188.pdf) | 2026-11-21 | low | LOG, TRACE, KPI |
| AR-017 | Vibration severity is judged on broadband RMS velocity using four ISO 10816-3 / ISO 20816-3 zones (A-D) by machine group and support type. | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | MAINT, DATA |
| AR-018 | Condition-monitoring alarms are best set relative to each machine's own baseline, not only to generic limits. | Industry Practice | [S25](https://www.tecowestinghouse.com/Stock_Motor_PDF/RTD_Alarm_Trip_Settings.pdf) | 2026-11-21 | low | MAINT |
| AR-019 | Pressed fibre normally retains 5-11% oil on a dry basis; extra loss here is a standard route by which a worn press reduces OER. | Industry Practice | [S17](https://jopr.mpob.gov.my/the-development-of-a-residual-oil-recovery-system-to-increase-the-revenue-of-a-palm-oil-mill/) | 2026-11-21 | med | MILL, MAINT, SCEN |
| AR-020 | Peak-season FFB oversupply causes queues; some mills offer certified smallholders a special unloading lane during the peak to cut waiting and weight loss. | Historical Public Information | [S14](https://rspo.org/wp-content/uploads/Oil-Palm-Development-in-Thailand-Trends-and-Progress-of-Sustainability-Efforts-in-Palm-Oil-Production-and-Procurement.pdf) | 2026-11-21 | med | LOG, TRACE |
| AR-021 | Industry-wide Thai mill capacity utilisation averaged 48.7% in 2023-2025: so for most mills FFB supply, not machine capacity, is the likelier limit on output (our inference from the statistic). A single mill can still be capacity-bound in peak weeks. | Verified Public Fact | [S13](https://www.krungsri.com/en/research/industry/industry-outlook/agriculture/palm-oil/io/plam-oil-2026) | 2026-11-21 | high | EXEC, MILL, ROI |
| AR-022 | A stoppage caused by lack of FFB is a supply event, not equipment downtime; value-at-risk for downtime depends on whether the mill is supply-constrained (output deferred, quality risk) or capacity-constrained (output lost). | Engineering Assumption | A00 (judgement) | 2026-11-21 | high | KPI, ROI, SCEN |
| AR-023 | Thai mill margins are thin in 2025-2026: at CPO 40.75 THB/kg and OER 18.2% oil revenue is ~7.4 THB per kg FFB versus an FFB price of ~7.45 THB/kg, so kernel and by-product income and cost control decide profitability. | Historical Public Information | [S31](https://www.thansettakij.com/economy/trade-agriculture/656721), [S13](https://www.krungsri.com/en/research/industry/industry-outlook/agriculture/palm-oil/io/plam-oil-2026) | 2026-11-21 | med | ROI, EXEC, SCEN |
| AR-024 | The Thai monthly FFB seasonal profile is anchored on one Surat Thani research site (Feb trough, Sep peak). The 12-month profile and its damping are assumptions; OAE monthly open data should replace them if calibration is ever required. | Engineering Assumption | [S20](https://ph03.tci-thaijo.org/index.php/kaset_rbruj/article/download/3071/2483/15597), [S45](https://data.go.th/en/dataset/nabc-oae00051) | 2026-11-21 | low | DATA, LOG, MILL |

## C. Domain parameters (generated from DOMAIN_PARAMETERS.json)

One row per parameter. The statement shows nominal and plausible range; full notes, caveats and supporting sources are in the JSON `notes` and `also_sources` fields. Parameter IDs are stable positions in the JSON file.

### C.1 plant capacity ops

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P001 | Design (nameplate) FFB processing capacity of the fictional demo mill. `mill_capacity_t_ffb_per_h` = **60** t FFB/h (30 to 90) | Industry Practice | [S18](https://bsigroup.com/siteassets/pdf/en/about-us/rspo/rspo-pc-public-summary-report-univanich-topi-siam-lamthap-mill-asa1-2.pdf) (+S10, S16, S19) | 2026-11-21 | med | DATA, MILL, TWIN, SCEN |
| AR-P002 | Scheduled running hours per day in a normal-supply day. `operating_hours_per_day` = **20** h/day (16 to 24) | Engineering Assumption | [S26](https://cuir.car.chula.ac.th/dspace/bitstream/123456789/69113/6/Orathai_ch_ch5_p.pdf) | 2026-11-21 | low | DATA, EXEC, ROI, SCEN |
| AR-P003 | Operating days per year (excludes annual shutdown and non-running days). `operating_days_per_year` = **300** d/yr (250 to 340) | Engineering Assumption | [S26](https://cuir.car.chula.ac.th/dspace/bitstream/123456789/69113/6/Orathai_ch_ch5_p.pdf) | 2026-11-21 | low | ROI, SCEN |
| AR-P004 | Share of design throughput actually achieved over scheduled hours in a normal-supply month. `capacity_utilisation_normal` = **0.78** fraction (0.6 to 0.92) | Engineering Assumption | [S26](https://cuir.car.chula.ac.th/dspace/bitstream/123456789/69113/6/Orathai_ch_ch5_p.pdf) (+S13) | 2026-11-21 | low | DATA, MILL, EXEC |
| AR-P005 | Utilisation in lean-supply months (Feb-Apr). `capacity_utilisation_lean_season` = **0.5** fraction (0.35 to 0.65) | Engineering Assumption | [S13](https://www.krungsri.com/en/research/industry/industry-outlook/agriculture/palm-oil/io/plam-oil-2026) | 2026-11-21 | low | DATA, MILL, LOG |
| AR-P006 | Utilisation in peak-supply months (Aug-Oct). `capacity_utilisation_peak_season` = **0.95** fraction (0.85 to 1) | Engineering Assumption | [S14](https://rspo.org/wp-content/uploads/Oil-Palm-Development-in-Thailand-Trends-and-Progress-of-Sustainability-Efforts-in-Palm-Oil-Production-and-Procurement.pdf) | 2026-11-21 | low | DATA, MILL, LOG |
| AR-P007 | Routine planned stop (cleaning, PM) per week. `planned_stop_hours_per_week` = **8** h/week (4 to 16) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, EXEC |
| AR-P008 | Annual overhaul shutdown. `annual_shutdown_days` = **21** d/yr (14 to 35) | Engineering Assumption | A00 (judgement) (+S18) | 2026-11-21 | low | DATA, MAINT, ROI |
| AR-P009 | Unplanned stoppage events per month (plant level, normal period). `unplanned_stop_events_per_month` = **6** events/month (2 to 15) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, EXEC |
| AR-P010 | Mean duration of an unplanned stoppage. `unplanned_stop_duration_h_mean` = **2** h (0.5 to 8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, EXEC |
| AR-P011 | Scheduled-time mechanical availability of the process line (excludes starvation for lack of FFB). `plant_availability_target_pct` = **93** % (85 to 97) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | EXEC, MAINT |

### C.2 feedstock yield

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P012 | Average FFB bunch weight (tenera, 7-12 y palms, Surat Thani). `ffb_bunch_weight_kg` = **19.7** kg/bunch (15.5 to 24.2) | Historical Public Information | [S20](https://ph03.tci-thaijo.org/index.php/kaset_rbruj/article/download/3071/2483/15597) | 2026-11-21 | med | DATA, TRACE |
| AR-P013 | Thai national FFB yield per harvested rai. `ffb_yield_t_per_rai_per_year` = **3.3** t/rai/yr (2.5 to 4) | Historical Public Information | [S13](https://www.krungsri.com/en/research/industry/industry-outlook/agriculture/palm-oil/io/plam-oil-2026) (+S02, S03, S14) | 2026-11-21 | med | DATA |
| AR-P014 | Typical ramp/estate-to-mill haul distance. `ffb_haul_distance_km` = **35** km (5 to 100) | Engineering Assumption | A00 (judgement) (+S14) | 2026-11-21 | low | DATA, LOG |
| AR-P015 | Average loaded truck speed on rural roads. `truck_average_speed_kmh` = **35** km/h (20 to 50) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P016 | Industry guidance: time from harvest to sterilisation. `ffb_harvest_to_sterilizer_target_h` = **24** h (12 to 48) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) (+S44) | 2026-11-21 | med | DATA, MILL, LOG |
| AR-P017 | Guidance: maximum harvest-to-mill transit time. `ffb_transport_max_h` = **8** h (4 to 12) | Industry Practice | [S42](https://ejournal.uin-suska.ac.id/index.php/sitekin/article/download/21947/8834) | 2026-11-21 | low | DATA, LOG |
| AR-P018 | Unripe/underripe bunch share of intake (normal supplier mix). `ffb_unripe_share_pct` = **4** % of bunches (0 to 15) | Engineering Assumption | [S40](https://ir.uitm.edu.my/38188/1/38188.pdf) | 2026-11-21 | low | DATA, MILL, TRACE |
| AR-P019 | Overripe bunch share of intake. `ffb_overripe_share_pct` = **8** % of bunches (2 to 25) | Engineering Assumption | [S40](https://ir.uitm.edu.my/38188/1/38188.pdf) | 2026-11-21 | low | DATA, MILL, TRACE |
| AR-P020 | Dirt/trash/long-stalk share of ticket weight. `ffb_dirt_trash_share_pct` = **1** % of weight (0.3 to 3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P021 | Mean grading deduction applied to ticket weight (unripe, long stalk, dirt). `ffb_grading_deduction_pct_mean` = **1.5** % of weight (0.5 to 4) | Engineering Assumption | [S40](https://ir.uitm.edu.my/38188/1/38188.pdf) | 2026-11-21 | low | DATA, KPI, TRACE |

### C.3 mass balance

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P022 | Oil extraction rate: CPO produced / FFB processed x 100 (nominal mill-level). `oer_pct` = **18.2** % of FFB mass (15.8 to 20.5) | Verified Public Fact | [S13](https://www.krungsri.com/en/research/industry/industry-outlook/agriculture/palm-oil/io/plam-oil-2026) (+S14, S18) | 2026-11-21 | med | DATA, MILL, EXEC, SCEN, ROI |
| AR-P023 | Kernel extraction rate: palm kernel produced / FFB processed x 100. `ker_pct` = **5.2** % of FFB mass (4.5 to 6) | Industry Practice | [S18](https://bsigroup.com/siteassets/pdf/en/about-us/rspo/rspo-pc-public-summary-report-univanich-topi-siam-lamthap-mill-asa1-2.pdf) (+S15) | 2026-11-21 | med | DATA, MILL, EXEC |
| AR-P024 | Empty fruit bunch (EFB) per tonne FFB (wet). `efb_pct_ffb` = **22** % of FFB mass (20 to 25) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | med | DATA, MILL, ENERGY, TRACE |
| AR-P025 | Mesocarp fibre per tonne FFB (wet). `fibre_pct_ffb` = **13.5** % of FFB mass (12 to 15) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | med | DATA, MILL, ENERGY |
| AR-P026 | Kernel shell per tonne FFB (wet). `shell_pct_ffb` = **5.5** % of FFB mass (5 to 7) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | med | DATA, MILL, ENERGY |
| AR-P027 | Raw palm oil mill effluent per tonne FFB. `pome_t_per_t_ffb` = **0.65** t/t FFB (0.5 to 0.9) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) (+S15) | 2026-11-21 | med | DATA, ENERGY, MILL |
| AR-P028 | Day-to-day OER measurement/process noise (standard deviation) in normal operation. `oer_daily_noise_sd_pp` = **0.25** percentage points (0.1 to 0.5) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P029 | Seasonal swing in OER (peak-supply months higher, lean months lower), half-amplitude. `oer_seasonal_amplitude_pp` = **0.5** percentage points (0 to 1) | Engineering Assumption | A00 (judgement) (+S20) | 2026-11-21 | low | DATA, MILL |

### C.4 oil losses

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P030 | Total oil lost in residues, per FFB mass (normal mill). `oil_loss_total_pct_ffb` = **1** % of FFB mass (0.6 to 1.6) | Industry Practice | [S37](https://test03.alfalaval.com/en-sg/industries/food-dairy-and-beverage/food-processing/fat-and-oil-processing/palm-oil-processing/recover-more-oil-generate-higher-revenue) | 2026-11-21 | low | DATA, MILL, EXEC |
| AR-P031 | Oil lost in EFB. `oil_loss_efb_pct_ffb` = **0.07** % of FFB mass (0.04 to 0.12) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P032 | Oil lost in sterilizer condensate. `oil_loss_sterilizer_condensate_pct_ffb` = **0.1** % of FFB mass (0.05 to 0.2) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | low | DATA, MILL |
| AR-P033 | Oil lost in pressed fibre/press cake. `oil_loss_fibre_pct_ffb` = **0.35** % of FFB mass (0.25 to 0.55) | Industry Practice | [S17](https://jopr.mpob.gov.my/the-development-of-a-residual-oil-recovery-system-to-increase-the-revenue-of-a-palm-oil-mill/) | 2026-11-21 | med | DATA, MILL, MAINT |
| AR-P034 | Oil lost in clarification sludge/POME. `oil_loss_sludge_pct_ffb` = **0.4** % of FFB mass (0.25 to 0.8) | Industry Practice | [S37](https://test03.alfalaval.com/en-sg/industries/food-dairy-and-beverage/food-processing/fat-and-oil-processing/palm-oil-processing/recover-more-oil-generate-higher-revenue) | 2026-11-21 | low | DATA, MILL |
| AR-P035 | Oil lost with nuts, unstripped bunches, decanter cake, spills. `oil_loss_other_pct_ffb` = **0.08** % of FFB mass (0.03 to 0.15) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P036 | Residual oil in pressed fibre, dry basis. `fibre_oil_pct_dry_basis` = **7** % of dry matter (5 to 11) | Industry Practice | [S17](https://jopr.mpob.gov.my/the-development-of-a-residual-oil-recovery-system-to-increase-the-revenue-of-a-palm-oil-mill/) | 2026-11-21 | med | DATA, MILL |
| AR-P037 | Moisture of pressed mesocarp fibre. `pressed_fibre_moisture_pct` = **36** % wet basis (30 to 45) | Industry Practice | [S17](https://jopr.mpob.gov.my/the-development-of-a-residual-oil-recovery-system-to-increase-the-revenue-of-a-palm-oil-mill/) (+S15) | 2026-11-21 | med | DATA, ENERGY |

### C.5 process front end

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P038 | Sterilizer peak steam pressure (gauge). `sterilizer_pressure_barg` = **2.8** bar(g) (2.5 to 3.2) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) (+S30) | 2026-11-21 | med | DATA, MILL, TWIN, MAINT |
| AR-P039 | Sterilizer cycle time (peak-to-peak cooking, excluding loading). `sterilizer_cycle_min` = **80** min (60 to 90) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA, MILL |
| AR-P040 | Saturated steam temperature at sterilizer peak. `sterilizer_temp_c` = **140** degC (130 to 145) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA, TWIN |
| AR-P041 | FFB per cage. `sterilizer_cage_capacity_t` = **2.5** t (2.5 to 10) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA, TWIN |
| AR-P042 | Number of horizontal sterilizer vessels in the demo mill. `sterilizer_vessel_count` = **5** count (3 to 8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, TWIN |
| AR-P043 | Cages per vessel. `sterilizer_cages_per_vessel` = **8** count (6 to 10) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA |
| AR-P044 | Steam used by sterilisation. `sterilizer_steam_kg_per_t_ffb` = **200** kg/t FFB (140 to 224) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA, ENERGY |
| AR-P045 | Unstripped bunches (oil loss path) after threshing. `thresher_unstripped_bunch_pct` = **1** % of bunches (0.3 to 3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P046 | Digester mash temperature. `digester_temp_c` = **93** degC (88 to 98) | Industry Practice | [S29](https://agris.fao.org/search/ar/records/64747395425ec3c088f34745) (+S16) | 2026-11-21 | med | DATA, MILL, TWIN |
| AR-P047 | Digester residence time. `digester_residence_min` = **25** min (15 to 40) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA |
| AR-P048 | Digester vessels. `digester_count` = **6** count (4 to 8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, TWIN |
| AR-P049 | Screw presses. `press_count` = **6** count (4 to 8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, TWIN |
| AR-P050 | Design capacity per screw press. `press_unit_capacity_t_ffb_per_h` = **10** t FFB/h (8 to 15) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA |
| AR-P051 | Screw press drive motor rating. `press_motor_kw` = **55** kW (37 to 90) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P052 | Press motor current as fraction of full-load current, healthy. `press_motor_load_fraction` = **0.8** fraction (0.55 to 0.95) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT, MILL |
| AR-P053 | Press hydraulic cone/back-pressure setting. `press_cone_pressure_bar` = **40** bar (25 to 60) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MILL, MAINT |

### C.6 clarification quality

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P054 | Continuous clarification tank temperature. `clarifier_temp_c` = **90** degC (85 to 95) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA, MILL, TWIN |
| AR-P055 | Clarifier retention time. `clarifier_retention_h` = **2** h (1 to 3) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA |
| AR-P056 | CPO storage tank temperature (held to avoid solidification and oxidation). `cpo_storage_temp_c` = **50** degC (35 to 55) | Industry Practice | [S28](https://pmc.ncbi.nlm.nih.gov/articles/PMC9198255/) (+S41) | 2026-11-21 | med | DATA, TWIN |
| AR-P057 | CPO density near 50 C. `cpo_density_t_per_m3` = **0.891** t/m3 (0.88 to 0.9) | Engineering Assumption | A00 (judgement) | 2026-11-21 | med | DATA, KPI |
| AR-P058 | Capacity per CPO storage tank. `cpo_storage_tank_capacity_t` = **1500** t (500 to 3000) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, KPI |
| AR-P059 | Number of CPO storage tanks. `cpo_storage_tank_count` = **3** count (2 to 6) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA |
| AR-P060 | CPO tanker payload at dispatch. `cpo_tanker_payload_t` = **28** t (20 to 32) | Engineering Assumption | [S05](https://www.the operator's public website/port.php) | 2026-11-21 | low | DATA, LOG |
| AR-P061 | Free fatty acid of CPO at production (normal supply). `cpo_ffa_pct` = **3.2** % as palmitic (2 to 5) | Industry Practice | [S28](https://pmc.ncbi.nlm.nih.gov/articles/PMC9198255/) | 2026-11-21 | med | DATA, MILL, EXEC, TRACE |
| AR-P062 | Contractual maximum FFA for crude palm oil. `cpo_ffa_spec_max_pct` = **5** % (fixed) | Industry Practice | [S27](https://agris.fao.org/search/en/records/647391e168b4c299a3f9e57f) | 2026-11-21 | med | DATA, KPI |
| AR-P063 | CPO moisture after vacuum drying. `cpo_moisture_pct` = **0.15** % (0.08 to 0.22) | Engineering Assumption | [S28](https://pmc.ncbi.nlm.nih.gov/articles/PMC9198255/) | 2026-11-21 | low | DATA, KPI |
| AR-P064 | CPO insoluble impurities (dirt). `cpo_dirt_pct` = **0.04** % (0.01 to 0.08) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, KPI |
| AR-P065 | Contractual maximum moisture and impurities (M&I) in CPO. `cpo_moisture_impurities_spec_max_pct` = **0.25** % (fixed) | Industry Practice | [S27](https://agris.fao.org/search/en/records/647391e168b4c299a3f9e57f) | 2026-11-21 | med | DATA, KPI |
| AR-P066 | Additional FFA (percentage points) per hour of FFB waiting beyond the free window. `ffa_rise_pp_per_h_delay` = **0.03** pp/h (0.01 to 0.06) | Engineering Assumption | [S22](https://repository.unsri.ac.id/72064/2/RAMA_41231_05091003007_0005076402_0031105601_01_front_ref.pdf) (+S23) | 2026-11-21 | low | DATA, MILL, LOG, SCEN |
| AR-P067 | Waiting hours before extra FFA is applied. `ffa_delay_free_hours` = **8** h (4 to 12) | Engineering Assumption | [S42](https://ejournal.uin-suska.ac.id/index.php/sitekin/article/download/21947/8834) | 2026-11-21 | low | DATA, MILL |
| AR-P068 | FFA drift in warm CPO storage. `cpo_storage_ffa_drift_pp_per_day` = **0.05** pp/day (0 to 0.3) | Engineering Assumption | [S28](https://pmc.ncbi.nlm.nih.gov/articles/PMC9198255/) | 2026-11-21 | low | DATA, MILL |
| AR-P069 | OER reduction per percentage point of unripe bunches above the baseline share. `oer_penalty_pp_per_pp_unripe` = **0.08** pp OER per pp unripe (0.03 to 0.15) | Engineering Assumption | [S40](https://ir.uitm.edu.my/38188/1/38188.pdf) | 2026-11-21 | low | DATA, MILL, SCEN, TRACE |
| AR-P070 | OER reduction per 24 h of FFB delay beyond the 24 h target. `oer_penalty_pp_per_24h_delay` = **0.1** pp OER per 24 h (0 to 0.4) | Engineering Assumption | [S22](https://repository.unsri.ac.id/72064/2/RAMA_41231_05091003007_0005076402_0031105601_01_front_ref.pdf) | 2026-11-21 | low | DATA, MILL, SCEN |
| AR-P071 | FFB weight loss while waiting in queue/ramp. `ffb_weight_loss_pct_per_day_wait` = **0.7** % per day (0.2 to 2) | Engineering Assumption | [S14](https://rspo.org/wp-content/uploads/Oil-Palm-Development-in-Thailand-Trends-and-Progress-of-Sustainability-Efforts-in-Palm-Oil-Production-and-Procurement.pdf) | 2026-11-21 | low | DATA, LOG, KPI |
| AR-P072 | Palm kernel moisture after drying. `kernel_moisture_pct` = **6.5** % (5 to 7.5) | Industry Practice | [S16](https://www.aocs.org/resource/palm-oil/) | 2026-11-21 | med | DATA |

### C.7 steam power water

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P073 | Total process steam consumption per tonne FFB. `steam_t_per_t_ffb` = **0.5** t steam/t FFB (0.42 to 0.65) | Industry Practice | [S15](https://edepot.wur.nl/288880) (+S16) | 2026-11-21 | med | DATA, ENERGY, MILL, SCEN |
| AR-P074 | Boiler operating pressure. `boiler_pressure_barg` = **21** bar(g) (18 to 26) | Industry Practice | [S30](https://palmoilis.mpob.gov.my/publications/POEB/poeb116-ravi2.pdf) | 2026-11-21 | low | DATA, MILL, MAINT, TWIN |
| AR-P075 | Back-pressure receiver / process steam header pressure. `bpv_header_pressure_barg` = **3** bar(g) (1.5 to 3.5) | Industry Practice | [S30](https://palmoilis.mpob.gov.my/publications/POEB/poeb116-ravi2.pdf) | 2026-11-21 | low | DATA, MILL, TWIN |
| AR-P076 | Installed boiler capacity (all boilers). `boiler_installed_t_steam_per_h` = **40** t steam/h (30 to 60) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY, MAINT |
| AR-P077 | Boiler thermal efficiency on fibre/shell. `boiler_efficiency` = **0.6** fraction (0.55 to 0.75) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | low | DATA, ENERGY |
| AR-P078 | Overall steam-to-electricity conversion efficiency. `steam_turbine_overall_efficiency` = **0.12** fraction (0.08 to 0.2) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | low | DATA, ENERGY |
| AR-P079 | Total electricity per tonne FFB (all machines). `electricity_kwh_per_t_ffb` = **17** kWh/t FFB (14 to 25) | Industry Practice | [S15](https://edepot.wur.nl/288880) (+S26, S43) | 2026-11-21 | med | DATA, ENERGY, EXEC, SCEN |
| AR-P080 | Installed steam turbine generator. `turbine_generator_kw` = **1500** kW (1000 to 2500) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY, MAINT |
| AR-P081 | Standby diesel genset. `diesel_genset_kw` = **800** kW (500 to 1500) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY |
| AR-P082 | Diesel genset specific consumption. `diesel_l_per_kwh` = **0.27** L/kWh (0.22 to 0.35) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY |
| AR-P083 | Share of electricity imported from grid. `grid_import_share_of_kwh` = **0.05** fraction (0 to 0.3) | Engineering Assumption | [S26](https://cuir.car.chula.ac.th/dspace/bitstream/123456789/69113/6/Orathai_ch_ch5_p.pdf) | 2026-11-21 | low | DATA, ENERGY |
| AR-P084 | Diesel for loaders/tractors and internal transport. `diesel_l_per_t_ffb_handling` = **0.4** L/t FFB (0.2 to 1) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY |
| AR-P085 | Fresh water intake per tonne FFB. `water_m3_per_t_ffb` = **1.4** m3/t FFB (1 to 2.5) | Industry Practice | [S38](https://ioigroup.com/our-businesses/water-management) | 2026-11-21 | med | DATA, ENERGY |
| AR-P086 | Higher heating value of EFB/fibre/shell on dry basis. `biomass_hhv_gj_per_t_dry` = **19** GJ/t dry (17.5 to 21.5) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | med | DATA, ENERGY |
| AR-P087 | EFB moisture (fresh weight). `efb_moisture_pct` = **60** % (55 to 65) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | med | DATA, ENERGY |
| AR-P088 | Shell moisture (fresh weight). `shell_moisture_pct` = **15** % (10 to 25) | Industry Practice | [S15](https://edepot.wur.nl/288880) | 2026-11-21 | med | DATA, ENERGY |
| AR-P089 | POME chemical oxygen demand. `pome_cod_mg_per_l` = **65000** mg/L (45000 to 80000) | Engineering Assumption | [S39](https://es.slideshare.net/LennartNilsson4/201605malaysia-palm-oil-mill-value-map-public) | 2026-11-21 | low | DATA, ENERGY |
| AR-P090 | Biogas yield per m3 POME. `biogas_m3_per_m3_pome` = **28** m3/m3 (20 to 33) | Industry Practice | [S39](https://es.slideshare.net/LennartNilsson4/201605malaysia-palm-oil-mill-value-map-public) | 2026-11-21 | low | DATA, ENERGY, SCEN |
| AR-P091 | Methane share of biogas. `biogas_methane_fraction` = **0.6** fraction (0.55 to 0.65) | Industry Practice | [S39](https://es.slideshare.net/LennartNilsson4/201605malaysia-palm-oil-mill-value-map-public) | 2026-11-21 | low | DATA, ENERGY |
| AR-P092 | Electricity per m3 biogas via gas engine. `biogas_kwh_el_per_m3` = **2** kWh/m3 (1.6 to 2.4) | Engineering Assumption | A00 (judgement) (+S19) | 2026-11-21 | low | DATA, ENERGY, SCEN |

### C.8 equipment sensors

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P093 | ISO 10816-3 zone boundary A/B, Group 1 machine on rigid support. `iso10816_3_group1_rigid_zone_ab_mm_s` = **2.3** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P094 | ISO 10816-3 zone boundary B/C, Group 1 machine on rigid support. `iso10816_3_group1_rigid_zone_bc_mm_s` = **4.5** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P095 | ISO 10816-3 zone boundary C/D, Group 1 machine on rigid support. `iso10816_3_group1_rigid_zone_cd_mm_s` = **7.1** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P096 | ISO 10816-3 zone boundary A/B, Group 1 machine on flexible support. `iso10816_3_group1_flexible_zone_ab_mm_s` = **3.5** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P097 | ISO 10816-3 zone boundary B/C, Group 1 machine on flexible support. `iso10816_3_group1_flexible_zone_bc_mm_s` = **7.1** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P098 | ISO 10816-3 zone boundary C/D, Group 1 machine on flexible support. `iso10816_3_group1_flexible_zone_cd_mm_s` = **11** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P099 | ISO 10816-3 zone boundary A/B, Group 2 machine on rigid support. `iso10816_3_group2_rigid_zone_ab_mm_s` = **1.4** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P100 | ISO 10816-3 zone boundary B/C, Group 2 machine on rigid support. `iso10816_3_group2_rigid_zone_bc_mm_s` = **2.8** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P101 | ISO 10816-3 zone boundary C/D, Group 2 machine on rigid support. `iso10816_3_group2_rigid_zone_cd_mm_s` = **4.5** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P102 | ISO 10816-3 zone boundary A/B, Group 2 machine on flexible support. `iso10816_3_group2_flexible_zone_ab_mm_s` = **2.3** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P103 | ISO 10816-3 zone boundary B/C, Group 2 machine on flexible support. `iso10816_3_group2_flexible_zone_bc_mm_s` = **4.5** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P104 | ISO 10816-3 zone boundary C/D, Group 2 machine on flexible support. `iso10816_3_group2_flexible_zone_cd_mm_s` = **7.1** mm/s RMS (fixed) | Industry Practice | [S24](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/) | 2026-11-21 | med | DATA, MAINT |
| AR-P105 | Healthy vibration, drive motors (Group 2). `vib_healthy_motor_mm_s` = **1** mm/s RMS (0.4 to 1.4) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P106 | Healthy vibration, screw press gearbox/drive end. `vib_healthy_press_gearbox_mm_s` = **1.6** mm/s RMS (0.8 to 2.3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P107 | Healthy vibration, centrifugal pumps. `vib_healthy_pump_mm_s` = **1.4** mm/s RMS (0.6 to 2.3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P108 | Healthy vibration, ID/FD fans. `vib_healthy_fan_mm_s` = **2** mm/s RMS (1 to 2.8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P109 | Healthy vibration, sludge separators/decanters. `vib_healthy_centrifuge_mm_s` = **1.8** mm/s RMS (0.8 to 2.8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P110 | Healthy vibration, conveyor drives. `vib_healthy_conveyor_drive_mm_s` = **1.5** mm/s RMS (0.6 to 2.3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P111 | Healthy vibration, steam turbine generator. `vib_healthy_turbine_gen_mm_s` = **1.2** mm/s RMS (0.5 to 2.3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P112 | Normal bearing housing temperature (rolling-element). `bearing_temp_normal_c` = **62** degC (45 to 75) | Industry Practice | [S25](https://www.tecowestinghouse.com/Stock_Motor_PDF/RTD_Alarm_Trip_Settings.pdf) | 2026-11-21 | low | DATA, MAINT |
| AR-P113 | Bearing temperature alarm. `bearing_temp_alarm_c` = **85** degC (75 to 95) | Industry Practice | [S25](https://www.tecowestinghouse.com/Stock_Motor_PDF/RTD_Alarm_Trip_Settings.pdf) | 2026-11-21 | low | MAINT |
| AR-P114 | Bearing temperature trip. `bearing_temp_trip_c` = **100** degC (90 to 115) | Industry Practice | [S25](https://www.tecowestinghouse.com/Stock_Motor_PDF/RTD_Alarm_Trip_Settings.pdf) | 2026-11-21 | low | MAINT |
| AR-P115 | Warning when bearing temperature exceeds own baseline by this much. `bearing_temp_warn_delta_c` = **10** degC (5 to 15) | Engineering Assumption | [S25](https://www.tecowestinghouse.com/Stock_Motor_PDF/RTD_Alarm_Trip_Settings.pdf) | 2026-11-21 | low | MAINT |
| AR-P116 | Normal motor winding temperature. `motor_winding_temp_normal_c` = **85** degC (60 to 110) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P117 | Winding temperature alarm. `motor_winding_temp_alarm_c` = **130** degC (120 to 150) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | MAINT |
| AR-P118 | Motor current as fraction of full-load current, general equipment, normal. `motor_current_load_fraction_normal` = **0.72** fraction (0.5 to 0.95) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P119 | Sustained current threshold (fraction of FLA) for overload alert. `motor_current_alarm_fraction` = **1.05** fraction (1 to 1.15) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | MAINT |
| AR-P120 | Typical induction motor power factor under load. `motor_power_factor` = **0.85** - (0.78 to 0.9) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA |
| AR-P121 | Alert when steam pressure deviates from setpoint by more than. `steam_pressure_alarm_deviation_pct` = **10** % of setpoint (5 to 20) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | MILL, MAINT |
| AR-P122 | Fraction of sensor samples missing/flatlined/spiked (data-quality realism). `sensor_dropout_rate_pct` = **0.5** % of samples (0 to 3) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA |

### C.9 logistics

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P123 | Net FFB payload, pickup/4-wheel. `truck_payload_pickup_t` = **1.5** t (1 to 2) | Engineering Assumption | [S36](https://www.prd.go.th/th/content/category/detail/id/31/iid/231843) | 2026-11-21 | low | DATA, LOG, TRACE |
| AR-P124 | Net FFB payload, 6-wheel truck. `truck_payload_6wheel_t` = **8** t (6 to 10) | Engineering Assumption | [S36](https://www.prd.go.th/th/content/category/detail/id/31/iid/231843) | 2026-11-21 | low | DATA, LOG, TRACE |
| AR-P125 | Net FFB payload, 10-wheel truck. `truck_payload_10wheel_t` = **15** t (12 to 17) | Engineering Assumption | [S36](https://www.prd.go.th/th/content/category/detail/id/31/iid/231843) | 2026-11-21 | low | DATA, LOG, TRACE |
| AR-P126 | Net FFB payload, truck-trailer combination. `truck_payload_trailer_t` = **25** t (20 to 30) | Engineering Assumption | [S05](https://www.the operator's public website/port.php) (+S36) | 2026-11-21 | low | DATA, LOG |
| AR-P127 | Trip-weighted mean net payload (given the truck mix profile). `truck_mean_payload_t` = **10.9** t (8 to 14) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P128 | Weighbridges at the mill. `weighbridge_count` = **2** count (1 to 3) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P129 | Service time per weighing event (positioning, ticket, release). `weighbridge_service_min_per_event` = **2** min (1 to 4) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P130 | Weighing events per inbound trip (gross, tare). `weighbridge_events_per_trip` = **2** count (1 to 2) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P131 | FFB grading/inspection time per truck. `grading_inspection_min` = **4** min (2 to 8) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P132 | Unloading bays/tippers at the reception ramp. `unloading_bays` = **3** count (2 to 6) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P133 | Unloading rate per bay. `unloading_rate_t_per_min_per_bay` = **1** t/min (0.5 to 2) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P134 | FFB held on the reception ramp/hopper area before sterilizer loading. `ramp_buffer_capacity_t` = **300** t (100 to 600) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG, MILL |
| AR-P135 | Gate-in to gate-out turnaround, normal day. `truck_turnaround_min_normal` = **45** min (25 to 70) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG, EXEC |
| AR-P136 | Gate-in to gate-out turnaround during congestion. `truck_turnaround_min_congested` = **150** min (90 to 360) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG, EXEC |
| AR-P137 | Queue wait before first weighing, normal. `truck_wait_to_weigh_min_normal` = **8** min (2 to 20) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P138 | Queue wait before first weighing, congested. `truck_wait_to_weigh_min_congested` = **60** min (30 to 180) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P139 | Variance/mean ratio of hourly truck arrivals (over-dispersion vs Poisson). `arrival_dispersion_index` = **1.3** - (1 to 2) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P140 | Active FFB suppliers (ramps, groups, estates, direct farmers). `supplier_count_active` = **45** count (20 to 120) | Engineering Assumption | [S14](https://rspo.org/wp-content/uploads/Oil-Palm-Development-in-Thailand-Trends-and-Progress-of-Sustainability-Efforts-in-Palm-Oil-Production-and-Procurement.pdf) | 2026-11-21 | low | DATA, TRACE, LOG |
| AR-P141 | Between-supplier standard deviation of unripe share. `supplier_unripe_share_sd_pp` = **3** pp (1 to 6) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, TRACE |
| AR-P142 | Coefficient of variation of daily FFB intake around its seasonal mean. `ffb_supply_daily_cv` = **0.15** fraction (0.08 to 0.3) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, LOG, MILL |

### C.10 economics illustrative

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P143 | CPO price, illustrative baseline. `cpo_price_thb_per_t` = **40000** THB/t (30000 to 50000) | Historical Public Information | [S31](https://www.thansettakij.com/economy/trade-agriculture/656721) (+S13, S32) | 2026-11-21 | med | DATA, ROI, SCEN, EXEC |
| AR-P144 | FFB purchase price delivered to mill, illustrative baseline. `ffb_price_thb_per_kg` = **7.5** THB/kg (4.5 to 9) | Historical Public Information | [S31](https://www.thansettakij.com/economy/trade-agriculture/656721) (+S13, S14, S32, S35) | 2026-11-21 | med | DATA, ROI, EXEC |
| AR-P145 | Oil-content basis on which quoted Thai FFB prices are stated. `ffb_price_oil_content_basis_pct` = **18** % (fixed) | Historical Public Information | [S32](https://www.nationthailand.com/business/economy/40065331) | 2026-11-21 | med | KPI, TRACE |
| AR-P146 | Palm kernel price. `palm_kernel_price_thb_per_t` = **15000** THB/t (8000 to 25000) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | DATA, ROI |
| AR-P147 | Palm kernel shell (PKS) price if sold. `pks_price_thb_per_t` = **2000** THB/t (1000 to 3500) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | ENERGY, ROI |
| AR-P148 | EFB value if sold/used offsite. `efb_price_thb_per_t` = **300** THB/t (0 to 600) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | ENERGY, ROI |
| AR-P149 | Diesel retail price. `diesel_price_thb_per_l` = **40.8** THB/L (30 to 45) | Historical Public Information | [S33](https://www.pptvhd36.com/news/Wealth/287289) | 2026-11-21 | med | ENERGY, ROI |
| AR-P150 | Average grid electricity tariff. `grid_electricity_thb_per_kwh` = **3.95** THB/kWh (3.3 to 4.8) | Historical Public Information | [S34](https://www.khaosod.co.th/economics/news_10334424) | 2026-11-21 | med | ENERGY, ROI |
| AR-P151 | Mill conversion cost excluding FFB purchase (labour, chemicals, utilities, overhead). `processing_cost_ex_ffb_thb_per_t_ffb` = **400** THB/t FFB (250 to 650) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | ROI, EXEC, SCEN |
| AR-P152 | Maintenance spend per tonne FFB. `maintenance_cost_thb_per_t_ffb` = **80** THB/t FFB (40 to 150) | Engineering Assumption | A00 (judgement) | 2026-11-21 | low | ROI, MAINT, EXEC |
| AR-P153 | Month-on-month CPO price volatility for synthetic price series. `cpo_price_volatility_sd_pct_per_month` = **6** % per month (2 to 12) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA |

### C.11 scenario effects

| ID | Statement (key = nominal, range, unit) | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-P154 | PRESS_VIBRATION_ANOMALY / press degradation: extra oil lost in fibre at full severity. `scn_press_degradation_extra_fibre_loss_pp` = **0.3** pp of FFB (0.1 to 0.6) | Synthetic Demonstration Data | A00 (judgement) (+S17) | 2026-11-21 | low | DATA, MILL, SCEN, MAINT |
| AR-P155 | Press motor current rise at full severity. `scn_press_degradation_current_rise_pct` = **12** % of baseline (5 to 25) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P156 | Peak vibration reached by the degrading press (zone C of Group 2 rigid = 2.8-4.5). `scn_press_degradation_vib_peak_mm_s` = **4.8** mm/s RMS (3.5 to 7) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P157 | Throughput derate of the affected press line at full severity. `scn_press_degradation_throughput_derate_pct` = **8** % (0 to 20) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P158 | Days from first detectable drift to critical. `scn_press_degradation_lead_days` = **14** d (7 to 45) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MAINT |
| AR-P159 | STEAM_PRESSURE_DEVIATION: drop of BPV/boiler pressure vs setpoint. `scn_steam_deviation_pressure_drop_pct` = **15** % (8 to 30) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P160 | Duration of steam deviation episode. `scn_steam_deviation_duration_h` = **8** h (4 to 24) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P161 | Added sterilizer cycle time during episode. `scn_steam_deviation_cycle_extension_min` = **15** min (5 to 30) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P162 | Extra oil loss (undercooked bunches, nuts) during episode. `scn_steam_deviation_extra_loss_pp` = **0.15** pp of FFB (0.05 to 0.3) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P163 | OER_DEGRADATION: total OER drop vs baseline at peak of episode. `scn_oer_degradation_total_drop_pp` = **1.1** pp (0.5 to 2) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL, EXEC, SCEN |
| AR-P164 | Clarifier temperature drop in OER degradation episode. `scn_clarifier_temp_drop_c` = **5** degC (3 to 10) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P165 | Sludge oil loss multiplier when clarifier is cold. `scn_clarifier_sludge_loss_multiplier` = **1.5** x (1.2 to 2.5) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, MILL |
| AR-P166 | TRUCK_QUEUE_CONGESTION: hourly arrival multiplier vs seasonal baseline. `scn_queue_arrival_multiplier` = **1.8** x (1.3 to 2.5) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P167 | Congestion episode duration. `scn_queue_duration_days` = **4** d (2 to 8) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, LOG |
| AR-P168 | ENERGY_EFFICIENCY_DROP: steam per tonne FFB increase (leaks, wet fuel, poor insulation). `scn_energy_steam_increase_pct` = **15** % of baseline (5 to 25) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY |
| AR-P169 | ENERGY_EFFICIENCY_DROP: electricity per tonne FFB increase (idle running, fouling). `scn_energy_kwh_increase_pct` = **10** % of baseline (3 to 20) | Synthetic Demonstration Data | A00 (judgement) | 2026-11-21 | low | DATA, ENERGY |

## D. Proposed future capabilities (nothing exists)

| ID | Statement | Category | Source | Retrieved | Confidence | Used by |
|---|---|---|---|---|---|---|
| AR-F01 | Integrations with ERP, MES, SCADA, PLC, OPC UA, MQTT, weighbridge, LIMS, GPS/fleet and accounting/HR are future interface contracts documented on paper only. The demo connects to none of them. | Proposed Future Capability | A00 (judgement) | 2026-11-21 | n/a | IT, docs/integration |
| AR-F02 | Computer-vision FFB grading needs a properly licensed labelled dataset, a camera/lighting standard, class definitions, a labelling protocol and pilot validation. The demo ships a research prototype/plan only and makes no accuracy claim. | Proposed Future Capability | [S40](https://ir.uitm.edu.my/38188/1/38188.pdf) | 2026-11-21 | n/a | CV prototype (P2) |
| AR-F03 | Climate-driven plantation yield forecasting has published precedent in southern Thailand (province-level R2 0.33-0.73, forecast lead 3-20 months) but would require the operator's own estate records to be useful. | Proposed Future Capability | [S21](https://li01.tci-thaijo.org/index.php/anres/article/view/272520) | 2026-11-21 | med | Plantation concept (P2) |
| AR-F04 | Petroleum depot inventory and port/terminal scheduling are prototype concepts without any company data; they are not modelled with real depot or fuel-logistics detail. | Proposed Future Capability | none | 2026-11-21 | n/a | P2 concepts |
| AR-F05 | A cross-company data platform would first need data-sharing agreements, master-data governance and role design across divisions. | Proposed Future Capability | A00 (judgement) | 2026-11-21 | n/a | P2 concept |
| AR-F06 | An RSPO-style audit data model is sketched for demonstration only. No certification is claimed for any entity. | Proposed Future Capability | [S10](https://rspo.org/wp-content/uploads/RSPO-PC-PC14-Public-Announcement-EN-PC-V2_PC-Palm_Rev.01_TM-Approved.pdf), [S18](https://bsigroup.com/siteassets/pdf/en/about-us/rspo/rspo-pc-public-summary-report-univanich-topi-siam-lamthap-mill-asa1-2.pdf) | 2026-11-21 | n/a | TRACE |
| AR-F07 | Models calibrated on real failure, work-order (CMMS), LIMS and weighbridge history would replace the synthetic-trained demo models; until then scores remain uncalibrated. | Proposed Future Capability | A00 (judgement) | 2026-11-21 | n/a | MAINT, MILL, ML docs |
| AR-F08 | Biogas-from-POME and biomass-export scenarios are what-if projects, not installed assets in the demo mill. | Proposed Future Capability | [S15](https://edepot.wur.nl/288880), [S39](https://es.slideshare.net/LennartNilsson4/201605malaysia-palm-oil-mill-value-map-public) | 2026-11-21 | n/a | ENERGY, SCEN |

## E. Known gaps in public information (and how a real engagement would close them)

| ID | What we do not know | What we found instead | Proposed way to close |
|---|---|---|---|
| GAP-01 | Whether a Thai palm oil operator's a southern Thai site mill is operating, commissioning or planned, and its real throughput | Public pages describe the mill only as planned (2014/2017); the Feb 2025 RSPO notice lists 60 t/h; nothing confirms operation. | 30-day discovery: site visit and stakeholder interview. |
| GAP-02 | Any real OER, KER, loss, FFA, downtime, energy or queue statistics | None are public. The RSPO forecast (CPO 1,320 t, kernel 330 t from 6,600 t FFB) is a forecast conversion factor for the certified supply base only. | Request historical data under NDA for the pilot. |
| GAP-03 | Existing systems: SCADA/DCS vendor, historian, weighbridge software, ERP, LIMS, CMMS | Not public. | IT discovery workshop; map data flows before proposing integration. |
| GAP-04 | Outcome of the March 2025 RSPO initial audit and current certification status | Only the public announcement was found. | Check RSPO member/certificate database or ask. |
| GAP-05 | Real FFB supplier mix, ramp network and truck fleet | Not public. | Weighbridge export for 90 days. |
| GAP-06 | Thai monthly FFB/CPO seasonality at national level | Only one Surat Thani site profile found in text; OAE open data not opened. | Pull OAE dataset (S45) to replace the assumed profile. |
| GAP-07 | Equipment inventory, motor ratings, boiler/turbine specifications | Not public. | Asset register from maintenance team. |
| GAP-08 | Official ISO 10816/20816 thresholds, PORAM contract clauses | Used secondary summaries; one source conflicts for Group 2 rigid B/C. | Verify against licensed standard and current contracts. |

## F. Source index

Retrieval date for every row: 2026-11-21. 'excerpt' in the type column means only a search-result excerpt was read; those rows are capped at low or med confidence. Paraphrased; no long quotations.

| ID | Source | Publisher | Date/period | Type | Reliability | URL |
|---|---|---|---|---|---|---|
| S01 | a Thai diversified group home page (Thai) | a Thai diversified group (official site) | Undated page; news items 2014-2015; hit counter, no copyright year | official website | med | https://www.the operator's public website/ |
| S02 | a Thai diversified group - Palm (Thai) | a Thai diversified group (official site) | Page dated 25 Aug 2560 BE (2017 CE) | official website | med | https://www.the operator's public website/palm.php |
| S03 | a Thai diversified group - Palm (English) | a Thai diversified group (official site) | Page dated 18 Feb 2014 | official website | low | https://www.the operator's public website/en/palm.php |
| S04 | a Thai diversified group - Petroleum (Thai) | a Thai diversified group (official site) | Page dated 10 Mar 2564 BE (2021 CE) | official website | med | https://www.the operator's public website/petroleum.php |
| S05 | a Thai diversified group - Port (Thai) | a Thai diversified group (official site) | Page dated 10 Mar 2564 BE (2021 CE) | official website | med | https://www.the operator's public website/port.php |
| S06 | a Thai diversified group - About us (Thai) | a Thai diversified group (official site) | Page shows 11 Oct 2556 BE (2013 CE) | official website | med | https://www.the operator's public website/about_us.php |
| S07 | a Thai diversified group - Mining (Thai) | a Thai diversified group (official site) | Page dated 10 May 2564 BE (2021 CE) | official website | med | https://www.the operator's public website/mining.php |
| S08 | a Thai diversified group - Tower (Thai) | a Thai diversified group (official site) | Page dated 10 May 2564 BE (2021 CE) | official website | med | https://www.the operator's public website/tower.php |
| S09 | a Thai diversified group - News list | a Thai diversified group (official site) | Items dated Sep 2014 - Jun 2015 | official website | med | https://www.the operator's public website/news/index.php |
| S10 | RSPO public announcement: initial audit of a Thai palm oil operator (Bureau Veritas) | RSPO / Bureau Veritas Certification (Thailand) | Notification dated 23 Feb 2025; audit 25-28 Mar 2025 | public certification notice | high | https://rspo.org/wp-content/uploads/RSPO-PC-PC14-Public-Announcement-EN-PC-V2_PC-Palm_Rev.01_TM-Approved.pdf |
| S11 | Nation Thailand - a Thai petroleum distributor group profile (news, April 2026) | Nation Thailand (news) | 5 Apr 2026 | news | med | https://www.nationthailand.com/business/economy/40064701 |
| S13 | Krungsri Research - Industry Outlook 2026-2028: Palm Oil Industry | Krungsri Research | 5 May 2026 | bank industry research | high | https://www.krungsri.com/en/research/industry/industry-outlook/agriculture/palm-oil/io/plam-oil-2026 |
| S14 | Thongrak, Kongmanee, Kiatpathomchai (PSU) - Oil Palm Development in Thailand: Trends and Progress of Sustainability Efforts (final report for RSPO) | Prince of Songkla University for RSPO | August 2023 (data to 2021/2022) | academic/NGO report | high | https://rspo.org/wp-content/uploads/Oil-Palm-Development-in-Thailand-Trends-and-Progress-of-Sustainability-Efforts-in-Palm-Oil-Production-and-Procurement.pdf |
| S15 | Elbersen, Meesters, Bakker (Wageningen UR) - Valorization of palm oil (mill) residues | Wageningen UR Food & Biobased Research / NL Agency | October 2013 | technical report | high | https://edepot.wur.nl/288880 |
| S16 | AOCS Lipid Library - Palm oil | AOCS | Undated reference page | technical reference | med | https://www.aocs.org/resource/palm-oil/ |
| S17 | Vijaya, Menon, Sin, Choo (2013) - Residual oil recovery system for a palm oil mill, J. Oil Palm Research 25(1):116-122 | MPOB / Journal of Oil Palm Research | 2013 | peer-reviewed article | high | https://jopr.mpob.gov.my/the-development-of-a-residual-oil-recovery-system-to-increase-the-revenue-of-a-palm-oil-mill/ |
| S18 | Univanich Palm Oil PCL - RSPO P&C Public Summary Report (ASA1_2), BSI | BSI / Univanich Palm Oil PCL | Report file dated Jul 2024; period 2023-2025 | public certification summary | high | https://bsigroup.com/siteassets/pdf/en/about-us/rspo/rspo-pc-public-summary-report-univanich-topi-siam-lamthap-mill-asa1-2.pdf |
| S19 | Univanich - Factory & Biogas / news | Univanich Palm Oil PCL | Footer (c) 2026; items 2025-2026 | company website | med | https://univanich.com/?p=7509 |
| S20 | Thawornrat et al. (2024) - Correlation between weather conditions and tenera oil palm yield in Surat Thani Province, Rambhai Barni Rajabhat Agricultural Journal 2(2) | Dept. of Agriculture (Thailand) researchers; Thai journal | Received Jul 2024; data 2016-2021 | peer-reviewed article | med | https://ph03.tci-thaijo.org/index.php/kaset_rbruj/article/download/3071/2483/15597 |
| S21 | Jantaraprasit et al. (2026) - Time-ordered empirical framework for forecasting climate-driven oil palm yield in southern Thailand, Agriculture and Natural Resources 60 | Kasetsart University | Available online 10 Jun 2026 | peer-reviewed article | high | https://li01.tci-thaijo.org/index.php/anres/article/view/272520 |
| S22 | Putra (2013) - Kinetics of change of free fatty acid and oil content of oil palm due to processing delay, Universitas Sriwijaya (Indonesian thesis) | Universitas Sriwijaya | 2013 | undergraduate thesis (lab study) | low | https://repository.unsri.ac.id/72064/2/RAMA_41231_05091003007_0005076402_0031105601_01_front_ref.pdf |
| S23 | Mustaffa, Lau, Choo (2010) - Effect of FFA and oil yield of FFB by prolonging storage after harvesting (AGRIS record) | UPM / MPOB (conference abstract) | 2010 | conference abstract | low | https://agris.fao.org/search/en/records/647391e368b4c299a3f9e659 |
| S24 | Fabrico - ISO 10816-3 vibration severity (zone table); cross-check Beckhoff TF3600 documentation | Fabrico (vendor blog); Beckhoff Infosys | Undated blog; Beckhoff page https://infosys.beckhoff.com/content/1033/tf3600_tc3_condition_monitoring/2708344331.html | secondary summary of standard | med | https://www.fabrico.io/blog/iso-10816-3-vibration-severity/ |
| S25 | Bearing RTD alarm/trip guidance (TECO-Westinghouse RTD alarm/trip table; GE 469 manual defaults; IEEE C50.13-style presets as quoted by a generator tool) | Motor/relay vendors | Undated | vendor documentation (excerpt) | low | https://www.tecowestinghouse.com/Stock_Motor_PDF/RTD_Alarm_Trip_Settings.pdf |
| S26 | Orathai (Chulalongkorn Univ.) - Thai crude palm oil mill thesis, chapter 5 (excerpt) | Chulalongkorn University | Undated thesis | thesis (excerpt) | low | https://cuir.car.chula.ac.th/dspace/bitstream/123456789/69113/6/Orathai_ch_ch5_p.pdf |
| S27 | Tan et al. (2001) - Palm oil survey for strategic quality improvement and specifications (AGRIS record) plus PORAM/MS 815 excerpts | MPOB seminar proceedings | Seminar Jul 2000; AGRIS 2001 | conference abstract + excerpts | med | https://agris.fao.org/search/en/records/647391e168b4c299a3f9e57f |
| S28 | Emebu et al. (2022) - Influence of moisture content, temperature and time on free fatty acid in stored crude palm oil, Scientific Reports 12:9846 | Springer Nature | 2022 | peer-reviewed article | high | https://pmc.ncbi.nlm.nih.gov/articles/PMC9198255/ |
| S29 | AGRIS record - Effect of high pressurized sterilization on oil palm fruit digestion operation (digestion at atmospheric pressure, 90-96 C) | FAO AGRIS (Thai university study) | Undated record | journal abstract (excerpt) | med | https://agris.fao.org/search/ar/records/64747395425ec3c088f34745 |
| S30 | MPOB Palm Oil Engineering Bulletin 116 - boilers and steam | MPOB | Undated bulletin | technical bulletin (excerpt) | med | https://palmoilis.mpob.gov.my/publications/POEB/poeb116-ravi2.pdf |
| S31 | Thansettakij - DIT price report, 10 Apr 2569 (FFB and CPO prices) | Thansettakij (relaying Dept. of Internal Trade) | 10 Apr 2026 | news | med | https://www.thansettakij.com/economy/trade-agriculture/656721 |
| S32 | Nation Thailand - bottled palm oil price rise clears amid cost surge | Nation Thailand (news) | 22 Apr 2026 | news | med | https://www.nationthailand.com/business/economy/40065331 |
| S33 | PPTV - retail fuel prices 18 Nov 2569 | PPTV (relaying PTT retail prices) | 13-18 Nov 2026 | news | med | https://www.pptvhd36.com/news/Wealth/287289 |
| S34 | Khaosod - ERC sets Ft for Sep-Dec 2569 (average tariff THB 3.95/kWh) | Khaosod (relaying ERC decision) | 2026 | news | med | https://www.khaosod.co.th/economics/news_10334424 |
| S35 | Infoquest - palm prices held up for 25+ weeks | Infoquest (relaying DIT) | 2026 | news | med | https://infoquest.co.th/2026/635915 |
| S36 | PRD Thailand - truck weight limits (6-wheel 15 t, 10-wheel 25 t gross) | Public Relations Dept. (excerpt via search) | Undated | government PR page (excerpt) | low | https://www.prd.go.th/th/content/category/detail/id/31/iid/231843 |
| S37 | Alfa Laval - Recover more oil, generate higher revenue (palm oil processing) | Alfa Laval (vendor) | Undated | vendor marketing page (excerpt) | low | https://test03.alfalaval.com/en-sg/industries/food-dairy-and-beverage/food-processing/fat-and-oil-processing/palm-oil-processing/recover-more-oil-generate-higher-revenue |
| S38 | IOI Group water management; REA Holdings minimising water use | IOI Corporation; REA Holdings plc | Sustainability pages | corporate sustainability disclosures (excerpt) | med | https://ioigroup.com/our-businesses/water-management |
| S39 | Malaysia palm oil mill value map (slide deck) | Industry presentation (2016) | 2016 | industry slide deck (excerpt) | low | https://es.slideshare.net/LennartNilsson4/201605malaysia-palm-oil-mill-value-map-public |
| S40 | UiTM theses and MPOB grading guidance on FFB grading and OER | Universiti Teknologi MARA | Undated theses | academic theses (excerpt) | low | https://ir.uitm.edu.my/38188/1/38188.pdf |
| S41 | MPOB Code of Practice for bulking of edible oils | MPOB | 2019 upload | code of practice (excerpt) | med | https://cdn.mpob.gov.my/wp-content/uploads/2019/11/CodesPractice_Bulking.pdf |
| S42 | Indonesian journal article on FFB handling (max 8 h harvest-to-mill) | UIN Suska Riau (Indonesia) | Undated | journal article (excerpt) | low | https://ejournal.uin-suska.ac.id/index.php/sitekin/article/download/21947/8834 |
| S43 | Utilizations of palm oil mill wastes as a source of energy (slide deck) | Academic slide deck | Undated | slide deck (excerpt) | low | https://fr.slideshare.net/AlexanderDecker/utilizations-of-palm-oil-mills-wastes-as-source-of-energy |
| S44 | Krungsri Research - IO Oil (palm oil quality emphasis, extraction within 24 h) | Krungsri Research | Undated PDF | bank industry research (excerpt) | low | https://www.krungsri.com/getmedia/de09fc89-060d-4545-ac44-1fe91709c640/IO_Oil_ |
| S45 | OAE open government data - monthly oil palm production (recommended future source) | Office of Agricultural Economics / data.go.th | Dataset index | open data (not opened) | n/a | https://data.go.th/en/dataset/nabc-oae00051 |
| A00 | Researcher engineering judgement (no external source) | Researcher agent | 2026-11-21 | assumption | low | n/a |
