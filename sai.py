# app/main.py
import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text, func
from sqlmodel import SQLModel, Field, Session, create_engine, select

# --- (optional) load .env locally: DB_URL=... ---
try:
    from dotenv import load_dotenv  # pip install python-dotenv (dev only)
    load_dotenv()
except Exception:
    # it's fine in containers where python-dotenv isn't installed
    pass

# ---------- Paths / Static ----------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# ---------- Database ----------
# Prefer env var; fall back to a local file DB for dev
# (In Azure you will set DB_URL to your PostgreSQL URL)
DB_URL = os.getenv("DB_URL")
#DB_URL = "postgresql+psycopg://fitappadmin:Zxcvbnm%40123@fitapp-pg-dev.postgres.database.azure.com:5432/fitapp?sslmode=require"


# echo=True for verbose SQL during troubleshooting
engine = create_engine(DB_URL, echo=False, pool_pre_ping=True, pool_recycle=300)


def create_db() -> None:
    """Create tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def is_sqlite() -> bool:
    return engine.url.get_backend_name() == "sqlite"


# ---------- Models ----------
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    price: float = Field(ge=0)
    category: Optional[str] = Field(default=None, index=True, max_length=100)


class ProductCreate(SQLModel):
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None


class ProductUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    category: Optional[str] = None


# ---------- App ----------
api = FastAPI(title="FitApp API", version="1.0.0")

# CORS (relaxed for dev/demo)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (your UI)
api.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@api.get("/", include_in_schema=False)
def root():
    # redirect to your UI
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return RedirectResponse(url="/static/index.html")
    # fallback if index.html isn't present for some reason
    return FileResponse(index_path)


@api.on_event("startup")
def startup() -> None:
    create_db()


# ---------- Health / Debug ----------
@api.get("/api/v1/health")
def health():
    return {"status": "ok"}


@api.get("/__dbinfo", include_in_schema=False)
def dbinfo():
    """Tiny helper to confirm which DB you're actually connected to."""
    try:
        with engine.connect() as conn:
            dialect = conn.dialect.name
            current_db = None
            if dialect == "postgresql":
                current_db = conn.execute(text("select current_database()")).scalar()
            elif dialect == "sqlite":
                current_db = "sqlite-file"
            return {
                "dialect": dialect,
                "database": current_db,
                "url_driver": engine.url.drivername,
            }
    except Exception as e:
        return {"error": str(e), "dialect": engine.url.get_backend_name()}


# ---------- CRUD ----------
@api.post("/api/v1/products", response_model=Product, status_code=201)
def create_product(data: ProductCreate, session: Session = Depends(get_session)):
    item = Product(**data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@api.get("/api/v1/products", response_model=List[Product])
def list_products(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    stmt = select(Product).offset(offset).limit(limit).order_by(Product.id.desc())
    return session.exec(stmt).all()


@api.get("/api/v1/products/search", response_model=List[Product])
def search_products(
    q: str = Query(..., min_length=1),
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    # Cross-DB case-insensitive filtering:
    # - PostgreSQL: ILIKE works
    # - SQLite: emulate with lower(...) LIKE lower(...)
    if is_sqlite():
        stmt = select(Product).where(func.lower(Product.name).like(f"%{q.lower()}%"))
        if category:
            stmt = stmt.where(func.lower(Product.category).like(f"%{category.lower()}%"))
    else:
        stmt = select(Product).where(Product.name.ilike(f"%{q}%"))
        if category:
            stmt = stmt.where(Product.category.ilike(f"%{category}%"))

    stmt = stmt.offset(offset).limit(limit).order_by(Product.id.desc())
    return session.exec(stmt).all()


@api.get("/api/v1/products/{product_id}", response_model=Product)
def get_product(product_id: int, session: Session = Depends(get_session)):
    item = session.get(Product, product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return item


@api.put("/api/v1/products/{product_id}", response_model=Product)
def update_product(
    product_id: int, data: ProductUpdate, session: Session = Depends(get_session)
):
    item = session.get(Product, product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@api.delete("/api/v1/products/{product_id}", status_code=204)
def delete_product(product_id: int, session: Session = Depends(get_session)):
    item = session.get(Product, product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(item)
    session.commit()
    return None


# ---------- Dev runner ----------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:api", host="0.0.0.0", port=8000, reload=True)
