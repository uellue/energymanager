# Choosing a Zigbee coordinator

Question: which Zigbee coordinator fits Home Assistant Container 2026.11 in Docker, first on WSL2 (USB only through usbipd), later on a Debian mini PC, preferring a network coordinator (Ethernet, ideally PoE)? First one temperature sensor, more later. And can the household's Sonoff ZB Bridge-P be reflashed into a network coordinator?

Provenance: research by a sub-agent on 2026-11-21 from the Home Assistant ZHA and ZBT-2 pages, the Zigbee2MQTT adapter pages, the Tasmota docs and repository, Sonoff's help centre, and the SMLIGHT and TubesZB product pages, all read that day; community threads are labelled. Spot-checked by the session on 2026-11-21: ZHA's two quotes (ZBT-2 "the recommended choice"; no EZSP connection over Wi-Fi), Sonoff's "ESP32+CC2652" for the ZB Bridge-P (the URL had a stray suffix, corrected), and Tasmota's listing of the Bridge Pro. Other quotes and prices are as reported.

## What the projects say

- **ZHA** (https://www.home-assistant.io/integrations/zha/): "If you do not have a coordinator yet, the Home Assistant Connect ZBT-2 is the recommended choice." No other adapter is ranked. Zeroconf discovery is tested for network adapters including the SMLIGHT SLZB-06 POE and Tube's Ethernet coordinators. Under troubleshooting: EZSP "requires a stable connection to the serial port. Therefore, it is not recommended to use a connection over Wi-Fi, WAN, or VPN."
- **Zigbee2MQTT** (https://www.zigbee2mqtt.io/guide/adapters/): recommended stacks are zStack (TI), EmberZNet (Silicon Labs) and deCONZ. "Network adapters connected via WiFi might have reduced stability"; if a local USB adapter is not possible, "the recommendation is to use remote adapter connected via Ethernet (wired)". Its EmberZNet page (https://www.zigbee2mqtt.io/guide/adapters/emberznet.html) supports firmware 7.4.x to 9.1.x and says of the SLZB-06M: "Not suitable for WiFi or other high latency connections."

## Candidates

| Candidate | Radio, stack | Connection | ZHA | Zigbee2MQTT | Price (manufacturer) | Notes |
|---|---|---|---|---|---|---|
| Home Assistant Connect ZBT-2 | Silicon Labs MG24, EmberZNet; ESP32-S3 as USB-serial bridge | USB-C only | the one recommended coordinator | listed (EFR32MG24); ZBT-2 page: "being used by many people with Zigbee2MQTT" | MSRP €45 incl. tax, $49 (https://www.home-assistant.io/connect/zbt-2) | Zigbee or Thread, not both. On WSL2 it needs usbipd. |
| SMLIGHT SLZB-06Mg24U | EFR32MG24, EmberZNet | Ethernet, 802.3af PoE; Wi-Fi "as a fallback"; USB | SLZB-06 POE tested for discovery | listed (EmberZNet) | not stated | SMLIGHT: "Compatible with Zigbee2MQTT and ZHA" (https://smlight.tech/en/slzb06) |
| SMLIGHT SLZB-06U / 06P7U | CC2652P / CC2652P7, Z-Stack | as above | as above | SLZB-06 and 06p7 listed under zStack | not stated | same family, TI radio |
| TubesZB EFR32 MGM24 PoE 2024 | MGM240PA32VNN, EmberZNet | Ethernet, PoE | Tube's EFR32 Ethernet tested for discovery | listed | $76.00 (https://tubeszb.com/) | Z2M: "do not use USB and POE at the same time!" |
| Sonoff ZB Bridge-P, reflashed | ESP32 + CC2652 (Sonoff help centre: "ESP32+CC2652", https://help.sonoff.tech/docs/lk902vfbs49fll4s); Z-Stack coordinator firmware from Tasmota | Wi-Fi 2.4 GHz only | Pro not named; socket path given for "Sonoff ZBBridge" | Pro not named; its ZBBridge guide uses `ezsp` | owned | see below |

## The ZB Bridge-P

- **Chips.** Sonoff's help centre gives the model as "ZB Bridge-P" and the chips as "ESP32+CC2652". Tasmota's Zigbee docs (https://tasmota.github.io/docs/Zigbee/) label the "Sonoff Zigbee Bridge Pro" as "ESP32 + CC2652P with ZNP". So it is a TI Z-Stack radio, not the Silicon Labs EZSP radio of the older ZBBridge.
- **Firmware.**
  - ESP32: Tasmota build `tasmota32-zbbrdgpro`, installed "USB to Serial" (https://templates.blakadder.com/sonoff_ZBBridge-P.html).
  - CC2652P: flashed from Tasmota, which ships `SonoffZBPro_coord_20220219/20230507/20240710.hex` (https://github.com/arendst/Tasmota/tree/development/tools/fw_SonoffZigbeeBridgePro_cc2652).
  - Community opinion (https://community.home-assistant.io/t/itead-sonoff-zigbee-bridge-pro-zbbridge-p-new-cc2652p-and-esp32-based-zigbee-gateway-to-wifi-bridge/378924): do not flash unmodified Koenkk CC2652P images, as a wrong configuration can brick the bootloader, recoverable only with cJTAG.
- **Effort.** A 3.3 V USB-serial adapter on the GPIO pads with GPIO0 held to ground. Blakadder: "Flashing the device does not require soldering" (https://zigbee.blakadder.com/Sonoff_ZBBridge-P.html). Opening the case is implied, but no primary source describes it.
- **Use.** In TCP-bridge mode Tasmota only passes bytes between Home Assistant or Zigbee2MQTT and the radio (Tasmota docs). Blakadder: "Confirmed working with" ZHA and Zigbee2MQTT.
- **Warnings.**
  - Zigbee2MQTT's remote ZBBridge guide: "WiFi-based Serial-to-IP bridges are not recommended as the serial protocol does not have enough fault-tolerance" (https://www.zigbee2mqtt.io/advanced/remote-adapter/connect_to_a_remote_sonoff_zbbridge.html).
  - Community opinion (https://community.home-assistant.io/t/sonoff-zbbridge-pro-w-tasmota-is-serial-to-ip-over-wifi-an-issue/483323, 2022): one user could not get the Pro working with ZHA or Zigbee2MQTT; another advises a directly connected coordinator. In the thread above, a user finds Wi-Fi "don't seems a problem for the TI Chips".

Verdict: reflashing is documented and works, but the bridge stays on Wi-Fi, which both projects advise against. Fine as a free trial coordinator for the first sensor, not for the long term.

## ZBT-1 and ZBT-2

Added on 2026-11-22 from the ZBT-2 page (https://www.home-assistant.io/connect/zbt-2), the ZBT-1 page (https://www.home-assistant.io/skyconnect/; `/connect/zbt-1` returns 404) and the ZHA page, read that day by a sub-agent; quotes as reported. The ZBT-1 was earlier sold as SkyConnect.

| | ZBT-1 | ZBT-2 |
|---|---|---|
| Radio | Silicon Labs EFR32MG21 | Silicon Labs MG24 |
| USB-serial chip | CP2102N | ESP32-S3 |
| Serial speed | 115200 baud | 460800 baud ("4x Faster") |
| Antenna | "Small and internal" (ZBT-2 page) | separate base with antenna, peak gain 4.16 dBi |
| Protocols | Zigbee 3.0, or Thread by firmware update; "Multiprotocol will remain an experimental feature and is not recommended for use." | Zigbee 3.0 or Thread; "cannot do both Zigbee and Thread simultaneously" |
| Connector | "USB 2.0 full-speed", plug type not stated | USB-C, 1.5 m cable included |
| Price | not stated | MSRP €45 incl. tax, $49 |
| Status | "no longer in production, but continues to receive software updates" | current model |

- Both use EmberZNet; ZHA lists both under `ezsp`.
- The ZBT-2 page credits the MG24 with "faster operation and sensitivity for weak signals" and the higher baud rate with better device responsiveness. Neither page gives a range figure.
- Transmit power is "up to +20 dBm" for the ZBT-1 and "10 dBm (Europe) 8 dBm (rest of world)" for the ZBT-2. The figures come from different spec tables and are no range comparison.
- ZBT-1 units sold June to October 2024 had a faulty part; a replacement program runs for "60 months (effective October 2, 2024) for verified purchases."

Verdict: a ZBT-1 is only worth taking if it comes cheap or free. Like the ZBT-2, it needs usbipd on WSL2.

## Summary

- **Decision (principal, 2026-11-22):** a ZBT-2, ordered. It goes into a USB port of the automation PC, on its included 1.5 m cable; keeping the antenna away from USB 3 ports and the PC is common advice against interference (not checked for the ZBT-2).

- **Recommendation:** an Ethernet/PoE coordinator from the SLZB-06 family, preferably the EmberZNet SLZB-06Mg24U, connected by cable, never over its Wi-Fi fallback. It avoids usbipd on WSL2, moves to the Debian mini PC without change, can sit away from the server, and ZHA (discovery tested) and Zigbee2MQTT (listed) both support it. The TubesZB EFR32 MGM24 PoE ($76.00) is the alternative with a stated price.
- **Strongest counter-argument:** ZHA recommends only the ZBT-2, the cheapest new option (€45). On the Debian mini PC a USB stick on an extension cable needs no usbipd, so the network coordinator mainly solves the WSL2 period and adds firmware to maintain.

## Not verified

- SMLIGHT prices: none are stated on the product page.
- Whether the SLZB-06Mg24U variant name matches the "SLZB-06Mg24" entry in Zigbee2MQTT's list.
- How to open the ZB Bridge-P case, the pad locations, and which Tasmota CC2652P image is current.
- Long-term stability of a ZB Bridge-P with ZHA or Zigbee2MQTT over Wi-Fi.
- Broader community opinion: no forum thread comparing the SLZB-06 and the ZBT-2 was found.
