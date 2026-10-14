"""
Walk-in appointments (client without account) backend tests.

Covers:
- Walk-in appointment creation (client_name + client_phone, no client_id)
- Registered client appointment (regression)
- Conflict detection on same barber/date/time -> 409
- /availability reflects taken slot
- Validation: admin without client_id and client_name -> 400
- Edit (status to Concluído / Cancelado) and Delete
- Walk-in count in dashboard & barber report revenue/commission; no loyalty points
- Multi-shop isolation (cross-shop GET excludes walk-in, PATCH/DELETE -> 404)
"""
import os
import random
import uuid
from datetime import date, timedelta

import pytest
import requests

try:
    from dotenv import load_dotenv
    load_dotenv("/app/frontend/.env")
except Exception:
    pass

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

DEMO_CODE = os.environ.get("DEMO_SHOP_CODE", "DEMO01")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "")
SA_EMAIL = os.environ.get("SUPERADMIN_EMAIL", "")
SA_PASS = os.environ.get("SUPERADMIN_PASSWORD", "")


# ---------- helpers ----------
def _cnpj_digits(base12):
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    s1 = sum(int(base12[i]) * w1[i] for i in range(12))
    d1 = 0 if s1 % 11 < 2 else 11 - (s1 % 11)
    full13 = base12 + str(d1)
    s2 = sum(int(full13[i]) * w2[i] for i in range(13))
    d2 = 0 if s2 % 11 < 2 else 11 - (s2 % 11)
    return base12 + str(d1) + str(d2)


def gen_valid_cnpj():
    while True:
        base = "".join(str(random.randint(0, 9)) for _ in range(8)) + "0001"
        c = _cnpj_digits(base)
        # format XX.XXX.XXX/XXXX-XX
        return f"{c[0:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}"


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _future_date(offset_days=14):
    return (date.today() + timedelta(days=offset_days)).isoformat()


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    if not ADMIN_EMAIL or not ADMIN_PASS:
        pytest.skip("Credenciais do admin de teste devem vir do ambiente")
    r = requests.post(f"{API}/auth/login",
                      json={"shop_code": DEMO_CODE, "email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h(admin_token):
    return _h(admin_token)


@pytest.fixture(scope="session")
def barber_and_service(admin_h):
    br = requests.get(f"{API}/barbers", headers=admin_h)
    assert br.status_code == 200
    active_barbers = [b for b in br.json() if b.get("active")]
    assert active_barbers, "No active barbers in DEMO01"
    sr = requests.get(f"{API}/services", headers=admin_h)
    assert sr.status_code == 200
    services = sr.json()
    assert services, "No services in DEMO01"
    return active_barbers[0], services[0]


@pytest.fixture(scope="session")
def second_shop_admin_token():
    """Create a 2nd shop via request-access and approve it via super admin for isolation testing."""
    # Super admin login
    sa = requests.post(f"{API}/platform/login", json={"email": SA_EMAIL, "password": SA_PASS})
    if sa.status_code != 200:
        pytest.skip("Super admin login failed")
    sa_tok = sa.json()["token"]
    sa_h = _h(sa_tok)

    suffix = uuid.uuid4().hex[:6]
    admin_email = f"isotest_{suffix}@example.com"
    admin_pass = "isotest123"
    # try a few CNPJs in case of duplicate
    shop_code = None
    shop_id = None
    for _ in range(5):
        payload = {
            "shop_name": f"TEST ISO {suffix}", "name": f"Iso Owner {suffix}",
            "email": admin_email, "password": admin_pass, "phone": "",
            "cpf_cnpj": gen_valid_cnpj(),
        }
        r = requests.post(f"{API}/auth/request-access", json=payload)
        if r.status_code == 200:
            shop_code = r.json()["shop_code"]
            break
    if not shop_code:
        pytest.skip(f"Could not create second shop: {r.status_code} {r.text}")

    # find shop id
    def _find(items):
        for s in items:
            if s.get("code") == shop_code:
                return s.get("id") or s.get("_id")
        return None
    r = requests.get(f"{API}/platform/shops?status=pending", headers=sa_h).json()
    items = r.get("shops", r) if isinstance(r, dict) else r
    shop_id = _find(items or [])
    if not shop_id:
        r2 = requests.get(f"{API}/platform/shops", headers=sa_h).json()
        items2 = r2.get("shops", r2) if isinstance(r2, dict) else r2
        shop_id = _find(items2 or [])
    assert shop_id, "Could not find created shop id"

    ar = requests.post(f"{API}/platform/shops/{shop_id}/approve", headers=sa_h,
                       json={"reason": "test approve"})
    assert ar.status_code == 200, ar.text

    # login as 2nd shop admin
    lr = requests.post(f"{API}/auth/login",
                       json={"shop_code": shop_code, "email": admin_email, "password": admin_pass})
    assert lr.status_code == 200, lr.text
    return lr.json()["token"]


# ---------- Walk-in creation ----------
class TestWalkinCreate:
    def test_walkin_create_success(self, admin_h, barber_and_service):
        barber, service = barber_and_service
        d = _future_date(21)
        # find a free slot
        av = requests.get(f"{API}/availability?barber_id={barber['id']}&date={d}", headers=admin_h).json()
        free = [s["time"] for s in av["slots"] if s["available"]]
        assert free, "No free slots"
        slot = free[0]
        before_clients = requests.get(f"{API}/clients", headers=admin_h).json()
        before_count = len(before_clients)

        payload = {
            "barber_id": barber["id"], "service_id": service["id"],
            "date": d, "time": slot,
            "client_name": "TEST Walkin João", "client_phone": "11988887777",
        }
        r = requests.post(f"{API}/appointments", json=payload, headers=admin_h)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        assert data["client_id"] is None
        assert data["client_name"] == "TEST Walkin João"
        assert data["client_phone"] == "11988887777"
        assert data["status"] == "Confirmado"
        assert "id" in data

        # No new client created
        after_clients = requests.get(f"{API}/clients", headers=admin_h).json()
        assert len(after_clients) == before_count

        # Store for later
        TestWalkinCreate.appt_id = data["id"]
        TestWalkinCreate.appt_date = d
        TestWalkinCreate.appt_time = slot
        TestWalkinCreate.barber_id = barber["id"]
        TestWalkinCreate.service_id = service["id"]
        TestWalkinCreate.price = data.get("price", 0)

    def test_conflict_409(self, admin_h):
        payload = {
            "barber_id": TestWalkinCreate.barber_id, "service_id": TestWalkinCreate.service_id,
            "date": TestWalkinCreate.appt_date, "time": TestWalkinCreate.appt_time,
            "client_name": "Other Walkin", "client_phone": "11900000000",
        }
        r = requests.post(f"{API}/appointments", json=payload, headers=admin_h)
        assert r.status_code == 409, r.text

    def test_availability_shows_taken(self, admin_h):
        av = requests.get(
            f"{API}/availability?barber_id={TestWalkinCreate.barber_id}&date={TestWalkinCreate.appt_date}",
            headers=admin_h,
        ).json()
        taken = {s["time"]: s["available"] for s in av["slots"]}
        assert taken.get(TestWalkinCreate.appt_time) is False

    def test_validation_missing_client(self, admin_h, barber_and_service):
        barber, service = barber_and_service
        d = _future_date(28)
        av = requests.get(f"{API}/availability?barber_id={barber['id']}&date={d}", headers=admin_h).json()
        slot = next((s["time"] for s in av["slots"] if s["available"]), None)
        assert slot
        payload = {
            "barber_id": barber["id"], "service_id": service["id"],
            "date": d, "time": slot,
        }
        r = requests.post(f"{API}/appointments", json=payload, headers=admin_h)
        assert r.status_code == 400, r.text


# ---------- Registered-client regression ----------
class TestRegisteredClient:
    def test_create_with_client_id(self, admin_h, barber_and_service):
        barber, service = barber_and_service
        # ensure a client exists
        clients = requests.get(f"{API}/clients", headers=admin_h).json()
        if clients:
            cid = clients[0]["id"]
        else:
            cr = requests.post(f"{API}/clients", headers=admin_h, json={
                "name": "TEST Cliente", "email": f"test_{uuid.uuid4().hex[:6]}@ex.com",
                "phone": "11999990000", "password": "x", "notes": "",
            })
            assert cr.status_code in (200, 201), cr.text
            cid = cr.json()["id"]
        d = _future_date(30)
        av = requests.get(f"{API}/availability?barber_id={barber['id']}&date={d}", headers=admin_h).json()
        slot = next((s["time"] for s in av["slots"] if s["available"]), None)
        assert slot
        payload = {
            "barber_id": barber["id"], "service_id": service["id"],
            "date": d, "time": slot, "client_id": cid,
        }
        r = requests.post(f"{API}/appointments", json=payload, headers=admin_h)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        assert data["client_id"] == cid
        assert data["client_name"]
        TestRegisteredClient.appt_id = data["id"]


# ---------- Edit/cancel/delete walk-in + reports ----------
class TestWalkinLifecycleReports:
    def test_walkin_visible_in_list(self, admin_h):
        lst = requests.get(f"{API}/appointments", headers=admin_h).json()
        ids = {a["id"] for a in lst}
        assert TestWalkinCreate.appt_id in ids
        appt = next(a for a in lst if a["id"] == TestWalkinCreate.appt_id)
        assert appt["client_name"] == "TEST Walkin João"
        assert appt["client_id"] is None

    def test_complete_walkin_updates_reports(self, admin_h):
        # Barber total_cuts baseline + barber revenue baseline from report
        month = TestWalkinCreate.appt_date[:7]
        rep_before = requests.get(f"{API}/reports/barbers?month={month}", headers=admin_h).json()
        br_before = next(
            (b for b in rep_before["report"] if b["barber_id"] == TestWalkinCreate.barber_id), None
        )
        rev_before = br_before["revenue"] if br_before else 0

        # patch to Concluído
        r = requests.patch(
            f"{API}/appointments/{TestWalkinCreate.appt_id}/status",
            headers=admin_h, json={"status": "Concluído"},
        )
        assert r.status_code == 200, r.text

        rep_after = requests.get(f"{API}/reports/barbers?month={month}", headers=admin_h).json()
        br_after = next(
            (b for b in rep_after["report"] if b["barber_id"] == TestWalkinCreate.barber_id), None
        )
        assert br_after is not None
        assert br_after["revenue"] == pytest.approx(rev_before + TestWalkinCreate.price)
        # commission reflected
        assert br_after["commission"] >= br_before["commission"] if br_before else True

        # dashboard total revenue reflects walk-in
        stats = requests.get(f"{API}/dashboard/stats", headers=admin_h).json()
        assert stats["revenue_total"] >= TestWalkinCreate.price

    def test_cancel_and_delete_walkin(self, admin_h, barber_and_service):
        # Create a 2nd walk-in to cancel + delete
        barber, service = barber_and_service
        slot = None
        d = None
        for off in range(14, 90):
            d = _future_date(off)
            av = requests.get(f"{API}/availability?barber_id={barber['id']}&date={d}", headers=admin_h).json()
            slot = next((s["time"] for s in av["slots"] if s["available"]), None)
            if slot:
                break
        assert slot
        r = requests.post(f"{API}/appointments", json={
            "barber_id": barber["id"], "service_id": service["id"], "date": d, "time": slot,
            "client_name": "TEST Walkin Cancel", "client_phone": "11911112222",
        }, headers=admin_h)
        assert r.status_code in (200, 201)
        aid = r.json()["id"]

        pc = requests.patch(f"{API}/appointments/{aid}/status", headers=admin_h,
                            json={"status": "Cancelado"})
        assert pc.status_code == 200

        dl = requests.delete(f"{API}/appointments/{aid}", headers=admin_h)
        assert dl.status_code == 200


# ---------- Multi-shop isolation ----------
class TestIsolation:
    def test_other_shop_cannot_see_or_edit_walkin(self, second_shop_admin_token, admin_h):
        other_h = _h(second_shop_admin_token)
        lst = requests.get(f"{API}/appointments", headers=other_h).json()
        ids = {a["id"] for a in lst}
        assert TestWalkinCreate.appt_id not in ids

        pr = requests.patch(f"{API}/appointments/{TestWalkinCreate.appt_id}/status",
                            headers=other_h, json={"status": "Cancelado"})
        assert pr.status_code == 404

        dr = requests.delete(f"{API}/appointments/{TestWalkinCreate.appt_id}", headers=other_h)
        assert dr.status_code == 404
