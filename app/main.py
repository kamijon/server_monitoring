from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from app.database import UptimeLog
from fastapi.responses import JSONResponse

from app.notifier import send_telegram_message
from app.database import SessionLocal, Server, User
from app.monitor import monitor_servers
import bcrypt

app = FastAPI()

# session middleware
app.add_middleware(SessionMiddleware, secret_key="kamran-monitoring-2025")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
async def startup_event():
    monitor_servers()

#  login
@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

# login
@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        request.session["user"] = username
        send_telegram_message(f"✅ {username} logged in!")
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

# logout
@app.get("/logout")
async def logout(request: Request):
    if "user" in request.session:
        send_telegram_message(f"🚪 {request.session['user']} logged out.")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not user or not user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("signup.html", {"request": request, "message": None, "error": None})

@app.post("/signup")
async def signup(request: Request, username: str = Form(...), password: str = Form(...)):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()

    if not current_user or not current_user.is_admin:
        db.close()
        return RedirectResponse(url="/", status_code=302)

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        db.close()
        return templates.TemplateResponse("signup.html", {"request": request, "message": None, "error": "Username already exists."})

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(username=username, password_hash=hashed_password, is_admin=False)
    db.add(new_user)
    db.commit()
    db.close()
    return templates.TemplateResponse("signup.html", {"request": request, "message": "User created successfully!", "error": None})

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

    return templates.TemplateResponse("users.html", {"request": request, "users": users, "current_user": current_user.username})

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
async def dashboard(request: Request):
    db = SessionLocal()
    servers = db.query(Server).all()

    total = len(servers)
    online = sum(1 for s in servers if s.status == "Online")
    offline = sum(1 for s in servers if s.status == "Offline")
    uptime = int((online / total) * 100) if total > 0 else 0

    db.close()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "servers": servers,
        "total": total,
        "online": online,
        "offline": offline,
        "uptime": uptime
    })


@app.get("/manage", response_class=HTMLResponse)
async def manage(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    db = SessionLocal()
    servers = db.query(Server).all()
    db.close()
    return templates.TemplateResponse("manage.html", {"request": request, "servers": servers})

@app.post("/add_server")
async def add_server(
    name: str = Form(...),
    address: str = Form(...),
    port: int = Form(0),
    check_type: str = Form(...),
    keyword: str = Form(None)
):
    db = SessionLocal()
    server = Server(
        name=name,
        address=address,
        port=port if port > 0 else None,
        status="Unknown",
        check_type=check_type,
        keyword=keyword,
        monitoring=True
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
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/stop/{server_id}")
async def stop_monitoring(server_id: int):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if server:
        server.monitoring = False
        db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)

    db = SessionLocal()
    current_user = db.query(User).filter(User.username == request.session["user"]).first()
    db.close()

    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=302)

    try:
        with open("server.log", "r") as f:
            log_content = f.read()
    except FileNotFoundError:
        log_content = "No logs available yet."

    return templates.TemplateResponse("logs.html", {"request": request, "logs": log_content})

@app.get("/edit/{server_id}", response_class=HTMLResponse)
async def edit_server(request: Request, server_id: int):
    if "user" not in request.session:
        return RedirectResponse(url="/login", status_code=302)
    
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    db.close()
    if not server:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("edit_server.html", {"request": request, "server": server})

@app.post("/update_server/{server_id}")
async def update_server(
    server_id: int,
    name: str = Form(...),
    address: str = Form(...),
    port: int = Form(0),
    check_type: str = Form(...),
    keyword: str = Form(None)
):
    db = SessionLocal()
    server = db.query(Server).filter(Server.id == server_id).first()
    if server:
        server.name = name
        server.address = address
        server.port = port if port > 0 else None
        server.check_type = check_type
        server.keyword = keyword
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

