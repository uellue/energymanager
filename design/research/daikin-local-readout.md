# Reading the pilot's Daikin unit locally

Question (requirements 2.3; walk p1-collect-and-view, step 4): how can the heat pump's electrical power, and ideally the compressor frequency, return-water temperature, flow and heat output, be read locally and read-only from the unit, without an extra meter?

Provenance: research by a sub-agent on 2026-11-21 from Daikin's installer guides and the projects' repositories. Spot-checked by the session: the ESPAltherma definition file for this unit exists and contains "INV primary current (A)", "Inlet water temp.(R4T)" and "Flow sensor (l/min)", commented out by default. Other figures are as reported and not re-checked.

## The unit

Daikin Altherma 3 R ECH₂O, a split system (not Altherma 3 H). Source: Daikin installer reference guide 4P663482-1C (2023.05), https://www.daikin.co.uk/content/dam/document-library/Installer-reference-guide/heat/ERLA11-14D(V3.W1).ERLA-D(V3.W1)7.EBS(H.X)(B)-D_Installer%20reference%20guide_4PEN663482-1C_English.pdf

- **Outdoor unit ERLA14D2W1:** low water temperature, R32, capacity class 14, D series, 3N~ 400 V.
- **Indoor unit EBSXB16P50DF:** floor-standing, unpressurised 500 l plastic storage tank, heating and cooling, bivalent heat exchanger.
- **User interface:** "Unified MMI2", firmware 7.11.0. EKRHH requires 7.8.0 or newer.

## Options

| Port | Tool or project | Fits this unit | Values | Rate | Licence, activity | Caveats |
|---|---|---|---|---|---|---|
| X10A (hydro PCB A1P) | Daikin EKPCCAB4 PC cable (USB) | yes | none: software and EEPROM updates only | – | Daikin option | not a logger |
| MMI USB port | USB stick | yes | settings export, software update | – | – | no logging documented |
| X10A | ESPAltherma (github.com/raomin/ESPAltherma), definition file `Altherma(ERLA D EBSH-X 16P30-50 D SERIES 11-16kW-ECH2O).h` | yes | inverter primary and secondary current, inverter frequency, flow (l/min), inlet water R4T (return), leaving water R1T/R2T, CT current L1–L3. No voltage and no power: v2 estimates power from current and a power factor, about 25 % off during ramps (issue #641) | default 30 s | MIT; v2.0.0-beta.33, 2026-11-18 | ESP32 plus a level shifter (5 V TTL); "use entirely at your own risk"; read-only; a bizone kit occupies X10A (then X12A) |
| X10A | esphome-altherma (github.com/jjohnsen/esphome-altherma), `erla_d_ebsh_11_16_ech2o.yaml` | yes | temperatures, R4T, flow, pressure; no current or frequency in the shipped config | not stated | no licence file | uses ESPAltherma code |
| P1/P2 bus | P1P2MQTT (github.com/Arnold-n/P1P2MQTT) | contradictory: its README excludes ECH₂O "E\*P50D\*" units, but Daikin's guides show P1/P2 on EBSX-D | compressor RPM, inverter current; energy counter hourly; flow and ΔT give COP | 1 s | CC BY-NC-ND 4.0 (conflicts with 2.9) | no galvanic isolation; connect with power off; at most 2 devices on the bus |
| P1/P2 → Modbus TCP/RTU | Daikin Home Hub EKRHH, use case 3 | yes: "ERLA11/14/16DV3/W1 … ECH2O EBSH(B)/X(B)-D", MMI 7.8.0 or newer | return-water temperature (reg. 42), flow (49), **heat pump power consumption 0–20 kW (51)**, compressor running (31), leaving water | polled by the client | Daikin product, guide revision 2026.01 | not combinable with LAN adapter BRP069A61/62 or DCOM; whether reg. 51 is measured or estimated is not stated |
| P1/P2 → Modbus RTU | DCOM-LT-MB | not listed for EBSX | no power register | – | – | – |

EKRHH guide: https://www.daikin.eu/content/dam/document-library/Installer-reference-guide/heat/accessories/ekrhh/EKRHH_Installer%20reference%20guide_4PEN744838-1E_English.pdf

## Summary

- The "USB device for the installer port" is most likely the Daikin EKPCCAB4 cable, which only updates software. Or it is a USB-TTL or ESP32 adapter on X10A, as ESPAltherma uses.
- For continuous read-only data:
  - ESPAltherma on X10A gives current, compressor frequency, flow and return temperature, but no true power.
  - EKRHH is the only vendor-documented local source of a power value (Modbus register 51) for this unit.

## Additions from a second research run (2026-11-21)

A second sub-agent answered the same question independently (a comparison of research methods; ledger row 5). It agreed with everything above and added the points below. The quotes from the P1P2MQTT and ESPAltherma repositories were spot-checked; the page numbers in Daikin's guides were not.

- **Daikin's energy figures are estimates.** Installer reference guide 4P663482-1C, p. 59: "The calculated produced heat and consumed energy are an estimation, the accuracy cannot be guaranteed." Without meters, consumed energy "is calculated internally based on: The actual power input of the outdoor unit; The set capacity of the backup heater; The voltage". External pulse meters are the "Preferred method because of higher accuracy" (§6.5.2; field settings [D-08]/[D-09], p. 232–233). So EKRHH register 51 most likely exposes this estimate too (inference, not stated by Daikin).
- **Resolution in practice.** The P1P2MQTT README: "the measurements by Daikin are not very accurate, its resolution in my system is 115 Watt" (another unit, not checked on this one).
- **EKRHH details** (guide 4P744838-1E):
  - Register addressing (p. 39): register 51 is PDU address 50. Register 51 is of type Pow16, a signed 16-bit value divided by 100, giving kW (p. 40).
  - Protocol (p. 39): Modbus TCP on port 502 without encryption, or 802 with TLS, or RTU over RS-485 at 9600 8N1.
  - Setup (§13.1.1, p. 56): Modbus is configured in the Onecta app, so a cloud account is needed once for onboarding.
  - **Write risk** (p. 39): input registers are read-only, but holding registers (setpoints, Smart Grid mode, power limits) can be written. Modbus TCP on 502 has no authentication. Read-only is therefore a property of the client's configuration, not of the hub; restrict network access with a VLAN or firewall.
  - Only one use case is active at a time (§6, p. 21), so Modbus (use case 3) excludes the hub's PV optimisation (use case 1).
  - The BRP069A78 WLAN cartridge is not named in the "cannot be combined" list (§2.4, p. 10), but coexistence is not confirmed either.
- **ESPAltherma:** the README states it "cannot change the configuration values of the heat pump". The definition file for this unit has CT-sensor current entries for L1–L3, which presumably need optional CT sensors (unverified). The X10A pinout per the README: pin 1 = 5 V, 2 = TX, 3 = RX, 5 = GND.
- **esphome-altherma:** one user reports that the Altherma's 5 V pin was not enough to power the board, which then needed external USB power. Its README says "provided as-is for educational and personal use".
- **P1P2MQTT:** the README excludes "Older Altherma 3R ECH2O models with a E\*P50D\* code [that] originate from Rotex and use CANbus", and says E\*P50\*E codes use P1/P2 and are supported. Whether EBSXB16P50DF falls under the excluded models remains open.
- **Settles the accuracy question:** a one-off comparison against a clamp meter or the house's smart meter.

## Additions from the installer reference guide and ESPAltherma v2 (2026-11-22)

A sub-agent read the installer reference guide 4P663482-1C in full and ESPAltherma's `beta` branch; the orchestrator re-checked pages 13, 59, 124, 153 and 160. Tracked in issue uellue-bot/energymanager#11.

- **Correction: ESPAltherma v2 is not read-only.** Under Settings → Experimental (off until ticked) it writes the two points of the weather-dependent curve (leaving water, hot water) and the power limit ([4-08], limit 1) through X10A (`doc/control.md` on `beta`). This unit's hydro software 20007903 is listed "from the boards' software … awaiting a first report". Under AGENTS.md, these writes need an independent review before they run; the readout runs with them off. The table above describes v1.
- **Telemetry is on by default in v2** ("Help others get their heat pump recognised"): a report with identification codes, readings, model and firmware on model confirmation and after each update, plus a daily heartbeat. Untick it.
- **Unit counters in v2:** heat produced, compressor hours per mode, pump hours and compressor starts for software 20007903, mapped from the software, not yet compared with a real unit. Electricity per mode only for 20002203.
- **X10A and the WLAN cartridge use different connectors.** X10A's only documented use is the EKPCCAB4 cable (p. 160). The WLAN cartridge BRP069A78 goes into the card slot of the user interface (p. 153, 295); the WLAN module and the bizone kit are wired to the user interface PCB A11P (p. 298). Whether ESPAltherma's polling disturbs the user interface or cloud traffic is not documented; no report of a conflict was found. ESPAltherma's warning that a bizone kit occupies X10A probably concerns other models (inference).
- **Access and safety:** the ECH₂O indoor unit always has its own dedicated power supply (p. 124), besides the outdoor unit's; a backup heater may have a third. Switch all off, wait more than 10 minutes and measure below 50 V DC before touching (p. 13). Opening: user interface panel, switch box cover, ground wire on the top cover (p. 83–84). The switch box carries 230 V outputs; keep signal cables more than 5 cm from power cables (p. 298).
- **Serial settings:** 9600 baud, 8E1, per the maintainer in ESPAltherma issue #40 (2021), not in the README. ESPAltherma's power estimate from current × voltage is written for single-phase units and does not apply as is to this three-phase unit (inference).

Checked on the pilot's unit (photos by the principal, 2026-11-23): X10A on A1P is a 5-pin connector with pin 1 marked, and it is free; the 8-pin X23A next to it is free as well. The display gives the indoor unit's software as "ID0793", which presumably matches ESPAltherma's 20007903 (not confirmed).

## To check on the unit

- On the hydro PCB A1P in the switch box: the X10A label, whether X10A is free, and whether a bizone kit is fitted.
- The P1/P2 terminals, and what is connected to them.
- Whether a LAN adapter or DCOM is installed; either one blocks EKRHH.

## Not verified

- What "Daikin Service Checker", "D-Checker" and "Heating Configurator" do.
- Prices of EKPCCAB4, EKRHH and the P1P2MQTT bridge.
- Whether EKRHH register 51 is measured; its refresh rate; whether EKRHH needs internet; whether it coexists with the BRP069A78.
- Whether P1P2MQTT works on EBSX-D.
- ESPAltherma v2's polling rate.
- Warranty impact.
