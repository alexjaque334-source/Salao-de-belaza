"""Isolated booking-rule tests; all database operations use in-memory fakes."""

import asyncio
import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx


class MemoryCursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, length):
        return self.documents[:length] if length is not None else self.documents


class MemoryCollection:
    def __init__(self, documents=()):
        self.documents = list(documents)

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$ne" in expected:
                if actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query, session=None):
        return next((doc for doc in self.documents if self._matches(doc, query)), None)

    def find(self, query, session=None):
        return MemoryCursor([doc for doc in self.documents if self._matches(doc, query)])

    async def insert_one(self, document, session=None):
        stored = dict(document)
        stored.setdefault("_id", _server.ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def update_one(self, query, update, upsert=False, session=None):
        document = next((doc for doc in self.documents if self._matches(doc, query)), None)
        upserted_id = None
        if document is None and upsert:
            document = {key: value for key, value in query.items() if not isinstance(value, dict)}
            for key, value in update.get("$setOnInsert", {}).items():
                document.setdefault(key, value)
            self.documents.append(document)
            upserted_id = document.get("_id")
        if document is None:
            return SimpleNamespace(matched_count=0, upserted_id=None)
        for key, value in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value
        return SimpleNamespace(matched_count=1, upserted_id=upserted_id)

    async def delete_one(self, query, session=None):
        for idx, doc in enumerate(self.documents):
            if self._matches(doc, query):
                del self.documents[idx]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class MemoryDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: MemoryCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        return self.collections.setdefault(name, MemoryCollection())

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


class NoNetworkMongoClient:
    """Stand-in used during module import; it never opens a socket."""

    def __init__(self, *args, **kwargs):
        self.database = MemoryDatabase()
        self.transaction_lock = asyncio.Lock()
        self.session_barrier = None
        self.session_attempts = 0

    def __getitem__(self, name):
        return self.database

    async def start_session(self):
        if self.session_barrier is not None:
            self.session_attempts += 1
            if self.session_attempts == 2:
                self.session_barrier.set()
            await self.session_barrier.wait()
        return MemorySession(self)


class MemorySession:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def with_transaction(self, callback):
        async with self.client.transaction_lock:
            return await callback(self)


_server = None


class BookingRulesUnitTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = patch.dict(
            os.environ,
            {
                "MONGO_URL": "mongodb://127.0.0.1:27017",
                "DB_NAME": "booking_unit_test",
                "JWT_SECRET": "unit-test-only",
            },
        )
        cls.environment.start()
        cls.dotenv = patch("dotenv.load_dotenv", return_value=False)
        cls.dotenv.start()
        cls.mongo = patch("motor.motor_asyncio.AsyncIOMotorClient", NoNetworkMongoClient)
        cls.mongo.start()
        global _server
        _server = importlib.import_module("backend.server")

    @classmethod
    def tearDownClass(cls):
        cls.mongo.stop()
        cls.dotenv.stop()
        cls.environment.stop()

    def setUp(self):
        self.shop_oid = _server.ObjectId()
        self.shop_id = str(self.shop_oid)
        self.platform_plan_oid = _server.ObjectId()
        self.barber_oid = _server.ObjectId()
        self.service_oid = _server.ObjectId()
        self.clients = [
            {"_id": _server.ObjectId(), "shop_id": self.shop_id, "name": "Test One", "role": "client"},
            {"_id": _server.ObjectId(), "shop_id": self.shop_id, "name": "Test Two", "role": "client"},
        ]
        self.server_db = MemoryDatabase(
            {
                "barbers": [
                    {
                        "_id": self.barber_oid,
                        "shop_id": self.shop_id,
                        "name": "Test Barber",
                        "active": True,
                        "working_hours": {"mon": {"start": "09:00", "end": "11:00"}},
                    }
                ],
                "services": [
                    {
                        "_id": self.service_oid,
                        "shop_id": self.shop_id,
                        "name": "Test Service",
                        "duration": 30,
                        "price": 30,
                        "active": True,
                    }
                ],
                "shops": [{
                    "_id": self.shop_oid,
                    "name": "Test Shop",
                    "public_slug": "test-shop",
                    "status": "active",
                    "platform_plan_id": self.platform_plan_oid,
                }],
                "platform_plans": [{
                    "_id": self.platform_plan_oid,
                    "name": "Premium",
                    "active": True,
                    "pdf_reports": True,
                }],
                "users": self.clients,
            }
        )
        _server.db = self.server_db
        _server.client.transaction_lock = asyncio.Lock()
        _server.client.session_barrier = None
        _server.client.session_attempts = 0

    def _admin_user(self):
        return {"_id": _server.ObjectId(), "shop_id": self.shop_id, "role": "admin"}

    async def _admin_availability(self, date="2026-10-12", service_id=None):
        return await _server.availability(
            str(self.barber_oid), date, {"shop_id": self.shop_id, "role": "admin"}, service_id
        )

    async def _public_availability(self, date="2026-10-12", service_id=None):
        async def public_shop(_slug):
            return {"_id": self.shop_oid, "name": "Test Shop", "status": "active"}

        with patch.object(_server, "_public_shop", new=public_shop):
            return await _server.public_availability("test-shop", str(self.barber_oid), date, service_id)

    def _appointment(self, client_id, time="09:00"):
        return _server.AppointmentIn(
            barber_id=str(self.barber_oid),
            service_id=str(self.service_oid),
            date="2026-10-12",
            time=time,
            client_id=str(client_id),
        )

    async def _create_admin_appointment(self, client_id, time="09:00"):
        return await _server.create_appointment(self._appointment(client_id, time), self._admin_user())

    def test_slot_generator_accepts_15_30_and_60_minute_intervals(self):
        expected = {
            15: ["09:00", "09:15", "09:30", "09:45"],
            30: ["09:00", "09:30"],
            60: ["09:00"],
        }
        for duration, slots in expected.items():
            with self.subTest(duration=duration):
                self.assertEqual(_server.gen_slots("09:00", "10:00", duration), slots)

    async def test_consecutive_30_minute_booking_is_available(self):
        _server.db.appointments.documents.append(
            {"shop_id": self.shop_id, "barber_id": str(self.barber_oid), "date": "2026-10-12",
             "time": "09:00", "duration": 30, "status": "Confirmado"}
        )
        result = await self._admin_availability(service_id=str(self.service_oid))
        availability = {slot["time"]: slot["available"] for slot in result["slots"]}
        self.assertTrue(availability["09:30"])

    async def test_15_minute_service_exposes_quarter_hour_starts(self):
        _server.db.services.documents[0]["duration"] = 15
        result = await self._admin_availability(service_id=str(self.service_oid))
        slots = [slot["time"] for slot in result["slots"]]
        self.assertIn("09:15", slots)

    async def test_60_minute_service_slots_fit_inside_working_hours(self):
        _server.db.services.documents[0]["duration"] = 60
        result = await self._admin_availability(service_id=str(self.service_oid))
        slots = [slot["time"] for slot in result["slots"]]
        self.assertEqual(slots, ["09:00", "09:30", "10:00"])

    async def test_60_minute_booking_blocks_partially_overlapping_slot_for_admin(self):
        _server.db.appointments.documents.append(
            {"shop_id": self.shop_id, "barber_id": str(self.barber_oid), "date": "2026-10-12",
               "time": "09:00", "service_id": str(self.service_oid),
             "status": "Confirmado"}
        )
        _server.db.services.documents[0]["duration"] = 60
        result = await self._admin_availability(service_id=str(self.service_oid))
        availability = {slot["time"]: slot["available"] for slot in result["slots"]}
        self.assertFalse(availability["09:30"])

    async def test_60_minute_booking_blocks_partially_overlapping_slot_for_public_booking(self):
        _server.db.appointments.documents.append(
            {"shop_id": self.shop_id, "barber_id": str(self.barber_oid), "date": "2026-10-12",
               "time": "09:00", "service_id": str(self.service_oid),
             "status": "Confirmado"}
        )
        _server.db.services.documents[0]["duration"] = 60
        result = await self._public_availability(service_id=str(self.service_oid))
        availability = {slot["time"]: slot["available"] for slot in result["slots"]}
        self.assertFalse(availability["09:30"])

    async def test_admin_creation_rejects_partially_overlapping_booking(self):
        _server.db.appointments.documents.append(
            {"shop_id": self.shop_id, "barber_id": str(self.barber_oid), "date": "2026-10-12",
             "time": "09:00", "service_id": str(self.service_oid), "status": "Confirmado"}
        )
        _server.db.services.documents[0]["duration"] = 60
        with self.assertRaises(_server.HTTPException) as raised:
            await self._create_admin_appointment(self.clients[0]["_id"], time="09:30")
        self.assertEqual(raised.exception.status_code, 409)

    async def test_public_creation_rejects_partially_overlapping_booking(self):
        _server.db.appointments.documents.append(
            {"shop_id": self.shop_id, "barber_id": str(self.barber_oid), "date": "2026-10-12",
             "time": "09:00", "service_id": str(self.service_oid), "status": "Confirmado"}
        )
        _server.db.services.documents[0]["duration"] = 60
        public_data = _server.PublicAppointmentIn(
            barber_id=str(self.barber_oid),
            service_id=str(self.service_oid),
            date="2026-10-12",
            time="09:30",
            client_name="Public Client",
            client_phone="11912345678",
        )

        async def public_shop(_slug):
            return {"_id": self.shop_oid, "name": "Test Shop", "status": "active"}

        with patch.object(_server, "_public_shop", new=public_shop):
            with self.assertRaises(_server.HTTPException) as raised:
                await _server.public_create_appointment("test-shop", public_data)
        self.assertEqual(raised.exception.status_code, 409)

    async def test_availability_stays_within_barber_working_hours(self):
        result = await self._admin_availability()
        slots = [slot["time"] for slot in result["slots"]]
        self.assertEqual(slots, ["09:00", "09:30", "10:00", "10:30"])
        sunday = await self._admin_availability("2026-10-18")
        self.assertEqual(sunday["slots"], [])

    async def test_admin_and_public_availability_return_same_slots(self):
        _server.db.appointments.documents.append(
            {"shop_id": self.shop_id, "barber_id": str(self.barber_oid), "date": "2026-10-12",
             "time": "09:30", "status": "Confirmado"}
        )
        admin_result = await self._admin_availability(service_id=str(self.service_oid))
        public_result = await self._public_availability(service_id=str(self.service_oid))
        self.assertEqual(admin_result, public_result)

    async def test_sequential_duplicate_booking_returns_conflict(self):
        await self._create_admin_appointment(self.clients[0]["_id"])
        with self.assertRaises(_server.HTTPException) as raised:
            await self._create_admin_appointment(self.clients[1]["_id"])
        self.assertEqual(raised.exception.status_code, 409)

    async def test_public_booking_conflicts_with_existing_admin_booking(self):
        await self._create_admin_appointment(self.clients[0]["_id"])

        async def public_shop(_slug):
            return {"_id": self.shop_oid, "name": "Test Shop", "status": "active"}

        public_data = _server.PublicAppointmentIn(
            barber_id=str(self.barber_oid),
            service_id=str(self.service_oid),
            date="2026-10-12",
            time="09:00",
            client_name="Public Client",
            client_phone="11912345678",
        )
        with patch.object(_server, "_public_shop", new=public_shop):
            with self.assertRaises(_server.HTTPException) as raised:
                await _server.public_create_appointment("test-shop", public_data)
        self.assertEqual(raised.exception.status_code, 409)

    async def test_public_endpoints_need_no_admin_token_and_stay_within_shop(self):
        other_shop_id = str(_server.ObjectId())
        other_barber_id = _server.ObjectId()
        other_service_id = _server.ObjectId()
        _server.db.barbers.documents.append({
            "_id": other_barber_id, "shop_id": other_shop_id, "name": "Other Barber",
            "active": True, "working_hours": {"mon": {"start": "09:00", "end": "11:00"}},
        })
        _server.db.services.documents.append({
            "_id": other_service_id, "shop_id": other_shop_id, "name": "Other Service",
            "duration": 30, "price": 10, "active": True,
        })
        transport = httpx.ASGITransport(app=_server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            shop_response = await client.get("/api/public/shops/test-shop")
            slots_response = await client.get(
                "/api/public/shops/test-shop/availability",
                params={"barber_id": str(self.barber_oid), "service_id": str(self.service_oid), "date": "2026-10-12"},
            )
        self.assertEqual(shop_response.status_code, 200)
        self.assertEqual(shop_response.json()["name"], "Test Shop")
        self.assertEqual([item["id"] for item in shop_response.json()["barbers"]], [str(self.barber_oid)])
        self.assertEqual([item["id"] for item in shop_response.json()["services"]], [str(self.service_oid)])
        self.assertEqual(slots_response.status_code, 200)

    async def test_public_http_booking_creates_confirmation_without_admin_token(self):
        transport = httpx.ASGITransport(app=_server.app)
        payload = {
            "barber_id": str(self.barber_oid),
            "service_id": str(self.service_oid),
            "date": "2026-10-12",
            "time": "09:00",
            "client_name": "Public Client",
            "client_phone": "11912345678",
        }
        with patch.object(_server.email_service, "safe_send_confirmation", new=AsyncMock(return_value=True)):
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post("/api/public/shops/test-shop/appointments", json=payload)
        self.assertEqual(response.status_code, 200)
        appointment = response.json()["appointment"]
        self.assertEqual(appointment["service_name"], "Test Service")
        self.assertEqual(appointment["barber_name"], "Test Barber")
        self.assertEqual(appointment["date"], "2026-10-12")
        self.assertEqual(appointment["time"], "09:00")

    async def test_invalid_public_slug_returns_clear_not_found(self):
        transport = httpx.ASGITransport(app=_server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/public/shops/unknown-shop")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Barbearia", response.json()["detail"])

    async def test_simultaneous_duplicate_bookings_do_not_both_succeed(self):
        _server.client.session_barrier = asyncio.Event()
        try:
            with patch.object(_server.email_service, "safe_send_confirmation", new=AsyncMock(return_value=True)):
                results = await asyncio.gather(
                    self._create_admin_appointment(self.clients[0]["_id"]),
                    self._create_admin_appointment(self.clients[1]["_id"]),
                    return_exceptions=True,
                )
        finally:
            _server.client.session_barrier = None
        successes = [result for result in results if not isinstance(result, Exception)]
        conflicts = [result for result in results if isinstance(result, _server.HTTPException)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].status_code, 409)
        self.assertEqual(len(_server.db.appointments.documents), 1)

    async def test_simultaneous_admin_and_public_booking_share_the_same_lock(self):
        _server.client.session_barrier = asyncio.Event()

        async def public_shop(_slug):
            return {"_id": self.shop_oid, "name": "Test Shop", "status": "active"}

        public_data = _server.PublicAppointmentIn(
            barber_id=str(self.barber_oid), service_id=str(self.service_oid),
            date="2026-10-12", time="09:00", client_name="Public Client",
            client_phone="11912345678",
        )
        try:
            with patch.object(_server, "_public_shop", new=public_shop):
                with patch.object(_server.email_service, "safe_send_confirmation", new=AsyncMock(return_value=True)):
                    results = await asyncio.gather(
                        self._create_admin_appointment(self.clients[0]["_id"]),
                        _server.public_create_appointment("test-shop", public_data),
                        return_exceptions=True,
                    )
        finally:
            _server.client.session_barrier = None
        successes = [result for result in results if not isinstance(result, Exception)]
        conflicts = [result for result in results if isinstance(result, _server.HTTPException)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].status_code, 409)
        self.assertEqual(len(_server.db.appointments.documents), 1)

    def test_client_ip_prefers_edge_headers_and_resists_xff_prepend_spoofing(self):
        fake_req = SimpleNamespace(
            headers={
                "x-forwarded-for": "1.2.3.4, 203.0.113.99",
                "cf-connecting-ip": "198.51.100.42",
            },
            client=SimpleNamespace(host="10.0.0.1"),
        )
        self.assertEqual(_server.client_ip(fake_req), "198.51.100.42")

        fake_xff_only = SimpleNamespace(
            headers={"x-forwarded-for": "1.2.3.4, 203.0.113.99"},
            client=SimpleNamespace(host="10.0.0.1"),
        )
        self.assertEqual(_server.client_ip(fake_xff_only), "203.0.113.99")

    async def test_public_booking_blocks_honeypot_and_rate_limits_phone_spam(self):
        transport = httpx.ASGITransport(app=_server.app)
        honeypot_payload = {
            "barber_id": str(self.barber_oid),
            "service_id": str(self.service_oid),
            "date": "2026-10-12",
            "time": "09:00",
            "client_name": "Bot User",
            "client_phone": "11912345678",
            "website": "https://spam.example.com",
        }
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            bot_resp = await client.post("/api/public/shops/test-shop/appointments", json=honeypot_payload)
            self.assertEqual(bot_resp.status_code, 400)
            self.assertEqual(bot_resp.headers.get("x-content-type-options"), "nosniff")
            self.assertEqual(bot_resp.headers.get("x-frame-options"), "DENY")

        # Pre-seed 5 recent attempts for the same phone to verify the 6th is blocked with 429
        for _ in range(5):
            await _server.bump_attempt(f"pub_appt_phone:{self.shop_id}:11912345678")

        valid_payload = {
            "barber_id": str(self.barber_oid),
            "service_id": str(self.service_oid),
            "date": "2026-10-12",
            "time": "09:00",
            "client_name": "Real Client",
            "client_phone": "11912345678",
        }
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            rate_resp = await client.post("/api/public/shops/test-shop/appointments", json=valid_payload)
            self.assertEqual(rate_resp.status_code, 429)


if __name__ == "__main__":
    unittest.main()