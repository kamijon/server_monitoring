from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import bcrypt

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    description = Column(String)
    servers = relationship("Server", back_populates="category")


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
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = relationship("Category", back_populates="servers")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_admin = Column(Boolean, default=False)

    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))


class UptimeLog(Base):
    __tablename__ = "uptime_logs"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, index=True)
    status = Column(String)  # Online یا Offline
    timestamp = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Create default categories if they don't exist
    db = SessionLocal()
    if not db.query(Category).first():
        default_categories = [
            Category(name="Websites", description="Hosted websites and web applications"),
            Category(name="Servers", description="Server IPs and services")
        ]
        db.add_all(default_categories)
        db.commit()
    db.close()


if __name__ == "__main__":
    init_db()
