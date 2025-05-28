#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment process...${NC}"

# 1. Push to GitHub
echo -e "\n${GREEN}Pushing changes to GitHub...${NC}"
git add .
git commit -m "feat: update server monitoring system"
git push origin main

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Successfully pushed to GitHub${NC}"
else
    echo -e "${RED}Failed to push to GitHub${NC}"
    exit 1
fi

# 2. Deploy to VPS
echo -e "\n${GREEN}Deploying to VPS...${NC}"

# Copy files to VPS
echo "Copying files to VPS..."
scp -r app/* root@157.180.70.164:/opt/server-monitoring/app/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Successfully copied files to VPS${NC}"
else
    echo -e "${RED}Failed to copy files to VPS${NC}"
    exit 1
fi

# Restart the application
echo "Restarting application..."
ssh root@157.180.70.164 "cd /opt/server-monitoring && source venv/bin/activate && pkill -9 -f uvicorn && sleep 2 && PYTHONPATH=/opt/server-monitoring uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug &"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Successfully restarted application${NC}"
else
    echo -e "${RED}Failed to restart application${NC}"
    exit 1
fi

echo -e "\n${GREEN}Deployment completed successfully!${NC}" 