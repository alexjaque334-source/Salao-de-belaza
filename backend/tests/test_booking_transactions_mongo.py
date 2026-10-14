"""Opt-in MongoDB replica-set tests for cross-request booking transactions.

Set BARBERSTUDIO_TEST_MONGO_URL to a dedicated test replica set. Never use the
application's production MONGO_URL. Each test writes to a unique database and
does not drop it automatically.
"""

import asyncio
import os
import secrets
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from pymongo import MongoClient


class BookingTransactionMongoTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        test_uri = os.environ.get("BARBERSTUDIO_TEST_MONGO_URL")
        if not test_uri:
            raise unittest.SkipTest("BARBERSTUDIO_TEST_MONGO_URL is not configured")

        cls.database_prefix = f"barberstudio_test_{uuid.uuid4().hex}"
        cls.test_uri = test_uri
        os.environ["MONGO_URL"] = test_uri
        os.environ["DB_NAME"] = f"{cls.database_prefix}_bootstrap"
        os.environ["JWT_SECRET"] = secrets.token_hex(32)

        from backend import server

        cls.server = server
        probe = MongoClient(test_uri, serverSelectionTimeoutMS=5000)
        try:
            hello = probe.admin.command("hello")
        except Exception:
            raise RuntimeError("Could not connect to the explicitly configured test MongoDB") from None
        finally:
            probe.close()
        if not hello.get("setName"):
            raise unittest.SkipTest("Configured MongoDB is not a replica set")
        server.client.close()

    async def asyncSetUp(self):
        self.mongo = self.server.AsyncIOMotorClient(self.test_uri, serverSelectionTimeoutMS=5000)
        self.database_name = f"{self.database_prefix}_{uuid.uuid4().hex}"
        self.database = self.mongo[self.database_name]
        self.server.client = self.mongo
        self.server.db = self.database
        self.shop_oid = self.server.ObjectId()
        self.shop_id = str(self.shop_oid)
        self.barber_oid = self.server.ObjectId()
        self.service_oid = self.server.ObjectId()
        self.client_oid = self.server.ObjectId()
        plan_oid = self.server.ObjectId()

        await self.database.platform_plans.insert_one({
            "_id": plan_oid, "name": "Premium", "active": True,
        })
        await self.database.shops.insert_one({
            "_id": self.shop_oid, "name": "Transaction Test Shop", "public_slug": "transaction-test-shop",
            "status": "active", "platform_plan_id": plan_oid,
        })
        await self.database.barbers.insert_one({
            "_id": self.barber_oid, "shop_id": self.shop_id, "name": "Test Barber", "active": True,
            "working_hours": {"mon": {"start": "09:00", "end": "12:00"}},
        })
        await self.database.services.insert_one({
            "_id": self.service_oid, "shop_id": self.shop_id, "name": "Test Service",
            "duration": 30, "price": 30, "active": True,
        })
        await self.database.users.insert_one({
            "_id": self.client_oid, "shop_id": self.shop_id, "role": "client", "name": "Test Client",
            "phone": "11911112222", "email": "client@example.invalid",
        })
        self.admin = {"_id": self.server.ObjectId(), "shop_id": self.shop_id, "role": "admin"}

    async def asyncTearDown(self):
        self.mongo.close()

    def _admin_booking(self, time="09:00"):
        return self.server.AppointmentIn(
            barber_id=str(self.barber_oid), service_id=str(self.service_oid),
            date="2026-10-12", time=time, client_id=str(self.client_oid),
        )

    async def _create_admin_booking(self, time="09:00"):
        return await self.server.create_appointment(self._admin_booking(time), self.admin)

    def _public_booking(self, time="09:00", phone="11912345678"):
        return self.server.PublicAppointmentIn(
            barber_id=str(self.barber_oid), service_id=str(self.service_oid),
            date="2026-10-12", time=time, client_name="Public Client", client_phone=phone,
        )

    async def _create_public_booking(self, time="09:00", phone="11912345678"):
        return await self.server.public_create_appointment(
            "transaction-test-shop", self._public_booking(time, phone)
        )

    async def _race(self, *booking_calls):
        with patch.object(self.server.email_service, "safe_send_confirmation", new=AsyncMock(return_value=True)):
            results = await asyncio.gather(*booking_calls, return_exceptions=True)
        successes = [result for result in results if not isinstance(result, Exception)]
        conflicts = [result for result in results if isinstance(result, self.server.HTTPException)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].status_code, 409)
        self.assertEqual(await self.database.appointments.count_documents({"shop_id": self.shop_id}), 1)

    async def test_two_administrative_requests_only_create_one_booking(self):
        await self._race(
            self._create_admin_booking(),
            self._create_admin_booking(),
        )

    async def test_administrative_and_public_requests_share_the_lock(self):
        await self._race(
            self._create_admin_booking(),
            self._create_public_booking(),
        )

    async def test_lock_and_conflict_queries_are_isolated_by_shop(self):
        other_shop_oid = self.server.ObjectId()
        other_shop_id = str(other_shop_oid)
        other_barber_oid = self.server.ObjectId()
        other_service_oid = self.server.ObjectId()
        other_client_oid = self.server.ObjectId()
        await self.database.barbers.insert_one({
            "_id": other_barber_oid, "shop_id": other_shop_id, "name": "Other Barber", "active": True,
            "working_hours": {"mon": {"start": "09:00", "end": "12:00"}},
        })
        await self.database.services.insert_one({
            "_id": other_service_oid, "shop_id": other_shop_id, "name": "Other Service",
            "duration": 30, "price": 30, "active": True,
        })
        await self.database.users.insert_one({
            "_id": other_client_oid, "shop_id": other_shop_id, "role": "client", "name": "Other Client",
        })
        await self.database.shops.insert_one({
            "_id": other_shop_oid,
            "name": "Other Test Shop", "public_slug": "other-transaction-test-shop", "status": "active",
            "platform_plan_id": (await self.database.platform_plans.find_one({"name": "Premium"}))[
                "_id"
            ],
        })
        with patch.object(self.server.email_service, "safe_send_confirmation", new=AsyncMock(return_value=True)):
            await self._create_admin_booking()
        other_admin = {"_id": self.server.ObjectId(), "shop_id": other_shop_id, "role": "admin"}
        other_booking = self.server.AppointmentIn(
            barber_id=str(other_barber_oid), service_id=str(other_service_oid),
            date="2026-10-12", time="09:00", client_id=str(other_client_oid),
        )
        result = await self.server.create_appointment(other_booking, other_admin)
        self.assertEqual(result["shop_id"], other_shop_id)
        self.assertEqual(await self.database.appointments.count_documents({"shop_id": self.shop_id}), 1)
        self.assertEqual(await self.database.appointments.count_documents({"shop_id": other_shop_id}), 1)

    async def test_failed_transaction_rolls_back_walkin_client_insert(self):
        phone = "11987654321"

        async def fail_after_client_insert(session):
            await self.database.users.insert_one({
                "shop_id": self.shop_id, "role": "client", "phone_normalized": phone,
                "test_marker": True,
            }, session=session)
            raise RuntimeError("intentional test transaction abort")

        with self.assertRaisesRegex(RuntimeError, "intentional test transaction abort"):
            await self.server._create_booking_atomically(
                self.shop_id, str(self.barber_oid), "2026-10-12", "09:00", 30, fail_after_client_insert
            )
        self.assertEqual(
            await self.database.users.count_documents({"shop_id": self.shop_id, "test_marker": True}), 0
        )

    def _require_failpoints(self):
        if os.environ.get("BARBERSTUDIO_TEST_MONGO_FAILPOINTS") != "1":
            self.skipTest("Set BARBERSTUDIO_TEST_MONGO_FAILPOINTS=1 on a disposable failpoint-enabled replica set")

    async def _run_with_failpoint(self, failpoint_data):
        self._require_failpoints()
        await self.database.booking_locks.update_one(
            {"_id": f"{self.shop_id}:{self.barber_oid}"},
            {"$setOnInsert": {"revision": 0}}, upsert=True,
        )
        await self.mongo.admin.command(
            "configureFailPoint", "failCommand", mode={"times": 1}, data=failpoint_data
        )
        try:
            with patch.object(self.server.email_service, "safe_send_confirmation", new=AsyncMock(return_value=True)):
                await self._create_admin_booking()
        finally:
            await self.mongo.admin.command("configureFailPoint", "failCommand", mode="off")
        self.assertEqual(await self.database.appointments.count_documents({"shop_id": self.shop_id}), 1)

    async def test_transient_transaction_error_retries_transaction(self):
        await self._run_with_failpoint({
            "failCommands": ["insert"], "errorCode": 112,
            "errorLabels": ["TransientTransactionError"],
        })

    async def test_unknown_commit_result_retries_commit_without_duplicate_booking(self):
        await self._run_with_failpoint({
            "failCommands": ["commitTransaction"], "errorCode": 91,
            "errorLabels": ["UnknownTransactionCommitResult"],
        })