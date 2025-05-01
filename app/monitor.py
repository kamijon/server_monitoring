import asyncio
import aiohttp
from app.database import SessionLocal, Server, UptimeLog
from app.notifier import send_telegram_message, write_log

async def ping_server(address):
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", address,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.communicate()
        return proc.returncode == 0
    except Exception:
        return False

async def check_port(address, port):
    try:
        reader, writer = await asyncio.open_connection(address, port)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

async def check_http(address):
    try:
        if not address.startswith("http"):
            address = "https://" + address

        async with aiohttp.ClientSession() as session:
            async with session.get(address, timeout=10, allow_redirects=True, ssl=False) as response:
                return response.status == 200
    except Exception:
        return False

async def check_http_keyword(address, keyword):
    try:
        if not address.startswith("http"):
            address = "https://" + address

        async with aiohttp.ClientSession() as session:
            async with session.get(address, timeout=10, allow_redirects=True, ssl=False) as response:
                if response.status == 200:
                    html = await response.text()
                    return keyword.lower() in html.lower()
    except Exception as e:
        print(f"[Keyword Check Error] {address} - {e}")
    return False


async def check_server(server):
    if server.check_type == "ping":
        return await ping_server(server.address)
    elif server.check_type == "port":
        return await check_port(server.address, server.port)
    elif server.check_type == "http":
        return await check_http(server.address)
    elif server.check_type == "http-keyword":
        return await check_http_keyword(server.address, server.keyword)
    return False

async def monitor_loop():
    previous_status = {}
    while True:
        db = SessionLocal()
        servers = db.query(Server).filter(Server.monitoring == True).all()
        for server in servers:
            is_online = await check_server(server)
            new_status = "Online" if is_online else "Offline"

            if server.id in previous_status and previous_status[server.id] != new_status:
                if new_status == "Offline":
                    msg = f"🚨 Server {server.name} ({server.address}) is OFFLINE!"
                else:
                    msg = f"✅ Server {server.name} ({server.address}) is ONLINE"

                send_telegram_message(f"*{msg}*")
                write_log(msg)

                # ✅ UptimeLog
                log_entry = UptimeLog(server_id=server.id, status=new_status)
                db.add(log_entry)

            server.status = new_status
            previous_status[server.id] = new_status

        db.commit()
        db.close()
        await asyncio.sleep(5)

def monitor_servers():
    asyncio.create_task(monitor_loop())
