from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String, index=True)
    port = Column(Integer, nullable=True)
    status = Column(String, default="Unknown")
    check_type = Column(String, default="ping")  # ping, port, http, http-keyword
    keyword = Column(String, nullable=True)
    monitoring = Column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_admin = Column(Boolean, default=False)


class UptimeLog(Base):
    __tablename__ = "uptime_logs"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, index=True)
    status = Column(String)  # Online یا Offline
    timestamp = Column(DateTime, default=datetime.utcnow)


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
