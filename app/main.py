from fastapi import FastAPI

from app.database import Base, engine, SessionLocal
from app.models import Route
from app.routers import auth, sms, routes

# Create tables on first run
Base.metadata.create_all(engine)

# Seed the two routes on first run
with SessionLocal() as db:
    if db.query(Route).count() == 0:
        db.add_all([
            Route(name="ROUTE_A", priority=1, failure_rate=0.30),
            Route(name="ROUTE_B", priority=2, failure_rate=0.10),
        ])
        db.commit()

app = FastAPI(title="Mini SMS Gateway")

# Attach all routers
app.include_router(auth.router,   tags=["auth"])
app.include_router(sms.router,    tags=["sms"])
app.include_router(routes.router, tags=["routes"])