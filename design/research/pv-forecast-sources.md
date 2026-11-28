# PV forecast sources

Question: which sources of 48-hour forecasts of PV power or irradiance could the project archive alongside the two it uses (forecast.solar's free estimate API, Open-Meteo's forecast API with `global_tilted_irradiance`), to compare them against measured production (first analysis 2027-01-31)? Can past forecast runs be retrieved, so that the comparison need not wait for months of archiving?

Provenance: a web search by a sub-agent on 2026-11-27; every page below was read on that date unless marked. No account was created, no API key used, no location sent. Labels: **read** = seen on the provider's page; **secondhand** = only in a search snippet or a third-party page; **not verified** = not found. Not reviewed by a person.

## For people

| Source | Forecasts | Horizon, step | Past runs | Access | Licence for an open archive |
|---|---|---|---|---|---|
| Open-Meteo, other models (ICON-D2, ICON-EU, ECMWF IFS 9 km, AROME) | irradiance incl. GTI | 2–15 days; 15 min (ICON-D2, AROME) or 1 h | yes, Previous Runs API from 2024 | free, no key, non-commercial | CC BY 4.0 |
| DWD MOSMIX_S | station point forecast, `Rad1h` (GHI) | 240 h, 1 h | no, about 48 h kept | free, no key | CC BY 4.0 |
| DWD ICON-D2 GRIB | `aswdir_s`, `aswdifd_s` | 48 h, 1 h files | no, current runs only | free, no key | CC BY 4.0 |
| Solcast hobbyist | PV power for 2 arrays | 14 days, 30 min | no | free account, 10 calls/day | no sharing with third parties |
| Quartz Solar Forecast (Open Climate Fix) | PV power (ML model) | 48 h | yes, by running it on past dates | MIT code, runs locally | MIT; inputs from Open-Meteo |
| Visual Crossing, Meteomatics, OpenWeather solar | irradiance / PV | 10–15 days | partly | free tiers without solar, or paid | various |
| PVGIS | no forecast | — | — | — | — |

Recommendation, in this order:

- **1 Open-Meteo with explicit `models`: ICON-D2, ECMWF IFS (and ICON-EU).** Same request as today plus one parameter, and the Previous Runs API gives each model's forecast at 1–7 days' lead back to January 2024, so the comparison can start on past months now. Against: all are turned into GTI by Open-Meteo's one transposition (isotropic sky, 20 % albedo), so differences in transposition error are invisible; and they share one provider and one failure.
- **2 DWD MOSMIX_S, nearest station, `Rad1h`.** The only free source with statistical correction against observations (MOS over ICON and IFS), independent of Open-Meteo. Against: a station point, not the roof; GHI only, so the project must transpose it; the all-stations file is about 34 MB per hourly run; nothing older than about two days can be fetched.
- **3 Solcast hobbyist (only if the principal registers and accepts the terms).** A specialist satellite-plus-NWP PV forecast, the strongest independent comparison. Against: its terms forbid sharing the data with third parties, so the archive must stay out of the repository and out of published plots unless Solcast agrees in writing.
- Quartz Solar Forecast is a cheap fourth: MIT, can be run on past dates. Against: its inputs come from Open-Meteo, so it tests a PV model, not a weather source.

## 1. Open-Meteo: models, PV variables, past runs

- Forecast API ([docs](https://open-meteo.com/en/docs)), **read**: radiation variables `shortwave_radiation`, `direct_radiation`, `diffuse_radiation`, `direct_normal_irradiance`, `global_tilted_irradiance`, `terrestrial_radiation`, each also `_instant`, hourly and 15-minutely. GTI "assumes a fixed albedo of 20% and in isotropic sky". Native 15-minute data only from DWD ICON-D2 and Météo-France AROME in central Europe; elsewhere interpolated. `forecast_days` 0–16. Models listed for central Europe: DWD ICON Seamless/Global/EU/D2 (and native-grid and RUC variants), MeteoSwiss ICON CH1/CH2, GeoSphere C-LAEF (AROME Austria "Discontinued 2026-11-04"), CHMI Aladin, ItaliaMeteo ICON 2I, Météo-France ARPEGE Europe and AROME France; default "Best match". Whether CH1/CH2, CHMI or AROME domains cover the site: **not verified**.
- DWD models ([docs](https://open-meteo.com/en/docs/dwd-api)), **read**: `dwd_icon_d2` 2 km, 2 days, every 3 h, 15-minutely; `dwd_icon_eu` 7 km, 5 days, every 3 h, hourly; `dwd_icon_global` 11 km, 7.5 days, every 6 h. On 30 November 2026 the lat-lon grids of these three "will be replaced with the native ICON grids", a break in any archive.
- ECMWF ([docs](https://open-meteo.com/en/docs/ecmwf-api)), **read**: `ecmwf_ifs` 9 km, 15 days, every 6 h, 1-hourly to 90 h; IFS 0.25° and AIFS provide "only global radiation", diffuse is modelled. Identifiers of the 0.25° and AIFS variants: **not verified**.
- Ensembles ([docs](https://open-meteo.com/en/docs/ensemble-api)), **read**: ICON-D2-EPS (20 members, 2 days), ICON-EU-EPS (40, 5 days), ECMWF IFS (51, 15 days); radiation variables listed, per-model availability **not verified**.
- Previous Runs API ([docs](https://open-meteo.com/en/docs/previous-runs-api)), **read**: endpoint `https://previous-runs-api.open-meteo.com/v1/forecast`; `<variable>_previous_day1` … `_previous_day7` is the value forecast 24–168 h before valid time; "same models as the Weather Forecast API"; most models archived "from January 2024"; solar variables incl. GTI listed. Hourly only. That `global_tilted_irradiance_previous_day1` works as a parameter name: **not verified** (no request sent).
- Historical Forecast API ([docs](https://open-meteo.com/en/docs/historical-forecast-api)), **read**: "built by stitching the first hours of each successive model run", from 2021/2022; shortest lead only, so it does not reproduce a 24–48 h forecast.
- Satellite Radiation API ([docs](https://open-meteo.com/en/docs/satellite-radiation-api)), **read**: observed, not forecast (MTG 10 min, MSG 15 min, SARAH3 30 min). A possible second "measured" reference, not a forecast source.
- Terms ([terms](https://open-meteo.com/en/terms), [pricing](https://open-meteo.com/en/pricing), [licence](https://open-meteo.com/en/licence)), **read**: free API non-commercial only, "personal home automation" named as allowed; under 10,000 calls/day, 5,000/hour, 600/minute; data CC BY 4.0, "You must include a link next to any location Open-Meteo data are displayed". Whether underlying providers (DWD, ECMWF) must be credited too: **not verified**.

## 2. DWD open data

- MOSMIX ([DWD page](https://www.dwd.de/EN/ourservices/met_application_mosmix/met_application_mosmix.html)), **read**: about 5400 points, "maximum forecasting time of +240h", hourly step; MOSMIX_S 24 runs/day, 40 parameters; MOSMIX_L 4 runs/day, 115 parameters, single-station files available; corrects "ICON (DWD) and IFS (ECMWF)"; KML format, to change with a new MOSMIX version.
- Element list ([MetElementDefinition.xml](https://opendata.dwd.de/weather/lib/MetElementDefinition.xml)), **read**: `Rad1h` "Global Irradiance" kJ/m², `SunD1`, `RRad1`. Whether `Rad1h` is in MOSMIX_S as well as L: **secondhand** (a third-party copy of DWD's table marks both).
- Retention, [MOSMIX_S listing](https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/), **read**: runs from 2026-11-25 12 to 2026-11-27 11, about 34.5 MB each.
- ICON-D2 GRIB ([run 00](https://opendata.dwd.de/weather/nwp/icon-d2/grib/00/)), **read**: `aswdir_s`, `aswdifd_s`, `asob_s` present; [aswdir_s](https://opendata.dwd.de/weather/nwp/icon-d2/grib/00/aswdir_s/) holds steps 000–048 of the current day's run only. Decoding GRIB on the native grid is real work; Open-Meteo already does it.
- Licence ([dwd.de/copyright](https://www.dwd.de/copyright)), **read**: freely accessible geodata reusable under CC BY 4.0 "unter Beigabe eines Quellenvermerks"; exact attribution wording on a separate template page, **not verified**. [opendata README](https://opendata.dwd.de/README.txt), **read**: "Access is granted without registration".
- Bright Sky ([GitHub](https://github.com/jdemaeyer/brightsky)), **read**: MIT JSON API over MOSMIX and DWD observations; whether it passes on solar radiation: **not verified**.

## 3. PV-power services

- forecast.solar (in use; [account models](https://doc.forecast.solar/account_models), [attribution](https://doc.forecast.solar/attribution), [sources](https://doc.forecast.solar/used_sources)), **read**: public tier 12 calls per rolling 60 min per IP, today and tomorrow, 1 h, no historic data; attribution link required; data licence not stated. Weather inputs named are PVGIS, "DarkSky and Wunderground"; whether current: **not verified**.
- Solcast ([hobbyist docs](https://docs.solcast.com.au/docs/section/rooftop-sites-hobbyist), [free rooftop](https://solcast.com/free-rooftop-solar-forecasting), [terms](https://solcast.com/solar-data-api/api/terms-and-conditions), [pricing](https://solcast.com/pricing)), **read**: 10 requests per UTC day, up to 2 arrays within 1 km, now to 14 days, 30 min (PT30M), past 7 days of estimated actuals; residential check; terms: "only use our data for non-commercial home use", no sharing with third parties without written permission, link back from a personal web page. Historic forecasts only on request from sales, price not stated.
- Quartz Solar Forecast ([GitHub](https://github.com/openclimatefix/open-source-quartz-solar-forecast)), **read**: "expected generation in `kw` for 0 to 48 hours for a single PV site" from GFS, ICON or ECMWF via Open-Meteo; MIT; for past dates uses historical data. GitHub API: last push 2026-09-06, last release v1.1.21 on 2025-09-01, not archived. Time step and use of tilt/azimuth: **not verified**.
- solarprognose.de: free with account and token per [evcc docs](https://docs.evcc.io/en/tariffs/solarprognose) (**secondhand**); terms **not verified**.

## 4. Others

- PVGIS ([JRC](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en)): historical and typical-year data (5.3 to 2023); no forecast found (**secondhand**, FAQ not opened).
- Visual Crossing ([editions](https://www.visualcrossing.com/weather-data-editions), [solar](https://www.visualcrossing.com/resources/documentation/weather-data/how-to-obtain-solar-radiation-data/)), **read**: free plan 15-day forecast; "Advanced solar and wind energy" (GHI, DNI, DHI, GTI) not in the free plan; whether basic `solarradiation` is: **not verified**; raw-data redistribution not allowed.
- Meteomatics free Basic: 500 queries/day, 15 basic parameters, non-commercial (**secondhand**, snippets of meteomatics.com; pages 404); whether radiation is among them: **not verified**.
- OpenWeather Solar Panel and Energy Prediction ([v1 docs](https://openweathermap.org/api/solar-panels-and-energy-prediction)), **read**: PV output and GHI/DNI/DHI, 15 days, 1 h or 15 min, "separate subscription only"; price **not verified**.

## Open points

- Send one Previous Runs request with GTI and `models=dwd_icon_d2` to confirm parameter names and coverage (needs the site's coordinates, so the principal's call).
- The ICON grid change on 2026-11-30 falls in the archive period: record model identifiers with each sample.
- Lead time: ICON-D2 runs every 3 h to +48 h, so "48 h ahead" from the latest run is at most 45–48 h. Decide which lead times the analysis compares.
- Solcast: whether a local, unpublished archive is acceptable under its terms; ask before registering.
- DWD attribution wording (template page) and whether Open-Meteo users must credit DWD/ECMWF.
