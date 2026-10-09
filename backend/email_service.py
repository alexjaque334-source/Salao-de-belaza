import os
import re
import ipaddress
import logging
import httpx
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse, quote
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Own-account Resend, read entirely from environment (nothing in code/chat).
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# Full RFC "Name <email@domain>" sender. Must be a verified Resend sender/domain.
RESEND_FROM = os.environ.get("RESEND_FROM", "BarberStudio <onboarding@resend.dev>")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")
APP_URL = os.environ.get("APP_URL", "https://example.com")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str | None:
    _assert_safe_email(subject, html)
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY not configured; skipping email send.")
        return None
    payload = {"from": RESEND_FROM, "to": [to], "subject": subject, "html": html}
    if EMAIL_REPLY_TO:
        payload["reply_to"] = EMAIL_REPLY_TO
    async with httpx.AsyncClient(timeout=30) as hc:
        resp = await hc.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json=payload,
        )
    resp.raise_for_status()
    return resp.json().get("id")


def _fmt_date(d: str) -> str:
    try:
        return "/".join(reversed(d.split("-")))
    except Exception:
        return d


def _wrap(shop: str, inner: str) -> str:
    return (
        '<table role="presentation" width="100%" style="background:#0a0a0c;padding:24px 0">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" style="max-width:560px;background:#121216;'
        'border:1px solid #272730;border-radius:16px;overflow:hidden">'
        '<tr><td style="padding:22px 28px;background:#18120a;border-bottom:1px solid #272730">'
        '<span style="font-family:Arial,sans-serif;font-size:20px;font-weight:800;color:#f59e0b">'
        'BARBER</span><span style="font-family:Arial,sans-serif;font-size:20px;font-weight:800;'
        f'color:#fafafa">STUDIO</span> &nbsp;<span style="font-family:Arial,sans-serif;font-size:13px;'
        f'color:#a1a1aa">{escape(shop)}</span></td></tr>'
        f'<tr><td style="padding:28px;font-family:Arial,sans-serif;color:#e4e4e7">{inner}</td></tr>'
        '<tr><td style="padding:18px 28px;border-top:1px solid #272730;font-family:Arial,sans-serif;'
        f'font-size:12px;color:#71717a">Enviado por {escape(shop)} via BarberStudio. Nunca pedimos sua '
        'senha ou dados de cartão por e-mail.</td></tr>'
        '</table></td></tr></table>'
    )


def _detail_rows(appt: dict) -> str:
    rows = [
        ("Serviço", appt.get("service_name", "")),
        ("Barbeiro", appt.get("barber_name", "")),
        ("Data", _fmt_date(appt.get("date", ""))),
        ("Horário", appt.get("time", "")),
    ]
    out = ""
    for label, val in rows:
        out += (
            f'<tr><td style="padding:6px 0;color:#a1a1aa;font-size:14px">{escape(label)}</td>'
            f'<td style="padding:6px 0;color:#fafafa;font-size:14px;font-weight:600;text-align:right">'
            f'{escape(str(val))}</td></tr>'
        )
    return f'<table role="presentation" width="100%" style="margin:14px 0">{out}</table>'


def _cta(label: str) -> str:
    return (
        f'<a href="{escape(APP_URL)}" style="display:inline-block;background:#f59e0b;color:#0a0a0c;'
        f'font-weight:700;font-size:14px;text-decoration:none;padding:11px 20px;border-radius:10px">'
        f'{escape(label)}</a>'
    )


def booking_confirmation(appt: dict) -> tuple:
    shop = appt.get("shop_name") or "BarberStudio"
    name = (appt.get("client_name") or "cliente").split(" ")[0]
    subject = f"Agendamento confirmado — {_fmt_date(appt.get('date',''))} às {appt.get('time','')}"
    inner = (
        f'<p style="font-size:16px;margin:0 0 6px">Olá, {escape(name)}!</p>'
        f'<p style="font-size:14px;color:#a1a1aa;margin:0 0 4px">Seu horário na {escape(shop)} está '
        '<strong style="color:#10b981">confirmado</strong>. Confira os detalhes:</p>'
        f'{_detail_rows(appt)}'
        '<p style="font-size:13px;color:#a1a1aa;margin:0 0 18px">Precisa remarcar? Acesse sua conta.</p>'
        f'{_cta("Ver meus agendamentos")}'
    )
    return subject, _wrap(shop, inner)


def booking_reminder(appt: dict) -> tuple:
    shop = appt.get("shop_name") or "BarberStudio"
    name = (appt.get("client_name") or "cliente").split(" ")[0]
    subject = f"Lembrete: seu corte é amanhã às {appt.get('time','')}"
    inner = (
        f'<p style="font-size:16px;margin:0 0 6px">Olá, {escape(name)}!</p>'
        f'<p style="font-size:14px;color:#a1a1aa;margin:0 0 4px">Lembrete do seu horário '
        f'<strong style="color:#f59e0b">amanhã</strong> na {escape(shop)}:</p>'
        f'{_detail_rows(appt)}'
        '<p style="font-size:13px;color:#a1a1aa;margin:0 0 18px">Chegue com alguns minutos de '
        'antecedência. Até lá!</p>'
        f'{_cta("Acessar minha conta")}'
    )
    return subject, _wrap(shop, inner)


async def safe_send_confirmation(appt: dict) -> bool:
    to = appt.get("client_email")
    if not to:
        return False
    try:
        subject, html = booking_confirmation(appt)
        await send_email(to=to, subject=subject, html=html)
        return True
    except Exception as e:
        logger.warning(f"Confirmation email not sent: {e}")
        return False


async def safe_send_reminder(appt: dict) -> bool:
    to = appt.get("client_email")
    if not to:
        return False
    try:
        subject, html = booking_reminder(appt)
        await send_email(to=to, subject=subject, html=html)
        return True
    except Exception as e:
        logger.warning(f"Reminder email not sent: {e}")
        return False


def activation_invite(invite: dict) -> tuple:
    shop = invite.get("shop_name") or "BarberStudio"
    name = (invite.get("client_name") or "cliente").split(" ")[0]
    token = invite.get("token") or ""
    activation_url = f"{APP_URL.rstrip('/')}/ativar-conta?token={quote(token, safe='')}"
    subject = f"Ative sua conta — {shop}"
    inner = (
        f'<p style="font-size:16px;margin:0 0 6px">Olá, {escape(name)}!</p>'
        f'<p style="font-size:14px;color:#a1a1aa;margin:0 0 16px">A {escape(shop)} criou seu acesso ao BarberStudio. Crie sua própria senha pelo botão abaixo.</p>'
        f'<a href="{escape(activation_url)}" style="display:inline-block;background:#f59e0b;color:#0a0a0c;font-weight:700;font-size:14px;text-decoration:none;padding:11px 20px;border-radius:10px">Criar minha senha</a>'
        '<p style="font-size:13px;color:#a1a1aa;margin:18px 0 0">Este link é de uso único e expira em 24 horas. Se você não reconhece este cadastro, ignore esta mensagem.</p>'
    )
    return subject, _wrap(shop, inner)


async def safe_send_activation_invite(invite: dict) -> bool:
    to = invite.get("client_email")
    if not to:
        return False
    try:
        subject, html = activation_invite(invite)
        message_id = await send_email(to=to, subject=subject, html=html)
        return bool(message_id)
    except Exception as e:
        logger.warning(f"Activation invite not sent: {e}")
        return False
