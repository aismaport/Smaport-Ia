import os
from fastapi import FastAPI, Depends, HTTPException, status, Body
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import models, schemas, auth
from .database import SessionLocal, engine, Base
from .auth import get_password_hash, verify_password, create_access_token, decode_token
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import Dict
import hashlib

# ======================================================
# 🔧 CONFIGURACIÓN DE LA BASE DE DATOS (Railway / Render)
# ======================================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")  # fallback local

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ======================================================
# 🚀 INICIALIZACIÓN DE LA APLICACIÓN
# ======================================================
app = FastAPI(title="Smaport IA Backend", version="1.0.0")

# ======================================================
# 🧱 MODELOS DE BASE DE DATOS
# ======================================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# ======================================================
# 📦 ESQUEMAS DE VALIDACIÓN
# ======================================================
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ======================================================
# 🔐 ENDPOINT: REGISTRO DE USUARIOS
# ======================================================
@app.post("/register")
def register_user(req: RegisterRequest):
    db = SessionLocal()

    # Comprobar si el usuario ya existe
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    # Cifrar la contraseña
    hashed_password = hashlib.sha256(req.password.encode()).hexdigest()

    # Crear y guardar el usuario
    new_user = User(email=req.email, password=hashed_password)
    db.add(new_user)
    db.commit()

    return {"message": f"Usuario {req.email} registrado correctamente"}

# ======================================================
# 🔑 ENDPOINT: LOGIN DE USUARIOS
# ======================================================
@app.post("/login")
def login_user(req: LoginRequest):
    db = SessionLocal()

    # Buscar el usuario
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Verificar contraseña
    hashed_password = hashlib.sha256(req.password.encode()).hexdigest()
    if user.password != hashed_password:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    return {"message": "Inicio de sesión correcto"}

# ======================================================
# 🏠 ENDPOINT PRINCIPAL (TEST)
# ======================================================
@app.get("/")
def root():
    return {"status": "ok", "message": "API Smaport IA funcionando correctamente ✅"}

    return {"ok": True, "result": data}
