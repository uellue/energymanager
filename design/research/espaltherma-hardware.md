# ESPAltherma on a Daikin Altherma 3 R ECH2O (ERLA14D2W1 + EBSXB16P50DF): hardware and installation

Research by a sub-agent, 2026-11-23; issue uellue-bot/energymanager#11. Not reviewed by a person. Sources are cited inline; "single report" marks what one user said, "documented" what the project's or Daikin's own documents say, "inference" what the sub-agent concluded without a source. Spot-checked by the orchestrator: esphome-altherma's hub writes to the UART in one place only, a 4-byte read query `{0x03, 0x40, regID, 0x00}` (`altherma_hub.cpp`, main branch, 2026-11-23). GitHub Discussions could not be read (the repository's hook blocks them).

## Shopping list for the pilot (esphome-altherma, decided 2026-11-23)

Recommended build: wired Ethernet with Power over Ethernet, board in a small box outside the unit, only a thin signal cable into the switch box. Example sources are for identifying the part; buy wherever you like.

**Needed**
- **1 Board: Olimex ESP32-POE-ISO** (ESP32 with Ethernet and 802.3af PoE; 3000 V DC galvanic isolation between the PoE part and the board's supply, so the network is not tied to the heat pump's ground). https://www.olimex.com/Products/IoT/ESP32/ESP32-POE-ISO/open-source-hardware. ESPHome supports it ("Olimex ESP32-POE" in the Ethernet docs, https://esphome.io/components/ethernet/). The WROOM variant is simplest; WROVER variants move the Ethernet clock pin (same docs).
- **2 PoE power:** an IEEE 802.3af PoE injector, plus a Cat 6 patch cable to the unit. The pilot's switch (TP-Link TL-SG1016) has no PoE: its specification lists IEEE 802.3i/u/ab/x only (https://www.tp-link.com/de/business-networking/unmanaged-switch/tl-sg1016/, read 2026-11-23). Example injector: TP-Link POE150S (formerly TL-POE150S), 802.3af, up to 15.4 W, gigabit ([datasheet](https://static.tp-link.com/upload/product-overview/2026/202609/20260923/POE150S(UN)7.0_Datasheet.pdf)). Take an 802.3af injector, not a "passive PoE" one: the board is specified for 802.3af, and passive injectors put a fixed voltage (often 24 V) on the cable without negotiation.
- **3 Plug for X10A: JST EH series, 2.5 mm pitch, 5 positions** — housing **EHR-5**, crimp contacts **SEH-001T-P0.6** (AWG 30–22), and a crimp tool for JST EH (e.g. Engineer PA-09). Or a ready-made "JST EH 2.5 mm 5-pin" pigtail, no tool needed. Only pins 2 (TX), 3 (RX) and 5 (GND) are used; pin 1 (5 V) stays free because the board runs on PoE.
- **4 Cable** from the plug to the board: 3- or 4-core, thin (e.g. LiYY 4 × 0.25 mm²), long enough to leave the switch box with slack for its service position (about 1 m).
- **5 Level shifter** for the heat pump's 5 V signal into the ESP32's 3.3 V input: a BSS138 bidirectional module, e.g. https://www.adafruit.com/product/757. esphome-altherma's README wires without one and users report it working; the ESP32's inputs are specified for 3.3 V, so I'd include it (cheap). One user reported a TXS0108E module *not* working.
- **6 Small enclosure** for the board and level shifter, cable glands or grommets, cable ties and adhesive tie mounts for strain relief inside the switch box.

**Tools you need anyway**
- A **multimeter** for the safety check before touching anything (below 50 V DC after switching off all supplies and waiting 10 minutes).
- A **micro-USB cable** for the first flash; afterwards updates go over the network.

**Not needed:** relays (no Smart Grid wiring), an external antenna, a separate USB power supply (PoE powers the board).

**Alternative without PoE (cheaper, Wi-Fi):** M5Stack AtomS3 Lite (https://shop.m5stack.com/products/atoms3-lite-esp32s3-dev-kit; esphome-altherma has a ready config for it) plus a USB 5 V power supply, or power from X10A pin 1. Risk: Wi-Fi through the closed metal casing is the most common complaint; then the board must sit outside.

**What I'll prepare once the parts are chosen:** the ESPHome configuration for the Olimex board. Its Ethernet uses GPIO 17, so esphome-altherma's default pins (RX 16 / TX 17) cannot be used; RX on GPIO 36 and TX on GPIO 4 (as ESPAltherma uses on this board) — to be checked against Olimex's schematic before flashing. It will contain only read sensors, and be reviewed before it runs.

## For people: short version

**Shopping list** (read-only monitoring, data to Home Assistant over MQTT):

- **Board, one of:**
  - M5StickC Plus2 (the ESPAltherma maintainer's recommendation for v2: display, magnet, insulated case, fits next to the board) — WiFi only.
  - Olimex ESP32-PoE or WT32-ETH01 — wired Ethernet, supported by v2. Worth considering here because the ECH2O switch box is metal and every WiFi complaint below is about the casing.
  - Any ESP32 DevKit / ESP32-S3 / C3, or M5Stack Atom Lite, also supported.
- **Cable:** a JST EH 2.5 mm 5-pin plug: housing **EHR-5** with crimp contacts **SEH-001T-P0.6** (AWG 30–22), or a ready-made EH 5-pin pigtail. Dupont jumpers do work, but the project names them as a "VERY COMMON" cause of failures. If the board sits away from the unit, extend with a short multi-core or Cat5/6 cable; don't chain Dupont wires.
- **Power:** X10A pin 1 (5 V) is documented as enough for an ESP32 (about 70 mA). Single reports of a weak 5 V exist (about 2.5 V on one EHVX, an ERLQ that needed USB, ROTEX units). The maintainer suggests a separate USB charger as "a cheap way to remove even the theoretical coupling". **Keep GND to X10A pin 5 in every case.**
- **Level shifter: optional.** The README says "to play it safe" use one; the maintainer runs without one. If you use one: users report a BSS138 4-channel module working (v2 drops the echo it causes), a TXS0108E that did not work, and an ADuM1201 digital isolator working on v2 (single reports).
- **Enclosure:** only needed if the board goes outside the unit (small plastic box on the wall). Strain relief and cable ties for the cable inside the switch box.
- **SG-Ready relays:** not needed for read-only.

**Installation steps** (ECH2O-specific steps from Daikin manual 4P663483-1C; ESPAltherma steps from the v2 README):

- **1** Flash v2 from the web installer (Chrome/Edge, USB data cable), enter WiFi, or use an Ethernet board.
- **2** Switch off all supplies, wait, measure (per the installer reference guide you already have).
- **3** Open the ECH2O: remove the user interface panel (open the hinges at the top, slide it down), remove the switch box cover, and disconnect the ground lead from the cover. Do NOT damage or remove the switch box's foam sealing. For easier access the switch box can be lowered into a service position (loosen the screws, lift, lower). Cables routed in the service position need extra length for the normal position.
- **4** Plug the EH plug into X10A on A1P, minding orientation: 1 = 5 V, 2 = TX (to ESP RX), 3 = RX (to ESP TX), 4 = NC, 5 = GND.
- **5** Route the cable along the existing low-voltage path. Fix it with cable ties to the cable-tie mountings, with strain relief, at least 50 mm from mains cables. Don't push spare cable into the unit.
- **6** Place the board. Inside the switch box is what the maintainer does with an M5Stick. Most reported trouble is WiFi through the closed metal casing, so expect to need the board outside the casing, a repeater or Ethernet. Check RSSI with the unit closed before you finalise.
- **7** Close in reverse order (ground lead to cover, cover, switch box back up, UI panel), and power up.
- **8** In the web interface: the model should be detected automatically. **Untick "Help others get their heat pump recognised" before confirming.** Leave everything under Settings → Experimental off. Untick the daily update check if no outbound traffic is wanted. Set an admin password, then the MQTT broker.

## 1. Shopping list: details and sources

### Boards

- **Documented (v2, beta branch README):** "Supported boards: ESP32 DevKit (and most ESP32 boards), ESP32-C3, ESP32-C6 (experimental), ESP32-S3, M5StickC, M5StickC Plus, M5StickC Plus2, M5Stack Tough, M5Stack Atom Lite, WT32-ETH01 and Olimex ESP32-PoE." It also says "I recommend an M5StickC (Plus, Plus2): it has an integrated display, a magnet, fits well next to the board and is properly isolated." The ESP8266 is no longer supported in v2 (it stays on v1). Source: https://github.com/raomin/ESPAltherma/blob/beta/README.md
- **Documented:** "Wi-Fi, or wired Ethernet on the WT32-ETH01 and Olimex ESP32-PoE." The WT32-ETH01 has no USB port: you flash it through a USB-serial adapter with IO0 held to GND at power-up. Pin table (RX ← X10A pin 2 / TX → X10A pin 3):

  | Board | RX | TX |
  | --- | --- | --- |
  | DevKit / S3 | GPIO 16 | GPIO 17 |
  | C3 / C6 | GPIO 4 | GPIO 5 |
  | M5StickC family | G36 | G26 |
  | Atom Lite | G26 (Grove) | G32 (Grove) |
  | WT32-ETH01 | GPIO 5 | GPIO 17 |
  | Olimex ESP32-PoE | GPIO 36 (UEXT) | GPIO 4 (UEXT) |

  Same README.
- **ECH2O ERLA D users in the tracker:**
  - Issues #632 and #641 (EBSX11P30D / ERLA 11 kW ECH2O, definition "ERLA D EBSH-X 16P30-50 D SERIES 11-16kW-ECH2O") run v2 on an **Olimex ESP32-PoE**; single user. https://github.com/raomin/ESPAltherma/issues/632 , https://github.com/raomin/ESPAltherma/issues/641
  - Other ECH2O owners (ERGA/EHSX) report M5StickC (#659, #708) and M5Stack Atom Lite (#639, #640). https://github.com/raomin/ESPAltherma/issues/659 , https://github.com/raomin/ESPAltherma/issues/639
- **WT32-ETH01 in v1 times:** one user's timeouts disappeared after removing chained Dupont wires (#204, single report). https://github.com/raomin/ESPAltherma/issues/204
- **OpenEnergyMonitor thread** (EDLA monobloc, not ECH2O): most users there run an M5StickC Plus2; the WT32-ETH01 was discussed as the Ethernet option. https://community.openenergymonitor.org/t/daikin-heat-pump-espaltherma-homeassistant-installer-bundle-for-emoncms/25711 and `?page=2`
- **Alternative firmware, esphome-altherma** (ESPHome component, not ESPAltherma):
  - It lists ESP32 DevKit, ESP32-S3, M5Stack Core/Basic and AtomS3 Lite.
  - It ships a mapping `confs/erla_d_ebsh_11_16_ech2o.yaml` labelled "EBSXB16P50DF / ERLA D EBSH-X 16P30-50 D series 11-16kW-ECH2O". That is the pilot's indoor model, added 2026-04-07 from one user's register export.
  - Its hub only sends read queries (`0x03 0x40 <reg>`), so it is read-only by construction; I checked `components/altherma_hub/altherma_hub.cpp`.
  - Latest release v1.4.0 (2026-10-27).
  - https://github.com/jjohnsen/esphome-altherma
- **Another alternative, DaikinAlthermaX10AConnect** (ESPHome, M5Stack PoE board, also writes: operation mode and Smart Grid): https://github.com/Dennis3321/DaikinAlthermaX10AConnect , announced at https://community.home-assistant.io/t/new-project-daikin-altherma-x10a-connect-native-esphome-integration-via-poe-v1-0-released/988126

### Cable and connector

- **Documented:** "A 5 pin JST EH 2.5 mm connector (or 4 Dupont wires M-F)". Beta README.
- **Documented (troubleshooting):** "a faulty Dupont cable, a VERY COMMON cause". "You can also use a common 2.54 female long header, plug it to the X10A connector and then your dupont cable to the long pins of the header." https://github.com/raomin/ESPAltherma/blob/beta/doc/troubleshooting.md
- **Issue #77** (users): the mating plug is JST **EHR-5**. Confirmed EH 2.5 mm by the user who built a cable; the README was corrected from "PH 2.0" then. https://github.com/raomin/ESPAltherma/issues/77
- **JST EH datasheet** (Mouser copy): contact **SEH-001T-P0.6**, wire AWG #30–#22 (0.05–0.33 mm²); the "-P0.6L" variant is low insertion force with a different crimp height. https://www.mouser.com/datasheet/2/564/eEH-3476922.pdf
- **Extensions:**
  - One user crimped Dupont/EH onto Cat6 (OEM thread page 2, single report).
  - Another extended with UTP to an ESP outside the unit (#17, single report). https://github.com/raomin/ESPAltherma/issues/17
  - Chaining two Dupont wires caused timeouts (#204, single report).
- **ESP32-CAM:** one ECH2O/HPSU user (EHSX08P50B) reports it gets enough power from X10A (#17, single report).

### Level shifter

- **Documented:** "The serial port of X10A is TTL 5V, where the ESP32 is 3.3V. Your ESP32 might not be 5V tolerant. If you want to play it safe, you should use a level shifter… In practice, I had no problem connecting an ESP32 without level shifters." (doc/troubleshooting.md, beta)
- **BSS138 4-channel bidirectional module:** in v1 the X10A echo of the ESP's own query caused "got 4/N bytes" timeouts (#585, single report). The maintainer: "ESPAltherma 2 now drops its own query when a level shifter hands it back". https://github.com/raomin/ESPAltherma/issues/585
- **TXS0108E:** "the ESP32 would not read anything" (#17, single report, EHSX08P30DA3-era post).
- **ADuM1201 digital isolator:** after a main-board failure (see 3.), one user reconnected with an ADuM1201, and "the v2 is flawless so far" (#584, single report). https://github.com/raomin/ESPAltherma/issues/584
- **Issue #139** shows the disagreement over 5 V tolerance. One user reports a board getting "extremely hot" and a version that would not power from X10A. https://github.com/raomin/ESPAltherma/issues/139

### Power supply

- **Documented:**
  - X10A pin 1 "Can supply voltage for the ESP". "On my Daikin Altherma, 5V is provided by a 7805 with a massive heat sink… ESPAltherma… consumes 70ma." (troubleshooting.md)
  - "A weak 5V from the X10A is a common cause [of restarts]: on M5 boards, the supply voltage is shown in the Values tab. Power the board from a USB charger in that case (and keep the GND wire)."
  - README: "make sure you keep a wire connecting the GND of the ESP32 to the GND pin of the X10A (even if you power your ESP32 with a USB charger)".
- **Weak 5 V, single reports:**
  - "~2.5 V out of the heater board" on an EHVX08S26CB9W, which led to USB power (#17).
  - ERLQ016CAW1: "needs external USB power (Altherma 5V pin insufficient)" (esphome-altherma README, Successful Installs table).
  - ROTEX units (README).
- **Maintainer in #584:** "powering the ESP from a separate USB supply is a cheap way to remove even the theoretical coupling".
- **Inference, not sourced:** with a PoE board, don't feed X10A 5 V into it as well. Leave pin 1 unconnected and check the board's own power documentation before combining supplies.

### SG-Ready relays (note only)

v2 drives SG1/SG2 through two relays on free GPIOs. On M5StickC, Grove pins 32/33. The maintainer finds X10A 5 V enough for ESP32 plus two relays, "your mileage may vary" (beta README). Not needed for read-only.

## 2. Installation in the ECH2O switch box

- **Daikin, EBSH/X(B)11+16P30+50D installation manual 4P663483-1C (2023.05):**
  - The switch box sits behind the user interface panel. Open: remove the UI panel (hinges at top, slide down), remove the switch box cover, disconnect the ground connection from the cover.
  - "Do NOT damage or remove the foam sealing of the switch box."
  - "To have easier front access, lower the switch box": loosen the screws, lift, lower. "If the switch box is lowered in service position while the electrical installation is done, additional cable length has to be taken into account… The cable routing in normal position is longer than in service position."
  - "All cables which will be connected to the switch box of the ECH2O must be fixed by strain relief." Cables are fixed "with cable ties to the cable tie mountings".
  - "The distance between the high voltage and low voltage cables should be at least 50 mm." (Your reference guide says >5 cm; the same thing.)
  - "Do NOT push or place redundant cable length into the unit."
  - Close: ground lead back, cover, top cover, switch box back into place, UI panel.
  - The WLAN cartridge goes "into the cartridge slot on the user interface", not onto X10A.
  - https://www.daikin-ce.com/content/dam/document-library/installation-manuals/heat/air-to-water-heat-pump-low-temperature/ebsh-d/EBSH-D.EBSHB-D.EBSX-D.EBSXB-D_Installation%20manual_4PEN663483-1C_English.pdf
  - The manual does not name a specific gland for retrofit signal cables. Which opening to use is for you (or the installer) to decide on site from the existing low-voltage path.
- **Placement inside vs. outside:**
  - Documented: the maintainer's M5Stick sits "next to the board" (README recommendation; a photo in https://github.com/raomin/ESPAltherma/blob/beta/doc/images/installation.png referenced from the README).
  - Community photo thread #17 (many builds, few ECH2O; photos linked there). One ECH2O/HPSU build (EHSX08P50B) used a LOLIN32 Lite powered through its battery connector, with a 3D-printed mini panel "adapted in order to close the cover". Single report. https://github.com/raomin/ESPAltherma/issues/17
- **WiFi through the metal casing** (all single reports unless marked):
  - #17 (EHVX wall unit): "At first I had the ESP near the main board, but with the metal covers the Wi-Fi reception was bad", so the cable was run out of the electrical box.
  - #559 (monobloc): RSSI drops to about −87 dBm once the case is closed; an external antenna on the M5 "helped, but not enough". Closed by the maintainer: "moving the module away from the metal casing solved it". https://github.com/raomin/ESPAltherma/issues/559
  - #203: WiFi connected only with the heat pump off; fixed with a repeater (−43 dBm). The maintainer: weak signal plus heat pump noise; "increase the distance from the heat pump with longer cable (a cat5 network cable should be good for that)". https://github.com/raomin/ESPAltherma/issues/203
  - esphome-altherma (ERLQ016CAW1): ESP32-WROOM-32U with an "External antenna routed outside casing (Faraday cage)".
  - Documented in v2 troubleshooting: "An ESP32 board with an external antenna connector, or a repeater near the heat pump, usually fixes it". The System tab shows RSSI.
- **Not found:** a photo-documented, step-by-step ESPAltherma install specific to EBSX/EBSH (ERLA D ECH2O). The ECH2O builds found are EHSX/HPSU (ERGA) units in #17. GitHub Discussions (ESPAltherma's v2 discussion, esphome-altherma discussions #4 and #47 with ECH2O installs) could not be read: this repository's hook blocks fetching GitHub discussion pages. If they matter, read them by hand.

## 3. Problems reported on ECH2O / ERLA D and similar

- **Detection / definition:**
  - Documented: v2's `data/as_numbers.json` (beta) maps AS number body 3608729, suffix 55, letter C to models EBSXB16P50DF/DG, definition "Altherma(ERLA D EBSH-X 16P30-50 D SERIES 11-16kW-ECH2O)", software **ID20007903**. That confirms the software ID for this indoor unit, and that it is a single-candidate AS number, so detection should be "high" confidence and used right away (doc/how-it-works.md).
  - `data/fingerprints.json` is still empty (`[]`).
  - https://github.com/raomin/ESPAltherma/blob/beta/data/as_numbers.json , https://github.com/raomin/ESPAltherma/blob/beta/doc/how-it-works.md
- **Values not on X10A on ECH2O:**
  - **Water pressure** reads 0. The maintainer found in the hydro board software that it is enabled by an installer field setting that is off on ECH2O, and believes the sensor is wired to the RoCon side. Since a later beta, no longer "recommended" on the ECH2O definitions (#615; checked on ERGA units, ERLA ECH2O "whether… behave" left open). https://github.com/raomin/ESPAltherma/issues/615
  - #275, user: the ECH2O has a second controller board where the backup heater is connected, so BUH data on X10A "are not always consistent". Single report. https://github.com/raomin/ESPAltherma/issues/275
  - #17: water pressure and 3-way valve positions are read via CAN (pyHPSU), not X10A (user reports).
  - #486 (ERLA-EBSX): the mixing valve registers are always 0; they are marked "[Future]" (unverified) in the definition. https://github.com/raomin/ESPAltherma/issues/486
- **v2 on ERLA ECH2O, open issues:**
  - #632: the "Circulation" flag on the health widget stays off although the pump runs.
  - #641: power estimate vs. a utility meter; mentions a mis-set BUH step in the GUI.
  - On ERGA ECH2O: #659 leaving water / heat calculation (adjusted in beta.28 for ECH2O); #708 card target value wrong in DHW/SG mode.
- **Communication errors:** "Time out", "Wrong CRC" are usually a missing GND, a bad Dupont cable, or RX/TX swapped (documented, troubleshooting).
- **Error codes on the unit (single reports):**
  - #347 (EDLA monobloc): after a wiring mistake (ESP GND on a 3.3 V pin) the controller showed **U8-07** and stuck at "synchronising 0%". https://github.com/raomin/ESPAltherma/issues/347
  - #40: unplugging X10A from a bizone module gave **UA-16** within 5–10 s. Relevant only where X10A is occupied, which is not the case on the pilot. https://github.com/raomin/ESPAltherma/issues/40
  - #584: a main PCB died after years with an ESP on X10A 5 V. The ESP was confirmed alive. The maintainer saw no causal path and closed it as a plain PCB failure. The user now uses an ADuM1201 isolator.
- **Onecta / WLAN cartridge / user interface:**
  - #501: a user suspected ESPAltherma made Onecta go offline, then reported Onecta was just as unstable without ESPAltherma (single report). https://github.com/raomin/ESPAltherma/issues/501
  - Documented: the WLAN cartridge plugs into the user interface, not X10A (Daikin manual above).
  - Documented: the user interface re-sends its setpoints every second, so writes through the diagnostic port are overwritten (beta README) — a further reason read-only is the natural mode.
- **Warranty:** no statement from Daikin or an installer about ESPAltherma and warranty was found. #584 only says "be aware of the extended warranty". Ask the installer or Daikin in writing if it matters.

## 4. v2 configuration for ERLA D EBSH-X ECH2O, read-only, no telemetry

- **Model:** Setup → Heat pump. v2 surveys the unit and should pick "ERLA D EBSH-X 16P30-50 D SERIES 11-16kW-ECH2O" from the AS number (see 3.). Check it and click **Confirm this model**. If it is not proposed, choose it from "Not this one?". Until confirmed, only "safe values" are published. (beta README, how-it-works.md)
- **Telemetry:**
  - In firmware (`include/config.h`, beta) the default is off: `configDefaults` zeroes the struct; `telemetry` is not set true.
  - But the web UI pre-ticks the "Help others get their heat pump recognised" box when you confirm a model (`$('#tmOn').checked = true` in `web/index.html`), and saving with it ticked turns telemetry on.
  - Reports and the daily heartbeat are only sent if `config.telemetry && config.modelConfirmed` (`include/webserver.h`).
  - So: **untick the box before Confirm this model**, then verify the telemetry checkbox in the System tab is unticked.
  - Separately, `updateCheck` defaults to **on**: once a day the board reads the release manifest from the installer site. Untick it under System → Firmware update if no outbound traffic is wanted.
- **Experimental writes:** `dhwTarget`, `lwtTarget`, `coolTarget`, `addTarget`, `powerLimit` and `ctlLimitOn` all default false. Writes through X10A happen only when one of them is ticked under Settings → Experimental, and only on hydro board software listed in `CONTROL_PROFILES` (`include/control.h`).
  - **20007903 is on that list** ("from the boards' software… awaiting a first report", beta README). So on this unit a ticked box *would* write. Keep Settings → Experimental untouched.
  - Relays (thermostat, cooling, SG, safety) only drive GPIOs; leave their pins at −1 (the default).
  - Set an admin password (Settings → This device) so nobody can tick these boxes over the network.
  - **Inference:** the write code is still in the firmware. If "read-only" must hold by construction rather than by configuration, the options are esphome-altherma (its hub only sends read queries) or a build of ESPAltherma with the control code removed.
- **MQTT / Home Assistant:**
  - Setup → Home Assistant → "Find my Home Assistant" (searches for the broker), or enter address, user and password; **Test the connection**, save.
  - Discovery is published on `homeassistant/device/espaltherma-mqtt-discovery/config`. Devices: "Daikin Altherma via ESPAltherma" (values) and "ESPAltherma" (relays, raw `sensor.althermasensors`). Entity IDs come from the English labels.
  - To clear discovery, publish an empty retained message to that topic.
  - Logs go to `espaltherma/log`.
  - Values: the Values tab; "Try not to get everything".
  - https://github.com/raomin/ESPAltherma/blob/beta/doc/home-assistant.md

## Fetch notes

- Read via the GitHub API: the READMEs on `main`, `beta` and `v1`, and from the `beta` branch `doc/troubleshooting.md`, `doc/how-it-works.md`, `doc/home-assistant.md`, `data/as_numbers.json`, `data/fingerprints.json`, `include/config.h`, `include/control.h`, `include/webserver.h` and `web/index.html`. Also the esphome-altherma README, `altherma_hub.cpp` and the ECH2O conf.
- Issues were read through `tools/gh_thread.py`: #17, 40, 77, 139, 203, 204, 212, 247, 275, 322, 347, 350, 486, 501, 508, 520, 523, 545, 559, 584, 585, 601, 615, 632, 639, 640, 641, 659, 708, 711, 712.
- Blocked by this repository's hook: GitHub Discussions pages (ESPAltherma v2 discussion, esphome-altherma discussions).
- Web searches in German forums (photovoltaikforum, haustechnikdialog) found nothing relevant.
- No Daikin warranty statement on third-party X10A devices was found.
