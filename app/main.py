import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.database import init_db, SessionLocal, Server
from app.monitor import check_server
from app.notifier import send_telegram_alert, send_email_alert
from app import config

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

# Background task: Monitoring loop
async def monitor_servers():
    while True:
        db = SessionLocal()
        servers = db.query(Server).filter(Server.is_active == True).all()
        for server in servers:
            is_up = await check_server(server)
            if not is_up:
                alert_message = f"⚠️ Server Down: {server.name} ({server.ip_or_url})"
                send_telegram_alert(alert_message)
                send_email_alert("Server Down Alert", alert_message)
        db.close()
        await asyncio.sleep(config.CHECK_INTERVAL_SECONDS)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_servers())

# Dashboard - Show all servers
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = SessionLocal()
    servers = db.query(Server).all()
    db.close()
    return templates.TemplateResponse("dashboard.html", {"request": request, "servers": servers})

# Add server form
@app.get("/add", response_class=HTMLResponse)
async def add_server_form(request: Request):
    return templates.TemplateResponse("manage.html", {"request": request})

# Save new server
@app.post("/add")
async def add_server(
    name: str = Form(...),
    ip_or_url: str = Form(...),
    check_type: str = Form(...),
    port: int = Form(None)
):
    db = SessionLocal()
    server = Server(
        name=name,
        ip_or_url=ip_or_url,
        check_type=check_type,
        port=port
    )
    db.add(server)
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)
