#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root${NC}"
    exit 1
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed${NC}"
    exit 1
fi

# Create installation directory
INSTALL_DIR="/opt/server-monitoring"
echo -e "${GREEN}Creating installation directory...${NC}"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Download the application files
echo -e "${GREEN}Downloading application files...${NC}"
curl -L https://github.com/kamijon/server-monitoring/archive/main.tar.gz | tar xz --strip-components=1

# Create virtual environment
echo -e "${GREEN}Setting up Python virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -r requirements.txt

# Create systemd service files
echo -e "${GREEN}Creating systemd service files...${NC}"

# Main application service
cat > /etc/systemd/system/server-monitoring.service << EOL
[Unit]
Description=Server Monitoring Application
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Sync service
cat > /etc/systemd/system/sync-ips.service << EOL
[Unit]
Description=Server List Sync Service
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python sync_ips.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Sync timer
cat > /etc/systemd/system/sync-ips.timer << EOL
[Unit]
Description=Run sync-ips every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit=sync-ips.service

[Install]
WantedBy=timers.target
EOL

# Monitor service
cat > /etc/systemd/system/monitor-servers.service << EOL
[Unit]
Description=Server Monitoring Service
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python -m app.monitor
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Set permissions
echo -e "${GREEN}Setting permissions...${NC}"
chown -R root:root $INSTALL_DIR
chmod -R 755 $INSTALL_DIR

# Enable and start services
echo -e "${GREEN}Enabling and starting services...${NC}"
systemctl daemon-reload
systemctl enable --now server-monitoring.service
systemctl enable --now monitor-servers.service
systemctl enable --now sync-ips.timer

# Create initial admin user
echo -e "${GREEN}Creating initial admin user...${NC}"
source venv/bin/activate
python -c "
from app.database import SessionLocal, User
import bcrypt
db = SessionLocal()
if not db.query(User).first():
    hashed = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
    admin = User(username='admin', password=hashed.decode('utf-8'), is_admin=True)
    db.add(admin)
    db.commit()
db.close()
"

echo -e "${GREEN}✅ Installation completed!${NC}"
echo -e "${GREEN}Visit your server at: http://<your-server-ip>:8000${NC}"
echo -e "${GREEN}Default admin credentials:${NC}"
echo -e "${GREEN}Username: admin${NC}"
echo -e "${GREEN}Password: admin123${NC}"
echo -e "${GREEN}Please change the default password after first login!${NC}"