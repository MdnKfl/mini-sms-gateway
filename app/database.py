import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Figure out the project root.
# __file__         = /path/to/project/app/database.py
# dirname(abspath(__file__))      = /path/to/project/app
# dirname(dirname(abspath(__file__)))  = /path/to/project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Always point at project_root/sms.db, no matter where you launch from
DB_PATH = os.path.join(BASE_DIR, "sms.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()