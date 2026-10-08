"""
Multi-shop isolation and cross-shop authorization tests for Barbearia CRM.
Covers: shop creation, same-email across shops, login scoping, isolation of
barbers/services/plans/clients/appointments/dashboard, and the reminders cron.
"""
import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://barber-loyalty-14.preview.emergentagent.com").rstrip("/")
CRON_SECRET = "b8f3d1a67c4e92f05ba7d8e1c3609f24a5e7b0d2c9f16834"


def _future_date(days=3):
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture(scope="module")
def shared_email():
    return f"TEST_owner_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(scope="module")
def shop_a(shared_email):
    r = requests.post(f"{BASE_URL}/api/auth/shop", json={
        "shop_name": "TEST Barbearia A",
        "name": "Owner A", "email": shared_email, "password": "passA123",
    })
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def shop_b(shared_email):
    r = requests.post(f"{BASE_URL}/api/auth/shop", json={
        "shop_name": "TEST Barbearia B",
        "name": "Owner B", "email": shared_email, "password": "passB456",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ----- Shop creation + same-email across shops -----
class TestShopCreation:
    def test_shops_created_with_distinct_codes(self, shop_a, shop_b):
        assert shop_a["shop_code"] != shop_b["shop_code"]
        assert len(shop_a["shop_code"]) == 6
        assert shop_a["user"]["role"] == "admin"
        assert shop_b["user"]["role"] == "admin"
        assert shop_a["user"]["shop_id"] != shop_b["user"]["shop_id"]

    def test_same_email_both_shops(self, shop_a, shop_b, shared_email):
        assert shop_a["user"]["email"] == shared_email.lower()
        assert shop_b["user"]["email"] == shared_email.lower()


# ----- Login per shop -----
class TestLogin:
    def test_login_shop_a(self, shop_a, shared_email):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "shop_code": shop_a["shop_code"], "email": shared_email, "password": "passA123",
        })
        assert r.status_code == 200
        assert r.json()["user"]["shop_code"] == shop_a["shop_code"]

    def test_login_shop_b(self, shop_b, shared_email):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "shop_code": shop_b["shop_code"], "email": shared_email, "password": "passB456",
        })
        assert r.status_code == 200
        assert r.json()["user"]["shop_code"] == shop_b["shop_code"]

    def test_login_wrong_password_for_shop(self, shop_a, shared_email):
        # Shop A code with B's password -> 401
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "shop_code": shop_a["shop_code"], "email": shared_email, "password": "passB456",
        })
        assert r.status_code == 401

    def test_login_nonexistent_shop(self, shared_email):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "shop_code": "ZZZZZZ", "email": shared_email, "password": "passA123",
        })
        assert r.status_code == 401


# ----- Seed defaults + isolation -----
class TestSeedAndIsolation:
    def test_shop_has_default_services_and_plans_no_barbers(self, shop_a):
        tok = shop_a["token"]
        srv = requests.get(f"{BASE_URL}/api/services", headers=_h(tok)).json()
        plans = requests.get(f"{BASE_URL}/api/plans", headers=_h(tok)).json()
        barbers = requests.get(f"{BASE_URL}/api/barbers", headers=_h(tok)).json()
        assert len(srv) == 5
        assert len(plans) == 3
        assert len(barbers) == 0

    def test_admin_a_creates_barber_service_plan_not_visible_to_b(self, shop_a, shop_b):
        ta, tb = shop_a["token"], shop_b["token"]
        # create barber in A
        rb = requests.post(f"{BASE_URL}/api/barbers", headers=_h(ta), json={
            "name": "TEST BarberA", "specialty": "x", "commission_rate": 50,
            "working_hours": {"mon": {"start": "09:00", "end": "18:00"},
                              "tue": {"start": "09:00", "end": "18:00"},
                              "wed": {"start": "09:00", "end": "18:00"},
                              "thu": {"start": "09:00", "end": "18:00"},
                              "fri": {"start": "09:00", "end": "18:00"},
                              "sat": {"start": "09:00", "end": "18:00"},
                              "sun": {"start": "09:00", "end": "18:00"}},
        })
        assert rb.status_code == 200, rb.text
        rs = requests.post(f"{BASE_URL}/api/services", headers=_h(ta),
                           json={"name": "TEST SvcA", "duration": 30, "price": 50})
        assert rs.status_code == 200
        rp = requests.post(f"{BASE_URL}/api/plans", headers=_h(ta),
                           json={"name": "TEST PlanA", "price": 99, "features": []})
        assert rp.status_code == 200

        # Verify B does not see any of these
        barbers_b = requests.get(f"{BASE_URL}/api/barbers", headers=_h(tb)).json()
        services_b = requests.get(f"{BASE_URL}/api/services", headers=_h(tb)).json()
        plans_b = requests.get(f"{BASE_URL}/api/plans", headers=_h(tb)).json()
        assert all(b["name"] != "TEST BarberA" for b in barbers_b)
        assert all(s["name"] != "TEST SvcA" for s in services_b)
        assert all(p["name"] != "TEST PlanA" for p in plans_b)

        # Save ids on shop_a fixture via pytest cache not needed; store on module
        pytest._a_barber_id = rb.json()["id"]
        pytest._a_service_id = rs.json()["id"]
        pytest._a_plan_id = rp.json()["id"]


# ----- Cross-shop authorization -----
class TestCrossShopAuthz:
    def test_update_barber_cross_shop_404(self, shop_b):
        tb = shop_b["token"]
        r = requests.put(f"{BASE_URL}/api/barbers/{pytest._a_barber_id}", headers=_h(tb),
                         json={"name": "HACK", "working_hours": {}})
        assert r.status_code == 404

    def test_delete_barber_cross_shop_404(self, shop_b):
        tb = shop_b["token"]
        r = requests.delete(f"{BASE_URL}/api/barbers/{pytest._a_barber_id}", headers=_h(tb))
        assert r.status_code == 404

    def test_delete_service_cross_shop_404(self, shop_b):
        tb = shop_b["token"]
        r = requests.delete(f"{BASE_URL}/api/services/{pytest._a_service_id}", headers=_h(tb))
        assert r.status_code == 404

    def test_update_plan_cross_shop_404(self, shop_b):
        tb = shop_b["token"]
        r = requests.put(f"{BASE_URL}/api/plans/{pytest._a_plan_id}", headers=_h(tb),
                         json={"name": "HACK", "price": 1, "features": []})
        assert r.status_code == 404

    def test_delete_plan_cross_shop_404(self, shop_b):
        tb = shop_b["token"]
        r = requests.delete(f"{BASE_URL}/api/plans/{pytest._a_plan_id}", headers=_h(tb))
        assert r.status_code == 404


# ----- Appointments + availability + isolation -----
class TestAppointmentsIsolation:
    def test_booking_conflict_and_isolation(self, shop_a, shop_b):
        ta, tb = shop_a["token"], shop_b["token"]
        services = requests.get(f"{BASE_URL}/api/services", headers=_h(ta)).json()
        sid = services[0]["id"]
        d = _future_date(5)
        # Pick a weekday with hours
        appt1 = requests.post(f"{BASE_URL}/api/appointments", headers=_h(ta), json={
            "barber_id": pytest._a_barber_id, "service_id": sid,
            "date": d, "time": "10:00",
            "client_name": "TEST Walkin A", "client_phone": "0",
        })
        assert appt1.status_code == 200, appt1.text
        pytest._a_appt_id = appt1.json()["id"]

        # Conflict same slot
        dup = requests.post(f"{BASE_URL}/api/appointments", headers=_h(ta), json={
            "barber_id": pytest._a_barber_id, "service_id": sid,
            "date": d, "time": "10:00",
            "client_name": "TEST Dup", "client_phone": "0",
        })
        assert dup.status_code == 409

        # Availability says 10:00 unavailable
        av = requests.get(f"{BASE_URL}/api/availability",
                          headers=_h(ta),
                          params={"barber_id": pytest._a_barber_id, "date": d}).json()
        slot = next((s for s in av["slots"] if s["time"] == "10:00"), None)
        assert slot and slot["available"] is False

        # B cannot see A's appointment
        appts_b = requests.get(f"{BASE_URL}/api/appointments", headers=_h(tb)).json()
        assert all(a["id"] != pytest._a_appt_id for a in appts_b)

        # B cannot patch status or delete A's appointment
        p = requests.patch(f"{BASE_URL}/api/appointments/{pytest._a_appt_id}/status",
                           headers=_h(tb), json={"status": "Cancelado"})
        assert p.status_code == 404
        de = requests.delete(f"{BASE_URL}/api/appointments/{pytest._a_appt_id}", headers=_h(tb))
        assert de.status_code == 404


# ----- Clients isolation -----
class TestClientsIsolation:
    def test_client_cross_shop(self, shop_a, shop_b):
        ta, tb = shop_a["token"], shop_b["token"]
        em = f"TEST_c_{uuid.uuid4().hex[:6]}@ex.com"
        c = requests.post(f"{BASE_URL}/api/clients", headers=_h(ta),
                          json={"name": "TEST ClientA", "email": em, "phone": "1"})
        assert c.status_code == 200, c.text
        cid = c.json()["id"]

        clients_b = requests.get(f"{BASE_URL}/api/clients", headers=_h(tb)).json()
        assert all(cl["id"] != cid for cl in clients_b)

        r = requests.patch(f"{BASE_URL}/api/clients/{cid}/loyalty", headers=_h(tb),
                           json={"points": 500})
        assert r.status_code == 404
        r2 = requests.post(f"{BASE_URL}/api/clients/{cid}/redeem", headers=_h(tb))
        assert r2.status_code == 404


# ----- Dashboard & reports scoping -----
class TestDashboardReports:
    def test_dashboard_scoped(self, shop_a, shop_b):
        ta, tb = shop_a["token"], shop_b["token"]
        da = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=_h(ta)).json()
        db_ = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=_h(tb)).json()
        assert da["total_barbers"] >= 1
        assert db_["total_barbers"] == 0  # B hasn't created any
        # Clients: A should have >=1 (just created), B 0
        assert da["total_clients"] >= 1
        assert db_["total_clients"] == 0

    def test_reports_barbers_scoped(self, shop_a, shop_b):
        ta, tb = shop_a["token"], shop_b["token"]
        ra = requests.get(f"{BASE_URL}/api/reports/barbers", headers=_h(ta)).json()
        rb = requests.get(f"{BASE_URL}/api/reports/barbers", headers=_h(tb)).json()
        assert len(ra["report"]) >= 1
        assert len(rb["report"]) == 0


# ----- Cron -----
class TestCron:
    def test_cron_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/cron/reminders").status_code == 401
        assert requests.get(f"{BASE_URL}/api/cron/reminders").status_code == 401

    def test_cron_authorized(self):
        r = requests.post(f"{BASE_URL}/api/cron/reminders",
                          headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200
        body = r.json()
        for k in ("date", "due", "sent"):
            assert k in body


# ----- Demo admin login still works -----
class TestDemoAdmin:
    def test_demo_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={
            "shop_code": "DEMO01", "email": "alexjaque334@gmail.com", "password": "admin123",
        })
        assert r.status_code == 200
        assert r.json()["user"]["shop_code"] == "DEMO01"
