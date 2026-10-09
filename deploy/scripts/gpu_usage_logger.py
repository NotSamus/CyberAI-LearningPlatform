#!/usr/bin/env python3
"""Append one CSV row per GPU process per minute: who is on which GPU and how much VRAM.

Run on the host from cron or a systemd timer:
    * * * * * /usr/bin/python3 /opt/cyberai/gpu_usage_logger.py >> /var/log/gpu-usage.csv
Columns: timestamp, gpu_uuid, container (jupyter-<username>--gpu), pid, vram_mib, gpu_util_percent
"""
import csv
import datetime
import re
import subprocess
import sys


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def container_for_pid(pid):
    try:
        cgroup = open(f"/proc/{pid}/cgroup").read()
    except OSError:
        return "host"
    m = re.search(r"([0-9a-f]{64})", cgroup)
    if not m:
        return "host"
    try:
        return sh("docker", "inspect", "--format", "{{.Name}}", m.group(1)).lstrip("/")
    except subprocess.CalledProcessError:
        return m.group(1)[:12]


util = {}
for line in sh("nvidia-smi", "--query-gpu=uuid,utilization.gpu", "--format=csv,noheader,nounits").splitlines():
    uuid, pct = [x.strip() for x in line.split(",")]
    util[uuid] = pct

now = datetime.datetime.now().isoformat(timespec="seconds")
out = csv.writer(sys.stdout)
apps = sh("nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory", "--format=csv,noheader,nounits")
for line in apps.splitlines():
    if not line.strip():
        continue
    uuid, pid, mem = [x.strip() for x in line.split(",")]
    out.writerow([now, uuid, container_for_pid(pid), pid, mem, util.get(uuid, "")])
