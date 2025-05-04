install service: bash <(curl -s https://raw.githubusercontent.com/kamijon/server-monitoring/main/install.sh)

Restart Service: systemctl restart server-monitoring

Stop Service: systemctl start server-monitoring

Server Status: systemctl status server-monitoring

Reload : systemctl daemon-reload
