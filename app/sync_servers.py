import requests
import json
from app.database import SessionLocal, Server, Category
from app.notifier import write_log, send_telegram_message

# Login credentials
LOGIN_URL = "https://xwork.app/"
IP_LIST_URL = "https://xwork.app/api/feed/etc/server_list/"
USERNAME = "tomas"
PASSWORD = "Tomas#@1421982)@S"

def fetch_remote_servers():
    with requests.Session() as session:
        # Login step
        payload = {
            "username": USERNAME,
            "password": PASSWORD,
            "redirect": "//xwork.app/api/feed/etc/server_list/"
        }
        print("Attempting to login...")
        response = session.post(LOGIN_URL, data=payload, timeout=10)
        if response.status_code != 200:
            print(f"Login failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception("Login failed!")

        print("Login successful, fetching server list...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Cookie': response.headers.get('Set-Cookie', '')
        }
        response = session.get(IP_LIST_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch server list with status code: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception("Cannot fetch server list")

        try:
            print("Parsing response...")
            data = response.json()
            print(f"Raw response: {json.dumps(data, indent=2)}")
            
            if not isinstance(data, dict):
                raise Exception("Invalid response format: expected a dictionary")
            
            # Extract servers with their names and addresses
            servers = []
            for service_type, service_servers in data.items():
                print(f"\nProcessing {service_type} servers:")
                for address, name in service_servers.items():
                    try:
                        if ':noport' in address:
                            ip = address.replace(':noport', '')
                            port = None
                        else:
                            ip, port = address.split(':')
                        
                        server_info = {
                            'name': name,
                            'address': ip,
                            'port': port,
                            'type': service_type
                        }
                        servers.append(server_info)
                        print(f"Added server: {name} ({ip}:{port})")
                    except Exception as e:
                        print(f"Error processing server {address}: {str(e)}")
            
            if not servers:
                raise Exception("No servers found in the response")
            
            print(f"\nTotal servers found: {len(servers)}")
            return servers
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            print(f"Response text: {response.text}")
            raise Exception("Failed to parse JSON response")
        except Exception as e:
            print(f"Error processing response: {str(e)}")
            raise Exception(f"Error processing response: {str(e)}")

def sync_servers():
    try:
        print("Starting server sync...")
        remote_servers = fetch_remote_servers()

        db = SessionLocal()
        
        # Get or create categories
        categories = {}
        for server_type in ['main', 'lb', 'proxy', 'relay', 'codec', 'etc', 'lfn', 'ns', 'mail', 'web', 'vodn', 'vods', 'vnc', 'guy_valid']:
            category = db.query(Category).filter(Category.name == server_type).first()
            if not category:
                print(f"Creating category: {server_type}")
                category = Category(name=server_type, description=f"{server_type} servers")
                db.add(category)
                db.commit()
            categories[server_type] = category
        
        current_servers = db.query(Server).all()
        # Use both address and port as the key
        current_servers_dict = {f"{server.address}:{server.port if server.port else 'noport'}": server for server in current_servers}
        print(f"Found {len(current_servers)} existing servers")

        changes_detected = False
        logs = []

        # Update or add servers
        for remote_server in remote_servers:
            server_key = f"{remote_server['address']}:{remote_server['port'] if remote_server['port'] else 'noport'}"
            if server_key in current_servers_dict:
                # Update existing server only if it's not manually added
                server = current_servers_dict[server_key]
                if not server.is_manual and (server.name != remote_server['name'] or server.category_id != categories[remote_server['type']].id):
                    old_name = server.name
                    server.name = remote_server['name']
                    server.category_id = categories[remote_server['type']].id
                    log_msg = f"🔄 Server configuration changed:\n"
                    log_msg += f"Name: {old_name} → {server.name}\n"
                    log_msg += f"Type: {remote_server['type']}\n"
                    log_msg += f"Address: {server.address}:{server.port if server.port else 'noport'}"
                    logs.append(log_msg)
                    changes_detected = True
                    print(f"Updated server: {server.name}")
            else:
                # Add new server
                new_server = Server(
                    name=remote_server['name'],
                    address=remote_server['address'],
                    port=remote_server['port'],
                    status="Unknown",
                    check_type="port" if remote_server['port'] else "ping",
                    monitoring=True,
                    category_id=categories[remote_server['type']].id,
                    is_manual=False  # Mark as auto-added
                )
                db.add(new_server)
                log_msg = f"➕ New server added:\n"
                log_msg += f"Name: {new_server.name}\n"
                log_msg += f"Type: {remote_server['type']}\n"
                log_msg += f"Address: {new_server.address}:{new_server.port if new_server.port else 'noport'}"
                logs.append(log_msg)
                changes_detected = True
                print(f"Added new server: {new_server.name}")

        # Remove servers that are no longer in the remote list, but only if they're not manually added
        remote_server_keys = {f"{server['address']}:{server['port'] if server['port'] else 'noport'}" for server in remote_servers}
        for server_key, server in current_servers_dict.items():
            if server_key not in remote_server_keys and not server.is_manual:
                log_msg = f"❌ Server removed:\n"
                log_msg += f"Name: {server.name}\n"
                log_msg += f"Type: {server.category.name}\n"
                log_msg += f"Address: {server.address}:{server.port if server.port else 'noport'}"
                logs.append(log_msg)
                changes_detected = True
                print(f"Removed server: {server.name}")
                db.delete(server)

        db.commit()
        db.close()

        # Only write to local log if there were changes
        if changes_detected:
            for log in logs:
                write_log(log)
                try:
                    send_telegram_message(log)
                except Exception as e:
                    print(f"Telegram alert error: {str(e)}")
            print("Sync completed with changes")
            return logs
        print("Sync completed with no changes")
        return []
    except Exception as e:
        print(f"Error during sync: {str(e)}")
        write_log(f"Error during sync: {str(e)}")
        try:
            send_telegram_message(f"❌ Error during sync: {str(e)}")
        except Exception as e:
            print(f"Telegram alert error: {str(e)}")
        return []

if __name__ == "__main__":
    changes = sync_servers()
    for line in changes:
        print(line) 