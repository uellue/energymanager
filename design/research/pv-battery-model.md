# PV and battery model for scheduling

Question: which PV production, forecast-correction and battery models let the optimizer reproduce closely what the pilot's PV string and battery do over a 48 h horizon at hourly resolution, how to calibrate them on measured data, and can the module temperature be inferred from the string voltage (issue #4)?

Provenance: a source search by a sub-agent on 2026-11-22. pvlib: the documentation and the source of the 0.16.1 wheel from PyPI. Datasheets: PDFs downloaded and read as text. Papers: abstracts only (via Semantic Scholar), DOIs checked against Crossref. Not reviewed by a person.

## Findings

### PV production model (pvlib 0.16.1)

- Transposition: `pvlib.irradiance.get_total_irradiance(surface_tilt, surface_azimuth, solar_zenith, solar_azimuth, dni, ghi, dhi, …, model='isotropic')`; other sky models include haydavies and perez ([docs](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.get_total_irradiance.html)).
- Open-Meteo already supplies global tilted irradiance for a tilt and azimuth (0° south, −90° east), by default averaged over the preceding hour; 15-minute data exist for Central Europe; `best_match` for Germany includes ICON-EU and ICON-D2 ([docs](https://open-meteo.com/en/docs)). Compare it with measured power averaged over the hour ending at the time stamp.
- Module temperature models in `pvlib.temperature`: `sapm_cell`, `pvsyst_cell` (default `u_c=29.0`, `u_v=0.0`), `faiman(poa_global, temp_air, wind_speed=1.0, u0=25.0, u1=6.84)`, `fuentes`, `noct_sam` and others ([docs](https://pvlib-python.readthedocs.io/en/stable/reference/pv_modeling/temperature.html)). Faiman's defaults come from 7 open-rack modules in the Negev (Faiman 2008, doi:10.1002/pip.813, cited by the [docs](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.temperature.faiman.html)). A roof mount is cooled differently (no source checked), so fit `u0` and `u1` to the pilot (see issue #4 below).
- DC: `pvlib.pvsystem.pvwatts_dc(effective_irradiance, temp_cell, pdc0, gamma_pdc, temp_ref=25.0, k=None, cap_adjustment=False)`, P = G/1000 · P0 · (1 + γ(T − 25)) ([docs](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.pvwatts_dc.html)). With the datasheet's γ = −0.29 %/K, a 20 K error in module temperature changes the power by about 6 %.
- Calibration: fitting P0 (in effect a performance ratio) together with `u0` and `u1` to measured DC power keeps the physics, so the model extrapolates to other seasons; a single performance ratio mixes temperature losses with irradiance errors.
- Accuracy reached in the sources: in the PVPMC blind intercomparison (measured weather given, six systems), the median mean bias was 0.6 % for annual irradiation and −3.3 % for annual energy; "human errors, modeling skills, and derates" still caused significant errors (Theristis et al. 2023, Prog Photovolt 31:1144, doi:10.1002/pip.3729, abstract). No source opened gives hourly errors.

### Forecast correction

- forecast.solar's own correction (`?actual=<kWh>`, Personal account or higher) scales "the actual day" only, not the following days ([docs](https://doc.forecast.solar/actual)). It does not help with tomorrow.
- Yang & van der Meer 2021, Renew Sustain Energy Rev, doi:10.1016/j.rser.2021.110735 (abstract): post-processing methods grouped into ten "thinking tools", such as regression, filtering, analog ensemble and probabilistic regression.
- Mayer et al. 2026, Solar Energy 307:114361, doi:10.1016/j.solener.2026.114361 (abstract, [arXiv](https://arxiv.org/abs/2508.15508)): on seven plants, every statistical post-processing beat the raw ensemble; nonlinear quantile regression was best.
- Lorenz et al. 2009, IEEE JSTARS, doi:10.1109/JSTARS.2009.2020300, "Irradiance Forecasting for the Power Prediction of Grid-Connected Photovoltaic Systems" (Crossref): abstract not accessible, content not reported.
- For the pilot: the archive keeps every forecast as issued, so a correction can be fitted per lead time on archived forecasts against measured production, first as a regression on clear-sky index and sun elevation, later as quantile regression.

### Module temperature from string voltage (issue #4)

- Module datasheet (Solarwatt Panel vision M 5.0, [Rev 16, 14.10.2025](https://www.solarwatt.de/canto/download/lq1eacp49d00te8084k5rij139); [Rev 11 EN](https://www.solarwatt.com/canto/download/abev9m2npt2cvbrhcng70mdv3m)):
  - coefficients: Pmax −0.29 %/K, V_oc −0.25 %/K, I_sc +0.05 %/K;
  - NMOT 42 °C, 3 bypass diodes, 108 half-cut TOPCon cells;
  - 445 Wp class: V_mp 33.0 V, I_mp 13.5 A, V_oc 39.6 V, I_sc 14.0 A; I_sc 15.4 A at the bifacial nameplate irradiance (1000 + 0.8 · 135 W/m²).
  - Neither revision lists a 440 Wp column or a V_mp temperature coefficient.
- Physics, as in pvlib's SAPM (`pvsystem.py`, lines 2492–2521): V_mp = V_mp0 + C2·N_s·δ·ln(Ee) + C3·N_s·(δ·ln(Ee))² + β_Vmp·(T − 25), with N_s cells in series and δ = n·k·T/q. The voltage depends on irradiance (logarithmically) and on temperature (linearly), so the irradiance must be estimated from the current first.
- Without SAPM coefficients: fit a single-diode model to the datasheet values with `pvlib.ivtools.sdm.fit_desoto(v_mp, i_mp, v_oc, i_sc, alpha_sc, beta_voc, cells_in_series, …)`, which needs no extra dependency (`fit_cec_sam` needs NREL-PySAM). Then compute V_mp(G, T) with `calcparams_desoto` and `max_power_point`, and invert it for T.
- Accuracy limits (reasoning, not from a source):
  - with β_Vmp around −0.3 %/K, a 1 % voltage error is about 3 K;
  - the string voltage includes cable losses and MPPT dither, and the module tolerances (V_oc ±3 %) make the absolute offset uncertain, so calibrate the offset at dawn, when the modules are near air temperature;
  - an active bypass diode drops a third of a module's voltage (about 11 V of about 594 V) and reads as a jump of about 6 K;
  - at low irradiance the logarithmic term dominates and the estimate degrades.
- Inverter limit: the RCT Power Storage DC 10.0 accepts at most 14 A DC per MPP tracker (28 A with the two in parallel), MPP range 380–800 V ([datasheet 2023V1EN](https://www.tritec-energy.com/wp-content/uploads/2023/10/RCT-Power-Storage-DC-8.0-10.0_Data_Web23V1EN.pdf)). I_mp is 13.5 A at STC and more with rear light, so in full sun the inverter may leave the MPP to limit current, biasing power and the voltage-based temperature. Not checked in data.

### Battery model

- Datasheets:
  - RCT Power Battery: LiFePO4, 1.9 kWh units (2 to 6 per stack), usable capacity 90 % depth of discharge, 25 A charge and discharge, standby below 5 W, no efficiency given ([2025V1EN](https://solarproof.com.au/datasheets/battery_datasheet_RCT-Power-Battery-3.8-11.5-2025V1EN.pdf)). Nominal 154 V per 2 units ÷ 3.84 kWh gives 25 Ah: the "about 25 Ah" read from the inverter is the unit capacity, not the installed energy.
  - PS 10.0 inverter: average efficiencies PV2Bat 98.00 %, AC2Bat 97.44 %, Bat2AC 97.48 %, PV2AC 97.89 %, with a Power Battery 11.5 (one footnote names the Storage 6.0, apparently a slip); 6.0 W standby with a discharged battery (datasheet above).
- Independent test: HTW Berlin and aquu, Stromspeicher-Inspektion 2026 ([PDF](https://solar.htw-berlin.de/wp-content/uploads/HTW-aquu-Stromspeicher-Inspektion-2026.pdf)), system F1 = PS DC 10.0 with Power Battery 11.5, software 2.3.5651. The pilot runs 2.3.5685.
  - SPI (10 kW) 96.4 %, conversion losses 2.8 %, standby losses 0.2 %;
  - the highest BAT2AC efficiency of all systems, 97.8 %; charging efficiencies "über 97,4 %";
  - the largest steady-state control deviation of the systems, 16 W.
- PV → battery → AC is then about 0.98 × (battery's own efficiency) × 0.975. The HTW report gives 87.9–97.1 % for the batteries it tested; the RCT figure was not read.
- For scheduling, an energy-bucket model fits the data:
  - E(t+1) = E(t) + η_c·P_c·Δt − P_d·Δt/η_d − standby;
  - limits from 25 A × battery voltage, the inverter's limits, and the 7 % and 97 % marks seen in the pilot (requirements 2.3).
  - None of the sources opened reports how accurate such a model is in operation; its parameters can be fitted to the pilot's state-of-charge record.
- Calibration cycles: interval 30 days, up to 3 days early (early threshold: state of charge 0.80), charge power 4000 W (inverter objects, rct-onecta-data.md). The scheduler can take the window from `bat_next_calib_date` as a forced event: charge to full, then the house runs from the battery down to 0 % while all PV goes to the grid (requirements 2.3). Leave these hours out of fitting.

## Gaps in the pilot's measurements and settings (ranked)

1. Installed battery energy: answered by the principal (2026-11-22), one battery of 5.7 kWh nominal, "usable sth like 5-ish". That is three 1.9 kWh units in one stack; at 90 % depth of discharge about 5.1 kWh usable. The fit to the state-of-charge record can check it.
2. No irradiance or module temperature measured on site. Temperature and transposition can only be fitted indirectly, through issue #4.
3. Inverter current limit and possible clipping: the whole roof is on one tracker, the second is unused (principal, 2026-11-22), so the limit is 14 A against I_mp of 13.5 A at STC, more with rear light. Check DC current (power ÷ voltage of generator A) on sunny days in spring.
4. Calibration is not yet marked in the record in a known way: the collector records `power_mng.state` and the battery status objects every minute since 2026-11-22, but which values mean "calibrating" is learned only at the next calibration (around 2026-12-18 to 21). (Corrected by the orchestrator: the note first said `power_mng.state` was not recorded.)
5. Module data for the 440 Wp class and a V_mp temperature coefficient are missing from the datasheets found.
6. No local wind speed or air temperature for the temperature model; Open-Meteo's are forecasts.
7. Roof tilt, azimuth and horizon shading are only in `.env`; not checked against measured clear-day curves.

## Not verified

- Lorenz et al. 2009: method and figures (abstract not accessible).
- Hourly accuracy of PV models: an [NREL report](https://www.nrel.gov/docs/fy14osti/61497.pdf) is said to give hourly errors below 7 %; the download failed.
- Bifacial rear gain on a roof (`pvlib.bifacial` targets racked rows).
- The RCT battery's own efficiency (HTW report, figure 12, not readable as text).
