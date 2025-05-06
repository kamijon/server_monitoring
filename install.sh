#!/bin/bash

# Exit on error
set -e

echo "Starting installation of Server Monitoring..."

# Update system and install dependencies
echo "Updating system and installing dependencies..."
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-full python3-pip python3-venv git nginx supervisor

# Ensure supervisor is running
echo "Ensuring supervisor is running..."
sudo systemctl enable supervisor
sudo systemctl start supervisor
sudo systemctl status supervisor

# Create application directory
echo "Creating application directory..."
sudo mkdir -p /opt/server-monitoring
sudo chown -R $USER:$USER /opt/server-monitoring

# Clone the repository
echo "Cloning repository..."
git clone https://github.com/kamijon/server-monitoring.git /opt/server-monitoring

# Verify application structure
echo "Verifying application structure..."
if [ ! -d "/opt/server-monitoring/app" ]; then
    echo "Error: Application directory structure is incorrect"
    exit 1
fi

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
cd /opt/server-monitoring
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# Verify Python and pip versions
echo "Verifying Python environment..."
python3 --version
pip --version

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt
pip install uvicorn fastapi sqlalchemy

# Verify uvicorn installation
echo "Verifying uvicorn installation..."
which uvicorn
uvicorn --version

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
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
EOF

# Enable Nginx site
sudo ln -sf /etc/nginx/sites-available/server-monitoring /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# Set up log directory for supervisor
echo "Setting up supervisor log directory..."
sudo mkdir -p /var/log/supervisor
sudo chown -R $USER:$USER /var/log/supervisor

# Create a startup script
echo "Creating startup script..."
cat > /opt/server-monitoring/start.sh << 'EOF'
#!/bin/bash
cd /opt/server-monitoring
source venv/bin/activate
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4 --log-level debug
EOF

# Make the startup script executable
chmod +x /opt/server-monitoring/start.sh

# Create Supervisor configuration
echo "Configuring Supervisor..."
sudo tee /etc/supervisor/conf.d/server-monitoring.conf << EOF
[program:server-monitoring]
directory=/opt/server-monitoring
command=/opt/server-monitoring/start.sh
user=$USER
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/server-monitoring.err.log
stdout_logfile=/var/log/supervisor/server-monitoring.out.log
environment=PYTHONUNBUFFERED=1,PYTHONPATH="/opt/server-monitoring"
stopasgroup=true
killasgroup=true
EOF

# Create database initialization script
echo "Creating database initialization script..."
cat > /opt/server-monitoring/init_db.py << 'EOF'
import os
import sys

# Add the application directory to Python path
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# Verify imports
try:
    from app.database import Base, engine, SessionLocal
    from app.models import User, Server, Category, Log
    from app.auth import get_password_hash
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(f"Current Python path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Directory contents: {os.listdir(app_dir)}")
    if os.path.exists(os.path.join(app_dir, 'app')):
        print(f"App directory contents: {os.listdir(os.path.join(app_dir, 'app'))}")
    sys.exit(1)

def init_db():
    try:
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        # Create admin user if not exists
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
        print("Database initialization completed successfully")
    except Exception as e:
        print(f"Error during database initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
EOF

# Initialize database
echo "Creating database tables and admin user..."
cd /opt/server-monitoring
source venv/bin/activate
export PYTHONPATH=/opt/server-monitoring:$PYTHONPATH
python3 init_db.py

# Reload Supervisor
echo "Starting the application..."
sudo supervisorctl reread
sudo supervisorctl update

# Wait for supervisor to update
sleep 2

# Check supervisor status
echo "Checking supervisor status..."
sudo supervisorctl status

# Start the application
echo "Starting server-monitoring..."
sudo supervisorctl start server-monitoring

# Wait for the application to start
echo "Waiting for the application to start..."
sleep 5

# Check application status
echo "Checking application status..."
sudo supervisorctl status server-monitoring

# Check if the application is running
if ! curl -s http://127.0.0.1:8000 > /dev/null; then
    echo "Error: Application failed to start. Checking logs..."
    echo "=== Supervisor Status ==="
    sudo supervisorctl status
    echo "=== Error Log ==="
    sudo tail -n 50 /var/log/supervisor/server-monitoring.err.log
    echo "=== Output Log ==="
    sudo tail -n 50 /var/log/supervisor/server-monitoring.out.log
    exit 1
fi

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
