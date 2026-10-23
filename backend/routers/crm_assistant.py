from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import os

router = APIRouter(prefix="/crm-assistant", tags=["CRM Assistant"])


class CustomMessageIn(BaseModel):
    client_id: str
    action_type: str = Field(..., description="reengage | birthday | loyalty | feedback | custom")
    custom_offer: Optional[str] = ""
    custom_text: Optional[str] = ""


def _first_name(full_name: str) -> str:
    parts = (full_name or "Cliente").strip().split()
    return parts[0].capitalize() if parts else "Cliente"


def _clean_phone(phone: str) -> str:
    digits = "".join(filter(str.isdigit, phone or ""))
    if not digits:
        return ""
    if not digits.startswith("55") and len(digits) in (10, 11):
        digits = "55" + digits
    return digits


def _make_whatsapp_url(phone: str, text: str) -> str:
    cleaned = _clean_phone(phone)
    if not cleaned:
        return ""
    return f"https://wa.me/{cleaned}?text={quote(text)}"


def build_crm_router(db, safe_object_id, oid, require_admin):
    @router.get("/summary")
    async def get_crm_summary(admin: dict = Depends(require_admin)):
        sid = admin["shop_id"]
        shop = await db.shops.find_one({"_id": safe_object_id(sid, "Barbearia")})
        shop_name = shop.get("name", "BarberStudio") if shop else "BarberStudio"
        public_slug = shop.get("public_slug") if shop else None
        app_url = os.environ.get("APP_URL", "https://barberstudio.app").rstrip("/")
        booking_link = f"{app_url}/agendar/{public_slug}" if public_slug else app_url

        now_utc = datetime.now(timezone.utc)
        today_date = now_utc.date()
        today_str = today_date.isoformat()
        today_md = today_date.strftime("%m-%d")

        # 1. Fetch clients of the shop
        clients = await db.users.find({"role": "client", "shop_id": sid}).to_list(1500)
        client_ids = [oid(c["_id"]) for c in clients]

        # 2. Fetch appointments of the shop to find the last visit for each client
        appts = await db.appointments.find({
            "shop_id": sid,
            "status": {"$in": ["Confirmado", "Concluído"]},
        }).sort("date", -1).to_list(5000)

        last_visit_by_client: Dict[str, Dict[str, Any]] = {}
        recent_yesterday_today: List[Dict[str, Any]] = []

        yesterday_str = (today_date - timedelta(days=1)).isoformat()

        for a in appts:
            cid = a.get("client_id")
            if cid and cid not in last_visit_by_client:
                last_visit_by_client[cid] = a

            # Check post-visit feedback candidates (yesterday or today)
            if a.get("date") in (yesterday_str, today_str) and a.get("status") == "Concluído":
                if cid:
                    recent_yesterday_today.append(a)

        # 3. Categorize clients
        inactive_clients = []
        birthday_clients = []
        loyalty_clients = []

        for c in clients:
            cid = oid(c["_id"])
            name = c.get("name", "Cliente")
            first = _first_name(name)
            phone = c.get("phone", "")
            points = c.get("points", 0)
            birthdate = c.get("birthdate", "")
            last_appt = last_visit_by_client.get(cid)

            # Inactive >= 45 days
            if last_appt and last_appt.get("date"):
                try:
                    last_d = datetime.fromisoformat(last_appt["date"]).date()
                    days_inactive = (today_date - last_d).days
                    if days_inactive >= 45:
                        msg = (
                            f"Fala, {first}! Tudo bem? 💈\n"
                            f"Notamos que faz {days_inactive} dias desde seu último corte aqui na {shop_name}.\n"
                            f"Que tal dar aquele talento no visual esta semana?\n\n"
                            f"Agende seu horário direto pelo link:\n{booking_link}\n\n"
                            f"Te esperamos por aqui!"
                        )
                        inactive_clients.append({
                            "client_id": cid,
                            "name": name,
                            "phone": phone,
                            "days_inactive": days_inactive,
                            "last_visit": last_appt["date"],
                            "preferred_barber": last_appt.get("barber_name", ""),
                            "last_service": last_appt.get("service_name", ""),
                            "suggested_message": msg,
                            "whatsapp_url": _make_whatsapp_url(phone, msg),
                        })
                except Exception:
                    pass

            # Birthdays (matching MM-DD or within next 7 days)
            if birthdate:
                try:
                    # Accepts YYYY-MM-DD or DD/MM or DD/MM/YYYY
                    b_clean = birthdate.replace("/", "-")
                    parts = b_clean.split("-")
                    b_month_day = None
                    if len(parts) == 3:
                        if len(parts[0]) == 4:  # YYYY-MM-DD
                            b_month_day = f"{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                        else:  # DD-MM-YYYY
                            b_month_day = f"{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    elif len(parts) == 2:  # DD-MM
                        b_month_day = f"{parts[1].zfill(2)}-{parts[0].zfill(2)}"

                    if b_month_day:
                        is_today = b_month_day == today_md
                        msg = (
                            f"Parabéns, {first}! 🎉🎂\n"
                            f"Toda a equipe da {shop_name} deseja um feliz aniversário, muita saúde e sucesso!\n"
                            f"Para comemorar, preparamos uma condição especial no seu próximo corte.\n\n"
                            f"Garanta seu horário aqui: {booking_link}\n"
                            f"Grande abraço!"
                        )
                        birthday_clients.append({
                            "client_id": cid,
                            "name": name,
                            "phone": phone,
                            "birthdate": birthdate,
                            "is_today": is_today,
                            "suggested_message": msg,
                            "whatsapp_url": _make_whatsapp_url(phone, msg),
                        })
                except Exception:
                    pass

            # Loyalty (100+ points free cut available, or 80-99 points close to reward)
            if points >= 80:
                has_reward = points >= 100
                if has_reward:
                    msg = (
                        f"Olá, {first}! 👑\n"
                        f"Você atingiu {points} pontos no Clube de Fidelidade da {shop_name}!\n"
                        f"Você já tem direito a resgatar 1 CORTE CORTESIA.\n\n"
                        f"Agende seu horário pelo link e venha aproveitar: {booking_link}"
                    )
                else:
                    msg = (
                        f"Fala, {first}! ⚡\n"
                        f"Você já tem {points} pontos no nosso Clube de Fidelidade na {shop_name}.\n"
                        f"Faltam apenas {100 - points} pontos para você garantir seu corte grátis!\n\n"
                        f"Agende seu próximo horário: {booking_link}"
                    )
                loyalty_clients.append({
                    "client_id": cid,
                    "name": name,
                    "phone": phone,
                    "points": points,
                    "tier": c.get("tier", "Bronze"),
                    "has_free_cut": has_reward,
                    "suggested_message": msg,
                    "whatsapp_url": _make_whatsapp_url(phone, msg),
                })

        # Sort lists by relevance
        inactive_clients.sort(key=lambda x: x["days_inactive"], reverse=True)
        loyalty_clients.sort(key=lambda x: x["points"], reverse=True)

        return {
            "shop_name": shop_name,
            "booking_link": booking_link,
            "stats": {
                "inactive_count": len(inactive_clients),
                "birthdays_count": len(birthday_clients),
                "loyalty_count": len(loyalty_clients),
                "total_opportunities": len(inactive_clients) + len(birthday_clients) + len(loyalty_clients),
            },
            "inactive_clients": inactive_clients[:50],
            "birthday_clients": birthday_clients[:50],
            "loyalty_clients": loyalty_clients[:50],
        }

    @router.post("/generate-custom")
    async def generate_custom_message(data: CustomMessageIn, admin: dict = Depends(require_admin)):
        sid = admin["shop_id"]
        client = await db.users.find_one({"_id": safe_object_id(data.client_id, "Cliente"), "shop_id": sid})
        if not client:
            raise HTTPException(404, "Cliente não encontrado")

        shop = await db.shops.find_one({"_id": safe_object_id(sid, "Barbearia")})
        shop_name = shop.get("name", "BarberStudio") if shop else "BarberStudio"
        public_slug = shop.get("public_slug") if shop else None
        app_url = os.environ.get("APP_URL", "https://barberstudio.app").rstrip("/")
        booking_link = f"{app_url}/agendar/{public_slug}" if public_slug else app_url

        first = _first_name(client.get("name", "Cliente"))
        phone = client.get("phone", "")
        offer = f"\n🎁 Bônus exclusivo: {data.custom_offer}" if data.custom_offer else ""

        if data.custom_text:
            text = data.custom_text.replace("{nome}", first).replace("{barbearia}", shop_name).replace("{link}", booking_link)
        elif data.action_type == "reengage":
            text = (
                f"Fala, {first}! Tudo tranquilo? 💈\n"
                f"Estamos com saudades de você aqui na {shop_name}.{offer}\n"
                f"Bora alinhar o visual para o fim de semana?\n\n"
                f"Escolha o melhor horário para você no link:\n{booking_link}"
            )
        elif data.action_type == "birthday":
            text = (
                f"Parabéns pelo seu dia, {first}! 🎂🎉\n"
                f"Muita saúde, paz e conquistas da equipe da {shop_name}.{offer}\n"
                f"Vem comemorar com visual novo: {booking_link}"
            )
        elif data.action_type == "feedback":
            text = (
                f"Fala, {first}! Tudo bem? ✂️\n"
                f"O que achou do atendimento na {shop_name}?\n"
                f"Sua opinião é fundamental para evoluirmos sempre. Esperamos te ver em breve!"
            )
        else:
            text = (
                f"Olá, {first}! Tudo bem? Passando para desejar uma ótima semana na {shop_name}.{offer}\n"
                f"Se precisar de um horário, agende com praticidade no link:\n{booking_link}"
            )

        return {
            "client_name": client.get("name"),
            "phone": phone,
            "message": text,
            "whatsapp_url": _make_whatsapp_url(phone, text),
        }

    return router
