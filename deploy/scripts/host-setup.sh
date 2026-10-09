#!/usr/bin/env bash
# Fresh Ubuntu 24.04 server -> Docker with working GPU containers. Run as a sudo-capable user.
set -euo pipefail

# 1. NVIDIA driver (reboot afterwards, then re-run this script; it is idempotent)
if ! command -v nvidia-smi >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y ubuntu-drivers-common
  sudo ubuntu-drivers install
  echo "Driver installed. Reboot, then run this script again."; exit 0
fi
nvidia-smi

# 2. Docker Engine + compose plugin
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

# 3. NVIDIA Container Toolkit
if ! command -v nvidia-ctk >/dev/null; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  sudo apt-get update
  sudo apt-get install -y nvidia-container-toolkit
fi
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4. Proof: a container can see the GPU
sudo docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# 5. Keep the driver loaded between sessions (faster first CUDA call)
sudo nvidia-smi -pm 1 || true

# 6. Firewall: only SSH + web from outside
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable

# 7. Student containers must not reach the school LAN or cloud metadata service.
#    DOCKER-USER is evaluated before Docker's own rules. Persist with iptables-persistent.
for net in 10.0.0.0/8 192.168.0.0/16 169.254.0.0/16; do
  sudo iptables -C DOCKER-USER -s 172.16.0.0/12 -d "$net" -j DROP 2>/dev/null \
    || sudo iptables -I DOCKER-USER -s 172.16.0.0/12 -d "$net" -j DROP
done

echo "Host ready."
