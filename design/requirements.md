# Demand and requirements: energymanager

Author: Claude (agent), from the interview. Principal: Dieter Weber. Date: 2026-11-21. Interviewed: the principal in person.
Markers per item: [answered] said or confirmed by the principal; [record] taken from <source>, not yet confirmed; [assumed] proposed by the author; [unknown] listed in 2.2 with what would resolve it; [deferred] listed under open questions with stage and owner.

## 1. Demand

### 1.1 Problem and context

- [answered] Optimize the operation of a heat pump in particular, but also other electricity use, in a home with solar power, a small home battery and charging of some electric vehicles.
- [answered] Heat pump operation is the tricky part:
  - COP depends on the temperature difference between inside and outside.
  - The home temperature is controlled by the underfloor heating water temperature (no flow regulation), to operate at the lowest temperature possible.
  - The heat pump cycles at too low a power setting, which is less efficient.
- [answered] The house has a high heat capacity that the principal would like to use as a buffer.
- [answered] Constraints that must hold:
  - no excessive temperatures in the underfloor heating;
  - no thermal shocks (stresses), so as not to damage the floor;
  - temperatures in the home always comfortable;
  - warm water ready;
  - legionella suppressed (sufficient warm water temperature).
- Proposed solution, one option (not yet the need): write a realistic cost function from all known factors and minimize it numerically with automatic differentiation and optimizers; optimistix (based on JAX) "worked well so far". [answered]
- [answered] Should work with Home Assistant "if that makes sense", as what most people use for open-source home automation. Having one dashboard in Home Assistant instead of many vendors' apps "would be a nice outcome as well".
- [answered] Objective: model appropriate loss functions rather than only hard limits. "Damaging the floor should be prohibitively expensive, but a bit of strain on the floor is OK." Hard limits that prevent excursions are best set in the heat pump itself (see 2.11).
- [answered] Not restricted to one make and model of heat pump; the principal's Daikin Altherma is the pilot.
- [answered] Proposed design direction, if the numerical core is developed here: a generic core of inputs, a state, a set of differential equations acting on it, and a solver ("I think").
- [answered] The principal's physical picture of the house (2026-11-22), as a starting point for the model structure: thermal masses (1) the floor slab, (2) inner walls, furniture and the like, coupled to the room only through air and radiation, (3) the outer walls, masonry with significant mass of their own, coupled to the outside. Heat sources: the heat pump, appliances, sun on the outer walls' surface, sun through the windows. How this maps onto published models and what makes it identifiable: `design/research/building-floor-model.md`.
- [answered] Keep EMHASS as relevant prior art; decide later, when the specifications are derived, which path makes most sense (see Open questions).

### 1.2 Current solutions

- [answered] A hand-optimized heating curve and schedule, set in the heat pump's own controller (Daikin Altherma, currently cloud-connected); it does not consider the actual weather forecast.
- [answered] No Home Assistant installation yet.
- [answered] Wanted: an existing optimizer that is numerical and model-based, not rules-based.
- Prior art, surveyed 2026-11-21 by a sub-agent from each project's repository and docs. The quotes are not yet re-checked against the sources (hand-over check 3).
  - **EMHASS** (github.com/davidusb-geek/emhass, MIT, v0.18.11, Home Assistant add-on). The closest match.
    - Method: LP/MILP (cvxpy, HiGHS), plus a dynamic-programming solver for the COP coupling.
    - Models: slab thermal mass for underfloor heating, Carnot COP from supply and outdoor temperature, heating curve, comfort band, domestic hot water tanks, minimum on/off times and startup penalties.
    - Lacks: a limit on the floor's rate of temperature change, a part-load COP, separate floor and room states, and a gradient-based nonlinear solve. Legionella is a cookbook recipe; the docs say it is "NOT handled" automatically.
  - **heating_curve_optimizer** (github.com/bvweerd/heating_curve_optimizer, GPL-3.0, v1.2.1, Home Assistant integration).
    - Method: dynamic programming over heating-curve offsets (±4 °C) for 24 h, with a 1R1C building model and COP from outdoor and supply temperature.
    - Lacks: floor limits, domestic hot water, cycling, and battery or EV co-optimisation. It outputs sensors only and is labelled experimental.
  - **evcc** (rules, SG-Ready boost) and **OpenEMS** (genetic algorithm; heat pump not in its scheduler) have no thermal or COP model. **EOS** (Akkudoktor) has a linear COP class that is not used. **Predbat** only predicts heating and is not OSI-licensed.
  - Generic nonlinear MPC libraries, with no Home Assistant integration and no ready-made house model: do-mpc (CasADi), AgentLib-MPC (RWTH-EBC), NeuroMANCER (PyTorch, differentiable). BOPTEST is a benchmark test bed.
  - Not found: an open-source, Home Assistant-integrated, gradient-based (JAX-style) optimizer covering PV, battery, EV, heat pump COP and part-load, floor dynamics and domestic hot water together.

### 1.3 Benefits

- [answered] Heating SCOP in 2025 was 3.9; the principal thinks it can be pushed "closer to 4.5".
- [answered] Electricity use in 2025: 5538 kWh in total, "of which 2960 kWh came from solar" (self-consumed), so the grid import was about 2578 kWh. About 5126 kWh of surplus was fed into the grid.
- [answered] Goals: reduce grid consumption and use more of the house's own solar production.
- [answered] The biggest gain is expected in February, March, April and November, by shifting consumption towards the middle of the day and towards sunny days.
- [answered] Pilot tariff: a fixed-rate contract at present (about 30 ct/kWh), plus own solar production; feed-in compensation 8 ct/kWh. The target users have a variable electricity price (1.4).
- [answered] Requirement: obtain the tariff and feed-in figures "in a convenient way for each site this will run"; they vary per setup.

### 1.4 Users

- [answered] Pilot: the principal's home.
- [answered] Target: all Home Assistant users with a heat pump and a variable electricity price.

## 2. Requirements

### 2.1 Use scenarios

- [answered] **S1 Collect and view.** The person at a site installs Home Assistant on a Linux machine in the home network and connects:
  - the heat pump, the inverter and battery, and extra sensors;
  - the solar forecast and a weather forecast.
  They see all of it on one dashboard, including solar production against the solar forecast and against the weather forecast. Pilot sources: Daikin Onecta, RCT, forecast.solar, perhaps a Zigbee thermometer. "Collecting data and a nice dashboard to view it sounds like the correct start." Development and testing run on the principal's development machine for now; it moves to the mini PC later. Examples E1, E2, E5.
- [answered] **S2 Simulate and compare.** From recorded data and the forecasts, the model predicts the next 48 h: room temperature, floor supply temperature, heat pump energy, battery and grid import. The prediction is then compared with what was measured. Nothing is written to devices. Example E3.
- [answered] **S3 Plan (advice only).** Hourly, the optimizer computes a 48 h plan that minimises the cost and shows it with the expected saving. Nothing is written to devices.
  - The cost is grid import at the site's tariff, minus feed-in, plus loss terms for comfort, floor strain and hot water.
  - The optimizer is tested on recorded data and recorded forecasts, kept as test cases (scenarios), and its outcomes are graded. No fixed periods.
  - No set start month: a "running start" when ready.
  Examples E3, E4.
- [deferred] **S4 Control.** The plan is written to the devices once the person at the site has authorised it and been informed of the risks, with a fallback and an alert. Reads are allowed from the start, also from the development machine. See Open questions.
  - [answered] Target start in the pilot: active control of the heat pump from the turn of the year 2026/2027, so that the controlled period matches the heat pump's and the inverter's yearly statistics (principal, 2026-11-22).
  - [answered] What is to be verified: lower energy consumption over long periods compared with a reference period. The model has to decide when to run the heat pump and at which setpoint, and for that it must reproduce closely enough what actually happens in the house; it need not be more exact than that (principal, 2026-11-22).
  - [answered] The approach is model- and optimizer-based, not simple heuristics, as a goal in itself: "because I want to", to see whether this approach works in the real world now that the tools exist to build it easily (principal, 2026-11-22). [unknown] How the comparison is normalised for weather, and which period is the reference. Candidates in `design/research/building-floor-model.md`, among them a fitted model that runs the old heating curve on the actual weather; the approaches are to be tried and compared on data before one is chosen (principal, 2026-11-22).
  - [answered] A baseline from today's operation (principal, 2026-11-22): the house is comfortable now, and its electricity use is known. The unit's screen shows the heat produced for heating per period (roughly year, month, week, day). Correlated with outdoor air temperature, this gives the heat the house needs to stay comfortable, as a fairly simple curve over outdoor temperature (in the field's terms an energy signature), which also accounts for weather differences.
  - [answered] Today's operation, the baseline the optimizer must beat (principal, 2026-11-23): a first iteration of using the house as a heat buffer. Hot water is heated almost always during the day, when it is warmer and solar power is available. The heating's leaving water follows a 2-point weather-dependent curve with a daily schedule of shifts, the same every day: −2 °C from 00:00, 0 °C from 10:00, +3 °C from 11:00, +1 °C from 15:00, 0 °C from 18:00, −1 °C from 22:00. The shifts lower the leaving water at night, when it is cold, and raise it in the day, when it is warmer and the sun shines; the curve alone does the opposite, so the two roughly cancel. The curve's two points: 37 °C leaving water at −6 °C outdoors and 25 °C at +10 °C, flat beyond both. Hot water follows its own daily schedule, the same every day: 45 °C from 00:00, 54 °C from 11:50, 47 °C from 15:00, 45 °C from 20:00. With the heat-pump on hysteresis of 8 °C, the tank reheats at or below 46 °C in the 54 °C window and at or below 37 °C at night.
  - [answered] Improvement counts as verified when the house is still comfortable, electricity use is lower, and the measured seasonal COP approaches the theoretical one. The theoretical seasonal COP is the best the unit can reach in this house: the datasheet's characteristic curves (COP at which outdoor temperature, supply temperature and load) applied to the house's actual heat demand and weather. It is not the label SCOP, which is rated under standard conditions. The gap between measured and theoretical is the measure of how well the control does (principal, 2026-11-22).
  - [unknown] Whether the screen separates heating from hot water, and how the unit measures the heat it shows. The data book found (EEDEN23, see `design/research/heat-pump-model.md`) gives full-load points with defrosting included, a few part-load points and maximum capacity, but no COP grid over part load and no minimum output; those have to come from measurements or another Daikin document.
### 2.2 Demand uncertainties

- [unknown] The legionella margin with copper piping, a hygienic storage tank, a 38 °C minimum and a future circulation. Would be resolved by research results on legionella growth in copper piping and hygienic storage tanks (the study the principal remembers, or others). The official rules are not the basis for the pilot (2.11). A first literature search is in `design/research/legionella.md` (2026-11-21). It finds copper's effect temporary or inconsistent, low risk for small stored volumes, and no study of coil-type tanks; the principal has not yet decided what follows from it.
- [answered] Strong hypothesis: comfort with underfloor heating is learned by collecting user reports ("too warm", "too chilly") alongside the measurements. This is how the principal dialled in the heating curve and the flow rate per room, and "it worked well".
- [answered] The floor's rate-of-change limit for the pilot is set at 10 °C in 2 h (2.11). Other sites need their own value; how they obtain it is open.
- [answered] A wood stove with a water jacket is planned in the pilot. It would be a second heat source for the storage tank, which the model then has to account for. [deferred] Measured by a sensor, later, "if possible without any routine human interaction"; "we get there when we get there".
- [answered] Which sources of information exist and which can be used "is still to be settled from iterating on requirements and specs". One candidate is a Zigbee thermometer the principal can set up.
- [answered] Zigbee coordinator: the principal ordered a Home Assistant Connect ZBT-2 (USB) on 2026-11-22, for the room thermometer. It goes on the automation PC, which needs no usbipd. Research: `design/research/zigbee-coordinator.md`.
- [answered] The forecast.solar estimate is "not very accurate". [unknown] How large the error is, and whether the optimizer must correct it with measured production.
### 2.3 Interfaces with existing systems

- [answered] Home Assistant, using its vocabulary (entities, devices, integrations) for the records.
- [answered] Pilot heat pump: Daikin Altherma, currently controlled through the Daikin cloud; the principal thinks a Home Assistant integration exists.
- [answered] Pilot unit, from a screenshot of the Daikin Onecta app (2026-11-21):
  - indoor unit EBSXB16P50DF, outdoor unit ERLA14D2W1, user interface version 7.11.0;
  - WLAN gateway BRP069A78, connected to the home network.
  This is the WLAN cartridge that the Onecta cloud integration uses. Which local options also fit this unit is not checked yet.
- [answered] PV inverter and battery: RCT. Read locally on 2026-11-21 over TCP port 8899 with `rctclient` 0.0.6 (read-only commands):
  - device name "PS 10.0 S2TX", control software 2.3.5685, grid code DE_ARN4105;
  - battery capacity about 25 Ah;
  - live values readable without a cloud: state of charge (returned as a fraction although labelled %), solar generator power, household load.
  - [answered] The battery occasionally runs a calibration, during which it behaves differently from normal operation; one ran on 2026-11-21 (principal). Seen in the record that afternoon: state of charge 99.9 % with the battery about idle while the house drew 1.26 kW from the grid (14:47 UTC). Analyses and the model must recognise such phases and leave them out of normal behaviour. Checked 2026-11-21 from the RCT integration's code and the recorded history, without new reads from the inverter:
    - The integration already records `sensor.battery_at_rct_power_storage_battery_status` (from `battery.bat_status`, a bit field) and `…_next_battery_calibration_date` (from `power_mng.bat_next_calib_date`).
    - It shows "calibrating" only when exactly the charging and discharging bits are set; other combinations show as "other".
    - On 2026-11-21 it showed "charging" from 12:17 to 14:52 UTC, never "calibrating" or "other". The next calibration date read 2026-11-24 all day.
    - So the record does not mark calibration. [answered] The 12:17–14:52 UTC charging phase was the calibration (principal, 2026-11-22). How to recognise one: the battery charges beyond the usual high mark of 97 %; it then runs all household consumption from the battery and feeds all solar production to the grid until 0 %, charges to the usual low mark of 7 %, and continues normally.
    - The inverter also has the calibration interval (`power_mng.bat_calib_reqularity`) and charge power (`power_mng.calib_charge_power`) as readable objects; the integration does not expose them.
- [answered] Electric vehicles: an electric scooter and an Ape (three-wheeled electric vehicle, 45 km/h). No wallbox; charged from a wall socket with a timer at about 800 W.
- [answered] First stage: no writes to devices; simulations instead (see 2.11). The model and its simulation are the stand-in for the real house.
  - [answered] One exception (principal, 2026-11-22): reading the inverter's own logs (`logger.*` objects) needs a WRITE frame carrying a timestamp, which `rctclient`'s command line sends as a query (RCT does not document the protocol). These query frames are allowed, for `logger.*` objects only; no other write to any device. Background: `design/research/rct-onecta-data.md`.
- [answered] Heat pump power: the principal knows the unit collects this and would rather read it from the unit than add a meter. They heard of a USB device that goes into the installer data port. Research of 2026-11-21 (`design/research/daikin-local-readout.md`):
  - The unit is a Daikin Altherma 3 R ECH₂O.
  - The installer USB cable (EKPCCAB4) only updates software.
  - ESPAltherma on the X10A port reads inverter current, compressor frequency, flow and return temperature, but power only as an estimate.
  - Daikin's EKRHH Home Hub offers power consumption over Modbus, but it is not stated whether that value is measured or estimated.
  - [unknown] Which route to take; this needs a look at the unit's PCB.
  - [answered] The X10A readout (ESPAltherma) is an option before the turn of the year; a separate electricity meter for the heat pump is not (principal, 2026-11-22). The principal will look at the unit's panel.
  - [answered] First approach, before any hardware (principal, 2026-11-21): infer the heat pump's power from the household load the inverter already measures. The heat pump is practically the only always-on load with a significant draw. It cycles characteristically at part load, draws within a specific power band, and heats water in a characteristic ramp; its power depends on outdoor and tank temperature. Basic success control: the daily totals from Onecta, and observing during the day whether it cycles. To be tried once a few days of data exist (S2). A separate meter or the PCB routes above stay the fallback.
  - [answered] The heat pump cycles for two reasons: running below the lowest power it can deliver continuously, and defrosting the outdoor heat exchanger (below roughly 3 °C outdoors). Checking whether cycling that costs energy is avoided must tell the two apart, e.g. from power draw, outdoor and water temperature, and plots should mark periods of low-load cycling and of defrosting (principal, 2026-11-22, issue uellue-bot/energymanager#6).
  - [answered] The leaving-water temperature (Onecta's "Austrittswasser") is the floor supply only while the unit heats the rooms. While it heats the hot-water tank, the same sensor shows the tank coil's inlet temperature (principal, 2026-11-21). Analyses and the model must split the series by operating mode and must not read tank-heating phases as floor supply.
  - [assumed] The outdoor unit is three-phase (3N~ 400 V, design/research/daikin-local-readout.md), and the inverter reports household load per phase. A balanced draw across all three phases may separate the compressor from mostly single-phase household loads.
- [answered] Alerts are a secondary feature: "I'd first like to get the math and integration working".
- [answered] Past statistics: "hopefully" readable from the RCT app, or collected by the project itself. [answered] The RCT protocol also has time-series objects for logged data; trying them belongs to S1.
- [answered] Forecasts as issued: the project's own container fetches the solar and weather forecasts and keeps every issue with its timestamp (E6), independent of Home Assistant.
- [answered] Data store and test-case format: no preference ("whatever works"), adjusted from results and tests, in particular the user experience.
- [answered] Solar forecast: one roof plane. forecast.solar estimate API ("not very accurate"). It returns watts per hour for today and tomorrow as JSON; the free tier allows 12 calls per hour (seen in the response). The location parameters belong in local configuration, not in the repository.
- Integration options for Daikin Altherma, surveyed 2026-11-21 by a sub-agent from the primary sources; items marked (unverified) could not be confirmed. Which ones apply depends on the unit's generation and adapter (open question 18).
  - **Daikin Onecta** (github.com/jwillemsen/daikin_onecta, HACS, GPL-3.0). Cloud, no extra hardware; Altherma 3 needs a WLAN cartridge.
    - Reads: room, outdoor, leaving-water and tank temperatures, and heating energy per day.
    - Writes: leaving-water offset, DHW setpoint, powerful mode, on/off.
    - Lacks: return-water temperature, compressor frequency and live power.
    - Limit: 200 calls per day for private developers, writes included.
  - **Local options**, depending on the generation:
    - Altherma 4: built-in Modbus TCP (github.com/joklee/ha_daikin_altherma4_modbus, GPL-3.0). Reads and writes everything needed, including power.
    - Altherma 3: EKRHH Home Hub with Modbus (github.com/gerione/daikin-ha-ekrhh-modbus, MIT; register list unverified), or the Intesis Modbus RTU gateway (commercial; unverified).
    - Altherma 2 (version CA and newer) and Altherma 3: P1P2MQTT bus bridge (CC BY-NC-ND 4.0, non-commercial; writes the leaving-water and DHW setpoints).
    - Older LAN adapter BRP069A61/A62: daikin_altherma integration (MIT, dormant since 2024-10).
  - **ESPAltherma** (ESP32 on the X10A port, MIT). Reads many internal values every 30 s; cannot change setpoints, only on/off and SG-Ready through relays.
  - **SG-Ready contacts**: four coarse modes only. They are the common denominator across heat pump brands; on Altherma 3 they need the EKRELSG relay kit (primary source unverified).
- Home Assistant entity types that fit: `climate`, `water_heater`, `number`, and `sensor` with the device classes temperature, power and energy.
### 2.4 Operating conditions

- [answered] Pilot: a mini PC, ready to be set up for this, running Linux, in the home network.
- [answered] Prototyping runs on the development machine (Windows with WSL2) first.
- [answered] Wish for the mini PC: stock Debian, with Home Assistant in a Docker container "if that makes any sense". Per the Home Assistant docs, the Container installation has no access to add-ons, which conflicts with 2.8; see Open questions.
- [answered] Resolution: weather forecasts every 30 min to 1 h "sounds more reasonable". [answered] Measurements are recorded at the rate each source delivers and kept indefinitely; the model downsamples. Solar, electricity and the heat pump "we can sample much more tightly": 1 min or less for electricity. Reason: the compressor's short cycles last minutes.
- [answered] Storage, for later refinement ("Not now, just keeping note"; principal, 2026-11-21): the data must not overflow the site's storage; it uses a format efficient in size and in speed of reading and processing; and it keeps a reasonable density over reasonable time frames, e.g. lower-density aggregates for long lookback. For the pilot, purging stays off and the database's growth is measured after a week ("Large is relative these days").
- [answered] The project runs as its own container next to Home Assistant (Docker Compose), talking to Home Assistant over its API. An add-on wrapper follows later, for P2 users on Home Assistant OS.
- [answered] Docker Engine from Docker's Debian repository, inside WSL (Debian 13) for prototyping, and the same on the mini PC.
- [answered] The pilot runs on the automation PC (Debian 13) since 2026-11-22.
- [answered] Access from the phone, at home and on the road, without browser warnings and without credentials crossing the home network unencrypted (principal, 2026-11-22). Remote access through a VPN, not an open port. HTTPS for now from an own certificate authority; Tailscale is the simpler fallback. Options and reasons: `design/research/remote-access-https.md`.
### 2.5 Availability and reliability
- [answered] Requirement: high error tolerance, or a safe fallback and an alert. The specific fallback behaviour is not fixed yet ("I would not fix the specific behavior yet").
- [answered] If an automatic fallback to the unit's current independent operation is not possible, the project can coach the user to set the correct fallback in the unit's programming screen. [deferred] The details wait for the heat pump's handbook, which the principal will provide.
- [answered] A missing source shows as a gap and raises an alert (E2): "let's roll with that and see how it will work in practice".

### 2.6 Performance

- [answered] Planning horizon 48 h; "48 h is also the maximum where we can reasonably use the house as a buffer".
- [answered] Re-planned hourly. This fits Daikin Onecta's 200 calls per day.
### 2.7 Testing, installation and service

- [answered] The model is trusted once its predictions match the measurements: compare predicted and measured room temperature, floor supply temperature and heat pump energy over past data. No fixed period ("I would not set a specific time, but the idea sounds about right"); the error limits are to be set once data exists.
- [answered] How detailed the model must be (principal, 2026-11-22): the plan found with the model may cost at most 5 % more than the true optimum of the total cost (price, comfort, no damage, …). A thermal mass or heat path enters the model only if, without it, the model differs so much from the house that the plan misses this target. Heat capacities and transfer coefficients of parts of the house are not goals of their own; paths that behave alike (conduction, radiation and convection along several routes) stay lumped. The 5 % are counted over a heating season (principal, 2026-11-22). [unknown] How it is checked, since the true optimum is unknown. One option: fit a richer model to the same data, plan with the lean model, and compare the plan's cost in the richer model with the richer model's own optimum.
- [answered] The room is a node of its own: it is what a person feels and what a room thermometer will measure, and it connects the thermal masses. Its temperature includes radiation, like the equilibrium temperature of a probe in the room (operative temperature).
- [answered] No sensors in the floor or walls: their cost would eat the savings. A remotely readable room thermometer is justified on its own, also to watch the house while away.

### 2.8 Portability and distribution

- [answered] Open source on GitHub. The pilot runs as a container next to Home Assistant Container; a Home Assistant add-on comes later, for P2.

### 2.9 Jurisdictions

- [answered] Licence: MIT, like EMHASS. Avoid dependencies whose licences restrict use or redistribution (e.g. P1P2MQTT, CC BY-NC-ND).
- [answered] Energy and temperature data and the site's location are personal data of the household. They stay on the site's own machine, and the repository holds no site-specific location or credentials.
### 2.10 Lifetime and decommissioning

- [answered] Open-ended: "probably until I'm dead or the system is superseded with something better".
- [answered] The data stays with the site's Home Assistant when the project is retired.
### 2.11 Safety and risks

- [answered] Hard limits that prevent excursions are set in the heat pump's own controller, outside the optimizer; the optimizer weighs strain through loss functions.
- [answered] Floor: no excessive underfloor heating temperatures and no thermal shocks.
  - [answered] Maximum floor supply temperature in the pilot: 37 °C, raised from 35 °C to keep the house warm enough on cold days; no problems with the floor so far (principal, 2026-11-23). A fixed maximum in the unit's settings caps the leaving water, so shifts cannot exceed it: [9-00] heating maximum 37 °C; the minimum [9-01] is 25 °C, so shifts below the curve's +10 °C point are clipped as well. The minimum was set while dialling in the unit: with the leaving water below 25 °C the compressor would not run and the backup heater took over (principal, 2026-11-23; cause not known). The optimizer must keep leaving-water setpoints at or above it. Further field settings read from the display on 2026-11-23: overshoot [9-04] 2 °C, modulation [8-05] off, leaving-water control [C-07]=0, no increase around 0 °C [D-03]=0, space heating interrupted during defrost [F-08]=0, heating only below 18 °C outdoors [4-02]. All settings, transcribed: `unit-field-settings-2026-11-23.tsv` in the host's data folder.
  - [answered] Maximum rate of change in the pilot: 10 °C in 2 h. It "is known to not cause problems, but should not be exceeded". The principal's reasons:
    - In their experience, floor installers' limits are very conservative, because installers don't pay the heating bills but want to avoid all liability; a well-installed floor can take more.
    - This floor has expansion joints in the screed, glass-fibre mesh reinforcement and a well-installed hardwood floor.
  - [answered] The gradient is needed. The lowest sustained water temperature that doesn't cause cycling is about 30 °C, so the supply must cross relatively quickly from 19 °C (resting temperature) to 30 °C.
- [answered] Domestic hot water: temperature high enough to suppress legionella.
  - [answered] Pilot settings: day target 54 °C, the highest the Altherma reaches without resistive heating. The indicated temperature may drop to 38 °C in the hours without solar power before it heats up again.
  - [answered] The tank is a "Hygienespeicher" (hygienic storage tank). Once a hot-water circulation is installed, operation gets close to the limits.
  - [answered] Copper piping. The principal remembers reading research that copper inhibits legionella well, so a lower temperature is OK and "we are within limits — but just so". [unknown] The source is not identified or checked; see 2.2.
  - [answered] The German drinking-water rules don't distinguish between copper and plastic piping, and are also on the conservative side. Most important is to avoid any dead ends and stale water that is warm but not hot. For the pilot, the legionella margin is based on actual research results, not official rules.
- [answered] Later deployments: no default may exceed what is usually officially recommended, but operators may set their own limits. [answered] This applies to every safety limit the software sets: legionella minimum, floor supply temperature, floor rate of change. The software never overheats anything; hardware caps that.
- [answered] Excessive temperature in the drinking-water system is prevented by hardware: a circulation pump and a mixer or thermostat keeping it at or below 65 °C. "Any installation should have that." The storage tank itself can get very hot from solar thermal heat (not present in the pilot) or from a stove with a water jacket (planned in the pilot).
- [answered] Comfort, for prototyping: 18.5–21 °C has been comfortable, read from a thermometer at one specific place. "To be adjusted in practice": later from user reports ("too warm" or "too chilly" at a given moment). Perceived warmth with underfloor heating is subjective and does not map 1:1 to room air temperature.
- [answered] No writes to devices yet, only simulations.
- [answered] When writes come: the person running it in their home network is likely authorised to allow them. The project must inform them about the risks and that the project accepts no liability.

### 2.12 Applicable standards

- [deferred] To be researched and considered when developing the specifications. Candidates: Home Assistant's entity model (the chosen vocabulary), SG-Ready for heat pumps, and the German drinking-water rules on legionella. The official recommendations set the upper bound for the defaults of later deployments (2.11). The pilot's own limits come from research results instead.

## Release

Decides: Dieter Weber. Builds: Dieter Weber with agents. Pays: Dieter Weber (own hardware and time). Signs off: Dieter Weber. Owns the instrument or shared system it acts on: at each site, the person running it in their home network authorises writes (likely) and is informed about risks and that the project accepts no liability; in the pilot, Dieter Weber. No writes in the first stage.

## Open questions

- How the planned wood stove's heat input is measured (a sensor, no routine human interaction). For the principal; resolves 2.2; deferred until the stove is installed.
- Fallback behaviour when the optimizer fails, and how to coach the user to set it in the unit's programming screen. For the principal (provides the heat pump handbook); resolves 2.5; deferred to the specification of S4.
- Build on EMHASS, use it as a reference, or develop our own numerical core? For the principal; resolves 1.1 and 2.3; deferred to deriving the specifications (OpenSpec proposal).
