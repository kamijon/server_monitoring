#!/bin/bash

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Updating and upgrading server...${NC}"
apt update && apt upgrade -y

echo -e "${GREEN}Installing Python3, pip3, and git...${NC}"
apt install -y python3 python3-pip git curl

echo -e "${GREEN}Cloning the project from GitHub...${NC}"
cd /opt
git clone https://github.com/kamijon/server-monitoring.git

echo -e "${GREEN}Installing Python dependencies...${NC}"
cd server-monitoring
pip3 install -r requirements.txt

echo -e "${GREEN}Creating systemd service...${NC}"
cat > /etc/systemd/system/server-monitoring.service << EOL
[Unit]
Description=Server Monitoring FastAPI App
After=network.target

[Service]
User=root
WorkingDirectory=/opt/server-monitoring
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOL

echo -e "${GREEN}Reloading systemd and starting service...${NC}"
systemctl daemon-reload
systemctl enable server-monitoring
systemctl start server-monitoring

echo -e "${GREEN}Installation complete. Server Monitoring is now running!${NC}"

