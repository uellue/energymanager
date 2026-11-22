# Heat pump model for control and verification

Question (requirements 1.1, 1.3, 2.3; issue #6): which COP, part-load, defrost and hot-water model can decide when to run the pilot's Daikin Altherma 3 R ECH₂O (ERLA14D2W1 + EBSXB16P50DF) and at which leaving-water offset? How accurately do such models reproduce real power, COP, cycling and defrost, and which measurements does the pilot lack?

Provenance: research by a sub-agent on 2026-11-22. Code was read from shallow clones at the commits named below. Daikin documents were read in full text. Papers were read as abstracts only (via Semantic Scholar), except where noted. The fits and fleet statistics marked "computed here" were calculated in this session from the published numbers and have not been re-checked independently.

## 1. COP models and how accurate they are

Daikin publishes rated full-load points for ERLA14D2W1 under EN 14511, as "integrated values", which include defrost. They are in data book EEDEN23, p. 22 (written for the single-phase EBVH indoor unit; the table names ERLA14D2W1 explicitly). The copy read is a retailer's, not Daikin's: https://www.oceanairuk.com/cdn/shop/files/ERLA11-14DV3.ERLA-DV37.EBVH-UD6V_Data_Book_EEDEN23_English_ERLA14DV3.pdf

| Outdoor / leaving water | 35 °C | 45 °C | 55 °C |
|---|---|---|---|
| +10 °C | 5.32 (9.2 kW) | | |
| +7 °C | 4.87 (12.0 kW) | 3.64 | 2.89 |
| +2 °C | 3.50 (10.8 kW); 4.01 at 6.29 kW | | |
| −2 °C | | 2.58 | |
| −7 °C | 3.00 | 2.29 | 1.82 |

- Daikin's product page for this exact combination gives the same A7/W35 COP of 4.87, plus SCOP 4.68 at 35 °C and 3.26 at 55 °C (average climate): https://www.daikin.eu/en_us/products/product.table.html/EBSXB-D---ERLA11-14DW1.html
- The data book has only maximum-capacity graphs. No minimum capacity, and no grid of COP over part load, was found.

Each model below was fitted to, or evaluated against, the nine full-load points (computed here). The errors are relative COP errors:

| Model | RMS | Max | Notes |
|---|---|---|---|
| Carnot η·T_lw/(T_lw−T_out), η fitted = 0.41 | 9 % | 20 % | overestimates −7 °C/55 °C |
| Carnot with condensing at flow +2 K and evaporating at outdoor −6 K (HeatpumpMonitor's form), η = 0.51 | 14 % | 31 % | |
| EMHASS default, raw Carnot with η = 0.45 | 16 % | 31 % | overestimates at every point |
| Linear in T_out and T_lw (3 parameters) | 9.5 % | 19 % | |
| Quadratic in lift ΔT (3 parameters) | 7 % | 16 % | |
| when2heat air-source curve (Ruhnau et al.), without its 0.85 factor | 13 % | 25 % | |
| heating_curve_optimizer defaults, without defrost | 15 % | 25 % | |

- Checked by the orchestrator (2026-11-22): a fit of the Carnot fraction to the nine full-load points by least relative error gives η = 0.40, 8 % RMS and 15 % at worst; η = 0.45 overestimates at every point (by 2 % at least). The figures above depend on the fitting criterion, the conclusions do not.
- The +2 °C point lies about 10 % below the Carnot trend of the other points (η 0.419 fitted without it). This is consistent with the defrost losses included at 2/1 °C.
- At +2 °C, the part-load point (6.29 kW, COP 4.01) is 15 % better than the full-load point (10.8 kW, COP 3.50). A model at full load therefore misses the part-load gain.
- Field accuracy, from HeatpumpMonitor.org's analysis notes (community analysis, not peer-reviewed; https://github.com/openenergymonitor/heatpumpmonitor.org/tree/bc0d7fd/analysis/performance_prediction/docs):
  - Predicting a year's SPF from the heat-weighted flow-minus-outdoor ΔT gives ±0.50 (90 % interval, cross-validated). Carnot with +2/−6 gives ±0.52. Curved fits are "no better". The metering error alone is ±0.10.
  - In a replay of 126 Vaillant Arotherm+ units, field COP divided by datasheet COP in steady space heating had a median of 0.96 (p10–p90 0.89–1.02).
  - So an uncalibrated datasheet model is off by up to about 10 % for a given unit. Getting closer needs a per-unit level fitted from measured heat and electricity.
- HeatpumpMonitor public stats, last 365 days, downloaded 2026-11-22 (computed here; API documented at https://heatpumpmonitor.org/api-helper). Selection: 283 air-source units, MID-metered, with more than 300 days of data.
  - % of Carnot: median 48 (IQR 45–51). For 19 Daikin Altherma 3: 44.5 (43–48).
  - Space-heating COP: median 4.25, Altherma 3: 3.68. Across systems (not within one unit), it falls by about 0.13 per K of mean flow temperature.

## 2. Part load and cycling

- Regulation (EU) 813/2013, Annex I: "if Cdh is not determined by measurement then the default degradation coefficient is Cdh = 0,9". https://legislation.gov.uk/eur/2013/813/annex/I/division/3/adopted
- The data book declares Cdh = 1.0 at EN 14825 points A–D for the EBVH + ERLA14DV3 combination. A declaration of 1.0 means Daikin claims no cycling loss at those points. Whether this was measured is not stated.
- Piechurski et al. 2018, doi:10.1051/e3sconf/20184400139 (abstract): the default 0.9 "often does not reflect the actual degree of the COP reduction". The authors fit a quasi-dynamic degradation model to field data from one air-to-water unit.
- Dongellini & Morini 2019, doi:10.1016/j.enconman.2019.06.022 (abstract, simulation only):
  - start-up losses cut SPF by up to 12 % for single-stage units;
  - inverter units avoid cycling "for a significant part of the season".
- HeatpumpMonitor machine replay (docs above):
  - start-ups, defrosts, ramps, hot water and standby each cost a median of 0.04–0.13 SPF;
  - starts per day have no link to quality (rho −0.09);
  - time at minimum compressor speed does (rho −0.43).
- Daikin installer reference guide 4P663482-1C, p. 189 (https://www.daikin.co.uk/content/dam/document-library/Installer-reference-guide/heat/ERLA11-14D(V3.W1).ERLA-D(V3.W1)7.EBS(H.X)(B)-D_Installer%20reference%20guide_4PEN663482-1C_English.pdf): leaving-water "Modulation" [8‑05]/[8‑06] gives "less on/off cycles" and lower water temperatures.
- For control: within the modulation range, lower output at a lower leaving-water temperature raises COP (the +2 °C part-load point). Below minimum output, the unit cycles. The cost per start, and the minimum output, are not published for this unit; both have to be measured.

## 3. Defrost

- Method: reversed cycle, controlled by a sensor on the outdoor heat exchanger (data book, specifications).
- Where the defrost heat comes from on ECH₂O (installer guide):
  - "To make tank defrost possible, we recommend a minimum tank temperature of 35°C" (tank settings);
  - "Continuous heating" [F‑08]: 0 means space heating stops during a defrost; 1 means it is supplied from the tank.
  - So the defrost heat comes from the storage tank, and the signature can show in the tank temperature as well as in the leaving water.
- Vocale, Morini & Spiga 2014, doi:10.1016/j.egypro.2014.01.070 (abstract, model of Italian sites): frost formation "is mainly affected by the relative humidity"; hourly COP drops by up to 20 %, SCOP by less than 13 %.
- HeatpumpMonitor:
  - about 1.6 % of net heat goes to defrost, about 0.15 SPF at SPF 4;
  - their model's penalty is up to 13 %, fully applied between −2 and +2 °C and fading to zero by +6 °C (`design_model.md`).
- heating_curve_optimizer's `calculate_defrost_factor` gives frosting onset at 3.1 °C at 100 % relative humidity and 5.3 °C at 70 %. It cites no source for these figures (`helpers.py`, commit 4453a90).
- Recognising defrost: HeatpumpMonitor classifies a defrost as "running with negative heat", plus a 600 s recovery (`scripts/feed_scan/replay.php`). This needs a heat meter.
- Without a heat meter (inference, not verified on this unit):
  - in a defrost, the compressor keeps drawing power while R1T (leaving water at the plate heat exchanger) falls below the return and the tank temperature drops;
  - in low-load cycling, power falls to standby for minutes.

## 4. Hot water

- COP at A7: 2.89 at 55 °C leaving water against 4.87 at 35 °C (data book).
- HeatpumpMonitor hot-water COP (computed here): median 3.06 at a median water flow temperature of 45 °C; 2.43 for the 19 Altherma 3 units.
- Valves: ECH₂O has a tank valve M1S and a bypass valve M2S, not a classic 3‑way valve (installer guide, hydraulic legend).
  - Hot-water runs have an anti-recycle timer [8‑02], with a minimum of 0.5 h, and a maximum running time [8‑01].
  - HeatpumpMonitor excludes the first 600 s after a switch from hot water to space heating ("post_dhw"), when hot primary water flows into the heating circuit.
- PV timing: COP rises with outdoor temperature, which favours early afternoon. The unit's Smart Grid "Recommended on" state buffers PV surplus into the tank up to its maximum temperature (installer guide, Smart Grid section). This needs the Smart Grid contacts.

## 5. Existing tools

- **EMHASS** (commit f88620c, https://github.com/davidusb-geek/emhass):
  - `utils.calculate_cop_heatpump` uses raw Carnot, carnot_efficiency × T_supply/(T_supply − T_outdoor);
  - in `thermal_dp.py`, the defaults are η 0.45, a heat-exchanger approach of 5 K and COP clipped to 1–8.
  - No defrost and no part-load term. No accuracy claim.
- **heating_curve_optimizer** (commit 4453a90, https://github.com/bvweerd/heating_curve_optimizer):
  - `heatpump_model.cop_at` is (4.2 + 0.08·T_out − 0.11·(T_sup − 35)) × compensation × defrost factor, capped at Carnot;
  - `calibration.py` fits the coefficients from measured heat, with a ridge regression towards the defaults;
  - `mass_model.py` treats a measured-to-modelled ratio outside 0.7–1.4 as implausible.
- **when2heat** (https://github.com/oruhnau/when2heat, `input/cop/cop_parameters.csv`): COP for air-source units = 6.08 − 0.0941·ΔT + 0.000464·ΔT², times 0.85 for real-world operation. The accompanying paper (Ruhnau et al. 2019, doi:10.1038/s41597-019-0199-y) was not opened.
- **HeatpumpMonitor.org**: per-system stats and 10 s time series through the API; its 19 Altherma 3 systems are a real-world comparison group.

## 6. Gaps in the pilot's measurements, ranked

The first gap matters most for both control and verification.

1. **Heat pump electrical power, time-resolved.** Onecta gives whole kWh per 2 h, and the household-load inference is unproven. Without it, start-ups, minimum output and defrost cannot be told apart reliably, and no per-unit COP level can be fitted.
2. **Heat output (flow rate and return temperature).** Without heat there is no measured COP at all. Verifying a lower energy use then rests on electricity alone, normalised for weather. Flow and return (R4T) are readable on X10A and EKRHH (`daikin-local-readout.md`).
3. **Operating state** (space heating, hot water, defrost, compressor on). This is needed to split R1T by mode and for issue #6. Today it can only be inferred.
4. **Compressor frequency or minimum output.** This gives the threshold below which the unit cycles, which the control decision depends on.
5. **Outdoor humidity.** It drives defrost. A weather service is enough; the Onecta outdoor sensor has no humidity.
6. **Tank temperature at minute resolution.** It is a defrost and hot-water signature on ECH₂O. Onecta's update rate is limited by its 200 calls per day.
7. **Hot-water draw volume.** It is the demand side of the tank model; not measured.

## Not verified

- No Heat Pump Keymark certificate or Eurovent entry for ERLA14D2W1 was found. The data book copy is from a retailer, and the EN 14825 part-load points with Cdh = 1.0 are for the EBVH indoor unit, not for EBSX.
- Whether Daikin's Cdh = 1.0 was measured.
- The ERLA14's minimum compressor output.
- The full texts of Piechurski 2018, Dongellini & Morini 2019, Vocale 2014 and Ruhnau 2019 (abstracts or code only). Uhlmann & Bertsch 2012 (doi:10.1016/j.ijrefrig.2012.08.008): no abstract available, not used.
- The defrost signature described in section 3 is inferred from the installer guide; it has not been observed on this unit.
- How the 2025 SCOP of 3.9 was obtained: the pilot does not measure heat.
