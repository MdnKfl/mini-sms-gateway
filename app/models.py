from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)                  # hashed, never plain
    balance = Column(Integer, default=100)     # credits


class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    priority = Column(Integer)       # 1 tried first
    failure_rate = Column(Float)     # 0.3 = 30% chance of failure
    balance = Column(Integer, default=1000)

    def get_balance(self) -> int:
        # Required by the brief: each provider has getBalance()
        return self.balance


class SmsMessage(Base):
    __tablename__ = "sms_messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    to_number = Column(String)
    message = Column(String)
    parts = Column(Integer)
    cost = Column(Integer)
    status = Column(String, default="pending")   # pending|sent|failed|refunded
    provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RouteAttempt(Base):
    __tablename__ = "route_attempts"
    id = Column(Integer, primary_key=True)
    route_name = Column(String)
    success = Column(Integer)        # 1 = yes, 0 = no
    created_at = Column(DateTime, default=datetime.utcnow)