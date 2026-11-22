# Legionella and the pilot's hot-water regime

Question (requirements 2.2 and 2.11): is a 38 °C minimum with a daily reheat to 54 °C safe in the pilot, with copper piping, a coil-type hygienic storage tank and a possible circulation?

Sources and provenance: a literature search by a sub-agent on 2026-11-21.
- "Abstract" means only the abstract was read (via Europe PMC or PubMed); "full text" means the document was read.
- All DOIs below were checked against Crossref on 2026-11-21: author, year, title and journal match.
- The figures were taken from the sub-agent's reading and have not been re-checked against the texts. Re-check a figure before it sets a limit in code.

## Findings

### Temperature
- Wadowsky et al. 1985, Appl Environ Microbiol 49:1197, doi:10.1128/aem.49.5.1197-1205.1985 (abstract): naturally occurring *L. pneumophila* multiplied between 25 and 37 °C in tap water.
- WHO 2007, *Legionella and the prevention of legionellosis* (full text, ISS copy https://www.epicentro.iss.it/legionellosi/pdf/9241562978_eng.pdf; catalogue https://www.who.int/publications/i/item/9241562978):
  - growth at 25–45 °C, optimum 32–42 °C;
  - decimal reduction time 80–124 min at 50 °C and 2 min at 60 °C;
  - "withstand[s] temperatures of 50 °C for several hours".
- Dennis, Green & Jones 1984, J Appl Bacteriol 56:349, doi:10.1111/j.1365-2672.1984.tb01359.x (abstract). Free-floating cells in the lab; time for a 90 % kill:

  | Temperature | Time |
  |---|---|
  | 50 °C | 111 min |
  | 54 °C | 27 min |
  | 58 °C | 6 min |

  Little loss at 46 °C.
- Rhoads et al. 2015, Microbiome 3:67, doi:10.1186/s40168-015-0134-1 (abstract). Pilot rig at 39–58 °C:
  - at 51 °C, 28.7× less in the recirculating line than at 39 °C;
  - it persisted, and apparently grew, up to 58 °C;
  - a low-use tap had 125× more than high-use taps.

### Copper
- van der Kooij et al. 2005, Water Res 39:2789, doi:10.1016/j.watres.2005.04.075 (abstract):
  - median 1500 CFU/L on copper, against about 4300 CFU/L on stainless steel and PEX;
  - equal on all materials after 2 years: copper "temporarily limited the growth".
- Mathys et al. 2008 (see below): copper systems were more often contaminated; "an inhibitory effect due to copper was not present".
- Song et al. 2021, Environ Sci Technol 55:1759, doi:10.1021/acs.est.0c06804 (abstract): free Cu²⁺ drops sharply above pH 7 or with phosphate or organic matter.
- Song et al. 2023, Water Res 242:120178, doi:10.1016/j.watres.2023.120178 (abstract): only about 1 log reduction even at more than 1.2 mg/L copper and pH below 7. Contributing factors: a copper-tolerant strain and pH effects of the tank's anode.
- Cullom et al. 2020, Pathogens 9:957, doi:10.3390/pathogens9110957 (review, abstract): copper's effect "is inconsistent", and under some conditions copper can even encourage growth.

### Small houses and heater type
- Mathys et al. 2008, Int J Hyg Environ Health 211:179, doi:10.1016/j.ijheh.2007.02.004 (abstract). 452 samples from German single-family houses:
  - instantaneous heaters 0 % positive; storage tanks with circulation 12 % positive, up to 10⁵ CFU/100 mL;
  - water below 46 °C was colonised most often;
  - intermittently raising the temperature above 60 °C, or switching the circulation off for some hours a day, had no influence.
- Roman et al., ACS ES&T Water 5:377, doi:10.1021/acsestwater.4c00894 (abstract; Crossref dates the work 2024, the volume is 2025). Volume at 38–47 °C, at a 48 °C setting:

  | Heater | Warm volume |
  |---|---|
  | with recirculation | 150 L |
  | standard tank | 40 L |
  | tankless heater | about 0.47 L |
- Haller & Ruesch, hk Gebäudetechnik 1/2021 (trade journal, not peer-reviewed; full text). 110 Swiss homes, 24 with *Legionella*:
  - heat-pump tanks tended to have fewer findings at the tank bottom;
  - central cold-water mixing with circulation was a significant factor (p = 0.01);
  - none of the 25 circulation systems reached 55 °C.
- No peer-reviewed study of coil-type ("hygienic") tanks was found.

### Stagnation and circulation
- WHO 2007 (above): heater outlet at least 60 °C, return at least 50 °C, at least 50 °C at the tap within 1 minute. Dead ends are a risk factor.
- Bédard et al. 2015, Water Res 71:244, doi:10.1016/j.watres.2015.01.006 (abstract): in 5 hospitals, systems held above 60 °C at the heater outlet and above 55 °C throughout were negative by culture and by qPCR.
- Ciesielski et al. 1984, Appl Environ Microbiol 48:984, doi:10.1128/aem.48.5.984-987.1984 (abstract): counts fell in tanks kept in use and persisted in stagnant ones; aerators were colonised.

### German rules (for context)
UBA fact sheet on drinking-water hot-water concepts, as of 1 Nov 2023 (full text, https://www.uba.de/system/files/medien/11850/publikationen/factsheet_trinkwarmwasserkonzepte.pdf):
- Testing under the TrinkwV applies to tanks of at least 400 L or more than 3 L of pipe volume, and only for commercial or public use.
- DVGW W 551 requires at least 60 °C at the heater outlet, and nowhere more than 5 K below that.
- One- and two-family houses have no fixed rules. 55–60 °C is recommended; UBA recommends "durchgängig über 55 °C".

## What the evidence says about the pilot's regime

- Small stored volumes and short pipes carry low risk: instantaneous heating was 0 % positive in German single-family houses (Mathys 2008). The coil-type tank is similar in principle but has not been studied.
- The evidence does not support relying on copper. Its effect is temporary or inconsistent, and depends on pH and phosphate.
- At 38 °C, water in the coil and the pipes is near the growth optimum for many hours a day.
- A daily peak of 54 °C gives about 2 logs per hour of holding in the lab, for free-floating cells only; biofilm and amoeba hosts are not covered.
- In the field, intermittent heating did not help (Mathys 2008), and *Legionella* persisted at 51–58 °C (Rhoads 2015).
- A circulation loop greatly increases the warm volume. If one is added, the evidence points to keeping it at 55 °C or more all the time, not cycling it.
- The evidence is thin on coil-type tanks, on daily temperature cycling, and on German homes with heat pumps.

## Could not verify
- The DVGW W 551 text itself (paywalled; known only through the UBA summary).
- Yee & Wadowsky 1982 and Schulze-Röbbecke et al. 1987 (seen only as cited by WHO).
- The full texts of all papers marked "abstract".
- The DOI of the WHO 2007 document.
