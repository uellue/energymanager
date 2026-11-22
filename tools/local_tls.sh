#!/usr/bin/env bash
# Own certificate authority and server certificate for Home Assistant on the
# home network (design/research/remote-access-https.md, option D).
#
# Usage: tools/local_tls.sh DIR NAME [NAME...]
#   DIR   where to keep the files, outside the repository: "$EM_DATA_DIR/tls"
#   NAME  each host name or IPv4 address the browser will use; the first is the
#         certificate's common name. Example: automation.fritz.box localhost 127.0.0.1
#
# The first run creates the authority in DIR/ca (key readable by the owner only,
# valid 10 years). The authority may sign only server certificates (TLS), and
# only for these names, their subdomains (x.automation.fritz.box) and these
# IPv4 addresses: no other IP addresses, no IPv6, no e-mail addresses or URIs
# (X.509 extended key usage and name constraints). Every run issues a fresh
# server certificate in DIR/server, valid 397 days. Files are replaced only
# after the new certificate verifies. To change the names, move DIR/ca away and
# run again; every device then has to trust the new authority.
set -euo pipefail

usage="usage: $0 DIR NAME [NAME...]"
dir="${1:?$usage}"
shift
[ "$#" -ge 1 ] || { echo "$usage" >&2; exit 2; }

ipv4='^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$'
label='[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?'
host="^$label(\\.$label)*\$"

san=() constraints=() has_ip=no
for name in "$@"; do
    if [[ "$name" =~ $ipv4 ]]; then
        san+=("IP:$name")
        constraints+=("permitted;IP:$name/255.255.255.255")
        has_ip=yes
    elif [[ "$name" =~ ^[0-9.]+$ ]]; then
        echo "$name: not a valid IPv4 address" >&2; exit 2
    elif [[ "$name" == *:* ]]; then
        echo "$name: IPv6 addresses are not supported" >&2; exit 2
    elif [[ "$name" =~ $host ]] && [ "${#name}" -le 253 ]; then
        san+=("DNS:$name")
        constraints+=("permitted;DNS:$name")
    else
        echo "$name: not a host name (lower case letters, digits, hyphens and dots, no leading dot or wildcard) or an IPv4 address" >&2
        exit 2
    fi
done
[ "${#1}" -le 64 ] || { echo "$1: the first name becomes the common name and may have at most 64 characters" >&2; exit 2; }
# No e-mail addresses or URIs (only the reserved domain .invalid), no IPv6, and
# no IPv4 unless listed: name constraints restrict only the name forms they name.
constraints+=("permitted;email:.invalid" "permitted;URI:.invalid" "excluded;IP:::/::")
[ "$has_ip" = yes ] || constraints+=("excluded;IP:0.0.0.0/0.0.0.0")
join() { local IFS=,; echo "$*"; }
# Runs openssl quietly; shows its messages only when it fails.
quiet() { local out; out="$("$@" 2>&1)" || { echo "$out" >&2; return 1; }; }

umask 077
mkdir -p "$dir/ca" "$dir/server"
# Containers read the folder and ca.crt (README, "Collector"); the keys stay owner-only.
chmod 755 "$dir" "$dir/ca"
tmp="$(mktemp -d "$dir/.new.XXXXXX")"
trap 'rm -rf -- "${tmp:?}"' EXIT

if [ -e "$dir/ca/ca.key" ] && [ -e "$dir/ca/ca.crt" ]; then
    ca_key="$dir/ca/ca.key" ca_crt="$dir/ca/ca.crt" new_ca=no
elif [ -e "$dir/ca/ca.key" ] || [ -e "$dir/ca/ca.crt" ]; then
    echo "$dir/ca holds only half an authority; move it away and run again" >&2; exit 1
else
    ca_key="$tmp/ca.key" ca_crt="$tmp/ca.crt" new_ca=yes
    quiet openssl req -x509 -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
        -keyout "$ca_key" -out "$ca_crt" -days 3650 \
        -subj "/CN=energymanager home CA" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        -addext "extendedKeyUsage=serverAuth" \
        -addext "nameConstraints=critical,$(join "${constraints[@]}")"
fi

if ! openssl x509 -noout -checkend $((397 * 86400)) -in "$ca_crt" >/dev/null; then
    echo "The authority expires within 397 days; move $dir/ca away and run again" >&2; exit 1
fi

printf '%s\n' \
    "basicConstraints=critical,CA:FALSE" \
    "keyUsage=critical,digitalSignature" \
    "extendedKeyUsage=serverAuth" \
    "subjectAltName=$(join "${san[@]}")" > "$tmp/server.ext"
quiet openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
    -keyout "$tmp/server.key" -subj "/CN=$1" -out "$tmp/server.csr"
quiet openssl x509 -req -in "$tmp/server.csr" -CA "$ca_crt" -CAkey "$ca_key" -days 397 \
    -extfile "$tmp/server.ext" -out "$tmp/server.crt"
if ! openssl verify -purpose sslserver -CAfile "$ca_crt" "$tmp/server.crt" >/dev/null; then
    echo "The server certificate does not verify against the authority in $dir/ca;" \
         "if the names changed, move $dir/ca away and run again" >&2
    exit 1
fi

if [ "$new_ca" = yes ]; then
    chmod 644 "$ca_crt"
    mv -- "$ca_key" "$dir/ca/ca.key"
    mv -- "$ca_crt" "$dir/ca/ca.crt"
    echo "Created the authority: $dir/ca/ca.crt (copy this file to each device and trust it there)"
fi
mv -f -- "$tmp/server.key" "$dir/server/server.key"
mv -f -- "$tmp/server.crt" "$dir/server/server.crt"

echo "Server certificate: $dir/server/server.crt, valid until $(openssl x509 -noout -enddate -in "$dir/server/server.crt" | cut -d= -f2)"
echo "Authority fingerprint (compare on each device): $(openssl x509 -noout -fingerprint -sha256 -in "$dir/ca/ca.crt" | cut -d= -f2)"
