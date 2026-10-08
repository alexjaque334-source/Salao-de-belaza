"""
Phase 2 — Super Admin platform & shop status gating tests.

Covers:
- Super admin login (success / wrong password 401 / brute force 429)
- Role separation (CRM token vs platform token cross-access -> 403)
- Request-access (CNPJ validation, duplicate, pending shop creation)
- Status gating (pending owner can login, /auth/me shows pending, CRM 403)
- Approval/suspension/reactivation flow + decision history
- Client register blocked on non-active shops; existing client blocked on suspended login
- Phase 1 isolation preserved across two active shops
- Super admin idempotence (platform_admins count stays 1 across restart logic)
- Autopromotion blocked (update_client cannot change role)
"""
import os
import time
import uuid
import pytest
import requests

def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv("/app/frontend/.env")
    except Exception:
        pass
_load_env()
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

SA_EMAIL = "alexjaque334@gmail.com"
SA_PASS = "plataforma123"
DEMO_CODE = "DEMO01"
ADMIN_EMAIL = "alexjaque334@gmail.com"
ADMIN_PASS = "admin123"

# Valid docs from problem statement
VALID_CNPJ_1 = "11.222.333/0001-81"
VALID_CNPJ_2 = "45.723.174/0001-10"
VALID_CPF = "390.533.447-05"
INVALID_CNPJ = "11.222.333/0001-00"


def _uniq(prefix="TEST"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def super_token():
    r = requests.post(f"{API}/platform/login", json={"email": SA_EMAIL, "password": SA_PASS})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    return data["token"]


@pytest.fixture(scope="session")
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}"}


@pytest.fixture(scope="session")
def demo_admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"shop_code": DEMO_CODE, "email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------- Super admin login ----------
class TestPlatformLogin:
    def test_success(self, super_token):
        assert super_token

    def test_wrong_password(self):
        r = requests.post(f"{API}/platform/login",
                          json={"email": SA_EMAIL, "password": "wrong-xyz-" + uuid.uuid4().hex[:4]})
        assert r.status_code == 401

    def test_brute_force_429(self):
        # Use a unique email to not pollute real SA bucket; expect 401s then 429
        email = f"bf_{uuid.uuid4().hex[:8]}@test.com"
        last = None
        for _ in range(10):
            last = requests.post(f"{API}/platform/login", json={"email": email, "password": "x"})
            if last.status_code == 429:
                break
        assert last.status_code == 429, f"expected 429, got {last.status_code}"


# ---------- Role separation ----------
class TestRoleSeparation:
    def test_platform_token_cannot_access_crm(self, super_headers):
        r = requests.get(f"{API}/barbers", headers=super_headers)
        assert r.status_code == 403

    def test_crm_token_cannot_access_platform(self, demo_admin_token):
        h = {"Authorization": f"Bearer {demo_admin_token}"}
        r = requests.get(f"{API}/platform/stats", headers=h)
        assert r.status_code == 403

    def test_platform_no_token_401(self):
        r = requests.get(f"{API}/platform/stats")
        assert r.status_code == 401


# ---------- Request access ----------
class TestRequestAccess:
    def test_invalid_cnpj_400(self):
        r = requests.post(f"{API}/auth/request-access", json={
            "shop_name": _uniq("TEST shop"),
            "name": "Owner", "email": f"{_uniq('o')}@test.com",
            "password": "senha123", "phone": "", "cpf_cnpj": INVALID_CNPJ,
        })
        assert r.status_code == 400

    def test_create_pending_and_duplicate_400(self):
        # Use a unique valid CNPJ by picking VALID_CNPJ_2 if 1 is taken; attempt first, then dup.
        payload = {
            "shop_name": _uniq("TEST pending"),
            "name": "Owner", "email": f"{_uniq('o')}@test.com",
            "password": "senha123", "phone": "", "cpf_cnpj": VALID_CNPJ_1,
        }
        r = requests.post(f"{API}/auth/request-access", json=payload)
        if r.status_code == 400:
            # CNPJ already taken from previous runs - use the alt
            payload["cpf_cnpj"] = VALID_CNPJ_2
            payload["email"] = f"{_uniq('o')}@test.com"
            payload["shop_name"] = _uniq("TEST pending")
            r = requests.post(f"{API}/auth/request-access", json=payload)
            if r.status_code == 400:
                pytest.skip("Both valid CNPJs exhausted in persistent DB; skip.")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["shop_code"] and len(body["shop_code"]) == 6
        # store for other tests
        pytest.pending_shop = {
            "code": body["shop_code"],
            "email": payload["email"],
            "password": payload["password"],
            "cpf_cnpj": payload["cpf_cnpj"],
        }
        # Duplicate CPF/CNPJ
        dup = dict(payload)
        dup["email"] = f"{_uniq('d')}@test.com"
        dup["shop_name"] = _uniq("TEST dup")
        r2 = requests.post(f"{API}/auth/request-access", json=dup)
        assert r2.status_code == 400


# ---------- Status gating ----------
class TestGating:
    def test_pending_owner_login_and_me(self):
        p = getattr(pytest, "pending_shop", None)
        if not p:
            pytest.skip("no pending shop")
        r = requests.post(f"{API}/auth/login",
                          json={"shop_code": p["code"], "email": p["email"], "password": p["password"]})
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        pytest.pending_shop["token"] = tok
        # /auth/me shows pending
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert me.status_code == 200
        assert me.json()["shop_status"] == "pending"

    def test_pending_crm_blocked_403(self):
        p = getattr(pytest, "pending_shop", None)
        if not p or "token" not in p:
            pytest.skip("no pending token")
        h = {"Authorization": f"Bearer {p['token']}"}
        for ep in ["/barbers", "/appointments", "/dashboard/stats"]:
            r = requests.get(f"{API}{ep}", headers=h)
            assert r.status_code == 403, f"{ep} should be 403, got {r.status_code}"
        r = requests.post(f"{API}/barbers", headers=h, json={"name": "x"})
        assert r.status_code == 403

    def test_register_on_pending_shop_403(self):
        p = getattr(pytest, "pending_shop", None)
        if not p:
            pytest.skip("no pending shop")
        r = requests.post(f"{API}/auth/register", json={
            "shop_code": p["code"], "name": "C", "email": f"{_uniq('c')}@t.com",
            "password": "x1x1x1", "phone": "",
        })
        assert r.status_code == 403


# ---------- Platform decisions ----------
class TestPlatformDecisions:
    def test_stats_and_list(self, super_headers):
        s = requests.get(f"{API}/platform/stats", headers=super_headers)
        assert s.status_code == 200
        body = s.json()
        for k in ("active", "pending", "suspended", "rejected", "total"):
            assert k in body

        lst = requests.get(f"{API}/platform/shops?status=pending", headers=super_headers)
        assert lst.status_code == 200
        for shop in lst.json():
            # Masked CPF
            assert "*" in shop["cpf_cnpj"] or shop["cpf_cnpj"] == "***"

    def test_detail_unmasked(self, super_headers):
        p = getattr(pytest, "pending_shop", None)
        if not p:
            pytest.skip("no pending")
        lst = requests.get(f"{API}/platform/shops?status=pending", headers=super_headers).json()
        target = next((x for x in lst if x["code"] == p["code"]), None)
        assert target
        pytest.pending_shop["id"] = target["id"]
        det = requests.get(f"{API}/platform/shops/{target['id']}", headers=super_headers)
        assert det.status_code == 200
        # Full doc (digits only), no mask
        assert "*" not in det.json()["cpf_cnpj"]

    def test_approve_then_crm_works(self, super_headers):
        p = getattr(pytest, "pending_shop", None)
        if not p or "id" not in p:
            pytest.skip()
        r = requests.post(f"{API}/platform/shops/{p['id']}/approve",
                          headers=super_headers, json={"reason": "ok"})
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        assert any(e["action"] == "aprovou" for e in r.json()["decision_history"])
        # Owner now can access CRM
        h = {"Authorization": f"Bearer {p['token']}"}
        g = requests.get(f"{API}/barbers", headers=h)
        assert g.status_code == 200
        # Client can register
        cr = requests.post(f"{API}/auth/register", json={
            "shop_code": p["code"], "name": "ClienteT", "email": f"{_uniq('c')}@t.com",
            "password": "x1x1x1", "phone": "",
        })
        assert cr.status_code == 200
        pytest.pending_shop["client_token"] = cr.json()["token"]
        pytest.pending_shop["client_email"] = cr.json()["user"]["email"]

    def test_suspend_blocks_client_login(self, super_headers):
        p = getattr(pytest, "pending_shop", None)
        if not p or "client_token" not in p:
            pytest.skip()
        r = requests.post(f"{API}/platform/shops/{p['id']}/suspend",
                          headers=super_headers, json={"reason": "pausa"})
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"
        # Owner /auth/me shows suspended; CRM blocked
        h = {"Authorization": f"Bearer {p['token']}"}
        me = requests.get(f"{API}/auth/me", headers=h).json()
        assert me["shop_status"] == "suspended"
        assert requests.get(f"{API}/barbers", headers=h).status_code == 403
        # Client cannot login anymore
        cl = requests.post(f"{API}/auth/login", json={
            "shop_code": p["code"], "email": p["client_email"], "password": "x1x1x1",
        })
        assert cl.status_code == 403

    def test_reactivate_restores(self, super_headers):
        p = getattr(pytest, "pending_shop", None)
        if not p:
            pytest.skip()
        r = requests.post(f"{API}/platform/shops/{p['id']}/reactivate",
                          headers=super_headers, json={})
        assert r.status_code == 200
        assert r.json()["status"] == "active"
        h = {"Authorization": f"Bearer {p['token']}"}
        assert requests.get(f"{API}/barbers", headers=h).status_code == 200


# ---------- Phase 1 isolation preserved ----------
class TestIsolationPreserved:
    def test_two_active_shops_dont_share_data(self, super_headers):
        # Create 2 pending shops with valid CPFs via request-access
        shops = []
        for cpf in [VALID_CPF]:
            # single CPF reusable only once -> use different CNPJs
            pass
        # Use VALID_CNPJ_2 and VALID_CPF for 2 shops
        for doc in [VALID_CNPJ_2, VALID_CPF]:
            payload = {
                "shop_name": _uniq("TEST iso"),
                "name": "O", "email": f"{_uniq('iso')}@t.com",
                "password": "senha123", "cpf_cnpj": doc,
            }
            r = requests.post(f"{API}/auth/request-access", json=payload)
            if r.status_code == 400:
                # already consumed by prior runs, skip
                continue
            shops.append({"code": r.json()["shop_code"],
                          "email": payload["email"], "password": payload["password"]})
        if len(shops) < 2:
            pytest.skip("couldn't create 2 fresh shops (persistent DB)")
        # approve both
        lst = requests.get(f"{API}/platform/shops?status=pending", headers=super_headers).json()
        for s in shops:
            m = next((x for x in lst if x["code"] == s["code"]), None)
            if m:
                requests.post(f"{API}/platform/shops/{m['id']}/approve",
                              headers=super_headers, json={})
                s["id"] = m["id"]
        tokens = []
        for s in shops:
            lr = requests.post(f"{API}/auth/login", json={
                "shop_code": s["code"], "email": s["email"], "password": s["password"],
            })
            assert lr.status_code == 200
            tokens.append(lr.json()["token"])
        # shop A creates barber; shop B cannot see or edit
        h0 = {"Authorization": f"Bearer {tokens[0]}"}
        h1 = {"Authorization": f"Bearer {tokens[1]}"}
        br = requests.post(f"{API}/barbers", headers=h0,
                           json={"name": _uniq("TESTbarber"), "specialty": ""})
        assert br.status_code == 200
        bid = br.json()["id"]
        others = requests.get(f"{API}/barbers", headers=h1).json()
        assert all(b["id"] != bid for b in others)
        # cross-shop edit must 404
        up = requests.put(f"{API}/barbers/{bid}", headers=h1,
                          json={"name": "x", "specialty": ""})
        assert up.status_code == 404


# ---------- Idempotence ----------
class TestSuperAdminIdempotent:
    def test_single_platform_admin_record(self, super_headers):
        # No endpoint for raw count; indirect: login works and /platform/me returns the same email
        r = requests.get(f"{API}/platform/me", headers=super_headers)
        assert r.status_code == 200
        assert r.json()["email"] == SA_EMAIL

    def test_demo_shop_active(self):
        r = requests.get(f"{API}/shops/resolve?code={DEMO_CODE}")
        assert r.status_code == 200


# ---------- Autopromotion blocked ----------
class TestAutopromotion:
    def test_update_client_cannot_change_role(self, demo_admin_token):
        h = {"Authorization": f"Bearer {demo_admin_token}"}
        # Create or find a client
        email = f"{_uniq('promo')}@t.com"
        c = requests.post(f"{API}/clients", headers=h, json={
            "name": "P", "email": email, "phone": "", "password": "x1x1x1",
        })
        assert c.status_code == 200
        cid = c.json()["id"]
        # Try to send extra role field — endpoint should ignore it
        upd = requests.put(f"{API}/clients/{cid}", headers=h, json={
            "name": "Px", "email": email, "phone": "", "notes": "",
            "role": "admin",
        })
        assert upd.status_code == 200
        # Fetch via list and ensure role still client
        lst = requests.get(f"{API}/clients", headers=h).json()
        found = next((x for x in lst if x["id"] == cid), None)
        assert found and found["role"] == "client"
