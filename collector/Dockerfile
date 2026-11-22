FROM python:3.15-slim-trixie
# rctclient: the RCT inverter protocol (GPL-3.0), approved 2026-11-22 (design C2).
RUN pip install --no-cache-dir rctclient==0.0.6 && useradd --uid 1000 --create-home collector
COPY collector.py /app/collector.py
USER collector
CMD ["python3", "-I", "/app/collector.py"]
