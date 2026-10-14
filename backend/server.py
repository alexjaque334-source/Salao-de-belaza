from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import secrets
import string
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
import bcrypt
import jwt
import hmac
import re
import hashlib
from . import email_service

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "preview").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------- Helpers ----------------
def validate_password(password: str) -> None:
    if len(password or "") < 10 or not re.search(r"[A-Za-z]", password or "") or not re.search(r"\d", password or ""):
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 10 caracteres, com letras e números.")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str, shop_id: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role, "shop_id": shop_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def oid(v) -> str:
    return str(v)


def safe_object_id(value, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{label} inválido")


def tier_for_points(points: int) -> str:
    if points >= 600: return "VIP Black"
    if points >= 300: return "Gold"
    if points >= 100: return "Silver"
    return "Bronze"


def serialize_user(doc, *, include_private_notes: bool = False) -> dict:
    points = doc.get("points", 0)
    data = {
        "id": oid(doc["_id"]),
        "email": doc.get("email"),
        "name": doc.get("name"),
        "role": doc.get("role"),
        "phone": doc.get("phone", ""),
        "points": points,
        "tier": tier_for_points(points),
        "total_spend": doc.get("total_spend", 0),
        "preferred_barber": doc.get("preferred_barber", ""),
        "shop_id": doc.get("shop_id"),
        "created_at": doc.get("created_at"),
    }
    if include_private_notes:
        data["notes"] = doc.get("notes", "")
    return data


async def _shop_fields(user: dict) -> dict:
    shop = None
    if user.get("shop_id"):
        shop = await db.shops.find_one({"_id": ObjectId(user["shop_id"])})
    return {
        "shop_code": shop["code"] if shop else None,
        "shop_name": shop["name"] if shop else None,
        "shop_status": shop_status(shop) if shop else None,
    }


async def auth_response(user: dict) -> dict:
    token = create_access_token(oid(user["_id"]), user["email"], user["role"], user["shop_id"])
    u = serialize_user(user)
    u.update(await _shop_fields(user))
    return {"token": token, "user": u}


def shop_status(shop) -> str:
    st = shop.get("status")
    if st:
        return st
    # Legacy/no explicit status: pending in production, active otherwise (tests/preview).
    return "pending" if IS_PRODUCTION else "active"


def _only_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def valid_cpf(cpf: str) -> bool:
    cpf = _only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in (9, 10):
        s = sum(int(cpf[n]) * ((i + 1) - n) for n in range(i))
        d = ((s * 10) % 11) % 10
        if d != int(cpf[i]):
            return False
    return True


def valid_cnpj(cnpj: str) -> bool:
    cnpj = _only_digits(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    for w, i in ((w1, 12), (w2, 13)):
        s = sum(int(cnpj[n]) * w[n] for n in range(i))
        d = s % 11
        d = 0 if d < 2 else 11 - d
        if d != int(cnpj[i]):
            return False
    return True


def valid_cpf_cnpj(v: str) -> bool:
    d = _only_digits(v)
    if len(d) == 11:
        return valid_cpf(d)
    if len(d) == 14:
        return valid_cnpj(d)
    return False


def mask_doc(v: str) -> str:
    d = _only_digits(v)
    if len(d) == 11:
        return f"***.***.{d[6:9]}-**"
    if len(d) == 14:
        return f"**.***.***/{d[8:12]}-**"
    return "***"


async def rate_limit(identifier: str, max_attempts: int = 10, window_minutes: int = 15):
    now = datetime.now(timezone.utc)
    rec = await db.login_attempts.find_one({"_id": identifier})
    if rec:
        first = datetime.fromisoformat(rec["first"])
        if (now - first).total_seconds() < window_minutes * 60:
            if rec.get("count", 0) >= max_attempts:
                raise HTTPException(status_code=429, detail="Muitas tentativas. Tente novamente em alguns minutos.")
        else:
            await db.login_attempts.delete_one({"_id": identifier})


async def bump_attempt(identifier: str):
    rec = await db.login_attempts.find_one({"_id": identifier})
    if not rec:
        await db.login_attempts.insert_one({"_id": identifier, "count": 1,
                                            "first": datetime.now(timezone.utc).isoformat()})
    else:
        await db.login_attempts.update_one({"_id": identifier}, {"$inc": {"count": 1}})


async def clear_attempts(identifier: str):
    await db.login_attempts.delete_one({"_id": identifier})


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _decode_token(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access" or not payload.get("sub"):
            raise HTTPException(status_code=401, detail="Token inválido")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


async def get_current_user_raw(request: Request) -> dict:
    payload = _decode_token(request)
    if payload.get("kind") == "super_admin":
        raise HTTPException(status_code=403, detail="Use o painel da plataforma")
    user = await db.users.find_one({"_id": safe_object_id(payload["sub"], "Token")})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    if not user.get("shop_id"):
        raise HTTPException(status_code=401, detail="Conta sem barbearia")
    return user


async def get_current_user(request: Request) -> dict:
    user = await get_current_user_raw(request)
    shop = await db.shops.find_one({"_id": ObjectId(user["shop_id"])})
    if not shop:
        raise HTTPException(status_code=401, detail="Barbearia não encontrada")
    st = shop_status(shop)
    if st != "active":
        raise HTTPException(status_code=403, detail=f"shop_{st}")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return user


def create_platform_token(admin_id: str, email: str) -> str:
    payload = {"sub": admin_id, "email": email, "kind": "super_admin",
               "exp": datetime.now(timezone.utc) + timedelta(days=2), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_super_admin(request: Request) -> dict:
    payload = _decode_token(request)
    if payload.get("kind") != "super_admin":
        raise HTTPException(status_code=403, detail="Acesso restrito à plataforma")
    admin = await db.platform_admins.find_one({"_id": safe_object_id(payload["sub"], "Token")})
    if not admin:
        raise HTTPException(status_code=401, detail="Super admin não encontrado")
    return admin


def gen_shop_code() -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))


async def unique_shop_code() -> str:
    for _ in range(20):
        code = gen_shop_code()
        if not await db.shops.find_one({"code": code}):
            return code
    raise HTTPException(500, "Não foi possível gerar código da barbearia")


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "barbearia"


async def unique_shop_slug(name: str) -> str:
    base = _slugify(name)
    slug = base
    n = 2
    while await db.shops.find_one({"public_slug": slug}):
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------- Models ----------------
class ShopCreateIn(BaseModel):
    shop_name: str
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = ""
    cpf_cnpj: str
    platform_plan_id: str


class PlatformLoginIn(BaseModel):
    email: EmailStr
    password: str


class DecisionIn(BaseModel):
    reason: Optional[str] = ""


class PlatformPlanIn(BaseModel):
    name: str
    monthly_price: float = Field(ge=0)
    description: Optional[str] = ""
    max_professionals: Optional[int] = Field(default=1, ge=1)
    max_services: Optional[int] = Field(default=1, ge=1)
    max_client_plans: Optional[int] = Field(default=1, ge=1)
    pdf_reports: bool = False
    active: bool = True


class PlatformPlanStatusIn(BaseModel):
    active: bool


class PlatformShopPlanIn(BaseModel):
    plan_id: str


class PlatformSubscriptionStatusIn(BaseModel):
    status: str
    reason: Optional[str] = ""


class PlatformSubscriptionProviderEventIn(BaseModel):
    provider: str
    external_subscription_id: str
    status: str
    event_id: Optional[str] = ""
    payment_method: Optional[str] = ""
    current_period_end: Optional[str] = None


class LoginIn(BaseModel):
    shop_code: str
    email: EmailStr
    password: str


class WhatsAppIntegrationIn(BaseModel):
    phone: str
    booking_enabled: bool = True
    plans_enabled: bool = True


class BarberIn(BaseModel):
    name: str
    specialty: Optional[str] = ""
    avatar: Optional[str] = ""
    phone: Optional[str] = ""
    active: bool = True
    commission_rate: float = 50
    working_hours: dict = Field(default_factory=dict)


class ServiceIn(BaseModel):
    name: str
    duration: int = 30
    price: float = 0


class AppointmentIn(BaseModel):
    barber_id: str
    service_id: str
    date: str
    time: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = ""


class PublicAppointmentIn(BaseModel):
    barber_id: str
    service_id: str
    date: str
    time: str
    client_name: str
    client_phone: str


class StatusIn(BaseModel):
    status: str


class PlanIn(BaseModel):
    name: str
    price: float
    description: Optional[str] = ""
    cuts_per_month: Optional[str] = ""
    features: List[str] = Field(default_factory=list)
    recommended: bool = False


class SubscriptionIn(BaseModel):
    plan_id: str
    client_id: Optional[str] = None


class ClientIn(BaseModel):
    name: str
    phone: str
    notes: Optional[str] = ""


class LoyaltyIn(BaseModel):
    points: int


WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DEFAULT_HOURS = {
    "mon": {"start": "09:00", "end": "19:00"},
    "tue": {"start": "09:00", "end": "19:00"},
    "wed": {"start": "09:00", "end": "19:00"},
    "thu": {"start": "09:00", "end": "19:00"},
    "fri": {"start": "09:00", "end": "20:00"},
    "sat": {"start": "09:00", "end": "17:00"},
    "sun": {},
}

DEFAULT_SERVICES = [
    {"name": "Corte de Cabelo", "duration": 30, "price": 45},
    {"name": "Barba Completa", "duration": 30, "price": 35},
    {"name": "Combo Corte + Barba", "duration": 60, "price": 70},
    {"name": "Sobrancelha", "duration": 15, "price": 20},
    {"name": "Corte Infantil", "duration": 30, "price": 40},
]

DEFAULT_PLANS = [
    {"name": "Plano Básico", "price": 79, "cuts_per_month": "2 cortes / mês",
     "description": "Ideal para manter o visual sempre em dia.",
     "features": ["2 cortes por mês", "10% off em produtos", "Agendamento prioritário"],
     "recommended": False},
    {"name": "Plano Executivo VIP", "price": 149, "cuts_per_month": "Cortes ilimitados + Barba",
     "description": "O favorito dos clientes exigentes.",
     "features": ["Cortes ilimitados", "Barba inclusa", "20% off em produtos", "Bebida cortesia"],
     "recommended": True},
    {"name": "Club Premium", "price": 229, "cuts_per_month": "Tudo incluso + Benefícios",
     "description": "Experiência completa de barbearia premium.",
     "features": ["Tudo ilimitado", "Sobrancelha inclusa", "30% off em produtos", "Horário exclusivo", "Brinde mensal"],
     "recommended": False},
]


async def seed_shop_defaults(shop_id: str, with_barbers: bool = False):
    if await db.services.count_documents({"shop_id": shop_id}) == 0:
        await db.services.insert_many([{**s, "shop_id": shop_id} for s in DEFAULT_SERVICES])
    if await db.plans.count_documents({"shop_id": shop_id}) == 0:
        await db.plans.insert_many([{**p, "shop_id": shop_id} for p in DEFAULT_PLANS])
    if with_barbers and await db.barbers.count_documents({"shop_id": shop_id}) == 0:
        await db.barbers.insert_many([
            {"name": "Marcos Silva", "specialty": "Fade & Degradê", "phone": "(11) 99999-1111",
             "avatar": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?crop=entropy&cs=srgb&fm=jpg&q=85&w=400",
             "active": True, "commission_rate": 50, "working_hours": DEFAULT_HOURS, "total_cuts": 0, "shop_id": shop_id},
            {"name": "Rafael Costa", "specialty": "Barba & Navalha", "phone": "(11) 99999-2222",
             "avatar": "https://images.unsplash.com/photo-1599351431202-1e0f0137899a?crop=entropy&cs=srgb&fm=jpg&q=85&w=400",
             "active": True, "commission_rate": 45, "working_hours": DEFAULT_HOURS, "total_cuts": 0, "shop_id": shop_id},
            {"name": "Diego Alves", "specialty": "Cortes Clássicos", "phone": "(11) 99999-3333",
             "avatar": "https://images.unsplash.com/photo-1536520002442-39764a41e987?crop=entropy&cs=srgb&fm=jpg&q=85&w=400",
             "active": True, "commission_rate": 55, "working_hours": DEFAULT_HOURS, "total_cuts": 0, "shop_id": shop_id},
        ])


# ---------------- Public signup / booking ----------------
@api_router.get("/public/platform-plans")
async def public_platform_plans():
    plans = await db.platform_plans.find({"active": {"$ne": False}}).sort("monthly_price", 1).to_list(100)
    return [_platform_plan_summary(p) for p in plans]


async def _public_shop(slug: str):
    shop = await db.shops.find_one({"public_slug": slug.strip().lower(), "status": "active"})
    if not shop:
        raise HTTPException(404, "Barbearia não encontrada ou indisponível")
    plan = await _shop_platform_plan(oid(shop["_id"]))
    if not plan or plan.get("name", "").strip().lower() not in {"profissional", "premium"}:
        raise HTTPException(403, "O agendamento público está disponível nos planos Profissional e Premium.")
    return shop


async def _public_whatsapp_settings(shop_id: str) -> dict:
    plan = await _shop_platform_plan(shop_id)
    if not plan or plan.get("name", "").strip().lower() != "premium":
        return {"booking_enabled": False, "phone": ""}
    doc = await db.whatsapp_integrations.find_one({"shop_id": shop_id})
    if not doc or not doc.get("booking_enabled"):
        return {"booking_enabled": False, "phone": ""}
    return {
        "booking_enabled": True,
        "phone": doc.get("phone_normalized", ""),
    }


@api_router.get("/public/shops/{slug}")
async def public_shop(slug: str):
    shop = await _public_shop(slug)
    sid = oid(shop["_id"])
    barbers = await db.barbers.find({"shop_id": sid, "active": {"$ne": False}}).to_list(100)
    services = await db.services.find({"shop_id": sid, "active": {"$ne": False}}).to_list(100)
    return {
        "name": shop.get("name", ""),
        "slug": shop.get("public_slug", ""),
        "whatsapp": await _public_whatsapp_settings(sid),
        "barbers": [{"id": oid(b["_id"]), "name": b.get("name", ""), "specialty": b.get("specialty", "")} for b in barbers],
        "services": [{"id": oid(x["_id"]), "name": x.get("name", ""), "duration": x.get("duration", 30), "price": x.get("price", 0)} for x in services],
    }


@api_router.get("/public/shops/{slug}/availability")
async def public_availability(slug: str, barber_id: str, date: str, service_id: Optional[str] = None):
    shop = await _public_shop(slug)
    sid = oid(shop["_id"])
    barber = await db.barbers.find_one({"_id": safe_object_id(barber_id, "Barbeiro"), "shop_id": sid, "active": {"$ne": False}})
    if not barber:
        raise HTTPException(404, "Barbeiro não encontrado")
    hours = _working_hours_for_date(barber, date)
    if not hours:
        return {"slots": []}
    duration = await _requested_service_duration(sid, service_id)
    return {"slots": await _available_slots(sid, barber_id, date, hours, duration)}


@api_router.post("/public/shops/{slug}/appointments")
async def public_create_appointment(slug: str, data: PublicAppointmentIn):
    shop = await _public_shop(slug)
    sid = oid(shop["_id"])
    name = data.client_name.strip()
    phone = data.client_phone.strip()
    phone_normalized = _only_digits(phone)
    if not name:
        raise HTTPException(400, "Informe seu nome")
    if len(phone_normalized) < 10 or len(phone_normalized) > 13:
        raise HTTPException(400, "Informe um telefone válido")
    barber = await db.barbers.find_one({"_id": safe_object_id(data.barber_id, "Barbeiro"), "shop_id": sid, "active": {"$ne": False}})
    service = await db.services.find_one({"_id": safe_object_id(data.service_id, "Serviço"), "shop_id": sid, "active": {"$ne": False}})
    if not barber or not service:
        raise HTTPException(404, "Barbeiro ou serviço indisponível")
    duration = _service_duration(service)
    _assert_within_working_hours(barber, data.date, data.time, duration)
    async def create_booking(session):
        cust = await db.users.find_one(
            {"shop_id": sid, "role": "client", "phone_normalized": phone_normalized},
            session=session,
        )
        client_name = name
        client_phone = phone
        if not cust:
            client_doc = {
                "name": name, "role": "client", "phone": phone, "phone_normalized": phone_normalized,
                "shop_id": sid, "crm_only": True, "points": 0, "total_spend": 0,
                "preferred_barber": "", "notes": "", "created_at": datetime.now(timezone.utc).isoformat(),
            }
            result = await db.users.insert_one(client_doc, session=session)
            client_id = oid(result.inserted_id)
        else:
            client_id = oid(cust["_id"])
            client_name = cust.get("name", client_name)
            client_phone = cust.get("phone", client_phone)
        doc = {
            "shop_id": sid, "shop_name": shop.get("name", "BarberStudio"),
            "barber_id": data.barber_id, "barber_name": barber.get("name", ""),
            "service_id": data.service_id, "service_name": service.get("name", ""),
            "price": service.get("price", 0), "date": data.date, "time": data.time,
            "client_id": client_id, "client_name": client_name, "client_phone": client_phone, "client_email": "",
            "status": "Confirmado", "reminder_sent": False, "booking_source": "public_link",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = await db.appointments.insert_one(doc, session=session)
        return result, doc

    result, doc = await _create_booking_atomically(
        sid, data.barber_id, data.date, data.time, duration, create_booking
    )
    out = dict(doc)
    out["id"] = oid(result.inserted_id)
    await email_service.safe_send_confirmation(out)
    return {"ok": True, "appointment": _appt_out({**doc, "_id": result.inserted_id})}


# ---------------- Auth routes ----------------
@api_router.post("/auth/request-access")
async def request_access(data: ShopCreateIn, request: Request):
    validate_password(data.password)
    await rate_limit(f"req:{client_ip(request)}", max_attempts=8, window_minutes=30)
    if not valid_cpf_cnpj(data.cpf_cnpj):
        await bump_attempt(f"req:{client_ip(request)}")
        raise HTTPException(status_code=400, detail="CPF/CNPJ inválido")
    doc_digits = _only_digits(data.cpf_cnpj)
    if await db.shops.find_one({"cpf_cnpj": doc_digits}):
        raise HTTPException(status_code=400, detail="Já existe uma barbearia com este CPF/CNPJ")
    plan_id = safe_object_id(data.platform_plan_id, "Plano")
    selected_plan = await db.platform_plans.find_one({"_id": plan_id, "active": {"$ne": False}})
    if not selected_plan:
        raise HTTPException(status_code=400, detail="Plano selecionado não está disponível")
    code = await unique_shop_code()
    public_slug = await unique_shop_slug(data.shop_name)
    shop_doc = {
        "name": data.shop_name.strip(), "code": code, "public_slug": public_slug, "status": "pending",
        "responsible_name": data.name, "cpf_cnpj": doc_digits,
        "phone": data.phone, "email": data.email.lower(),
        "decision_history": [],
        "platform_plan_id": selected_plan["_id"],
        "platform_plan_name": selected_plan.get("name", ""),
        "subscription_status": "pending",
        "subscription_status_source": "signup",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    shop_res = await db.shops.insert_one(shop_doc)
    shop_id = oid(shop_res.inserted_id)
    email = data.email.lower()
    admin = {
        "email": email, "password_hash": hash_password(data.password),
        "name": data.name, "role": "admin", "phone": data.phone, "shop_id": shop_id,
        "points": 0, "total_spend": 0, "preferred_barber": "", "notes": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(admin)
    await seed_shop_defaults(shop_id)
    return {
        "status": "pending", "shop_code": code, "public_slug": public_slug,
        "platform_plan_name": selected_plan.get("name", ""),
        "message": "Cadastro em análise — aguardando aprovação do administrador da plataforma.",
    }


@api_router.post("/auth/login")
async def login(data: LoginIn, request: Request):
    ident = f"login:{client_ip(request)}:{data.shop_code.strip().upper()}:{data.email.lower()}"
    await rate_limit(ident)
    shop = await db.shops.find_one({"code": data.shop_code.strip().upper()})
    email = data.email.lower()
    user = await db.users.find_one({"shop_id": oid(shop["_id"]), "email": email}) if shop else None
    if not shop or not user or not verify_password(data.password, user["password_hash"]):
        await bump_attempt(ident)
        raise HTTPException(status_code=401, detail="Barbearia, e-mail ou senha inválidos")
    # Client accounts are kept only as CRM records for now; the customer portal is disabled.
    if user.get("role") == "client":
        raise HTTPException(status_code=403, detail="Acesso de clientes não está disponível.")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Perfil sem acesso ao painel.")
    await clear_attempts(ident)
    return await auth_response(user)


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user_raw)):
    u = serialize_user(user)
    u.update(await _shop_fields(user))
    return u


@api_router.get("/shops/resolve")
async def resolve_shop(code: str):
    shop = await db.shops.find_one({"code": code.strip().upper()})
    if not shop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada")
    return {"code": shop["code"], "name": shop["name"]}


@api_router.get("/shop/public-link")
async def shop_public_link(admin: dict = Depends(require_admin)):
    shop = await db.shops.find_one({"_id": safe_object_id(admin["shop_id"], "Barbearia")})
    if not shop:
        raise HTTPException(404, "Barbearia não encontrada")
    plan = await _shop_platform_plan(admin["shop_id"])
    if not plan or plan.get("name", "").strip().lower() not in {"profissional", "premium"}:
        raise HTTPException(403, "O agendamento público está disponível nos planos Profissional e Premium.")
    slug = shop.get("public_slug")
    if not slug:
        slug = await unique_shop_slug(shop.get("name", "barbearia"))
        await db.shops.update_one({"_id": shop["_id"]}, {"$set": {"public_slug": slug}})
    return {"slug": slug, "path": f"/agendar/{slug}"}


# ---------------- Plan capabilities ----------------
@api_router.get("/shop/capabilities")
async def shop_capabilities(admin: dict = Depends(require_admin)):
    plan = await _shop_platform_plan(admin["shop_id"])
    name = plan.get("name", "").strip().lower() if plan else ""
    return {
        "platform_plan_name": plan.get("name", "") if plan else "",
        "public_booking": name in {"profissional", "premium"},
        "whatsapp_booking_confirmation": name == "premium",
    }


# ---------------- WhatsApp integration ----------------
@api_router.get("/integrations/whatsapp")
async def get_whatsapp_integration(admin: dict = Depends(require_admin)):
    plan = await _shop_platform_plan(admin["shop_id"])
    if not plan or plan.get("name", "").strip().lower() != "premium":
        raise HTTPException(403, "A confirmação pelo WhatsApp é exclusiva do plano Premium.")
    doc = await db.whatsapp_integrations.find_one({"shop_id": admin["shop_id"]})
    if not doc:
        return {"phone": "", "status": "not_connected", "booking_enabled": True, "plans_enabled": True}
    return {
        "phone": doc.get("phone", ""), "status": doc.get("status", "configured"),
        "booking_enabled": doc.get("booking_enabled", True),
        "plans_enabled": doc.get("plans_enabled", True),
    }


@api_router.put("/integrations/whatsapp")
async def save_whatsapp_integration(data: WhatsAppIntegrationIn, admin: dict = Depends(require_admin)):
    plan = await _shop_platform_plan(admin["shop_id"])
    if not plan or plan.get("name", "").strip().lower() != "premium":
        raise HTTPException(403, "A confirmação pelo WhatsApp é exclusiva do plano Premium.")
    phone = _only_digits(data.phone)
    if data.booking_enabled and (len(phone) < 10 or len(phone) > 13):
        raise HTTPException(400, "Número de WhatsApp inválido")
    if phone and len(phone) <= 11 and not phone.startswith("55"):
        phone = "55" + phone
    now = datetime.now(timezone.utc).isoformat()
    await db.whatsapp_integrations.update_one(
        {"shop_id": admin["shop_id"]},
        {"$set": {
            "shop_id": admin["shop_id"], "phone": data.phone.strip(),
            "phone_normalized": phone, "status": "configured",
            "booking_enabled": data.booking_enabled, "plans_enabled": data.plans_enabled,
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"phone": data.phone.strip(), "status": "configured",
            "booking_enabled": data.booking_enabled, "plans_enabled": data.plans_enabled}


# ---------------- Platform plan limits ----------------
async def _shop_platform_plan(shop_id):
    shop_oid = safe_object_id(shop_id, "Barbearia") if isinstance(shop_id, str) else shop_id
    shop = await db.shops.find_one({"_id": shop_oid})
    if not shop or not shop.get("platform_plan_id"):
        return None
    # The commercial plan defines limits even if billing is pending/suspended.
    # Billing status controls access separately; it must not silently remove limits.
    return await db.platform_plans.find_one({"_id": shop["platform_plan_id"]})


async def _enforce_platform_limit(shop_id, resource: str):
    plan = await _shop_platform_plan(shop_id)
    if not plan:
        return
    if resource == "professionals":
        limit = plan.get("max_professionals")
        current = await db.barbers.count_documents({"shop_id": shop_id, "active": {"$ne": False}})
        label = "profissionais"
    elif resource == "services":
        limit = plan.get("max_services")
        current = await db.services.count_documents({"shop_id": shop_id, "active": {"$ne": False}})
        label = "serviços"
    else:
        limit = plan.get("max_client_plans")
        current = await db.plans.count_documents({"shop_id": shop_id})
        label = "planos de assinatura para clientes"
    if limit is not None and current >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Seu plano {plan.get('name', '')} permite até {limit} {label}. Faça upgrade do plano para adicionar mais.",
        )


# ---------------- Barbers ----------------
@api_router.get("/barbers")
async def list_barbers(user: dict = Depends(get_current_user)):
    docs = await db.barbers.find({"shop_id": user["shop_id"]}).to_list(500)
    return [{"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in docs]


@api_router.post("/barbers")
async def create_barber(data: BarberIn, admin: dict = Depends(require_admin)):
    if data.active:
        await _enforce_platform_limit(admin["shop_id"], "professionals")
    doc = data.model_dump()
    doc["total_cuts"] = 0
    doc["shop_id"] = admin["shop_id"]
    out = dict(doc)
    res = await db.barbers.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out


@api_router.put("/barbers/{barber_id}")
async def update_barber(barber_id: str, data: BarberIn, admin: dict = Depends(require_admin)):
    d = await db.barbers.find_one({"_id": safe_object_id(barber_id, "Barbeiro"), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Barbeiro não encontrado")
    if data.active and not d.get("active", True):
        await _enforce_platform_limit(admin["shop_id"], "professionals")
    await db.barbers.update_one({"_id": safe_object_id(barber_id, "Barbeiro")}, {"$set": data.model_dump()})
    d = await db.barbers.find_one({"_id": safe_object_id(barber_id, "Barbeiro")})
    return {"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}}


@api_router.delete("/barbers/{barber_id}")
async def delete_barber(barber_id: str, admin: dict = Depends(require_admin)):
    res = await db.barbers.delete_one({"_id": safe_object_id(barber_id, "Barbeiro"), "shop_id": admin["shop_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Barbeiro não encontrado")
    return {"ok": True}


# ---------------- Services ----------------
@api_router.get("/services")
async def list_services(user: dict = Depends(get_current_user)):
    query = {"shop_id": user["shop_id"]}

    if user["role"] != "admin":
        query["active"] = {"$ne": False}

    docs = await db.services.find(query).to_list(500)

    return [
        {"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}}
        for d in docs
    ]


@api_router.post("/services")
async def create_service(data: ServiceIn, admin: dict = Depends(require_admin)):
    await _enforce_platform_limit(admin["shop_id"], "services")
    doc = data.model_dump()
    doc["shop_id"] = admin["shop_id"]
    out = dict(doc)
    res = await db.services.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out

@api_router.put("/services/{service_id}")
async def update_service(
    service_id: str,
    data: ServiceIn,
    admin: dict = Depends(require_admin)
):
    if not ObjectId.is_valid(service_id):
        raise HTTPException(400, "ID do serviço inválido")

    result = await db.services.update_one(
        {
            "_id": safe_object_id(service_id, "Serviço"),
            "shop_id": admin["shop_id"]
        },
        {
            "$set": {
                "name": data.name,
                "duration": data.duration,
                "price": data.price
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Serviço não encontrado")

    return {"ok": True}
    


@api_router.patch("/services/{service_id}/status")
async def change_service_status(
    service_id: str,
    admin: dict = Depends(require_admin)
):
    service = await db.services.find_one({
        "_id": safe_object_id(service_id, "Serviço"),
        "shop_id": admin["shop_id"]
    })

    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    new_status = not service.get("active", True)
    if new_status:
        await _enforce_platform_limit(admin["shop_id"], "services")

    await db.services.update_one(
        {"_id": service["_id"], "shop_id": admin["shop_id"]},
        {"$set": {"active": new_status}}
    )

    return {"ok": True, "active": new_status}


# ---------------- Availability ----------------
def _service_duration(service: dict | None, default: int = 30) -> int:
    try:
        duration = int(service.get("duration", default)) if service else default
    except (TypeError, ValueError):
        duration = default
    return duration if duration > 0 else default


async def _requested_service_duration(shop_id: str, service_id: Optional[str]) -> int:
    if not service_id:
        return 30
    service = await db.services.find_one({
        "_id": safe_object_id(service_id, "Serviço"),
        "shop_id": shop_id,
        "active": {"$ne": False},
    })
    if not service:
        raise HTTPException(404, "Serviço não encontrado")
    return _service_duration(service)


def _time_to_minutes(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError):
        raise HTTPException(400, "Horário inválido")
    return parsed.hour * 60 + parsed.minute


def _working_hours_for_date(barber: dict, date: str):
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Data inválida")
    hours = (barber.get("working_hours") or {}).get(WEEKDAYS[day.weekday()])
    if not hours or not hours.get("start") or not hours.get("end"):
        return None
    return hours


def _assert_within_working_hours(barber: dict, date: str, time: str, duration: int) -> None:
    hours = _working_hours_for_date(barber, date)
    if not hours:
        raise HTTPException(400, "O barbeiro não atende nesta data")
    start = _time_to_minutes(time)
    end = _time_to_minutes(hours["end"])
    opening = _time_to_minutes(hours["start"])
    if start < opening or start + duration > end:
        raise HTTPException(400, "Agendamento fora do horário de atendimento")


def gen_slots(start: str, end: str, interval: int = 30, duration: Optional[int] = None):
    slots = []
    cur = _time_to_minutes(start)
    last = _time_to_minutes(end)
    duration = duration or interval
    interval = max(1, interval)
    while cur + duration <= last:
        slots.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += interval
    return slots


async def _appointment_duration(appointment: dict, shop_id: str, session=None) -> int:
    if appointment.get("duration") is not None:
        return _service_duration({"duration": appointment["duration"]})
    service_id = appointment.get("service_id")
    if service_id and ObjectId.is_valid(service_id):
        service = await db.services.find_one(
            {"_id": ObjectId(service_id), "shop_id": shop_id}, session=session
        )
        if service:
            return _service_duration(service)
    return 30


def _intervals_overlap(start: int, duration: int, other_start: int, other_duration: int) -> bool:
    return start < other_start + other_duration and other_start < start + duration


async def _booking_conflicts(
    shop_id: str, barber_id: str, date: str, time: str, duration: int, session=None
) -> bool:
    appointments = await db.appointments.find({
        "shop_id": shop_id,
        "barber_id": barber_id,
        "date": date,
        "status": {"$ne": "Cancelado"},
    }, session=session).to_list(None)
    start = _time_to_minutes(time)
    for appointment in appointments:
        try:
            other_start = _time_to_minutes(appointment["time"])
        except (KeyError, HTTPException):
            continue
        other_duration = await _appointment_duration(appointment, shop_id, session=session)
        if _intervals_overlap(start, duration, other_start, other_duration):
            return True
    return False


async def _create_booking_atomically(
    shop_id: str,
    barber_id: str,
    date: str,
    time: str,
    duration: int,
    create_booking,
):
    lock_id = f"{shop_id}:{barber_id}"
    try:
        await db.booking_locks.update_one(
            {"_id": lock_id}, {"$setOnInsert": {"revision": 0}}, upsert=True
        )
    except DuplicateKeyError:
        # Another instance created this shop/barber/day lock concurrently.
        pass

    async def in_transaction(session):
        lock_result = await db.booking_locks.update_one(
            {"_id": lock_id}, {"$inc": {"revision": 1}}, session=session
        )
        if lock_result.matched_count != 1:
            raise RuntimeError("Não foi possível adquirir o bloqueio transacional da agenda")
        if await _booking_conflicts(shop_id, barber_id, date, time, duration, session=session):
            raise HTTPException(status_code=409, detail="Este horário já está indisponível")
        return await create_booking(session)

    async with await client.start_session() as session:
        return await session.with_transaction(in_transaction)


async def _available_slots(shop_id: str, barber_id: str, date: str, hours: dict, duration: int):
    interval = min(30, duration)
    slots = gen_slots(hours["start"], hours["end"], interval=interval, duration=duration)
    appointments = await db.appointments.find({
        "shop_id": shop_id,
        "barber_id": barber_id,
        "date": date,
        "status": {"$ne": "Cancelado"},
    }).to_list(None)
    available = []
    for slot in slots:
        start = _time_to_minutes(slot)
        conflict = False
        for appointment in appointments:
            try:
                other_start = _time_to_minutes(appointment["time"])
            except (KeyError, HTTPException):
                continue
            other_duration = await _appointment_duration(appointment, shop_id)
            if _intervals_overlap(start, duration, other_start, other_duration):
                conflict = True
                break
        available.append({"time": slot, "available": not conflict})
    return available


@api_router.get("/availability")
async def availability(
    barber_id: str,
    date: str,
    user: dict = Depends(get_current_user),
    service_id: Optional[str] = None,
):
    barber = await db.barbers.find_one({"_id": safe_object_id(barber_id, "Barbeiro"), "shop_id": user["shop_id"]})
    if not barber:
        raise HTTPException(404, "Barbeiro não encontrado")
    hours = _working_hours_for_date(barber, date)
    if not hours:
        return {"slots": []}
    duration = await _requested_service_duration(user["shop_id"], service_id)
    return {"slots": await _available_slots(user["shop_id"], barber_id, date, hours, duration)}


# ---------------- Appointments ----------------
def _appt_out(a):
    return {"id": oid(a["_id"]), **{k: v for k, v in a.items() if k != "_id"}}


@api_router.get("/appointments")
async def list_appointments(user: dict = Depends(get_current_user)):
    q = {"shop_id": user["shop_id"]}
    if user["role"] != "admin":
        q["client_id"] = oid(user["_id"])
    docs = await db.appointments.find(q).sort("date", 1).to_list(1000)
    return [_appt_out(a) for a in docs]


@api_router.post("/appointments")
async def create_appointment(data: AppointmentIn, user: dict = Depends(get_current_user)):
    sid = user["shop_id"]
    barber = await db.barbers.find_one({"_id": safe_object_id(data.barber_id, "Barbeiro"), "shop_id": sid})
    if not barber:
        raise HTTPException(404, "Barbeiro não encontrado")

    service = await db.services.find_one({
        "_id": safe_object_id(data.service_id, "Serviço"),
        "shop_id": sid,
        "active": {"$ne": False}
    })
    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    duration = _service_duration(service)
    _assert_within_working_hours(barber, data.date, data.time, duration)
    if user["role"] == "admin" and not data.client_id and not data.client_name:
        raise HTTPException(400, "Informe o cliente cadastrado ou o nome do cliente avulso")
    shop = await db.shops.find_one({"_id": ObjectId(sid)})
    async def create_booking(session):
        if user["role"] == "admin" and data.client_id:
            cust = await db.users.find_one(
                {"_id": safe_object_id(data.client_id, "Cliente"), "shop_id": sid},
                session=session,
            )
            if not cust:
                raise HTTPException(404, "Cliente não encontrado")
            client_id = data.client_id
            client_name = cust["name"]
            client_phone = cust.get("phone", "")
            client_email = cust.get("email", "")
        elif user["role"] == "admin" and data.client_name:
            client_name = data.client_name.strip()
            client_phone = (data.client_phone or "").strip()
            phone_normalized = _only_digits(client_phone)
            cust = None
            if 10 <= len(phone_normalized) <= 13:
                cust = await db.users.find_one({
                    "shop_id": sid, "role": "client", "phone_normalized": phone_normalized
                }, session=session)
            if not cust:
                client_doc = {
                    "name": client_name, "role": "client", "phone": client_phone,
                    "phone_normalized": phone_normalized, "shop_id": sid, "crm_only": True,
                    "points": 0, "total_spend": 0, "preferred_barber": "", "notes": "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                result = await db.users.insert_one(client_doc, session=session)
                client_id = oid(result.inserted_id)
            else:
                client_id = oid(cust["_id"])
                client_name = cust.get("name", client_name)
                client_phone = cust.get("phone", client_phone)
            client_email = ""
        else:
            client_id = oid(user["_id"])
            client_name = user["name"]
            client_phone = user.get("phone", "")
            client_email = user.get("email", "")
        doc = {
            "shop_id": sid, "shop_name": shop["name"] if shop else "BarberStudio",
            "barber_id": data.barber_id, "barber_name": barber["name"],
            "service_id": data.service_id, "service_name": service["name"],
            "price": service.get("price", 0),
            "date": data.date, "time": data.time,
            "client_id": client_id, "client_name": client_name,
            "client_phone": client_phone, "client_email": client_email,
            "status": "Confirmado", "reminder_sent": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = await db.appointments.insert_one(doc, session=session)
        return result, doc

    res, doc = await _create_booking_atomically(
        sid, data.barber_id, data.date, data.time, duration, create_booking
    )
    out = dict(doc)
    out["id"] = oid(res.inserted_id)
    # Serverless-safe: send confirmation inline (safe_send never raises).
    await email_service.safe_send_confirmation(out)
    return out


@api_router.patch("/appointments/{appt_id}/status")
async def update_status(appt_id: str, data: StatusIn, admin: dict = Depends(require_admin)):
    allowed_statuses = {"Confirmado", "Concluído", "Cancelado"}
    if data.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Status de agendamento inválido")
    appointment_oid = safe_object_id(appt_id, "Agendamento")
    appt = await db.appointments.find_one({"_id": appointment_oid, "shop_id": admin["shop_id"]})
    if not appt:
        raise HTTPException(404, "Agendamento não encontrado")
    await db.appointments.update_one(
        {"_id": appointment_oid, "shop_id": admin["shop_id"]},
        {"$set": {"status": data.status}},
    )
    if data.status == "Concluído" and appt.get("status") != "Concluído":
        if appt.get("client_id"):
            await db.users.update_one(
                {"_id": safe_object_id(appt["client_id"], "Cliente"), "shop_id": admin["shop_id"]},
                {"$inc": {"points": 10, "total_spend": appt.get("price", 0)}},
            )
        await db.barbers.update_one(
            {"_id": safe_object_id(appt["barber_id"], "Barbeiro"), "shop_id": admin["shop_id"]},
            {"$inc": {"total_cuts": 1}},
        )
    return {"ok": True}


@api_router.delete("/appointments/{appt_id}")
async def delete_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    appt = await db.appointments.find_one({"_id": safe_object_id(appt_id, "Agendamento"), "shop_id": user["shop_id"]})
    if not appt:
        raise HTTPException(404, "Agendamento não encontrado")
    if user["role"] != "admin" and appt.get("client_id") != oid(user["_id"]):
        raise HTTPException(403, "Sem permissão")
    await db.appointments.delete_one({"_id": safe_object_id(appt_id, "Agendamento")})
    return {"ok": True}


# ---------------- Clients (CRM) ----------------
@api_router.get("/clients")
async def list_clients(admin: dict = Depends(require_admin)):
    sid = admin["shop_id"]
    docs = await db.users.find({"role": "client", "shop_id": sid}).to_list(1000)
    out = []
    for d in docs:
        count = await db.appointments.count_documents({"client_id": oid(d["_id"]), "shop_id": sid})
        sub = await db.subscriptions.find_one({"client_id": oid(d["_id"]), "shop_id": sid, "status": "Ativo"})
        u = serialize_user(d, include_private_notes=True)
        u["visits"] = count
        u["plan_name"] = sub["plan_name"] if sub else None
        out.append(u)
    return out


@api_router.post("/clients")
async def create_client(data: ClientIn, admin: dict = Depends(require_admin)):
    sid = admin["shop_id"]
    name = data.name.strip()
    phone = _only_digits(data.phone)
    if not name:
        raise HTTPException(400, "Nome é obrigatório")
    if len(phone) < 10 or len(phone) > 13:
        raise HTTPException(400, "Telefone inválido")
    if await db.users.find_one({"shop_id": sid, "role": "client", "phone_normalized": phone}):
        raise HTTPException(409, "Já existe um cliente com este telefone nesta barbearia")

    doc = {
        "name": name, "role": "client", "phone": data.phone.strip(),
        "phone_normalized": phone, "shop_id": sid, "crm_only": True,
        "points": 0, "total_spend": 0, "preferred_barber": "", "notes": (data.notes or "").strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize_user(doc, include_private_notes=True)


@api_router.put("/clients/{client_id}")
async def update_client(client_id: str, data: ClientIn, admin: dict = Depends(require_admin)):
    d = await db.users.find_one({"_id": safe_object_id(client_id, "Cliente"), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    name = data.name.strip()
    phone = _only_digits(data.phone)
    if not name:
        raise HTTPException(400, "Nome é obrigatório")
    if len(phone) < 10 or len(phone) > 13:
        raise HTTPException(400, "Telefone inválido")
    duplicate = await db.users.find_one({
        "shop_id": admin["shop_id"], "role": "client", "phone_normalized": phone,
        "_id": {"$ne": d["_id"]},
    })
    if duplicate:
        raise HTTPException(409, "Já existe um cliente com este telefone nesta barbearia")
    await db.users.update_one(
        {"_id": d["_id"], "shop_id": admin["shop_id"]},
        {"$set": {"name": name, "phone": data.phone.strip(), "phone_normalized": phone,
                  "notes": (data.notes or "").strip()}},
    )
    d = await db.users.find_one({"_id": d["_id"], "shop_id": admin["shop_id"]})
    return serialize_user(d, include_private_notes=True)


@api_router.patch("/clients/{client_id}/loyalty")
async def set_loyalty(client_id: str, data: LoyaltyIn, admin: dict = Depends(require_admin)):
    d = await db.users.find_one({"_id": safe_object_id(client_id, "Cliente"), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    client_oid = safe_object_id(client_id, "Cliente")
    await db.users.update_one(
        {"_id": client_oid, "shop_id": admin["shop_id"], "role": "client"},
        {"$set": {"points": max(0, data.points)}},
    )
    d = await db.users.find_one({"_id": client_oid, "shop_id": admin["shop_id"], "role": "client"})
    return serialize_user(d, include_private_notes=True)


@api_router.post("/clients/{client_id}/redeem")
async def redeem(client_id: str, admin: dict = Depends(require_admin)):
    d = await db.users.find_one({"_id": safe_object_id(client_id, "Cliente"), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    if d.get("points", 0) < 100:
        raise HTTPException(400, "Pontos insuficientes (mínimo 100)")
    await db.users.update_one(
        {"_id": safe_object_id(client_id, "Cliente"), "shop_id": admin["shop_id"], "role": "client"},
        {"$inc": {"points": -100}},
    )
    return {"ok": True, "message": "Recompensa resgatada: 1 corte grátis"}


# ---------------- Plans ----------------
@api_router.get("/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    docs = await db.plans.find({"shop_id": user["shop_id"]}).to_list(500)
    return [{"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in docs]


@api_router.post("/plans")
async def create_plan(data: PlanIn, admin: dict = Depends(require_admin)):
    await _enforce_platform_limit(admin["shop_id"], "client_plans")
    doc = data.model_dump()
    doc["shop_id"] = admin["shop_id"]
    out = dict(doc)
    res = await db.plans.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out


@api_router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, data: PlanIn, admin: dict = Depends(require_admin)):
    d = await db.plans.find_one({"_id": safe_object_id(plan_id, "Plano"), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Plano não encontrado")
    await db.plans.update_one(
        {"_id": safe_object_id(plan_id, "Plano"), "shop_id": admin["shop_id"]},
        {"$set": data.model_dump()},
    )
    d = await db.plans.find_one({"_id": safe_object_id(plan_id, "Plano"), "shop_id": admin["shop_id"]})
    return {"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}}


@api_router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, admin: dict = Depends(require_admin)):
    res = await db.plans.delete_one({"_id": safe_object_id(plan_id, "Plano"), "shop_id": admin["shop_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Plano não encontrado")
    return {"ok": True}


# ---------------- Subscriptions ----------------
@api_router.get("/subscriptions")
async def list_subscriptions(admin: dict = Depends(require_admin)):
    docs = await db.subscriptions.find({"shop_id": admin["shop_id"]}).sort("created_at", -1).to_list(1000)
    return [{"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in docs]


@api_router.get("/subscriptions/me")
async def my_subscription(user: dict = Depends(get_current_user)):
    docs = await db.subscriptions.find(
        {"client_id": oid(user["_id"]), "shop_id": user["shop_id"]}
    ).sort("created_at", -1).to_list(100)
    return [{"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in docs]


@api_router.post("/subscriptions")
async def create_subscription(data: SubscriptionIn, user: dict = Depends(get_current_user)):
    sid = user["shop_id"]
    plan = await db.plans.find_one({"_id": safe_object_id(data.plan_id, "Plano"), "shop_id": sid})
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    if user["role"] == "admin" and data.client_id:
        cust = await db.users.find_one({"_id": safe_object_id(data.client_id, "Cliente"), "shop_id": sid})
        if not cust:
            raise HTTPException(404, "Cliente não encontrado")
        client_id = data.client_id
        client_name = cust["name"]
    else:
        client_id = oid(user["_id"])
        client_name = user["name"]
    await db.subscriptions.update_many(
        {"client_id": client_id, "shop_id": sid, "status": "Ativo"}, {"$set": {"status": "Cancelado"}}
    )
    doc = {
        "shop_id": sid, "client_id": client_id, "client_name": client_name,
        "plan_id": data.plan_id, "plan_name": plan["name"], "price": plan["price"],
        "status": "Pendente",
        "start_date": None,
        "renewal_date": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out = dict(doc)
    res = await db.subscriptions.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out


@api_router.delete("/subscriptions/{sub_id}")
async def cancel_subscription(sub_id: str, admin: dict = Depends(require_admin)):
    res = await db.subscriptions.update_one(
        {"_id": safe_object_id(sub_id, "Assinatura"), "shop_id": admin["shop_id"]}, {"$set": {"status": "Cancelado"}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Assinatura não encontrada")
    return {"ok": True}


# ---------------- Dashboard ----------------
@api_router.get("/dashboard/stats")
async def dashboard_stats(admin: dict = Depends(require_admin)):
    sid = admin["shop_id"]
    today = datetime.now(timezone.utc).date().isoformat()
    month_prefix = today[:7]
    appts_today = await db.appointments.count_documents({"shop_id": sid, "date": today, "status": {"$ne": "Cancelado"}})
    completed = await db.appointments.find({"shop_id": sid, "status": "Concluído"}).to_list(5000)
    revenue_month = sum(a.get("price", 0) for a in completed if a.get("date", "").startswith(month_prefix))
    revenue_total = sum(a.get("price", 0) for a in completed)
    total_clients = await db.users.count_documents({"role": "client", "shop_id": sid})
    total_barbers = await db.barbers.count_documents({"shop_id": sid})
    active_subs = await db.subscriptions.count_documents({"shop_id": sid, "status": "Ativo"})
    barber_rev = {}
    for a in completed:
        barber_rev[a.get("barber_name", "?")] = barber_rev.get(a.get("barber_name", "?"), 0) + a.get("price", 0)
    top_barber = max(barber_rev.items(), key=lambda x: x[1])[0] if barber_rev else "—"
    upcoming = await db.appointments.find(
        {"shop_id": sid, "date": {"$gte": today}, "status": "Confirmado"}
    ).sort("date", 1).to_list(8)
    upcoming_out = [{"id": oid(a["_id"]), **{k: v for k, v in a.items() if k != "_id"}} for a in upcoming]
    series = []
    for i in range(6, -1, -1):
        d = (datetime.now(timezone.utc).date() - timedelta(days=i)).isoformat()
        rev = sum(a.get("price", 0) for a in completed if a.get("date") == d)
        series.append({"date": d[5:], "revenue": rev})
    return {
        "appts_today": appts_today, "revenue_month": revenue_month, "revenue_total": revenue_total,
        "total_clients": total_clients, "total_barbers": total_barbers, "active_subs": active_subs,
        "top_barber": top_barber, "upcoming": upcoming_out, "series": series,
    }


# ---------------- Barber Reports ----------------
@api_router.get("/reports/capabilities")
async def report_capabilities(admin: dict = Depends(require_admin)):
    plan = await _shop_platform_plan(admin["shop_id"])
    return {
        "pdf_reports": bool(plan and plan.get("pdf_reports", False)),
        "platform_plan_name": plan.get("name", "") if plan else "",
    }


@api_router.get("/reports/barbers")
async def barber_report(month: Optional[str] = None, admin: dict = Depends(require_admin)):
    sid = admin["shop_id"]
    if not month:
        month = datetime.now(timezone.utc).date().isoformat()[:7]
    barbers = await db.barbers.find({"shop_id": sid}).to_list(500)
    completed = await db.appointments.find({
        "shop_id": sid, "status": "Concluído", "date": {"$regex": f"^{month}"},
    }).to_list(5000)
    report = []
    for b in barbers:
        bid = oid(b["_id"])
        rate = b.get("commission_rate", 50)
        appts = [a for a in completed if a.get("barber_id") == bid]
        revenue = sum(a.get("price", 0) for a in appts)
        services = {}
        for a in appts:
            services[a.get("service_name", "?")] = services.get(a.get("service_name", "?"), 0) + 1
        report.append({
            "barber_id": bid, "name": b["name"], "avatar": b.get("avatar", ""),
            "specialty": b.get("specialty", ""), "commission_rate": rate,
            "completed": len(appts), "revenue": revenue,
            "commission": round(revenue * rate / 100, 2),
            "avg_ticket": round(revenue / len(appts), 2) if appts else 0,
            "services": [{"name": k, "count": v} for k, v in sorted(services.items(), key=lambda x: -x[1])],
        })
    report.sort(key=lambda x: -x["revenue"])
    totals = {
        "revenue": sum(r["revenue"] for r in report),
        "commission": sum(r["commission"] for r in report),
        "completed": sum(r["completed"] for r in report),
    }
    return {"month": month, "report": report, "totals": totals}


# ---------------- Cron: reminders (works for Emergent cron POST and Vercel cron GET) ----------------
async def _run_reminders():
    brt = timezone(timedelta(hours=-3))
    target = (datetime.now(brt) + timedelta(days=1)).date().isoformat()
    appts = await db.appointments.find({
        "date": target, "status": "Confirmado", "reminder_sent": {"$ne": True},
    }).to_list(2000)
    sent_count = 0
    for a in appts:
        if await email_service.safe_send_reminder(a):
            await db.appointments.update_one({"_id": a["_id"]}, {"$set": {"reminder_sent": True}})
            sent_count += 1
    logger.info(f"Reminders for {target}: {len(appts)} due, {sent_count} sent")
    return {"date": target, "due": len(appts), "sent": sent_count}


def _cron_authorized(request: Request) -> bool:
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or os.environ.get("CRON_SECRET") or ""
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    return bool(secret) and hmac.compare_digest(token, secret)


@api_router.post("/cron/reminders")
async def cron_reminders_post(request: Request):
    if not _cron_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await _run_reminders()


@api_router.get("/cron/reminders")
async def cron_reminders_get(request: Request):
    if not _cron_authorized(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await _run_reminders()


# ---------------- Platform (Super Admin) ----------------
def _shop_admin_summary(shop: dict, full: bool = False) -> dict:
    return {
        "id": oid(shop["_id"]),
        "name": shop.get("name"),
        "code": shop.get("code"),
        "status": shop_status(shop),
        "responsible_name": shop.get("responsible_name", ""),
        "email": shop.get("email", ""),
        "phone": shop.get("phone", ""),
        "cpf_cnpj": shop.get("cpf_cnpj", "") if full else mask_doc(shop.get("cpf_cnpj", "")),
        "decision_history": shop.get("decision_history", []),
        "platform_plan_id": oid(shop["platform_plan_id"]) if shop.get("platform_plan_id") else None,
        "platform_plan_name": shop.get("platform_plan_name", ""),
        "subscription_status": shop.get("subscription_status", "unassigned"),
        "subscription_started_at": shop.get("subscription_started_at"),
        "subscription_current_period_end": shop.get("subscription_current_period_end"),
        "subscription_payment_method": shop.get("subscription_payment_method"),
        "billing_provider": shop.get("billing_provider"),
        "external_subscription_id": shop.get("external_subscription_id"),
        "subscription_status_source": shop.get("subscription_status_source", "manual"),
        "created_at": shop.get("created_at"),
    }


@api_router.post("/platform/login")
async def platform_login(data: PlatformLoginIn, request: Request):
    ident = f"plogin:{client_ip(request)}:{data.email.lower()}"
    await rate_limit(ident, max_attempts=6, window_minutes=15)
    admin = await db.platform_admins.find_one({"email": data.email.lower()})
    if not admin or not verify_password(data.password, admin["password_hash"]):
        await bump_attempt(ident)
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    await clear_attempts(ident)
    token = create_platform_token(oid(admin["_id"]), admin["email"])
    return {"token": token, "admin": {"email": admin["email"], "name": admin.get("name", "Super Admin")}}


@api_router.get("/platform/me")
async def platform_me(admin: dict = Depends(get_super_admin)):
    return {"email": admin["email"], "name": admin.get("name", "Super Admin")}


@api_router.get("/platform/stats")
async def platform_stats(_: dict = Depends(get_super_admin)):
    out = {
        "active": 0, "pending": 0, "suspended": 0, "rejected": 0, "total": 0,
        "subscriptions_active": 0, "subscriptions_past_due": 0,
        "subscriptions_pending": 0, "projected_mrr": 0.0,
    }
    plans = {oid(p["_id"]): p for p in await db.platform_plans.find().to_list(500)}
    for shop in await db.shops.find().to_list(5000):
        status = shop_status(shop)
        out[status] = out.get(status, 0) + 1
        out["total"] += 1
        sub_status = shop.get("subscription_status", "unassigned")
        if sub_status == "active":
            out["subscriptions_active"] += 1
            plan = plans.get(oid(shop["platform_plan_id"])) if shop.get("platform_plan_id") else None
            if plan:
                out["projected_mrr"] += float(plan.get("monthly_price", 0) or 0)
        elif sub_status == "past_due":
            out["subscriptions_past_due"] += 1
        elif sub_status == "pending":
            out["subscriptions_pending"] += 1
    out["projected_mrr"] = round(out["projected_mrr"], 2)
    return out


@api_router.get("/platform/shops")
async def platform_list_shops(status: Optional[str] = None, q: Optional[str] = None,
                              _: dict = Depends(get_super_admin)):
    shops = await db.shops.find().sort("created_at", -1).to_list(5000)
    out = []
    for s in shops:
        if status and shop_status(s) != status:
            continue
        if q:
            hay = f"{s.get('name','')} {s.get('responsible_name','')} {s.get('email','')} {s.get('code','')}".lower()
            if q.lower() not in hay:
                continue
        out.append(_shop_admin_summary(s))
    return out


@api_router.put("/platform/shops/{shop_id}/plan")
async def platform_assign_shop_plan(shop_id: str, data: PlatformShopPlanIn, admin: dict = Depends(get_super_admin)):
    try:
        sid = ObjectId(shop_id)
        pid = safe_object_id(data.plan_id, "Plano")
    except Exception:
        raise HTTPException(400, "Barbearia ou plano inválido")
    shop = await db.shops.find_one({"_id": sid})
    if not shop:
        raise HTTPException(404, "Barbearia não encontrada")
    plan = await db.platform_plans.find_one({"_id": pid})
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    if not plan.get("active", True):
        raise HTTPException(400, "Não é possível vincular um plano inativo")
    now = datetime.now(timezone.utc).isoformat()
    history = {
        "action": "alterou plano",
        "by": admin["email"],
        "at": now,
        "reason": f"Plano: {plan.get('name', '')}",
    }
    await db.shops.update_one(
        {"_id": sid},
        {"$set": {
            "platform_plan_id": pid,
            "platform_plan_name": plan.get("name", ""),
            "subscription_status": "active",
            "subscription_started_at": shop.get("subscription_started_at") or now,
            "subscription_updated_at": now,
        }, "$push": {"decision_history": history}},
    )
    return _shop_admin_summary(await db.shops.find_one({"_id": sid}), full=True)


@api_router.patch("/platform/shops/{shop_id}/subscription-status")
async def platform_subscription_status(shop_id: str, data: PlatformSubscriptionStatusIn, admin: dict = Depends(get_super_admin)):
    allowed = {"active", "pending", "past_due", "canceled", "suspended"}
    status = data.status.strip().lower()
    if status not in allowed:
        raise HTTPException(400, "Status de assinatura inválido")
    try:
        sid = ObjectId(shop_id)
    except Exception:
        raise HTTPException(400, "Barbearia inválida")
    shop = await db.shops.find_one({"_id": sid})
    if not shop:
        raise HTTPException(404, "Barbearia não encontrada")
    now = datetime.now(timezone.utc).isoformat()
    reason = f"Status: {status}" + (f" — {data.reason.strip()}" if data.reason and data.reason.strip() else "")
    entry = {"action": "alterou assinatura", "by": admin["email"], "source": "manual", "at": now, "reason": reason}
    await db.shops.update_one(
        {"_id": sid},
        {"$set": {
            "subscription_status": status,
            "subscription_status_source": "manual",
            "subscription_updated_at": now,
        }, "$push": {"decision_history": entry}},
    )
    return _shop_admin_summary(await db.shops.find_one({"_id": sid}), full=True)


async def _apply_provider_subscription_event(shop: dict, event: PlatformSubscriptionProviderEventIn):
    """Provider-neutral hook for future billing webhooks (Efí Bank will plug in here)."""
    allowed = {"active", "pending", "past_due", "canceled", "suspended"}
    status = event.status.strip().lower()
    if status not in allowed:
        raise HTTPException(400, "Status de assinatura inválido")
    provider = event.provider.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    if event.event_id:
        duplicate = await db.billing_events.find_one({"provider": provider, "event_id": event.event_id})
        if duplicate:
            return False
    update = {
        "subscription_status": status,
        "subscription_status_source": provider,
        "subscription_updated_at": now,
        "billing_provider": provider,
        "external_subscription_id": event.external_subscription_id,
    }
    if event.payment_method:
        update["subscription_payment_method"] = event.payment_method
    if event.current_period_end:
        update["subscription_current_period_end"] = event.current_period_end
    await db.shops.update_one(
        {"_id": shop["_id"]},
        {"$set": update, "$push": {"decision_history": {
            "action": "atualizou assinatura", "by": provider, "source": "provider",
            "at": now, "reason": f"Status: {status}",
        }}},
    )
    if event.event_id:
        await db.billing_events.insert_one({
            "provider": provider, "event_id": event.event_id,
            "external_subscription_id": event.external_subscription_id,
            "shop_id": shop["_id"], "processed_at": now,
        })
    return True


@api_router.get("/platform/shops/{shop_id}")
async def platform_shop_detail(shop_id: str, _: dict = Depends(get_super_admin)):
    s = await db.shops.find_one({"_id": safe_object_id(shop_id, "Barbearia")})
    if not s:
        raise HTTPException(404, "Barbearia não encontrada")
    return _shop_admin_summary(s, full=True)


async def _decide(shop_id: str, new_status: str, action: str, admin: dict, reason: str):
    shop_oid = safe_object_id(shop_id, "Barbearia")
    s = await db.shops.find_one({"_id": shop_oid})
    if not s:
        raise HTTPException(404, "Barbearia não encontrada")
    entry = {
        "action": action, "by": admin["email"],
        "at": datetime.now(timezone.utc).isoformat(), "reason": (reason or "").strip(),
    }
    await db.shops.update_one(
        {"_id": shop_oid},
        {"$set": {"status": new_status}, "$push": {"decision_history": entry}},
    )
    s = await db.shops.find_one({"_id": shop_oid})
    return _shop_admin_summary(s, full=True)


@api_router.post("/platform/shops/{shop_id}/approve")
async def platform_approve(shop_id: str, data: DecisionIn, admin: dict = Depends(get_super_admin)):
    return await _decide(shop_id, "active", "aprovou", admin, data.reason)


@api_router.post("/platform/shops/{shop_id}/reject")
async def platform_reject(shop_id: str, data: DecisionIn, admin: dict = Depends(get_super_admin)):
    return await _decide(shop_id, "rejected", "rejeitou", admin, data.reason)


@api_router.post("/platform/shops/{shop_id}/suspend")
async def platform_suspend(shop_id: str, data: DecisionIn, admin: dict = Depends(get_super_admin)):
    return await _decide(shop_id, "suspended", "suspendeu", admin, data.reason)


@api_router.post("/platform/shops/{shop_id}/reactivate")
async def platform_reactivate(shop_id: str, data: DecisionIn, admin: dict = Depends(get_super_admin)):
    return await _decide(shop_id, "active", "reativou", admin, data.reason)


def _platform_plan_summary(plan: dict) -> dict:
    return {
        "id": oid(plan["_id"]),
        "name": plan.get("name", ""),
        "monthly_price": plan.get("monthly_price", 0),
        "description": plan.get("description", ""),
        "max_professionals": plan.get("max_professionals", 1),
        "max_services": plan.get("max_services", 1),
        "max_client_plans": plan.get("max_client_plans"),
        "pdf_reports": plan.get("pdf_reports", False),
        "active": plan.get("active", True),
        "created_at": plan.get("created_at"),
        "updated_at": plan.get("updated_at"),
    }


@api_router.get("/platform/plans")
async def platform_list_plans(_: dict = Depends(get_super_admin)):
    plans = await db.platform_plans.find().sort("created_at", -1).to_list(500)
    return [_platform_plan_summary(p) for p in plans]


@api_router.post("/platform/plans")
async def platform_create_plan(data: PlatformPlanIn, _: dict = Depends(get_super_admin)):
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Nome do plano é obrigatório")
    if await db.platform_plans.find_one({"name_normalized": name.lower()}):
        raise HTTPException(409, "Já existe um plano com esse nome")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "name": name,
        "name_normalized": name.lower(),
        "monthly_price": data.monthly_price,
        "description": (data.description or "").strip(),
        "max_professionals": data.max_professionals,
        "max_services": data.max_services,
        "max_client_plans": data.max_client_plans,
        "pdf_reports": data.pdf_reports,
        "active": data.active,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.platform_plans.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _platform_plan_summary(doc)


@api_router.put("/platform/plans/{plan_id}")
async def platform_update_plan(plan_id: str, data: PlatformPlanIn, _: dict = Depends(get_super_admin)):
    try:
        pid = safe_object_id(plan_id, "Plano")
    except Exception:
        raise HTTPException(400, "Plano inválido")
    existing = await db.platform_plans.find_one({"_id": pid})
    if not existing:
        raise HTTPException(404, "Plano não encontrado")
    name = data.name.strip()
    if not name:
        raise HTTPException(400, "Nome do plano é obrigatório")
    duplicate = await db.platform_plans.find_one({"name_normalized": name.lower(), "_id": {"$ne": pid}})
    if duplicate:
        raise HTTPException(409, "Já existe um plano com esse nome")
    changes = {
        "name": name,
        "name_normalized": name.lower(),
        "monthly_price": data.monthly_price,
        "description": (data.description or "").strip(),
        "max_professionals": data.max_professionals,
        "max_services": data.max_services,
        "max_client_plans": data.max_client_plans,
        "pdf_reports": data.pdf_reports,
        "active": data.active,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.platform_plans.update_one({"_id": pid}, {"$set": changes})
    return _platform_plan_summary(await db.platform_plans.find_one({"_id": pid}))


@api_router.patch("/platform/plans/{plan_id}/status")
async def platform_plan_status(plan_id: str, data: PlatformPlanStatusIn, _: dict = Depends(get_super_admin)):
    try:
        pid = safe_object_id(plan_id, "Plano")
    except Exception:
        raise HTTPException(400, "Plano inválido")
    if not await db.platform_plans.find_one({"_id": pid}):
        raise HTTPException(404, "Plano não encontrado")
    await db.platform_plans.update_one(
        {"_id": pid},
        {"$set": {"active": data.active, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return _platform_plan_summary(await db.platform_plans.find_one({"_id": pid}))


@api_router.delete("/platform/plans/{plan_id}")
async def platform_delete_plan(plan_id: str, _: dict = Depends(get_super_admin)):
    pid = safe_object_id(plan_id, "Plano")
    plan = await db.platform_plans.find_one({"_id": pid})
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    in_use = await db.shops.count_documents({"platform_plan_id": pid})
    if in_use:
        raise HTTPException(409, f"Este plano está vinculado a {in_use} barbearia(s). Altere o plano delas antes de excluir.")
    await db.platform_plans.delete_one({"_id": pid})
    return {"ok": True}


app.include_router(api_router)

cors_raw = os.environ.get("CORS_ORIGINS", "").strip()
if IS_PRODUCTION and not cors_raw:
    logger.warning("CORS_ORIGINS is not configured in production; cross-origin browser requests are disabled.")
cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
if not IS_PRODUCTION and not cors_origins:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------- Startup / indexes / example shop ----------------
@app.on_event("startup")
async def seed():
    # Drop legacy global-unique email index (single-shop era) if present.
    try:
        await db.users.drop_index("email_1")
    except Exception:
        pass
    try:
        await db.shops.create_index("code", unique=True)
        # CRM clients intentionally have no e-mail. A normal unique compound index
        # treats missing e-mail values as duplicates, blocking the 2nd CRM client.
        try:
            await db.users.drop_index("shop_id_1_email_1")
        except Exception:
            pass
        await db.users.create_index(
            [("shop_id", 1), ("email", 1)],
            unique=True,
            partialFilterExpression={"email": {"$type": "string"}},
            name="shop_email_unique_when_present",
        )
    except Exception as e:
        logger.warning(f"Index setup: {e}")

    # Commercial BarberStudio plans. Existing plans with these names are aligned
    # to the current offer; custom plans created by the Super Admin are preserved.
    commercial_plans = [
        {"name": "Essencial", "monthly_price": 59.90, "description": "Para barbearias pequenas.",
         "max_professionals": 3, "max_services": 7, "max_client_plans": 5, "pdf_reports": False},
        {"name": "Profissional", "monthly_price": 99.90, "description": "Para barbearias em crescimento.",
         "max_professionals": 5, "max_services": 10, "max_client_plans": 7, "pdf_reports": False},
        {"name": "Premium", "monthly_price": 149.90, "description": "Recursos e cadastros sem limites.",
         "max_professionals": None, "max_services": None, "max_client_plans": None, "pdf_reports": True},
    ]
    now = datetime.now(timezone.utc).isoformat()
    for item in commercial_plans:
        normalized = item["name"].lower()
        await db.platform_plans.update_one(
            {"name_normalized": normalized},
            {"$set": {**item, "name_normalized": normalized, "active": True, "updated_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    # Super Admin (platform owner), idempotent: created only once, never reset here.
    sa_email = os.environ.get("SUPERADMIN_EMAIL", "").lower()
    sa_password = os.environ.get("SUPERADMIN_PASSWORD", "")
    if sa_email and sa_password:
        if not await db.platform_admins.find_one({"email": sa_email}):
            await db.platform_admins.insert_one({
                "email": sa_email, "password_hash": hash_password(sa_password),
                "name": "Super Admin", "role": "super_admin",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    # Example barbershop (owner = ADMIN_EMAIL) so the app is usable on a fresh database.
    demo_code = os.environ.get("DEMO_SHOP_CODE", "DEMO01").upper()
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    # DEMO is active only outside production, so prod requires real approval flow.
    demo_status = "pending" if IS_PRODUCTION else "active"
    shop = await db.shops.find_one({"code": demo_code})
    if not shop:
        res = await db.shops.insert_one({
            "name": "Barbearia Exemplo", "code": demo_code, "status": demo_status,
            "responsible_name": "Administrador", "cpf_cnpj": "", "phone": "",
            "email": admin_email, "decision_history": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        shop = {"_id": res.inserted_id, "code": demo_code, "name": "Barbearia Exemplo"}
    elif not shop.get("status"):
        await db.shops.update_one({"_id": shop["_id"]}, {"$set": {"status": demo_status}})
    shop_id = oid(shop["_id"])
    existing = await db.users.find_one({"shop_id": shop_id, "email": admin_email})
    if not existing and admin_password:
        await db.users.insert_one({
            "email": admin_email, "password_hash": hash_password(admin_password),
            "name": "Administrador", "role": "admin", "phone": "", "shop_id": shop_id,
            "points": 0, "total_spend": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
    # Existing admin passwords must never be overwritten during startup.
    await seed_shop_defaults(shop_id, with_barbers=True)
    logger.info(f"Seed concluído. Barbearia exemplo code={demo_code}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
