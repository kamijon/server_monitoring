from app.database import SessionLocal, User

def list_users():
    db = SessionLocal()
    users = db.query(User).all()
    print("\n📋 List of registered users:\n")
    for user in users:
        print(f"👤  Username: {user.username}  |  Admin: {user.is_admin}")
    db.close()

if __name__ == "__main__":
    list_users()
