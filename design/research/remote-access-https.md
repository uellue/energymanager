# Remote access and HTTPS for Home Assistant

Question: how can the principal open the dashboard from the phone, at home and on the road, without browser warnings and without credentials crossing the home network unencrypted? Home Assistant runs in Docker on the automation PC, behind a FRITZ!Box (assumed from the address range, not checked), with the domain `uellue.de` at gc-web.de.

Provenance: the session on 2026-11-22. Tailscale facts from tailscale.com/kb/1153/enabling-https, /kb/1312/serve, /pricing and the Docker pages, read that day by a sub-agent; Caddy and module facts from GitHub (caddyserver/caddy release v2.11.9 of 2026-11-05; caddy-dns has a `desec` module and none for gc-web). Other statements are the session's knowledge, marked (not checked).

## Decision (principal, 2026-11-22)

- Remote access through a VPN, not by opening a port to Home Assistant.
- HTTPS for now from our own certificate authority (option D). Tailscale (option A) is noted as the simpler path if the own authority proves cumbersome, above all on the phone.

## Options

| | Option | Effort | HTTPS without warning | Remote | Depends on |
|---|---|---|---|---|---|
| A | Tailscale: `tailscale serve` gives `https://<machine>.<tailnet>.ts.net` with a Let's Encrypt certificate, and is the VPN at the same time | low | yes, on every device with Tailscale | yes | Tailscale (company); Personal plan free, "only suitable for non-commercial use", up to 6 users, unlimited devices |
| B | FRITZ!Box WireGuard for the VPN; Caddy with Let's Encrypt via DNS-01 for `ha.uellue.de` (A record to the PC's LAN address), the challenge delegated by CNAME to deSEC because gc-web has no Caddy module; DNS rebind exception on the router | high | yes | yes, through the router's VPN | deSEC, the domain's DNS, Caddy |
| C | Home Assistant Cloud (Nabu Casa) | very low | only for the remote address | yes | a subscription (about €7.50 per month, not checked) |
| D | Own certificate authority, certificate served by Home Assistant itself; remote through the router's WireGuard | medium | only on devices that trust the authority | through the router's VPN | none new (openssl) |
| — | Port forwarding with DynDNS and Let's Encrypt | medium | yes | yes, directly | rejected: the login page faces the internet, on the machine that will one day control the heat pump |

Notes:

- A: machine names are published in the public Certificate Transparency log ("Do not enable the HTTPS feature if any of your machine names contain sensitive information"). Each device needs the Tailscale app, at home too, if HTTPS is the only way in. Certificates from `tailscale cert` are renewed by the user; Serve's own handling is implied by its docs, not stated.
- B: the A record publishes a LAN address, which is harmless but visible. The FRITZ!Box's DNS rebind protection must exempt the name.
- D: Android does not let apps trust user-installed certificate authorities unless the app opts in. Tried on 2026-11-22: the Home Assistant app on Android, Chrome and Edge on Windows, and Firefox on Windows accept the authority. Apple limits certificates from user-trusted authorities to 825 days; the script issues 397.
- D, as built (2026-11-22): `tools/local_tls.sh`. An independent review found that name constraints restrict only the name forms they list, so the first version's authority could still have signed e-mail, URI and IPv6 names and certificates for any purpose. The authority was replaced the same day by one limited to server certificates (extended key usage) with e-mail, URI and IPv6 excluded; the old key was deleted.
