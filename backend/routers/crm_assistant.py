from fastapi import APIRouter, Depends, HTTPException
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

        # 2. Fetch appointments of the shop
        appts = await db.appointments.find({
            "shop_id": sid,
            "status": {"$in": ["Confirmado", "Concluído"]},
        }).sort("date", -1).to_list(5000)

        last_visit_by_client: Dict[str, Dict[str, Any]] = {}
        today_reminders: List[Dict[str, Any]] = []

        for a in appts:
            cid = a.get("client_id")
            if cid and cid not in last_visit_by_client:
                last_visit_by_client[cid] = a

            # Check today's active appointments for anti-no-show reminders
            if a.get("date") == today_str and a.get("status") == "Confirmado":
                client_name = a.get("client_name") or "Cliente"
                first = _first_name(client_name)
                phone = a.get("client_phone") or ""
                time_slot = a.get("time", "")
                barber_name = a.get("barber_name", "nosso profissional")
                service_name = a.get("service_name", "seu corte")

                msg_2h = (
                    f"Fala, {first}! Tudo bem? 💈\n"
                    f"Passando para confirmar seu horário hoje às {time_slot} na {shop_name}.\n"
                    f"Serviço: {service_name} com {barber_name}.\n\n"
                    f"Tudo certo para você? Caso precise de algum ajuste ou remarcação, nos avise por aqui.\n"
                    f"Até já! ✂️"
                )
                today_reminders.append({
                    "appointment_id": oid(a["_id"]),
                    "client_id": cid,
                    "name": client_name,
                    "phone": phone,
                    "time": time_slot,
                    "barber_name": barber_name,
                    "service_name": service_name,
                    "reminder_sent": bool(a.get("reminder_2h_sent")),
                    "reminder_at": a.get("reminder_2h_at"),
                    "suggested_message": msg_2h,
                    "whatsapp_url": _make_whatsapp_url(phone, msg_2h),
                })

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

            # Birthdays
            if birthdate:
                try:
                    b_clean = birthdate.replace("/", "-")
                    parts = b_clean.split("-")
                    b_month_day = None
                    if len(parts) == 3:
                        if len(parts[0]) == 4:
                            b_month_day = f"{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                        else:
                            b_month_day = f"{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    elif len(parts) == 2:
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

            # Loyalty
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

        today_reminders.sort(key=lambda x: x["time"])
        inactive_clients.sort(key=lambda x: x["days_inactive"], reverse=True)
        loyalty_clients.sort(key=lambda x: x["points"], reverse=True)

        return {
            "shop_name": shop_name,
            "booking_link": booking_link,
            "stats": {
                "today_reminders_count": len(today_reminders),
                "inactive_count": len(inactive_clients),
                "birthdays_count": len(birthday_clients),
                "loyalty_count": len(loyalty_clients),
                "total_opportunities": len(today_reminders) + len(inactive_clients) + len(birthday_clients) + len(loyalty_clients),
            },
            "today_reminders": today_reminders,
            "inactive_clients": inactive_clients[:50],
            "birthday_clients": birthday_clients[:50],
            "loyalty_clients": loyalty_clients[:50],
        }

    @router.post("/appointments/{appt_id}/mark-reminded")
    async def mark_appointment_reminded(appt_id: str, admin: dict = Depends(require_admin)):
        sid = admin["shop_id"]
        appt_oid = safe_object_id(appt_id, "Agendamento")
        appt = await db.appointments.find_one({"_id": appt_oid, "shop_id": sid})
        if not appt:
            raise HTTPException(404, "Agendamento não encontrado")

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.appointments.update_one(
            {"_id": appt_oid},
            {"$set": {"reminder_2h_sent": True, "reminder_2h_at": now_iso}}
        )
        return {"ok": True, "reminder_2h_at": now_iso}

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
