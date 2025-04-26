# Configuration settings for the monitoring project

# Telegram settings
TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"

# Email settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USERNAME = "your-email@example.com"
EMAIL_PASSWORD = "your-email-password"
EMAIL_RECEIVER = "receiver-email@example.com"

# Monitoring settings
CHECK_INTERVAL_SECONDS = 60  # How often to check servers (in seconds)

# Database settings
DATABASE_URL = "sqlite:///./monitoring.db"
