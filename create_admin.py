from app.database import SessionLocal, User
import bcrypt

username = "admin"
password = "admin123"

hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

db = SessionLocal()
existing_user = db.query(User).filter(User.username == username).first()
if not existing_user:
    new_user = User(username=username, password_hash=hashed_password, is_admin=True)
    db.add(new_user)
    db.commit()
    print("✅ admin user created successfully")
else:
    print("⚠️  admin user already exists")
db.close()
