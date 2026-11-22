# Stakeholders

Personas for walk-throughs and hallway tests. The pilot is built for P1 first, to get the maths, physics, technology and core functionality right. P2 and P3 are for later refinement, rollout and productification; they are kept in mind now, not designed for (principal, 2026-11-21).

## P1 Pilot operator: the principal

- **Who:** owner of the pilot house. Knows the heat pump, the house's physics and numerical optimisation (JAX, optimistix) well. New to Home Assistant.
- **Wants:** reliable recorded data from all sources, one dashboard, and a model and optimizer that verifiably save grid energy without stressing the floor or compromising hot-water hygiene.
- **Has:** a Windows PC with WSL2 (development and testing), a Linux mini PC for later, a Daikin Altherma with Onecta, an RCT inverter and battery, a forecast.solar estimate, maybe a Zigbee thermometer later.
- **Would never read:** marketing material and generic Home Assistant beginner guides beyond what is needed.
- **Source:** the principal, interview of 2026-11-21. Real.

## P2 Home Assistant user elsewhere (later)

- **Who:** runs Home Assistant already; has a heat pump, PV and a variable tariff. Installs this from the add-on store.
- **Wants:** lower bills and less grid import, with comfort unchanged and no risk to the house.
- **Knows:** their own devices and Home Assistant's interface. Doesn't read code or the physics behind it.
- **Would never read:** the model's equations.
- **Source:** simulated by the agent; no real P2 met yet.

## P3 Household member (later)

- **Who:** lives in the house.
- **Wants:** to be comfortable, with no fuss.
- **Does:** reports "too warm" or "too chilly", and may glance at the dashboard.
- **Would never read:** docs or settings.
- **Source:** simulated by the agent.

## Owners of what it touches

- At each site, the person running it authorises writes to devices (later) and is informed of the risks and that the project accepts no liability. In the pilot, that is the principal.
- The vendors' cloud services (Daikin Onecta, forecast.solar) are interfaces with their own limits, not personas.
