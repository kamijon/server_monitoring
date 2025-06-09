from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from app.database import UptimeLog, Category
from fastapi.responses import JSONResponse
import asyncio
from app.sync_servers import sync_servers

from app.notifier import send_telegram_message, write_log, add_chat_id, remove_chat_id, load_chat_ids
from app.database import SessionLocal, Server, User
from app.monitor import monitor_servers
import bcrypt
from datetime import datetime

app = FastAPI()

# session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key="kamran-monitoring-2025",
    session_cookie="server_monitoring_session",
    max_age=14 * 24 * 60 * 60,  # 14 days
    same_site="lax",
    https_only=False
)

templates = Jinja2Templates(directory="/opt/server-monitoring/app/templates")
app.mount("/static", StaticFiles(directory="/opt/server-monitoring/app/static"), name="static")

async def sync_servers_task():
    while True:
        try:
            sync_servers()
        except Exception as e:
            print(f"Error syncing servers: {e}")
        await asyncio.sleep(300)  # 5 minutes

@app.on_event("startup")
async def startup_event():
    monitor_servers()
    asyncio.create_task(sync_servers_task())
    # Initialize database with default categories
    from app.database import init_db
    init_db()

#  login
@app.get("/login")
async def login_form(request: Request):
    if "user" in request.session:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "user": None})

# login
@app.post("/login")
async def login(request: Request):
    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")

    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        request.session["user"] = user.username
        write_log(f"User {username} logged in")
        send_telegram_message(f"*🔐 User Login*\nUser: {username}")
        return RedirectResponse(url="/", status_code=302)
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password", "user": None})

# logout
@app.get("/logout")
async def logout(request: Request):
    if "user" in request.session:
        username = request.session["user"]
        write_log(f"User {username} logged out")
        send_telegram_message(f"*🔓 User {username} logged out*")
        request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/signup")
async def signup_form(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("signup.html", {"request": request, "user": current_user})

@app.post("/signup")
async def signup(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    form_data = await request.form()
    username = form_data.get("username")
    password = form_data.get("password")
    confirm_password = form_data.get("confirm_password")
    is_admin = form_data.get("is_admin") == "on"

    if password != confirm_password:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Passwords do not match", "user": current_user})

    db = SessionLocal()
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        db.close()
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Username already exists", "user": current_user})

    hashed_password = get_password_hash(password)
    new_user = User(username=username, password=hashed_password, is_admin=is_admin)
    db.add(new_user)
    db.commit()
    db.close()

    write_log(f"New user {username} created by admin {current_user.username}")
    send_telegram_message(f"*👤 New User Created*\nUsername: {username}\nAdmin: {is_admin}\nCreated by: {current_user.username}")
    return RedirectResponse(url="/users", status_code=303)

@app.get("/users", response_class=HTMLResponse)
async def list_users(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    if not current_user or not current_user.is_admin:
        db.close()
        return RedirectResponse(url="/", status_code=302)

    users = db.query(User).all()
    db.close()

    return templates.TemplateResponse("users.html", {"request": request, "users": users, "user": current_user})

@app.post("/delete_user/{user_id}")
async def delete_user(request: Request, user_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    user_to_delete = db.query(User).filter(User.id == user_id).first()

    # فقط ادمین میتونه حذف کنه و خودش رو حذف نکنه
    if current_user and current_user.is_admin and user_to_delete and user_to_delete.username != current_user.username:
        db.delete(user_to_delete)
        db.commit()

    db.close()
    return RedirectResponse(url="/users", status_code=302)

@app.get("/change_password", response_class=HTMLResponse)
async def change_password_form(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("change_password.html", {"request": request, "message": None, "error": None})

@app.post("/change_password")
async def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    user = db.query(User).filter(User.username == request.session["user"]).first()

    if user and bcrypt.checkpw(old_password.encode(), user.password_hash.encode()):
        new_hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode('utf-8')
        user.password_hash = new_hashed_password
        db.commit()
        db.close()
        return templates.TemplateResponse("change_password.html", {"request": request, "message": "Password changed successfully!", "error": None})
    else:
        db.close()
        return templates.TemplateResponse("change_password.html", {"request": request, "message": None, "error": "Incorrect current password."})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    categories = db.query(Category).all()
    servers_by_category = {}
    for category in categories:
        servers = db.query(Server).filter(Server.category_id == category.id).all()
        servers_by_category[category] = servers

    total = sum(len(servers) for servers in servers_by_category.values())
    online = sum(1 for servers in servers_by_category.values() for s in servers if s.status == "Online")
    offline = sum(1 for servers in servers_by_category.values() for s in servers if s.status == "Offline")
    uptime = int((online / total) * 100) if total > 0 else 0
    db.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "servers_by_category": servers_by_category,
        "total": total,
        "online": online,
        "offline": offline,
        "uptime": uptime,
        "user": current_user
    })


@app.get("/add_server", response_class=HTMLResponse)
async def add_server_form(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    categories = db.query(Category).all()
    db.close()

    return templates.TemplateResponse("add_server.html", {
        "request": request,
        "categories": categories,
        "user": current_user
    })

@app.post("/add_server")
async def add_server(
    request: Request,
    name: str = Form(...),
    address: str = Form(...),
    port: int = Form(0),
    check_type: str = Form(...),
    keyword: str = Form(None),
    category_id: int = Form(...)
):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    
    db = SessionLocal()
    server = Server(
        name=name,
        address=address,
        port=port if port > 0 else None,
        status="Unknown",
        check_type=check_type,
        keyword=keyword,
        monitoring=True,
        category_id=category_id,
        is_manual=True  # Mark as manually added
    )
    db.add(server)
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{server_id}")
async def delete_server(server_id: int):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if server:
        db.delete(server)
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/start/{server_id}")
async def start_monitoring(server_id: int):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if server:
        server.monitoring = True
        db.commit()
        message = f"*▶️ Server Monitoring Started*\n"
        message += f"Server: {server.name}\n"
        message += f"Address: {server.address}:{server.port}"
        send_telegram_message(message)
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/stop/{server_id}")
async def stop_monitoring(server_id: int):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if server:
        server.monitoring = False
        db.commit()
        message = f"*⏹️ Server Monitoring Stopped*\n"
        message += f"Server: {server.name}\n"
        message += f"Address: {server.address}:{server.port}"
        send_telegram_message(message)
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/logs", response_class=HTMLResponse)
async def list_logs(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    try:
        with open("/opt/server-monitoring/server.log", "r") as f:
            log_lines = f.readlines()
            logs = []
            for line in log_lines:
                try:
                    # Parse timestamp and message from log line
                    timestamp_str = line[:19]  # First 19 characters for timestamp
                    message = line[20:].strip()  # Rest is the message
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    logs.append({
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "message": message
                    })
                except Exception as e:
                    print(f"Error parsing log line: {e}")
                    continue
    except FileNotFoundError:
        logs = []

    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs, "user": current_user})

@app.get("/edit/{server_id}", response_class=HTMLResponse)
async def edit_server_form(request: Request, server_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    server = db.query(Server).filter(Server.id == server_id).first()
    categories = db.query(Category).all()
    db.close()

    if not server:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("edit_server.html", {
        "request": request,
        "server": server,
        "categories": categories,
        "user": current_user
    })

@app.post("/update_server/{server_id}")
async def update_server(
    server_id: int,
    name: str = Form(...),
    address: str = Form(...),
    port: int = Form(0),
    check_type: str = Form(...),
    keyword: str = Form(None),
    category_id: int = Form(...)
):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if server:
        server.name = name
        server.address = address
        server.port = port if port > 0 else None
        server.check_type = check_type
        server.keyword = keyword
        server.category_id = category_id
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/logs/server/{server_id}", response_class=HTMLResponse)
async def uptime_history(request: Request, server_id: int):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    logs = db.query(UptimeLog).filter(UptimeLog.server_id == server_id).order_by(UptimeLog.timestamp.desc()).all()
    db.close()
    if not server:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("uptime_history.html", {
        "request": request,
        "server": server,
        "logs": logs
    })


@app.get("/charts/server/{server_id}", response_class=HTMLResponse)
async def chart_view(request: Request, server_id: int):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    logs = db.query(UptimeLog).filter(UptimeLog.server_id == server_id).order_by(UptimeLog.timestamp.asc()).all()
    db.close()
    if not server:
        return RedirectResponse(url="/", status_code=302)

    labels = [log.timestamp.strftime("%Y-%m-%d %H:%M") for log in logs]
    statuses = [1 if log.status == "Online" else 0 for log in logs]

    return templates.TemplateResponse("chart.html", {
        "request": request,
        "server": server,
        "labels": labels,
        "statuses": statuses
    })

@app.get("/api/chart-data/{server_id}")
async def chart_data(server_id: int):
    db = SessionLocal()
    logs = db.query(UptimeLog).filter(UptimeLog.server_id == server_id).order_by(UptimeLog.timestamp.asc()).all()
    db.close()

    labels = [log.timestamp.strftime("%H:%M") for log in logs][-20:]  # فقط ۲۰ مورد آخر
    statuses = [1 if log.status == "Online" else 0 for log in logs][-20:]

    return JSONResponse(content={"labels": labels, "statuses": statuses})

@app.get("/sync")
async def sync_servers_endpoint(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    try:
        changes = sync_servers()
        if changes:
            return JSONResponse(content={"status": "success", "changes": changes})
        else:
            return JSONResponse(content={"status": "success", "message": "No changes detected"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Category management routes
@app.get("/categories", response_class=HTMLResponse)
async def list_categories(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    
    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    categories = db.query(Category).all()
    db.close()
    
    return templates.TemplateResponse("categories.html", {"request": request, "categories": categories, "user": current_user})

@app.get("/categories/new", response_class=HTMLResponse)
async def add_category_form(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    if not current_user or not current_user.is_admin:
        db.close()
        return RedirectResponse(url="/", status_code=302)
    db.close()

@app.post("/categories")
async def create_category(request: Request, name: str = Form(...), description: str = Form(...)):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    
    db = SessionLocal()
    category = Category(name=name, description=description)
    db.add(category)
    db.commit()
    db.close()
    
    return RedirectResponse(url="/categories", status_code=302)

@app.post("/delete_category/{category_id}")
async def delete_category(request: Request, category_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    
    db = SessionLocal()
    category = db.query(Category).filter(Category.id == category_id).first()
    if category:
        db.delete(category)
        db.commit()
    db.close()
    
    return RedirectResponse(url="/categories", status_code=302)

@app.get("/edit_category/{category_id}", response_class=HTMLResponse)
async def edit_category_form(request: Request, category_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    if not current_user or not current_user.is_admin:
        db.close()
        return RedirectResponse(url="/", status_code=302)

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        db.close()
        return RedirectResponse(url="/categories", status_code=302)

    db.close()
    return templates.TemplateResponse("edit_category.html", {"request": request, "category": category, "user": current_user})

async def check_server_status(server: Server):
    try:
        if server.check_type == "ping":
            response = await ping_server(server.address)
            new_status = "Online" if response else "Offline"
        elif server.check_type == "port":
            response = await check_port(server.address, server.port)
            new_status = "Online" if response else "Offline"
        elif server.check_type == "http":
            response = await check_http(server.address, server.port)
            new_status = "Online" if response else "Offline"
        elif server.check_type == "http-keyword":
            response = await check_http_keyword(server.address, server.port, server.keyword)
            new_status = "Online" if response else "Offline"
        else:
            new_status = "Unknown"

        # Only send notification if status has changed
        if server.status != new_status:
            old_status = server.status
            server.status = new_status
            server.last_check = datetime.now()
            
            # Send Telegram notification for status change
            if old_status != "Unknown":  # Don't notify for initial status
                status_emoji = "🟢" if new_status == "Online" else "🔴"
                message = f"*{status_emoji} Server Status Change*\n"
                message += f"Server: {server.name}\n"
                message += f"Address: {server.address}:{server.port}\n"
                message += f"Status: {old_status} → {new_status}"
                send_telegram_message(message)
            
            return True  # Status changed
        return False  # Status unchanged

    except Exception as e:
        print(f"Error checking server {server.name}: {str(e)}")
        return False

@app.get("/edit_user/{user_id}", response_class=HTMLResponse)
async def edit_user_form(request: Request, user_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    if not current_user or not current_user.is_admin:
        db.close()
        return RedirectResponse(url="/", status_code=302)

    edit_user = db.query(User).filter(User.id == user_id).first()
    if not edit_user:
        db.close()
        return RedirectResponse(url="/users", status_code=302)

    db.close()
    return templates.TemplateResponse("edit_user.html", {"request": request, "edit_user": edit_user, "user": current_user})

@app.post("/edit_user/{user_id}")
async def edit_user(request: Request, user_id: int, username: str = Form(...), is_admin: bool = Form(False), new_password: str = Form(None), confirm_password: str = Form(None)):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    user_to_edit = db.query(User).filter(User.id == user_id).first()
    
    if not current_user or not current_user.is_admin or not user_to_edit:
        db.close()
        return RedirectResponse(url="/users", status_code=302)

    try:
        # Check if username is already taken by another user
        existing_user = db.query(User).filter(User.username == username, User.id != user_id).first()
        if existing_user:
            db.close()
            return templates.TemplateResponse("edit_user.html", {
                "request": request,
                "user": user_to_edit,
                "message": None,
                "error": "Username already exists."
            })

        # Handle password change if new password is provided
        if new_password:
            if new_password != confirm_password:
                db.close()
                return templates.TemplateResponse("edit_user.html", {
                    "request": request,
                    "user": user_to_edit,
                    "message": None,
                    "error": "New passwords do not match."
                })
            
            if len(new_password) < 8:
                db.close()
                return templates.TemplateResponse("edit_user.html", {
                    "request": request,
                    "user": user_to_edit,
                    "message": None,
                    "error": "Password must be at least 8 characters long."
                })
            
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_to_edit.password_hash = hashed_password

        user_to_edit.username = username
        user_to_edit.is_admin = is_admin
        db.commit()
        
        write_log(f"User {user_to_edit.username} updated by admin {current_user.username}")
        send_telegram_message(f"*👤 User Updated*\nUpdated by: {current_user.username}\nUsername: {user_to_edit.username}\nAdmin: {is_admin}")
        
        db.close()
        return RedirectResponse(url="/users", status_code=303)
    except Exception as e:
        db.rollback()
        db.close()
        return templates.TemplateResponse("edit_user.html", {
            "request": request,
            "user": user_to_edit,
            "message": None,
            "error": f"An error occurred: {str(e)}"
        })

@app.post("/clear_logs")
async def clear_logs(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    try:
        with open("server.log", "w") as f:
            f.write("")
        write_log(f"Logs cleared by admin {current_user.username}")
        send_telegram_message(f"*🗑️ Logs Cleared*\nCleared by: {current_user.username}")
        return RedirectResponse(url="/logs", status_code=303)
    except Exception as e:
        print(f"Error clearing logs: {str(e)}")
        return RedirectResponse(url="/logs?error=clear_failed", status_code=303)

@app.get("/api/telegram/chats")
async def get_telegram_chats(request: Request):
    """Get list of configured Telegram chat IDs."""
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    return {"chat_ids": load_chat_ids()}

@app.post("/api/telegram/chats/add")
async def add_telegram_chat(request: Request, chat_id: str = Form(...)):
    """Add a new Telegram chat ID."""
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    if add_chat_id(chat_id):
        write_log(f"Added new Telegram chat ID: {chat_id}")
        send_telegram_message(f"*📱 New Chat Added*\nChat ID: {chat_id}\nAdded by: {current_user.username}")
        return {"status": "success", "message": "Chat ID added successfully"}
    return {"status": "error", "message": "Failed to add chat ID"}

@app.post("/api/telegram/chats/remove")
async def remove_telegram_chat(request: Request, chat_id: str = Form(...)):
    """Remove a Telegram chat ID."""
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    if remove_chat_id(chat_id):
        write_log(f"Removed Telegram chat ID: {chat_id}")
        send_telegram_message(f"*📱 Chat Removed*\nChat ID: {chat_id}\nRemoved by: {current_user.username}")
        return {"status": "success", "message": "Chat ID removed successfully"}
    return {"status": "error", "message": "Failed to remove chat ID"}

@app.get("/telegram-chats")
async def telegram_chats(request: Request):
    """Telegram chat management page."""
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("telegram_chats.html", {
        "request": request,
        "user": current_user
    })

