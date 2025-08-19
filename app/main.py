from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Field, create_engine, Session, select

# -------------------- DB --------------------
DB_URL = os.getenv("DB_URL", "sqlite:///./app.db")
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=300)

class CatalogItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=1, max_length=120)
    category: str = Field(index=True, max_length=60)   # sleep|stress|mobility|meds|safety|nutrition
    description: Optional[str] = Field(default=None, max_length=2000)
    price: Optional[float] = Field(default=0.0, ge=0)
    # IMPORTANT: use plain string, not typing.Literal or Enum to avoid the issubclass() error
    device: str = Field(default="any", index=True, max_length=10)  # "watch" | "phone" | "any"
    voice_prompt: Optional[str] = Field(default=None, max_length=240)

def create_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s

# -------------------- App --------------------
api = FastAPI(title="H&N Health Skills Catalog", version="1.0.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
api.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@api.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")

@api.on_event("startup")
def on_startup():
    create_db()

# -------------------- CRUD --------------------
@api.post("/api/v1/items", response_model=CatalogItem, status_code=201)
def create_item(item: CatalogItem, session: Session = Depends(get_session)):
    item.id = None
    # normalize device to expected set
    if item.device not in {"watch", "phone", "any"}:
        item.device = "any"
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@api.get("/api/v1/items", response_model=List[CatalogItem])
def list_items(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    device: Optional[str] = Query(None),     # watch|phone|any
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    session: Session = Depends(get_session),
):
    stmt = select(CatalogItem)
    if q:
        stmt = stmt.where(CatalogItem.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(CatalogItem.category == category)
    if device:
        if device in ("watch", "phone"):
            stmt = stmt.where((CatalogItem.device == device) | (CatalogItem.device == "any"))

    stmt = stmt.order_by(CatalogItem.id.desc()).offset((page - 1) * page_size).limit(page_size)
    return session.exec(stmt).all()

@api.delete("/api/v1/items/{item_id}", status_code=204)
def delete_item(item_id: int, session: Session = Depends(get_session)):
    obj = session.get(CatalogItem, item_id)
    if not obj:
        raise HTTPException(404, "Not found")
    session.delete(obj)
    session.commit()
    return None

# -------------------- Demo seed --------------------
DEMO: List[CatalogItem] = [
    CatalogItem(name="5-min Box Breathing", category="stress", device="any",
                voice_prompt="Let's do a 5-minute box breathing together. Inhale… hold… exhale…",
                description="Short guided breathing for stress relief."),
    CatalogItem(name="Medication reminder (8 AM)", category="meds", device="phone",
                voice_prompt="It's time for your morning medication. Would you like to log it?",
                description="Daily reminder with quick confirm."),
    CatalogItem(name="Hydration nudge", category="nutrition", device="watch",
                voice_prompt="Time to drink a glass of water. I’ll check again in 2 hours.",
                description="Watch tap + short prompt."),
    CatalogItem(name="Gentle mobility: 10-min walk", category="mobility", device="watch",
                voice_prompt="A gentle 10-minute walk would help today. Shall I start an Outdoor Walk?",
                description="Starts Apple Watch workout."),
    CatalogItem(name="Wind-down for sleep", category="sleep", device="phone",
                voice_prompt="Let’s dim the noise. I’ll start a 10-minute wind-down routine.",
                description="Bedtime routine helper."),
    CatalogItem(name="Fall-risk check-in", category="safety", device="watch",
                voice_prompt="How steady are you feeling today? Any dizziness or unsteadiness?",
                description="Daily stability check-in."),
    CatalogItem(name="Mindful minute", category="stress", device="any",
                voice_prompt="One mindful minute together. Focus on your breath.",
                description="Ultra-short reset."),
    CatalogItem(name="Stretch set (hips)", category="mobility", device="any",
                voice_prompt="Let’s do a gentle hip stretch. I’ll guide each step.",
                description="Low-impact range of motion."),
    CatalogItem(name="Breakfast check", category="nutrition", device="phone",
                voice_prompt="How was breakfast today? Any changes to note?",
                description="Simple adherence journaling."),
    CatalogItem(name="Evening medication", category="meds", device="phone",
                voice_prompt="Evening meds time. Would you like me to record it?",
                description="Second daily reminder."),
    CatalogItem(name="Sleep posture tip", category="sleep", device="any",
                voice_prompt="Try a side-sleep posture tonight with pillow support.",
                description="Small suggestion for better rest."),
    CatalogItem(name="Home safety tip", category="safety", device="any",
                voice_prompt="Quick safety check: clear walkways, good lighting, non-slip mats.",
                description="Daily rotating tip."),
]

@api.post("/api/v1/items/seed_demo")
def seed_demo(session: Session = Depends(get_session)):
    any_row = session.exec(select(CatalogItem).limit(1)).first()
    if any_row:
        return {"status": "exists"}
    for it in DEMO:
        session.add(it)
    session.commit()
    return {"status": "ok", "count": len(DEMO)}

# -------------------- Recommend --------------------
GOAL_TO_CATEGORY = {
    "sleep": "sleep",
    "stress": "stress",
    "mobility": "mobility",
    "meds": "meds",
    "safety": "safety",
    "nutrition": "nutrition",
}

@api.get("/api/v1/recommend", response_model=List[CatalogItem])
def recommend(
    persona: Optional[str] = Query(None),
    goal: str = Query(...),
    device: str = Query("any"),
    session: Session = Depends(get_session),
):
    cat = GOAL_TO_CATEGORY.get(goal, goal)
    stmt = select(CatalogItem).where(CatalogItem.category == cat)
    if device in ("watch", "phone"):
        stmt = stmt.where((CatalogItem.device == device) | (CatalogItem.device == "any"))
    stmt = stmt.order_by(CatalogItem.id.desc()).limit(5)
    return session.exec(stmt).all()
