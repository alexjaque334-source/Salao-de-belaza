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
import bcrypt
import jwt
import hmac
import re
import email_service

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


def tier_for_points(points: int) -> str:
    if points >= 600: return "VIP Black"
    if points >= 300: return "Gold"
    if points >= 100: return "Silver"
    return "Bronze"


def serialize_user(doc) -> dict:
    points = doc.get("points", 0)
    return {
        "id": oid(doc["_id"]),
        "email": doc.get("email"),
        "name": doc.get("name"),
        "role": doc.get("role"),
        "phone": doc.get("phone", ""),
        "points": points,
        "tier": tier_for_points(points),
        "total_spend": doc.get("total_spend", 0),
        "preferred_barber": doc.get("preferred_barber", ""),
        "notes": doc.get("notes", ""),
        "shop_id": doc.get("shop_id"),
        "created_at": doc.get("created_at"),
    }


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
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


async def get_current_user_raw(request: Request) -> dict:
    payload = _decode_token(request)
    if payload.get("kind") == "super_admin":
        raise HTTPException(status_code=403, detail="Use o painel da plataforma")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
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
    admin = await db.platform_admins.find_one({"_id": ObjectId(payload["sub"])})
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


# ---------------- Models ----------------
class ShopCreateIn(BaseModel):
    shop_name: str
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = ""
    cpf_cnpj: str


class PlatformLoginIn(BaseModel):
    email: EmailStr
    password: str


class DecisionIn(BaseModel):
    reason: Optional[str] = ""


class RegisterIn(BaseModel):
    shop_code: str
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = ""


class LoginIn(BaseModel):
    shop_code: str
    email: EmailStr
    password: str


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
    email: EmailStr
    phone: Optional[str] = ""
    password: Optional[str] = "cliente123"
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


# ---------------- Auth routes ----------------
@api_router.post("/auth/request-access")
async def request_access(data: ShopCreateIn, request: Request):
    await rate_limit(f"req:{client_ip(request)}", max_attempts=8, window_minutes=30)
    if not valid_cpf_cnpj(data.cpf_cnpj):
        await bump_attempt(f"req:{client_ip(request)}")
        raise HTTPException(status_code=400, detail="CPF/CNPJ inválido")
    doc_digits = _only_digits(data.cpf_cnpj)
    if await db.shops.find_one({"cpf_cnpj": doc_digits}):
        raise HTTPException(status_code=400, detail="Já existe uma barbearia com este CPF/CNPJ")
    code = await unique_shop_code()
    shop_doc = {
        "name": data.shop_name.strip(), "code": code, "status": "pending",
        "responsible_name": data.name, "cpf_cnpj": doc_digits,
        "phone": data.phone, "email": data.email.lower(),
        "decision_history": [],
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
        "status": "pending", "shop_code": code,
        "message": "Cadastro em análise — aguardando aprovação do administrador da plataforma.",
    }


@api_router.post("/auth/register")
async def register(data: RegisterIn, request: Request):
    await rate_limit(f"reg:{client_ip(request)}", max_attempts=15, window_minutes=30)
    shop = await db.shops.find_one({"code": data.shop_code.strip().upper()})
    if not shop:
        raise HTTPException(status_code=404, detail="Barbearia não encontrada. Verifique o código.")
    if shop_status(shop) != "active":
        raise HTTPException(status_code=403, detail="Esta barbearia ainda não está ativa.")
    shop_id = oid(shop["_id"])
    email = data.email.lower()
    if await db.users.find_one({"shop_id": shop_id, "email": email}):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado nesta barbearia")
    doc = {
        "email": email, "password_hash": hash_password(data.password),
        "name": data.name, "role": "client", "phone": data.phone, "shop_id": shop_id,
        "points": 0, "total_spend": 0, "preferred_barber": "", "notes": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return await auth_response(doc)


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
    # Clients cannot sign in to a non-active shop; owners can (to see the status screen).
    if user["role"] == "client" and shop_status(shop) != "active":
        raise HTTPException(status_code=403, detail="Esta barbearia não está disponível no momento.")
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


# ---------------- Barbers ----------------
@api_router.get("/barbers")
async def list_barbers(user: dict = Depends(get_current_user)):
    docs = await db.barbers.find({"shop_id": user["shop_id"]}).to_list(500)
    return [{"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in docs]


@api_router.post("/barbers")
async def create_barber(data: BarberIn, admin: dict = Depends(require_admin)):
    doc = data.model_dump()
    doc["total_cuts"] = 0
    doc["shop_id"] = admin["shop_id"]
    out = dict(doc)
    res = await db.barbers.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out


@api_router.put("/barbers/{barber_id}")
async def update_barber(barber_id: str, data: BarberIn, admin: dict = Depends(require_admin)):
    d = await db.barbers.find_one({"_id": ObjectId(barber_id), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Barbeiro não encontrado")
    await db.barbers.update_one({"_id": ObjectId(barber_id)}, {"$set": data.model_dump()})
    d = await db.barbers.find_one({"_id": ObjectId(barber_id)})
    return {"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}}


@api_router.delete("/barbers/{barber_id}")
async def delete_barber(barber_id: str, admin: dict = Depends(require_admin)):
    res = await db.barbers.delete_one({"_id": ObjectId(barber_id), "shop_id": admin["shop_id"]})
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
            "_id": ObjectId(service_id),
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
        "_id": ObjectId(service_id),
        "shop_id": admin["shop_id"]
    })

    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    new_status = not service.get("active", True)

    await db.services.update_one(
        {"_id": service["_id"], "shop_id": admin["shop_id"]},
        {"$set": {"active": new_status}}
    )

    return {"ok": True, "active": new_status}


# ---------------- Availability ----------------
def gen_slots(start: str, end: str, interval: int = 30):
    slots = []
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    cur = sh * 60 + sm
    last = eh * 60 + em
    while cur < last:
        slots.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += interval
    return slots


@api_router.get("/availability")
async def availability(barber_id: str, date: str, user: dict = Depends(get_current_user)):
    barber = await db.barbers.find_one({"_id": ObjectId(barber_id), "shop_id": user["shop_id"]})
    if not barber:
        raise HTTPException(404, "Barbeiro não encontrado")
    try:
        d = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Data inválida")
    wd = WEEKDAYS[d.weekday()]
    hours = (barber.get("working_hours") or {}).get(wd)
    if not hours or not hours.get("start") or not hours.get("end"):
        return {"slots": []}
    all_slots = gen_slots(hours["start"], hours["end"])
    taken = await db.appointments.find({
        "shop_id": user["shop_id"], "barber_id": barber_id, "date": date,
        "status": {"$ne": "Cancelado"},
    }).to_list(500)
    taken_times = {t["time"] for t in taken}
    return {"slots": [{"time": s, "available": s not in taken_times} for s in all_slots]}


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
       barber = await db.barbers.find_one({"_id": ObjectId(data.barber_id), "shop_id": sid})
    if not barber:
        raise HTTPException(404, "Barbeiro não encontrado")

    service = await db.services.find_one({
        "_id": ObjectId(data.service_id),
        "shop_id": sid,
        "active": {"$ne": False}
    })
    if not service:
        raise HTTPException(404, "Serviço não encontrado")

    exists = await db.appointments.find_one({
        "shop_id": sid, "barber_id": data.barber_id, "date": data.date, "time": data.time,
        "status": {"$ne": "Cancelado"},
    })
    if exists:
        raise HTTPException(status_code=409, detail="Este horário já está indisponível")
    if user["role"] == "admin" and data.client_id:
        cust = await db.users.find_one({"_id": ObjectId(data.client_id), "shop_id": sid})
        if not cust:
            raise HTTPException(404, "Cliente não encontrado")
        client_id = data.client_id
        client_name = cust["name"]
        client_phone = cust.get("phone", "")
        client_email = cust.get("email", "")
    elif user["role"] == "admin" and data.client_name:
        # Walk-in: manual booking for a client without an account.
        client_id = None
        client_name = data.client_name.strip()
        client_phone = (data.client_phone or "").strip()
        client_email = ""
    elif user["role"] == "admin":
        raise HTTPException(400, "Informe o cliente cadastrado ou o nome do cliente avulso")
    else:
        client_id = oid(user["_id"])
        client_name = user["name"]
        client_phone = user.get("phone", "")
        client_email = user.get("email", "")
    shop = await db.shops.find_one({"_id": ObjectId(sid)})
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
    out = dict(doc)
    res = await db.appointments.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    # Serverless-safe: send confirmation inline (safe_send never raises).
    await email_service.safe_send_confirmation(out)
    return out


@api_router.patch("/appointments/{appt_id}/status")
async def update_status(appt_id: str, data: StatusIn, admin: dict = Depends(require_admin)):
    appt = await db.appointments.find_one({"_id": ObjectId(appt_id), "shop_id": admin["shop_id"]})
    if not appt:
        raise HTTPException(404, "Agendamento não encontrado")
    await db.appointments.update_one({"_id": ObjectId(appt_id)}, {"$set": {"status": data.status}})
    if data.status == "Concluído" and appt.get("status") != "Concluído":
        if appt.get("client_id"):
            await db.users.update_one(
                {"_id": ObjectId(appt["client_id"])},
                {"$inc": {"points": 10, "total_spend": appt.get("price", 0)}},
            )
        await db.barbers.update_one({"_id": ObjectId(appt["barber_id"])}, {"$inc": {"total_cuts": 1}})
    return {"ok": True}


@api_router.delete("/appointments/{appt_id}")
async def delete_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    appt = await db.appointments.find_one({"_id": ObjectId(appt_id), "shop_id": user["shop_id"]})
    if not appt:
        raise HTTPException(404, "Agendamento não encontrado")
    if user["role"] != "admin" and appt.get("client_id") != oid(user["_id"]):
        raise HTTPException(403, "Sem permissão")
    await db.appointments.delete_one({"_id": ObjectId(appt_id)})
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
        u = serialize_user(d)
        u["visits"] = count
        u["plan_name"] = sub["plan_name"] if sub else None
        out.append(u)
    return out


@api_router.post("/clients")
async def create_client(data: ClientIn, admin: dict = Depends(require_admin)):
    sid = admin["shop_id"]
    email = data.email.lower()
    if await db.users.find_one({"shop_id": sid, "email": email}):
        raise HTTPException(400, "E-mail já cadastrado nesta barbearia")
    doc = {
        "email": email, "password_hash": hash_password(data.password or "cliente123"),
        "name": data.name, "role": "client", "phone": data.phone, "shop_id": sid,
        "points": 0, "total_spend": 0, "preferred_barber": "", "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize_user(doc)


@api_router.put("/clients/{client_id}")
async def update_client(client_id: str, data: ClientIn, admin: dict = Depends(require_admin)):
    d = await db.users.find_one({"_id": ObjectId(client_id), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    await db.users.update_one({"_id": ObjectId(client_id)},
                              {"$set": {"name": data.name, "phone": data.phone, "notes": data.notes}})
    d = await db.users.find_one({"_id": ObjectId(client_id)})
    return serialize_user(d)


@api_router.patch("/clients/{client_id}/loyalty")
async def set_loyalty(client_id: str, data: LoyaltyIn, admin: dict = Depends(require_admin)):
    d = await db.users.find_one({"_id": ObjectId(client_id), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    await db.users.update_one({"_id": ObjectId(client_id)}, {"$set": {"points": max(0, data.points)}})
    d = await db.users.find_one({"_id": ObjectId(client_id)})
    return serialize_user(d)


@api_router.post("/clients/{client_id}/redeem")
async def redeem(client_id: str, admin: dict = Depends(require_admin)):
    d = await db.users.find_one({"_id": ObjectId(client_id), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Cliente não encontrado")
    if d.get("points", 0) < 100:
        raise HTTPException(400, "Pontos insuficientes (mínimo 100)")
    await db.users.update_one({"_id": ObjectId(client_id)}, {"$inc": {"points": -100}})
    return {"ok": True, "message": "Recompensa resgatada: 1 corte grátis"}


# ---------------- Plans ----------------
@api_router.get("/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    docs = await db.plans.find({"shop_id": user["shop_id"]}).to_list(500)
    return [{"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}} for d in docs]


@api_router.post("/plans")
async def create_plan(data: PlanIn, admin: dict = Depends(require_admin)):
    doc = data.model_dump()
    doc["shop_id"] = admin["shop_id"]
    out = dict(doc)
    res = await db.plans.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out


@api_router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, data: PlanIn, admin: dict = Depends(require_admin)):
    d = await db.plans.find_one({"_id": ObjectId(plan_id), "shop_id": admin["shop_id"]})
    if not d:
        raise HTTPException(404, "Plano não encontrado")
    await db.plans.update_one({"_id": ObjectId(plan_id)}, {"$set": data.model_dump()})
    d = await db.plans.find_one({"_id": ObjectId(plan_id)})
    return {"id": oid(d["_id"]), **{k: v for k, v in d.items() if k != "_id"}}


@api_router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, admin: dict = Depends(require_admin)):
    res = await db.plans.delete_one({"_id": ObjectId(plan_id), "shop_id": admin["shop_id"]})
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
    plan = await db.plans.find_one({"_id": ObjectId(data.plan_id), "shop_id": sid})
    if not plan:
        raise HTTPException(404, "Plano não encontrado")
    if user["role"] == "admin" and data.client_id:
        cust = await db.users.find_one({"_id": ObjectId(data.client_id), "shop_id": sid})
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
        "status": "Ativo",
        "start_date": datetime.now(timezone.utc).date().isoformat(),
        "renewal_date": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out = dict(doc)
    res = await db.subscriptions.insert_one(doc)
    out["id"] = oid(res.inserted_id)
    return out


@api_router.delete("/subscriptions/{sub_id}")
async def cancel_subscription(sub_id: str, admin: dict = Depends(require_admin)):
    res = await db.subscriptions.update_one(
        {"_id": ObjectId(sub_id), "shop_id": admin["shop_id"]}, {"$set": {"status": "Cancelado"}}
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
    out = {"active": 0, "pending": 0, "suspended": 0, "rejected": 0, "total": 0}
    for shop in await db.shops.find().to_list(5000):
        out[shop_status(shop)] = out.get(shop_status(shop), 0) + 1
        out["total"] += 1
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


@api_router.get("/platform/shops/{shop_id}")
async def platform_shop_detail(shop_id: str, _: dict = Depends(get_super_admin)):
    s = await db.shops.find_one({"_id": ObjectId(shop_id)})
    if not s:
        raise HTTPException(404, "Barbearia não encontrada")
    return _shop_admin_summary(s, full=True)


async def _decide(shop_id: str, new_status: str, action: str, admin: dict, reason: str):
    s = await db.shops.find_one({"_id": ObjectId(shop_id)})
    if not s:
        raise HTTPException(404, "Barbearia não encontrada")
    entry = {
        "action": action, "by": admin["email"],
        "at": datetime.now(timezone.utc).isoformat(), "reason": (reason or "").strip(),
    }
    await db.shops.update_one(
        {"_id": ObjectId(shop_id)},
        {"$set": {"status": new_status}, "$push": {"decision_history": entry}},
    )
    s = await db.shops.find_one({"_id": ObjectId(shop_id)})
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


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- Startup / indexes / example shop ----------------
@app.on_event("startup")
async def seed():
    # Drop legacy global-unique email index (single-shop era) if present.
    try:
        await db.users.drop_index("email_1")
    except Exception:
        pass
    # Remove legacy data that predates multi-shop (no shop_id) so isolation stays clean.
    for coll in ("users", "barbers", "services", "appointments", "plans", "subscriptions"):
        try:
            await db[coll].delete_many({"shop_id": {"$exists": False}})
        except Exception:
            pass
    try:
        await db.shops.create_index("code", unique=True)
        await db.users.create_index([("shop_id", 1), ("email", 1)], unique=True)
    except Exception as e:
        logger.warning(f"Index setup: {e}")

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
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
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
    if not existing:
        await db.users.insert_one({
            "email": admin_email, "password_hash": hash_password(admin_password),
            "name": "Administrador", "role": "admin", "phone": "", "shop_id": shop_id,
            "points": 0, "total_spend": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"_id": existing["_id"]},
                                  {"$set": {"password_hash": hash_password(admin_password)}})
    await seed_shop_defaults(shop_id, with_barbers=True)
    logger.info(f"Seed concluído. Barbearia exemplo code={demo_code}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
