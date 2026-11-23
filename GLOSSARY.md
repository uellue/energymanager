# Glossary

Terms as this project uses them. Where the field has an established term, it is used and its source named; Home Assistant's entity model is the vocabulary for entities (requirements 2.12).

- **Solar headroom**: the extra energy that can be used within a time window without more grid import, given the plan for battery and heat pump; in kWh per window (the next hour, in 15 min steps). It is the marginal figure: it counts energy the battery could forgo now and still recharge later. No established term exists; chosen by the principal on 2026-11-23 (issue uellue-bot/energymanager#12). Not "PV surplus", which in the field means power exported right now, and not "free energy", a fixed term in thermodynamics.
- **Energy signature**: the heat a building needs per period plotted over outdoor temperature; here from the heat pump's own figures. Used as the weather-normalised baseline (requirements S4).
- **Baseline**: today's operation of the pilot (heating curve with shift schedule, hot-water schedule), against which the optimizer's savings are measured (requirements S4).
- **Theoretical seasonal COP**: the heat pump's datasheet characteristics (COP at which outdoor temperature, leaving-water temperature and load) applied to the house's actual heat demand and weather; the best the unit can reach in this house. Not the label SCOP, which is rated under standard conditions (requirements S4).
- **Operative temperature**: the temperature a person feels, combining air and surrounding surfaces (radiation); what the model's room node stands for (requirements 2.7).
- **Leaving water**: the water leaving the heat pump towards the floor heating or the tank (Daikin: "leaving water", Onecta: "Austrittswasser"); its temperature is what the heating curve sets.
- **Shift**: an offset in °C added to the weather-dependent curve's leaving-water value, set by hand or by a schedule; limited by the unit's minimum and maximum ([9-01], [9-00]).
- **Backup heater**: the heat pump's resistive heater (COP 1); runs when the compressor cannot, for example with leaving water below 25 °C on the pilot.
- **Performance ratio (PR)**: final yield over reference yield of a PV system, Y_f / Y_r (IEC 61724-1:2021, clause 13.6); the temperature-corrected form in clause 14.3.2. Used for long-term array health (issue uellue-bot/energymanager#4).
- **Equivalent cell temperature**: a PV cell temperature derived from the module's voltage (IEC 60904-5, from V_oc); this project derives it from the string's MPP voltage instead (issue uellue-bot/energymanager#4).
