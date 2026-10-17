# -*- coding: utf-8 -*-
"""SQLite integration tests for registration, partner routing, and tickets."""

import os
import tempfile
from unittest import IsolatedAsyncioTestCase

from agentscope.app.auth import AuthService
from agentscope.app.business import (
    BusinessAuthorizationError,
    BusinessService,
)
from agentscope.app.storage import AsyncSQLAlchemyStorage


class AreaPlatformIntegrationTest(IsolatedAsyncioTestCase):
    """Exercise the non-pgvector workflow against a migrated database."""

    async def test_register_domain_key_and_area_ticket_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite+aiosqlite:///{os.path.join(tmp, 'platform.db')}"
            async with AsyncSQLAlchemyStorage(
                url,
                auto_migrate=True,
                create_tables=False,
            ):
                pass

            async with AuthService(
                database_url=url,
                jwt_secret="j" * 48,
                refresh_pepper="r" * 48,
            ) as auth:
                user = await auth.register(
                    tenant_id="default",
                    email="manager.op1@example.com",
                    username="manager_op1",
                    password="long-enough-password",
                    domain_id="vinhomes",
                    area_id="ocean-park-1",
                )
                self.assertEqual(user.role, "AREA_MANAGER")
                tokens = await auth.login(
                    tenant_id="default",
                    identity="manager_op1",
                    password="long-enough-password",
                )
                manager = auth.verify_access_token(tokens.access_token)
                await auth.register(
                    tenant_id="default",
                    email="manager.op2@example.com",
                    username="manager_op2",
                    password="another-long-password",
                    domain_id="vinhomes",
                    area_id="ocean-park-2",
                )
                tokens_op2 = await auth.login(
                    tenant_id="default",
                    identity="manager_op2",
                    password="another-long-password",
                )
                manager_op2 = auth.verify_access_token(tokens_op2.access_token)

            async with BusinessService(
                database_url=url,
                api_key_pepper="p" * 48,
                provisioning_secret="s" * 48,
            ) as business:
                issued = await business.issue_partner_api_key(
                    tenant_id="default",
                    domain_id="vinhomes",
                    name="Vinhomes Mobile",
                )
                partner = await business.authenticate_partner_api_key(
                    issued.api_key,
                )
                await business.upsert_partner_residence(
                    partner,
                    residence_id="S1-0205",
                    external_user_id="resident-1",
                    area_id="ocean-park-1",
                )
                await business.upsert_partner_residence(
                    partner,
                    residence_id="T3-1510",
                    external_user_id="resident-1",
                    area_id="ocean-park-2",
                )
                ticket = await business.create_ticket(
                    partner,
                    external_user_id="resident-1",
                    residence_id="S1-0205",
                    external_ticket_id="external-1",
                    title="Elevator issue",
                    description="Elevator S1 is unavailable",
                )
                duplicate = await business.create_ticket(
                    partner,
                    external_user_id="resident-1",
                    residence_id="S1-0205",
                    external_ticket_id="external-1",
                    title="Elevator issue",
                    description="Elevator S1 is unavailable",
                )
                self.assertEqual(duplicate["id"], ticket["id"])
                ticket_op2 = await business.create_ticket(
                    partner,
                    external_user_id="resident-1",
                    residence_id="T3-1510",
                    external_ticket_id="external-2",
                    title="Water issue",
                    description="No water in T3",
                )

                manager_tickets = await business.list_tickets_for_manager(
                    manager,
                )
                self.assertEqual(
                    [item["id"] for item in manager_tickets], [ticket["id"]]
                )
                manager_op2_tickets = await business.list_tickets_for_manager(
                    manager_op2,
                )
                self.assertEqual(
                    [item["id"] for item in manager_op2_tickets],
                    [ticket_op2["id"]],
                )

                updated = await business.update_ticket_status(
                    manager,
                    ticket_id=ticket["id"],
                    new_status="in_progress",
                    note="Technician assigned",
                )
                self.assertEqual(updated["status"], "in_progress")
                partner_view = await business.get_partner_ticket(
                    partner,
                    ticket["id"],
                )
                self.assertEqual(partner_view["status"], "in_progress")
                self.assertEqual(len(partner_view["events"]), 2)

                vinpearl_key = await business.issue_partner_api_key(
                    tenant_id="default",
                    domain_id="vinpearl",
                    name="Vinpearl Mobile",
                )
                vinpearl = await business.authenticate_partner_api_key(
                    vinpearl_key.api_key,
                )
                with self.assertRaises(BusinessAuthorizationError):
                    await business.upsert_partner_residence(
                        vinpearl,
                        residence_id="S1-0205",
                        external_user_id="guest-1",
                        area_id="ocean-park-1",
                    )
