import os
from fastapi import FastAPI, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import models, schemas, auth
from .database import SessionLocal, engine, Base
from .auth import get_password_hash, verify_password, create_access_token, decode_token
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import Dict

# crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smaport IA Backend")

# CORS (permitir frontend local)
origins = os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependencia DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Registro de usuario sencillo
@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    hashed = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed, full_name=user.full_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Token (login)
@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# Obtener usuario actual
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    data = decode_token(token)
    if not data or not data.email:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user

# Proxy endpoint a OpenAI (seguro en backend)
@app.post("/openai/proxy")
async def openai_proxy(payload: schemas.OpenAIRequest = Body(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Proxy seguro que llama a la API de OpenAI usando la clave del servidor.
    Control básico de uso por usuario (registro en tabla Usage).
    """
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key no configurada en el servidor.")

    # opción simple de rate limit: permitir X llamadas por día si plan free
    # (a modo de ejemplo: free 20/day, pro 1000/day)
    from datetime import datetime, timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    usage_count = db.query(models.Usage).filter(models.Usage.user_id == current_user.id, models.Usage.created_at >= today_start).count()
    limit = 20 if current_user.plan == "free" else 1000
    if usage_count >= limit:
        raise HTTPException(status_code=429, detail="Límite diario excedido para tu plan. Actualiza a Pro.")

    # realizar la llamada a OpenAI (usamos chat.completions estilo compat)
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # aquí adaptamos al endpoint que uses; este ejemplo usa v1/chat/completions
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json={
                    "model": payload.model,
                    "messages": [{"role": "user", "content": payload.prompt}],
                    "max_tokens": payload.max_tokens,
                },
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                timeout=60.0
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Error al contactar OpenAI: {e}")

    # registrar uso básico
    usage = models.Usage(user_id=current_user.id, endpoint="/openai/proxy", cost=0.0)
    db.add(usage)
    db.commit()

    return {"ok": True, "result": data}
