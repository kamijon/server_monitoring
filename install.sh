#!/bin/bash

# Exit on error
set -e

echo "Starting installation of Server Monitoring..."

# Update system and install dependencies
echo "Updating system and installing dependencies..."
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-full python3-pip python3-venv git nginx supervisor

# Create application directory
echo "Creating application directory..."
sudo mkdir -p /opt/server-monitoring
sudo chown $USER:$USER /opt/server-monitoring

# Clone the repository
echo "Cloning repository..."
git clone https://github.com/kamijon/server-monitoring.git /opt/server-monitoring

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
cd /opt/server-monitoring
python3 -m venv venv --clear
source venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt

# Create log file and set permissions
echo "Setting up log file..."
sudo touch /opt/server-monitoring/server.log
sudo chown $USER:$USER /opt/server-monitoring/server.log

# Create Nginx configuration
echo "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/server-monitoring << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/server-monitoring /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# Create Supervisor configuration
echo "Configuring Supervisor..."
sudo tee /etc/supervisor/conf.d/server-monitoring.conf << EOF
[program:server-monitoring]
directory=/opt/server-monitoring
command=/opt/server-monitoring/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
user=$USER
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/server-monitoring.err.log
stdout_logfile=/var/log/supervisor/server-monitoring.out.log
environment=PYTHONUNBUFFERED=1
EOF

# Create database tables
echo "Creating database tables..."
cd /opt/server-monitoring
source venv/bin/activate
python3 -c "
from app.database import Base, engine
from app.models import User, Server, Category, Log
Base.metadata.create_all(bind=engine)
"

# Create initial admin user
echo "Creating initial admin user..."
python3 -c "
from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash

db = SessionLocal()
if not db.query(User).first():
    admin = User(
        username='admin',
        password_hash=get_password_hash('admin123'),
        is_admin=True
    )
    db.add(admin)
    db.commit()
db.close()
"

# Reload Supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start server-monitoring

# Configure firewall
echo "Configuring firewall..."
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

echo "Installation completed successfully!"
echo "The application should now be running at http://your-server-ip"
echo "Default login credentials:"
echo "Username: admin"
echo "Password: admin123"
echo "To check the status, run: sudo supervisorctl status server-monitoring"
echo "To view logs, run: sudo tail -f /var/log/supervisor/server-monitoring.out.log"
