import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Route, SmsMessage, RouteAttempt
from app.security import get_current_user
from app.utils import normalize_phone, count_parts
from datetime import timedelta

router = APIRouter()


class SendBody(BaseModel):
    to: list[str]
    message: str


@router.post("/sms/send", status_code=201)
def send_sms(
    body: SendBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 1. Validate + normalize every number
    try:
        numbers = [normalize_phone(n) for n in body.to]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not numbers:
        raise HTTPException(status_code=422, detail="No recipients given")

    # 2. Cost = parts per message × number of recipients
    parts = count_parts(body.message)
    total_cost = parts * len(numbers)

    # 3. ATOMIC DEBIT (the critical line)
    # ------------------------------------------------------------------
    # One SQL statement checks AND deducts:
    #   "subtract total_cost, but only if balance >= total_cost"
    # If two requests arrive at once, they run one after another.
    # The second one sees the reduced balance, WHERE fails, rowcount=0.
    # ------------------------------------------------------------------
    result = db.execute(
        update(User)
        .where(User.id == user.id, User.balance >= total_cost)
        .values(balance=User.balance - total_cost)
    )
    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # 4. Create one SmsMessage row per recipient (same transaction)
    messages = []
    for number in numbers:
        msg = SmsMessage(
            user_id=user.id,
            to_number=number,
            message=body.message,
            parts=parts,
            cost=parts,
            status="pending",
        )
        db.add(msg)
        messages.append(msg)
    db.commit()

    # 5. Send via routes in priority order, skipping broke routes
    routes = db.query(Route).order_by(Route.priority).all()
    for msg in messages:
        for route in routes:
            if route.balance < msg.cost:
                continue               # route can't afford this message

            success = random.random() >= route.failure_rate
            db.add(RouteAttempt(
                route_name=route.name,
                success=1 if success else 0,
            ))

            if success:
                route.balance -= msg.cost
                msg.status = "sent"
                msg.provider = route.name
                break
            # else: try next route (loop continues)

        else:
            # for-loop finished without break → every route failed
            msg.status = "failed"

        db.commit()
        if msg.status == "failed":
            refund_message(db, msg)

    # 6. Response
    db.refresh(user)
    return {
        "parts_per_message": parts,
        "total_cost": total_cost,
        "new_balance": user.balance,
        "messages": [
            {"to": m.to_number, "status": m.status, "provider": m.provider}
            for m in messages
        ],
    }


def refund_message(db: Session, msg: SmsMessage):
    """
    Refund credits. Idempotent because the UPDATE only fires if status
    is still 'failed'. A second call finds nothing → rowcount=0 → return.
    """
    result = db.execute(
        update(SmsMessage)
        .where(SmsMessage.id == msg.id, SmsMessage.status == "failed")
        .values(status="refunded")
    )
    if result.rowcount == 0:
        db.rollback()
        return

    db.execute(
        update(User)
        .where(User.id == msg.user_id)
        .values(balance=User.balance + msg.cost)
    )
    db.commit()


@router.get("/sms/logs")
def get_logs(
    status: str = None,
    number: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SmsMessage).filter(SmsMessage.user_id == user.id)

    if status:
        query = query.filter(SmsMessage.status == status)
    if number:
        query = query.filter(SmsMessage.to_number.contains(number))
    if date_from:
        query = query.filter(SmsMessage.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        end = datetime.fromisoformat(date_to)
        # If only a date was given, include the whole day
        if end.hour == 0 and end.minute == 0 and end.second == 0:
            end = end + timedelta(days=1)
        query = query.filter(SmsMessage.created_at < end)

    total = query.count()
    items = (
        query.order_by(SmsMessage.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "messages": [
            {
                "id": m.id,
                "to": m.to_number,
                "status": m.status,
                "provider": m.provider,
                "parts": m.parts,
                "cost": m.cost,
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ],
    }