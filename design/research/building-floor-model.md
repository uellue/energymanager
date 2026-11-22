# A building and floor model for the pilot: structure, identification, savings, floor limits

Question (requirements 1.1, 2.11, S2 and model trust in 2.6/2.7): which grey-box (RC) structure reproduces the pilot house closely enough to plan when and at which leaving-water offset the heat pump runs; what identifying it from operating data takes; how a saving of a few percent against a reference period can be shown; what is published on the floor's rate of change; and which measurements the pilot lacks.

Provenance: a literature search by a sub-agent on 2026-11-22. "Full text" means the document was read (author manuscripts where noted); "abstract" means only the abstract. DOIs checked against Crossref on 2026-11-22. Quotes are from the full texts. Not reviewed by a person.

## Findings

### Model structure
- Bacher & Madsen 2011, Energy and Buildings 43:1511, doi:10.1016/j.enbuild.2011.02.005 (full text, author manuscript https://backend.orbit.dtu.dk/ws/files/126769045/modelselection09.pdf). 120 m² light timber house, electric heaters, 6 days of 5-minute data, heat input measured and driven by a pseudo-random binary sequence; outdoor temperature and global irradiance from an on-site station. Forward selection with likelihood-ratio tests from Ti (1R1C) to five states:
  - states: Ti indoor air, Th heater, Te envelope, Tm "interior walls and furniture", Ts sensor; solar enters through windows (Aw) and onto the envelope (Ae);
  - Ti and TiTh fail the residual checks; TiTeTh (3 states) "describes the heat dynamics of the building quite well"; selected: TiTeThTsAe;
  - adding Tm did not raise the likelihood (TiTmTeThTsAe 5614.6, TiTeThTsAe 5614.6, Table 1): the interior medium was not identifiable from that data;
  - largest remaining errors at high irradiance; the solar part is where to improve.
- The principal's structure (slab heated by the heat pump; inner walls and furniture coupled through the room; massive outer wall coupled to outside; sun on the outer wall and through windows; appliance gains) is Bacher & Madsen's full model with Th as the slab: Ti, Th(slab), Tm, Te with Aw and Ae, plus appliance heat into Ti. Tahersima et al. 2012 (IEEE CDC, doi:10.1109/CDC.2012.6425810, full text, preprint https://vbn.aau.dk/ws/files/73867242/cdc_2012.pdf) model underfloor heating with "three main thermal masses: air, concrete floor, and water", estimating floor and water temperatures with a Kalman filter.
- IBPSA/Modelica Buildings `ReducedOrder.RC` (VDI 6007-1; docs https://simulationresearch.lbl.gov/modelica/releases/latest/help/Buildings_ThermalZones_ReducedOrder_RC.html): One- to FourElements add exterior walls, interior walls (adiabatic on the outside), floor plate ("long-term effects dominate the excitation of the floor plate") and roof. A white-box template for the same split; it has no floor-heating element.
- Picard et al. 2017, Energy and Buildings 152:739, doi:10.1016/j.enbuild.2017.07.027 (full text, preprint https://lirias.kuleuven.be/retrieve/498e6786-2848-4f5f-8fb8-ff58f48c8398). Simulated 6-room house, reduced models of 4 to 100 states as MPC models: each zone needs its own states, floors and walls between zones need enough states, the minimum "increases with the building mass content"; 30 instead of 20 states improved comfort by a factor 2 to 6. Heating was idealised as direct heat injection, not a slab.
- Arroyo et al. 2020, J Build Perf Sim 13:472, doi:10.1080/19401493.2020.1770861 (full text, https://lirias.kuleuven.be/retrieve/9f03f0a8-e11b-4d28-868e-9c7ea690dd30). BOPTEST emulator, radiators: one-zone models "suitable as well if the heat distribution to the zones is properly balanced"; open-loop error grows with distance from training without state updates.
- Blum et al. 2019, Applied Energy 236:410, doi:10.1016/j.apenergy.2018.11.093 (abstract): up to 20 % cost difference between best and worst model in MPC, mainly from model structure and initial guesses.

Accuracy: the sources read give no room-temperature RMSE per structure for a floor-heated house on operating data. Bacher & Madsen judge by residual whiteness, not by error in K. Picard et al. cite simplified white-box models matching detailed simulation within ±0.5–1 K. Arroyo et al. show residual box plots only. Hedegaard & Petersen 2017, Energy Procedia 132:982, doi:10.1016/j.egypro.2017.09.692 (abstract): heat loss coefficient within 4 % for all structures, thermal mass overestimated by 10–32 %.

### Identification from operating data
- Length: Arroyo et al.: no further gain beyond 7 days of training (3–14 tested); 5 days gave a model that failed; estimates are "not unique and … very sensitive to data", physical bounds help. Annex 71 tested 15, 30 and 60 days for the heat loss coefficient (Project Summary Report, Roels ed. 2022, Figure 4, https://www.iea-ebc.org/Data/publications/EBC_PSR_Annex_71.pdf; the result is shown only as a figure).
- Excitation: Bacher & Madsen used a pseudo-random binary heat input "designed to excite the heat dynamics at several ranges of frequencies"; Arroyo et al. used none ("business-as-usual"). A weather-compensated heat pump correlates heat input with outdoor temperature, which neither paper tested.
- Signals in every source read: heat input (measured), indoor temperature, outdoor temperature, irradiance.
- Identifiability of the principal's four masses from one room sensor: no source read shows it. Bacher & Madsen, with measured heat and a designed input, could not identify Tm. A measured slab or floor-surface temperature, or the return-water temperature, would observe Th directly; an inner-wall surface temperature would observe Tm. This follows from the structure; no source tested it.

### Savings against a reference period
- FEMP M&V Guidelines 4.0, 2015 (full text, https://www.energy.gov/sites/prod/files/2016/01/f28/mv_guide_4_0.pdf), Option C (whole facility or submeter regression): use only when savings exceed "about 10% to 20% of the overall consumption", with at least 12 (preferably 24) months of baseline and at least 9 (preferably 12) months of reporting data.
- Same document, Table 4-2 (from ASHRAE Guideline 14), calibrated simulation (Option D): monthly mean bias ±5 % and CV(RMSE) 15 %; hourly ±10 % and 30 %. The FEMP supplement 2023 (https://www.energy.gov/sites/default/files/2023-09/supplement-to-mv-guidelines_version-4.pdf) gives for regression models R² > 0.75, CV(RMSE) < 15 %, bias ±7 %, and suggests a "custom temperature base" for degree days.
- Eurostat heating degree days: 18 °C − daily mean on days with mean ≤ 15 °C (https://ec.europa.eu/eurostat/cache/metadata/en/nrg_chdd_esms.htm).
- PRISM (Fels 1986, Energy and Buildings 9:5, doi:10.1016/0378-7788(86)90003-4; not opened): the standard degree-day regression with a fitted base temperature.
- Consequence: a few percent is below FEMP's floor for Option C. A model-based counterfactual (the calibrated model run with the old heating curve on the actual weather, Option D) fits the project better and uses the same model; its calibration targets are the ones above.

### Floor limits
- DIN EN 1264-4 functional heating, as given in a screed maker's protocol (LANXESS, cement screed, https://lanxess.com/-/media/project/lanxess/corporate-internet/products-and-solutions/brands/anhydrit/aufheizprotokoll_ct_.pdf): from day 21, 3 days at 25 °C supply, then 4 days at maximum supply (≤ 55 °C), then off. No ramp between the steps.
- Parkett-Aktion leaflet 2023 (https://parkett-aktion.com/media/6e/d4/9d/1714047643/merkblatt-parkett-auf-fussbodenheizung-2023.pdf): screed drying from 25 °C up by 10 °C per day, down by 10 °C per day; parquet surface at most 29 °C; after laying, run a week at the set temperature, then raise "schrittweise".
- HFA leaflet 2018 (https://holzforschung.at/fileadmin/user_upload/Downloads/Broschueren/gratisdownloads/Merkblatt/HFA-Merkblatt-Fussbodenheizung-2018.pdf): wood floor surface at most 29 °C, also in edge zones (ÖNORM B 2242-7).
- No source found gives a rate-of-change limit for a floor in operation. The daily steps above are for drying new screed. The pilot's 10 K in 2 h has no published counterpart either way; the 29 °C surface limit is the only operational figure found, and the pilot does not measure surface temperature.

## What this means for the pilot
- Start from Bacher & Madsen's sequence, with Th as the slab: TiThTe with Aw, then Ae, then Tm, accepting each step only by likelihood-ratio test and residual checks. A sensor state Ts may be needed if the room sensor sits in the heat pump's user interface.
- Expect TiThTe to be identifiable from a week or more of cold-season data; expect Tm not to be, without an extra sensor.
- The weakest link is heat input: every source measured heat, the pilot infers electrical power and has no COP. Without heat, the envelope's UA and the COP scale each other.
- For the savings claim, plan Option D from the start: keep the old heating curve as a simulated baseline and meet the calibration targets on the reference winter.

## Gaps in the pilot's measurements, by importance
1. Heat delivered to the floor: no flow rate, no return temperature, electrical power only inferred from the household load, Onecta energy in whole kWh per 2 h.
2. Slab or floor-surface temperature: none; needed to observe the slab state and the 29 °C surface limit.
3. Return-water temperature: none; leaving water is the floor supply only in space-heating mode.
4. Irradiance: only PV output of one string as a proxy (one orientation, clipped at the inverter).
5. Room temperature: one sensor, the heat pump's; resolution and placement not checked.
6. Outdoor temperature: the outdoor unit's sensor, possibly biased by its own operation and sun; no weather-station reference.
7. Operating mode (space heating vs hot water) as a time series: needed to split the leaving-water series; not checked whether Onecta records it with enough time resolution.
8. Inner-wall surface temperature or a second room sensor: only needed to identify Tm.

## Not verified
- Annex 71 "Building behaviour identification" report (https://lirias.kuleuven.be/retrieve/639342): fetch timed out. Its guidance on MPC models and data length is unread.
- Annex 58 reports: not searched beyond the Annex 71 summary.
- Reynders, Diriken & Saelens 2014, Energy and Buildings 82:263, doi:10.1016/j.enbuild.2014.07.025 (input and sensor accuracy versus model quality): paywalled, abstract not available.
- Harb et al. 2016, doi:10.1016/j.enbuild.2016.02.021, and Vivian et al. 2017, doi:10.1016/j.enbuild.2017.06.021 (model order versus accuracy): no abstract obtained.
- Halvgaard et al. 2012, doi:10.1109/isgt.2012.6175631: not opened.
- DIN EN 1264-2 and -4, ASHRAE Guideline 14, IPMVP: paywalled; known only through the sources above.
- CTSM-R (https://ctsm.info): only the start page read; it estimates "continuous time stochastic state space model" parameters from R.
- "Darwin" in the brief: no building-modelling tool of that name identified.
- The value of switchback tests (alternating control days) for proving savings: no primary source found.
