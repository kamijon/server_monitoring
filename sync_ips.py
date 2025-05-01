import requests
from bs4 import BeautifulSoup
from app.database import SessionLocal, Server
from app.notifier import write_log, send_telegram_message

# مشخصات لاگین
LOGIN_URL = "https://xwork.app/"
IP_LIST_URL = "https://xwork.app/tools/list-of-our-ips.php"
USERNAME = "tomas"
PASSWORD = "Tomas#@1421982)@S"

def fetch_remote_ips():
    with requests.Session() as session:
        # مرحله لاگین
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "redirect": "//xwork.app/tools/list-of-our-ips.php"
        }
        response = session.post(LOGIN_URL, data=payload, timeout=10)
        if response.status_code != 200:
            raise Exception("Login failed!")

        # حالا باید به صفحه آی‌پی‌ها بریم
        response = session.get(IP_LIST_URL, timeout=10)
        if response.status_code != 200:
            raise Exception("Cannot fetch IP list")

        soup = BeautifulSoup(response.text, "html.parser")
        pre_tag = soup.find("pre")
        if not pre_tag:
            raise Exception("<pre> tag not found in IP list page")

        raw_ips = pre_tag.text.strip().splitlines()
        return set(ip.strip() for ip in raw_ips if ip.strip())

def sync_ips():
    remote_ips = fetch_remote_ips()

    db = SessionLocal()
    current_servers = db.query(Server).all()
    current_ips = set(server.address for server in current_servers)

    removed_ips = current_ips - remote_ips
    added_ips = remote_ips - current_ips

    logs = []

    for server in current_servers:
        if server.address in removed_ips:
            logs.append(f"❌ Removed server {server.name} ({server.address})")
            db.delete(server)

    for ip in added_ips:
        new_server = Server(name=f"Auto-{ip}", address=ip, status="Unknown", check_type="ping", monitoring=True)
        db.add(new_server)
        logs.append(f"➕ Added new server {ip}")

    db.commit()
    db.close()

    for log in logs:
        write_log(log)
        send_telegram_message(f"*{log}*")

    return logs

if __name__ == "__main__":
    changes = sync_ips()
    for line in changes:
        print(line)
