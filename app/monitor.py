import asyncio
import aiohttp
import socket
import subprocess

# Ping check using system command
async def ping_server(ip_or_url):
    try:
        process = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", ip_or_url,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        await process.communicate()
        return process.returncode == 0
    except Exception:
        return False

# Port check using TCP connection
async def check_port(ip_or_url, port):
    try:
        reader, writer = await asyncio.open_connection(ip_or_url, port)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False

# HTTP check using aiohttp
async def check_http(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                return response.status == 200
    except Exception:
        return False

# Main function to check server based on its type
async def check_server(server):
    if server.check_type == "ping":
        return await ping_server(server.ip_or_url)
    elif server.check_type == "port":
        if server.port:
            return await check_port(server.ip_or_url, server.port)
        else:
            return False
    elif server.check_type == "http":
        return await check_http(server.ip_or_url)
    else:
        return False
