from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# Create database engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Server model
class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ip_or_url = Column(String, nullable=False)
    check_type = Column(String, nullable=False)  # ping, port, http
    port = Column(Integer, nullable=True)  # used if check_type is port
    is_active = Column(Boolean, default=True)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    # Initialize the database and create tables
    init_db()

    # Create a new server entry
    db = SessionLocal()
    new_server = Server(
        name="Test Server",
        ip_or_url="8.8.8.8",
        check_type="ping",
        port=None,
        is_active=True
    )

    db.add(new_server)
    db.commit()
    db.refresh(new_server)
    print(f"Added server: {new_server.name} with IP/URL: {new_server.ip_or_url}")
    db.close()
