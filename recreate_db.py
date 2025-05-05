from app.database import Base, engine, SessionLocal, Category, Server, User, UptimeLog
import bcrypt

def recreate_database():
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables with new schema
    Base.metadata.create_all(bind=engine)
    
    # Create a new session
    db = SessionLocal()
    
    try:
        # Create default categories
        default_categories = [
            Category(name="Websites", description="Hosted websites and web applications"),
            Category(name="Servers", description="Server IPs and services")
        ]
        db.add_all(default_categories)
        db.commit()
        
        # Create default admin user if needed
        admin_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        admin_user = User(username="admin", password_hash=admin_password, is_admin=True)
        db.add(admin_user)
        db.commit()
        
        print("Database recreated successfully!")
    except Exception as e:
        print(f"Error recreating database: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    recreate_database() 