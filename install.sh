#!/bin/bash

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Updating system...${NC}"
apt update && apt upgrade -y

echo -e "${GREEN}Installing Python3, pip, git, curl...${NC}"
apt install -y python3 python3-pip git curl

PYVER=$(python3 --version | awk '{print $2}' | cut -d. -f1,2)
echo -e "${GREEN}Detected Python version: $PYVER${NC}"

echo -e "${GREEN}Installing python$PYVER-venv...${NC}"
apt install -y python$PYVER-venv

echo -e "${GREEN}Cloning the server-monitoring project...${NC}"
cd /opt
rm -rf server-monitoring
git clone https://github.com/kamijon/server-monitoring.git
cd server-monitoring

echo -e "${GREEN}Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

echo -e "${GREEN}Installing Python dependencies...${NC}"
pip install --upgrade pip
pip install fastapi uvicorn aiohttp sqlalchemy jinja2 requests python-multipart itsdangerous bcrypt

echo -e "${GREEN}Creating server-monitoring.service...${NC}"
cat <<EOF > /etc/systemd/system/server-monitoring.service
[Unit]
Description=Server Monitoring FastAPI App
After=network.target

[Service]
User=root
WorkingDirectory=/opt/server-monitoring
ExecStart=/opt/server-monitoring/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}Creating sync-ips.service and timer...${NC}"
cat <<EOF > /etc/systemd/system/sync-ips.service
[Unit]
Description=Sync server IPs from xwork.app

[Service]
Type=oneshot
WorkingDirectory=/opt/server-monitoring
ExecStart=/opt/server-monitoring/venv/bin/python3 /opt/server-monitoring/sync_ips.py
EOF

cat <<EOF > /etc/systemd/system/sync-ips.timer
[Unit]
Description=Run sync-ips.service every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo -e "${GREEN}Reloading systemd and enabling services...${NC}"
systemctl daemon-reexec
systemctl daemon-reload
systemctl enable --now server-monitoring
systemctl enable --now sync-ips.timer

echo -e "${GREEN}✅ Installation completed!${NC}"
echo -e "${GREEN}Visit your server at: http://<your-server-ip>:8000${NC}"
