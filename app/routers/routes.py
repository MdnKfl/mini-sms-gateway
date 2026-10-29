from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Route, RouteAttempt

router = APIRouter()


@router.get("/routes/health")
def route_health(db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=24)
    result = []

    for route in db.query(Route).order_by(Route.priority).all():
        attempts = (
            db.query(RouteAttempt)
            .filter(
                RouteAttempt.route_name == route.name,
                RouteAttempt.created_at >= since,
            )
            .all()
        )
        total = len(attempts)
        successes = sum(a.success for a in attempts)
        rate = successes / total if total > 0 else 1.0

        # Health = 70% success + 30% balance ratio (capped at 1.0)
        health = 0.7 * rate + 0.3 * min(1.0, route.balance / 1000)

        result.append({
            "route": route.name,
            "balance": route.balance,
            "attempts_24h": total,
            "success_rate": round(rate, 2),
            "health_percent": round(health * 100, 1),
        })

    return result


@router.post("/demo/set-failure-rate")
def set_failure_rate(
    route_name: str,
    rate: float,
    db: Session = Depends(get_db),
):
    route = db.query(Route).filter_by(name=route_name).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    route.failure_rate = rate
    db.commit()
    return {"route": route.name, "failure_rate": route.failure_rate}