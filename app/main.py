# app/main.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel, Field, create_engine, Session, select

# -------------------- DB --------------------
# ✅ use DB_URL exactly (as you had)
DB_URL = os.getenv("DB_URL", "sqlite:///./app.db")
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=300)

def create_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s

# -------------------- Models --------------------
class CatalogItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=1, max_length=120)
    category: str = Field(index=True, min_length=1, max_length=60)  # sleep|stress|mobility|meds|safety|nutrition
    description: Optional[str] = Field(default=None, max_length=2000)
    price: float = Field(default=0.0, ge=0)
    device: str = Field(default="any", index=True, max_length=10)   # "watch" | "phone" | "any"
    voice_prompt: Optional[str] = Field(default=None, max_length=240)
    # stored in DB as "prize"; API will expose as "reward"
    prize: Optional[float] = Field(default=None, ge=0)

class CatalogItemCreate(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    price: float = Field(ge=0)
    description: Optional[str] = Field(default=None, max_length=2000)
    device: str = Field(default="any", max_length=10)
    voice_prompt: Optional[str] = Field(default=None, max_length=240)
    # Accept either "reward" (preferred) or legacy "prize"
    reward: Optional[float] = Field(default=None, ge=0)
    prize: Optional[float] = Field(default=None, ge=0)

class CatalogItemRead(SQLModel):
    id: int
    name: str
    category: str
    price: float
    description: Optional[str]
    device: str
    voice_prompt: Optional[str]
    reward: Optional[float]  # serialized from CatalogItem.prize

# -------------------- App --------------------
api = FastAPI(title="H&N Health Assistant Skills Catalog", version="1.1.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)  # ensure folder exists
api.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@api.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")

@api.get("/health")
def health():
    return {"status": "ok"}

@api.get("/__dbinfo")
def dbinfo():
    """Redacted DB info + simple connectivity/row count check (uses DB_URL)."""
    url = make_url(DB_URL)
    redacted = url.set(password="***") if url.password else url
    info = {
        "env_var": "DB_URL",
        "dialect": url.get_backend_name(),
        "driver": url.get_driver_name(),
        "database": url.database,
        "username": redacted.username,
        "host": redacted.host,
        "port": redacted.port,
        "url_redacted": str(redacted),
        "connected": False,
        "server_version": None,
        "items_count": 0,
    }
    try:
        with engine.connect() as conn:
            # version (best effort)
            try:
                if info["dialect"] == "sqlite":
                    v = conn.exec_driver_sql("select sqlite_version()").scalar()
                else:
                    v = conn.exec_driver_sql("select version()").scalar()
                info["server_version"] = str(v)
            except Exception:
                pass
            # count items safely
            with Session(engine) as s:
                info["items_count"] = len(s.exec(select(CatalogItem)).all())
            info["connected"] = True
    except Exception:
        info["connected"] = False
    return info

@api.on_event("startup")
def on_startup():
    create_db()

# --------- helper (DB -> API model) ----------
def to_read(obj: CatalogItem) -> CatalogItemRead:
    return CatalogItemRead(
        id=obj.id,
        name=obj.name,
        category=obj.category,
        price=obj.price,
        description=obj.description,
        device=obj.device,
        voice_prompt=obj.voice_prompt,
        reward=obj.prize,  # None is OK (Optional)
    )

# -------------------- CRUD --------------------
@api.post("/api/v1/items", response_model=CatalogItemRead, status_code=201)
def create_item(data: CatalogItemCreate, session: Session = Depends(get_session)):
    device = data.device if data.device in {"watch", "phone", "any"} else "any"
    reward_value = data.reward if data.reward is not None else data.prize
    item = CatalogItem(
        name=data.name,
        category=data.category,
        description=data.description,
        price=data.price,
        device=device,
        voice_prompt=data.voice_prompt,
        prize=reward_value,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return to_read(item)

@api.get("/api/v1/items", response_model=List[CatalogItemRead])
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
    rows = session.exec(stmt).all()
    return [to_read(r) for r in rows]

@api.get("/api/v1/items/{item_id}", response_model=CatalogItemRead)
def get_item(item_id: int, session: Session = Depends(get_session)):
    obj = session.get(CatalogItem, item_id)
    if not obj:
        raise HTTPException(404, "Not found")
    return to_read(obj)

@api.delete("/api/v1/items/{item_id}", status_code=204)
def delete_item(item_id: int, session: Session = Depends(get_session)):
    obj = session.get(CatalogItem, item_id)
    if not obj:
        raise HTTPException(404, "Not found")
    session.delete(obj)
    session.commit()
    return None

# -------------------- Demo seed (8 items) --------------------
DEMO: List[CatalogItem] = [
    CatalogItem(name="5-min Box Breathing", category="stress", device="any",
                voice_prompt="Let's do a 5-minute box breathing together. Inhale… hold… exhale…",
                description="Short guided breathing for stress relief.", price=0.0, prize=10.0),
    CatalogItem(name="Medication reminder (8 AM)", category="meds", device="phone",
                voice_prompt="It's time for your morning medication. Would you like to log it?",
                description="Daily reminder with quick confirm.", price=0.0, prize=5.0),
    CatalogItem(name="Hydration nudge", category="nutrition", device="watch",
                voice_prompt="Time to drink a glass of water. I’ll check again in 2 hours.",
                description="Watch tap + short prompt.", price=0.0, prize=2.5),
    CatalogItem(name="Gentle mobility: 10-min walk", category="mobility", device="watch",
                voice_prompt="A gentle 10-minute walk would help today. Start an Outdoor Walk?",
                description="Starts Apple Watch workout.", price=0.0, prize=7.5),
    CatalogItem(name="Wind-down for sleep", category="sleep", device="phone",
                voice_prompt="Let’s dim the noise. I’ll start a 10-minute wind-down routine.",
                description="Bedtime routine helper.", price=0.0, prize=6.0),
    CatalogItem(name="Fall-risk check-in", category="safety", device="watch",
                voice_prompt="How steady are you feeling today? Any dizziness or unsteadiness?",
                description="Daily stability check-in.", price=0.0, prize=4.0),
    CatalogItem(name="Yoga Mat Flow (10-min)", category="mobility", device="any",
                voice_prompt="Ready for a quick 10-minute mat flow? I’ll guide the moves.",
                description="Gentle yoga mobility.", price=0.0, prize=8.0),
    CatalogItem(name="Gratitude check", category="stress", device="phone",
                voice_prompt="Take a moment—what's one thing you’re grateful for today?",
                description="Positive reflection to lower stress.", price=0.0, prize=3.0),
]

@api.post("/api/v1/items/seed_demo")
def seed_demo(session: Session = Depends(get_session)):
    exists = session.exec(select(CatalogItem).limit(1)).first()
    if exists:
        return {"status": "exists"}
    session.add_all(DEMO)
    session.commit()
    return {"status": "ok", "count": len(DEMO)}

# -------------------- Recommend --------------------
@api.get("/api/v1/recommend", response_model=List[CatalogItemRead])
def recommend(
    goal: str = Query(..., description="sleep|stress|mobility|meds|safety|nutrition"),
    device: str = Query("any"),
    session: Session = Depends(get_session),
):
    stmt = select(CatalogItem).where(CatalogItem.category == goal)
    if device in ("watch", "phone"):
        stmt = stmt.where((CatalogItem.device == device) | (CatalogItem.device == "any"))
    stmt = stmt.order_by(CatalogItem.id.desc()).limit(5)
    rows = session.exec(stmt).all()
    return [to_read(r) for r in rows]
