import asyncio
import aiohttp
from app.database import SessionLocal, Server, UptimeLog
from app.notifier import send_telegram_message, write_log

async def ping_server(address):
    try:
        # Remove any protocol prefix for ping
        clean_address = address.replace("http://", "").replace("https://", "")
        print(f"[Ping Check] Testing: {clean_address}")
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", clean_address,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"[Ping Error] {clean_address} - {stderr.decode()}")
        return proc.returncode == 0
    except Exception as e:
        print(f"[Ping Error] {address} - {e}")
        return False

async def check_port(address, port):
    if port is None or port == "noport":
        return await ping_server(address)
    try:
        # Remove any protocol prefix for port check
        clean_address = address.replace("http://", "").replace("https://", "")
        print(f"[Port Check] Testing: {clean_address}:{port}")
        reader, writer = await asyncio.open_connection(clean_address, port)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        print(f"[Port Check Error] {address}:{port} - {e}")
        return False

async def check_http(address, port=None):
    try:
        # For port 80, always use HTTP
        if port == 80:
            protocol = "http"
        # For port 443, always use HTTPS
        elif port == 443:
            protocol = "https"
        # For other ports, use the protocol from the address if present
        else:
            protocol = "https" if address.startswith("https://") else "http"

        # Clean the address
        clean_address = address.replace("http://", "").replace("https://", "")
        
        # Construct the URL
        url = f"{protocol}://{clean_address}"
        if port and port not in [80, 443]:
            url = f"{url}:{port}"

        print(f"[HTTP Check] Testing URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10, allow_redirects=True, ssl=False) as response:
                if response.status != 200:
                    print(f"[HTTP Error] {url} - Status: {response.status}")
                return response.status == 200
    except Exception as e:
        print(f"[HTTP Check Error] {address} - {e}")
        return False

async def check_http_keyword(address, port=None, keyword=None):
    try:
        # For port 80, always use HTTP
        if port == 80:
            protocol = "http"
        # For port 443, always use HTTPS
        elif port == 443:
            protocol = "https"
        # For other ports, use the protocol from the address if present
        else:
            protocol = "https" if address.startswith("https://") else "http"

        # Clean the address
        clean_address = address.replace("http://", "").replace("https://", "")
        
        # Construct the URL
        url = f"{protocol}://{clean_address}"
        if port and port not in [80, 443]:
            url = f"{url}:{port}"

        print(f"[Keyword Check] Testing URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10, allow_redirects=True, ssl=False) as response:
                if response.status == 200:
                    html = await response.text()
                    found = keyword.lower() in html.lower()
                    if not found:
                        print(f"[Keyword Error] {url} - Keyword '{keyword}' not found")
                    return found
                else:
                    print(f"[Keyword Error] {url} - Status: {response.status}")
                    return False
    except Exception as e:
        print(f"[Keyword Check Error] {address} - {e}")
        return False

async def check_server(server):
    try:
        print(f"\n[Server Check] {server.name} ({server.address}:{server.port}) - Type: {server.check_type}")
        
        # For servers with port 80, force HTTP check
        if server.port == 80:
            if server.check_type == "http-keyword":
                return await check_http_keyword(server.address, server.port, server.keyword)
            return await check_http(server.address, server.port)
        # For servers with noport, use ping
        elif server.port is None or server.port == "noport":
            return await ping_server(server.address)
        # For other servers, use their configured check type
        elif server.check_type == "ping":
            return await ping_server(server.address)
        elif server.check_type == "port":
            return await check_port(server.address, server.port)
        elif server.check_type == "http":
            return await check_http(server.address, server.port)
        elif server.check_type == "http-keyword":
            return await check_http_keyword(server.address, server.port, server.keyword)
        return False
    except Exception as e:
        print(f"[Server Check Error] {server.name} ({server.address}) - {e}")
        return False

async def monitor_loop():
    previous_status = {}
    while True:
        try:
            db = SessionLocal()
            servers = db.query(Server).filter(Server.monitoring == True).all()
            for server in servers:
                is_online = await check_server(server)
                new_status = "Online" if is_online else "Offline"

                if server.id in previous_status and previous_status[server.id] != new_status:
                    if new_status == "Offline":
                        msg = f"🚨 Server {server.name} ({server.address}:{server.port if server.port else 'noport'}) is OFFLINE!"
                    else:
                        msg = f"✅ Server {server.name} ({server.address}:{server.port if server.port else 'noport'}) is ONLINE"

                    send_telegram_message(f"*{msg}*")
                    write_log(msg)

                    # Log status change
                    log_entry = UptimeLog(server_id=server.id, status=new_status)
                    db.add(log_entry)

                server.status = new_status
                previous_status[server.id] = new_status

            db.commit()
            db.close()
        except Exception as e:
            print(f"Error in monitor loop: {e}")
            try:
                db.close()
            except:
                pass
        await asyncio.sleep(5)

def monitor_servers():
    asyncio.create_task(monitor_loop())
