# Walk-through: P1 sets up data collection and the dashboard (S1)

Persona: P1, the principal (design/stakeholders.md): new to Home Assistant, expert on the house and the maths; works on the Windows PC with WSL2 first and moves to the mini PC later. Confidence: the persona is real, but the walk itself was simulated by the agent on 2026-11-21. The answers are still pending.

What exists: nothing of the project's own code yet. Checked against reality on the development machine on 2026-11-21:
- no Docker in WSL2; 16 cores, 15 GB RAM;
- WSL2 is NATed (172.18.x), but reaches the home network outbound: the RCT inverter was read over TCP 8899.

Home Assistant docs read on 2026-11-21:
- the Linux installation page (HA Container "does not have access to apps"; HA OS "supports apps");
- the recorder (`purge_keep_days` default 10);
- weather (forecasts through the action `weather.get_forecasts`);
- forecast.solar (an account is needed only for more frequent updates or more than one plane);
- the Daikin Onecta README (HACS; Daikin Developer Portal account and application; OAuth redirect through My Home Assistant).

The RCT integration is not in Home Assistant core. The HACS integration weltenwort/home-assistant-rct-power-integration is MIT-licensed and was last pushed 2026-11-17.

Ends when: the dashboard shows the E1 data, and the E2 alert has fired on a mocked outage. The unit is not unplugged. The move to the mini PC is a separate walk.

## Steps

1. **Choose how to run Home Assistant on the development machine.**
   - Does: opens the installation page. Finds Home Assistant OS (needs a VM, here Hyper-V or VirtualBox on Windows) or Home Assistant Container (needs Docker, which WSL2 lacks).
   - Needs to know: which type matches what the mini PC will run, and that only Home Assistant OS can run add-ons. Requirements 2.8 plans to distribute the project as an add-on.
   - Goes wrong: developing on Container and deploying on OS means the add-on path is never exercised during development, and the two setups differ.
   - Would ask: "Which installation type do I use here, and which on the mini PC? Does it matter that Container can't run add-ons?"
2. **Onboarding.**
   - Does: creates a user, sets the home location and the time zone.
   - Needs to know: the location stays local, which matches 2.9.
   - Goes wrong: nothing particular.
3. **Reach Home Assistant from the phone, for alerts.**
   - Does: installs the Companion app on the phone and tries to connect.
   - Goes wrong: under WSL2's NAT the phone can't reach Home Assistant without port forwarding on Windows. A VM in bridged mode can be reached.
   - Would ask: "Where should alerts reach me during the pilot: phone, e-mail, or only on the dashboard?"
4. **Install HACS, then Daikin Onecta.**
   - Does: installs HACS (needs a GitHub account); creates a Daikin Developer Portal account and an application; authorises it through the OAuth redirect.
   - Needs to know: the call budget is 200 per day for private developers, polls and writes together. Default polling is every 10 min in the high-frequency period and every 30 min otherwise.
   - Goes wrong: if the development instance and, later, the mini PC poll at the same time, do they share one budget? It is unknown whether the limit applies per account or per application. Onecta has no return-water temperature, no compressor frequency and no live power, so the heat pump's electrical power is only available as daily energy.
   - Would ask: "Is daily energy from Daikin enough for the model, or do I need a power meter on the heat pump's supply?"
5. **Install the RCT integration from HACS.**
   - Needs to know: which entities it gives (solar power per string, battery state of charge and power, household load, grid import and export, energy counters), and at which interval.
   - Goes wrong: unknown whether the inverter accepts several clients at once (the RCT app, Home Assistant, our own scripts).
   - Would ask: "Can Home Assistant and my own scripts read the RCT at the same time?"
6. **Add forecast.solar.**
   - Does: adds the core integration and enters declination 35°, azimuth 55° and 7.92 kWp, the values from the URL the principal gave.
   - Goes wrong: the free tier has 12 calls per hour per IP, shared with any calls our own code makes. An account is needed for more than one plane.
   - Would ask: "Is it one roof plane, or several?"
7. **Add a weather forecast** (E1, E5).
   - Does: met.no is set up at onboarding; Open-Meteo is also in core.
   - Needs to know: which variables E5 needs (cloud cover, global irradiance, temperature) and which provider supplies them hourly for 48 h.
   - Goes wrong: forecasts are fetched through the action `weather.get_forecasts`, not kept as entity states. [Inferred from the weather docs, to be verified] The recorder then does not keep the forecasts as they were issued, which E3 and E5 need.
   - Would ask: "How do we keep every issued forecast, solar and weather?"
8. **Zigbee thermometer** (optional).
   - Does: plugs a Zigbee coordinator stick into the PC.
   - Goes wrong: USB devices reach WSL2 only through extra tooling (usbipd-win), and the stick then has to move to the mini PC.
   - Would ask: "Leave Zigbee until the mini PC?"
9. **Keep the history.**
   - Needs to know: how long raw data is kept. The recorder purges after 10 days by default; long-term statistics keep hourly aggregates.
   - Goes wrong: after a month, the 15-minute or 5-minute data the model needs is gone unless retention is raised or the data goes to another store.
   - Would ask: "How long do I need raw data, and at what resolution?"
10. **Get the data into Python** for S2.
    - Needs to know: the route out of Home Assistant. Candidates are the recorder's SQLite database, the REST or WebSocket API with a long-lived token, or an export.
    - Goes wrong: tokens end up in the repository; or the model needs a reproducible test case (E3), but Home Assistant's database changes all the time.
    - Would ask: "Where do recorded test cases live, and in what format?"
11. **Build the dashboard** (E1, E5).
    - Does: tries Home Assistant's Energy dashboard (grid, solar, battery) and adds temperature graphs.
    - Goes wrong: production against the forecasts (E5) needs a chart card that can show forecast series. The core cards may not, and a HACS card is another dependency.
12. **Mock an outage and check the alert** (E2).
    - Does: simulates Daikin being unreachable without touching the unit, e.g. by disabling the integration or blocking its traffic.
    - Needs to know: whether a real Onecta outage makes the entities "unavailable", which shows as a gap, or keeps the last value, which would show as a flat line.
    - Goes wrong: if the mock behaves differently from a real outage, E2 passes in the test and fails in practice.
    - Would ask: "How does Onecta behave when the cloud is down?"
13. **Done** when the dashboard shows the E1 values and the mocked outage raised the alert. Then the walk to the mini PC follows.

## Product hat

P1 wants data good enough to fit and test a model, not just a pretty dashboard. "Done" means three things:
- every source is recorded at a known resolution, including forecasts as issued;
- the recorded data is reachable from Python;
- nothing is lost when the development machine is off or the setup moves to the mini PC.

P1 would complain about months of data with gaps, or forecasts that weren't kept.

## Developer hat

- The development PC isn't on around the clock, so data collected there will have gaps. Collecting on the mini PC early may matter more than setting up Home Assistant twice.
- The Daikin cloud's call budget is shared by every client.
- Tokens for Daikin, Home Assistant and forecast.solar must stay out of git.
- Home Assistant's recorder is a running store, not an archive of test cases.
- Onecta reports only daily energy, so it can't give a heat pump power curve. That limits how well COP and part-load can be fitted (1.1).

## Questions for the principal

- From step 1: which installation type on the development machine and on the mini PC?
- From the developer hat: should the mini PC collect data from now on, with development reading from it?
- From step 4: is daily energy from Daikin enough, or should a power meter go on the heat pump's supply?
- From step 3: where should alerts reach you?
- From step 7: how do we keep every issued forecast (solar and weather)?
- From step 9: how long do you need raw data, and at what resolution?
- From step 10: where do recorded test cases live, and in what format?
- From step 6: is it one roof plane, or several?
- From step 8: leave Zigbee until the mini PC?

## Answers from the principal (2026-11-21)

- Installation type and where to collect data: "let's prototype here". On the mini PC, ideally stock Debian with Home Assistant in Docker "if that makes any sense". This conflicts with the add-on plan; see the requirements' open questions.
- Power meter: "I'd rather get it from the unit somehow"; a USB device for the installer data port was mentioned. Research in progress.
- Resolution: 30 min to 1 h for weather forecasts. The measurement resolution is still open.
- Alerts: "a secondary feature, I'd first like to get the math and integration working". E2 was split: showing the gap stays a must; the alert became E9, should, later.
- Forecast archive (E6): yes. Our own container fetches the solar and weather forecasts and keeps every issue with its timestamp.
- Data store and test-case format (E7): no preference, "whatever works". It will be adjusted from results and tests, in particular the user experience.
- Roof: one plane.
- Zigbee thermometer: no fixed time. The principal gets it from the attic and changes the battery, and will say when it is ready.
- PCB check (X10A, P1/P2): the principal will look at the unit; it decides between ESPAltherma and EKRHH.

## Gaps

- No record of which Home Assistant installation type is used where (steps 1, 3).
- No way to keep issued forecasts (step 7).
- No retention policy for raw data (step 9).
- No defined export route or test-case format (step 10).
- No heat pump power measurement (step 4).

## Acceptance examples

- E6 (added to design/examples.md), from step 7.
- E7, from step 10.
- E8, from step 12.

## Questionnaire

- 2.4 Operating conditions: the development machine's setup (WSL2, NAT, no Docker), and whether the PC runs around the clock.
- 2.6 Performance: data resolution and retention; the call budgets (Daikin 200 per day, forecast.solar 12 per hour per IP) shared by all clients.
- 2.7 Testing, installation and service: the route from Home Assistant into the test cases; backup of the recorded data.
