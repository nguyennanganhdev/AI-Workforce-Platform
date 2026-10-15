"""Canonical invoices and explicitly synthetic payment recording for local demo."""

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from .v3_auth import scoped_connection
from .v3_mutations import visible_ticket, record_event
from .v3_water import _responsible_management
from .v3_security import digest

router = APIRouter(tags=["V3 accountant data APIs"])
Scope = Annotated[tuple[AsyncConnection, str, bool], Depends(scoped_connection)]
TENANT = "nullif(current_setting('app.tenant_id',true),'')::uuid"


class InvoiceLine(BaseModel):
    category_id: UUID
    description: str = Field(min_length=1, max_length=2000)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    discount: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=2
    )
    tax_rate: Decimal = Field(
        default=Decimal("0"), ge=0, le=1, max_digits=5, decimal_places=4
    )


class InvoiceCreate(BaseModel):
    issued_by_staff_id: UUID
    bill_to_user_id: str = Field(min_length=1, max_length=160)
    work_order_id: UUID | None = None
    lines: list[InvoiceLine] = Field(min_length=1, max_length=30)
    idempotency_key: str = Field(min_length=1, max_length=160)


async def invoice_access(scope: Scope, invoice_id: UUID, lock=False):
    row = (
        (
            await scope[0].execute(
                text("select * from invoices where id=:id"), {"id": invoice_id}
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Invoice not found")
    ticket = await visible_ticket(scope, row["ticket_id"], lock=lock)
    await _responsible_management(scope, ticket)
    if lock:
        row = (
            (
                await scope[0].execute(
                    text("select * from invoices where id=:id for update"),
                    {"id": invoice_id},
                )
            )
            .mappings()
            .one()
        )
    return dict(row), ticket


@router.post("/tickets/{ticket_id}/invoices", status_code=201)
async def create_invoice(ticket_id: UUID, body: InvoiceCreate, scope: Scope):
    ticket = await visible_ticket(scope, ticket_id, lock=True)
    await _responsible_management(scope, ticket)
    tenant = (
        await scope[0].execute(text("select current_setting('app.tenant_id')"))
    ).scalar_one()
    iid = uuid5(
        NAMESPACE_URL, f"invoice:{tenant}:{ticket_id}:{scope[1]}:{body.idempotency_key}"
    )
    fp = digest(body.model_dump(exclude={"idempotency_key"}))
    old = (
        await scope[0].execute(
            text("select id from invoices where id=:id"), {"id": iid}
        )
    ).scalar_one_or_none()
    if old:
        stored = (
            await scope[0].execute(
                text(
                    "select payload->>'requestHash' from ticket_events where ticket_id=:ticket and event_type='invoice.created' and payload->>'invoiceId'=:invoice order by seq limit 1"
                ),
                {"ticket": ticket_id, "invoice": str(iid)},
            )
        ).scalar_one_or_none()
        if stored != fp:
            raise HTTPException(409, "Invoice key already used")
        return await invoice_detail(iid, scope)
    if body.work_order_id:
        same = await scope[0].execute(
            text("select 1 from work_orders where id=:id and ticket_id=:ticket"),
            {"id": body.work_order_id, "ticket": ticket_id},
        )
        if same.first() is None:
            raise HTTPException(422, "Work order must belong to ticket")
    issuer = await scope[0].execute(
        text(
            "select 1 from staff_profiles sp join users u on u.id=sp.user_id where sp.id=:id and sp.management_unit_id=:management and sp.active and u.status='active'"
        ),
        {"id": body.issued_by_staff_id, "management": ticket["management_unit_id"]},
    )
    if issuer.first() is None:
        raise HTTPException(
            422, "Active issuer in responsible management unit required"
        )
    # Payer responsibility is an explicit input from management, never inferred by a model.
    payer = await scope[0].execute(
        text(
            "select 1 from tenant_memberships m join users u on u.id=m.user_id where m.user_id=:id and m.status='active' and u.status='active'"
        ),
        {"id": body.bill_to_user_id},
    )
    if payer.first() is None:
        raise HTTPException(422, "Active payer in tenant required")
    requester = (
        await scope[0].execute(
            text("select requester_user_id from tickets where id=:id"),
            {"id": ticket_id},
        )
    ).scalar_one()
    if body.bill_to_user_id != requester:
        responsible = await scope[0].execute(
            text("""select 1 from scoped_user_roles r join tenant_memberships m on m.id=r.membership_id and m.tenant_id=r.tenant_id join access_scopes s on s.id=r.scope_id and s.tenant_id=r.tenant_id
          where m.user_id=:payer and m.status='active' and r.role_code='management' and r.valid_from<=now() and (r.valid_to is null or r.valid_to>now())
          and (s.kind='tenant' or (s.kind='management' and s.management_unit_id=:management))"""),
            {"payer": body.bill_to_user_id, "management": ticket["management_unit_id"]},
        )
        if responsible.first() is None:
            raise HTTPException(
                422, "Payer must be the requester or responsible management account"
            )
    lines = []
    subtotal = Decimal(0)
    tax_total = Decimal(0)
    for line in body.lines:
        category = await scope[0].execute(
            text("select 1 from service_categories where id=:id and enabled"),
            {"id": line.category_id},
        )
        if category.first() is None:
            raise HTTPException(422, "Unavailable invoice category")
        gross = (line.quantity * line.unit_price).quantize(
            Decimal(".01"), rounding=ROUND_HALF_UP
        )
        if line.discount > gross:
            raise HTTPException(422, "Discount exceeds line amount")
        net = gross - line.discount
        tax = (net * line.tax_rate).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        subtotal += net
        tax_total += tax
        lines.append((line, net, tax))
    await scope[0].execute(
        text(f"""insert into invoices(id,tenant_id,ticket_id,work_order_id,invoice_no,issued_by_staff_id,bill_to_user_id,status,currency,subtotal,tax_total,discount_total,grand_total)
        values(:id,{TENANT},:ticket,:work,:number,:staff,:payer,'draft','VND',:subtotal,:tax,0,:total)"""),
        {
            "id": iid,
            "ticket": ticket_id,
            "work": body.work_order_id,
            "number": "DEMO-" + iid.hex[:20].upper(),
            "staff": body.issued_by_staff_id,
            "payer": body.bill_to_user_id,
            "subtotal": subtotal,
            "tax": tax_total,
            "total": subtotal + tax_total,
        },
    )
    for n, (line, net, tax) in enumerate(lines, 1):
        await scope[0].execute(
            text(
                f"insert into invoice_lines(tenant_id,invoice_id,line_no,category_id,description,quantity,unit_price,discount,tax_rate,net_amount,tax_amount,total_amount) values({TENANT},:invoice,:n,:category,:description,:quantity,:price,:discount,:rate,:net,:tax,:total)"
            ),
            {
                "invoice": iid,
                "n": n,
                "category": line.category_id,
                "description": line.description,
                "quantity": line.quantity,
                "price": line.unit_price,
                "discount": line.discount,
                "rate": line.tax_rate,
                "net": net,
                "tax": tax,
                "total": net + tax,
            },
        )
    await record_event(
        scope,
        ticket,
        "invoice.created",
        json.dumps({"invoiceId": str(iid), "requestHash": fp}),
    )
    return await invoice_detail(iid, scope)


@router.get("/invoices/{invoice_id}")
async def invoice_detail(invoice_id: UUID, scope: Scope):
    invoice, _ = await invoice_access(scope, invoice_id)
    lines = await scope[0].execute(
        text("select * from invoice_lines where invoice_id=:id order by line_no"),
        {"id": invoice_id},
    )
    paid = (
        await scope[0].execute(
            text(
                "select coalesce(sum(pa.amount),0) from payment_allocations pa join payments p on p.id=pa.payment_id and p.tenant_id=pa.tenant_id where pa.invoice_id=:id and p.reconciliation_status='confirmed'"
            ),
            {"id": invoice_id},
        )
    ).scalar_one()
    return {
        "invoice": invoice,
        "lines": [dict(r) for r in lines.mappings()],
        "collectedAmount": paid,
        "outstandingAmount": max(invoice["grand_total"] - paid, 0),
    }


@router.get("/tickets/{ticket_id}/financial-summary")
async def financial_summary(ticket_id: UUID, scope: Scope):
    ticket = await visible_ticket(scope, ticket_id)
    await _responsible_management(scope, ticket)
    estimates = await scope[0].execute(
        text(
            "select id,title,estimated_amount,status from vh_ticket_plans where ticket_id=:id order by created_at desc"
        ),
        {"id": ticket_id},
    )
    invoices = await scope[0].execute(
        text(
            "select id,invoice_no,status,grand_total,currency,bill_to_user_id from invoices where ticket_id=:id order by created_at desc"
        ),
        {"id": ticket_id},
    )
    return {
        "ticketId": ticket_id,
        "estimates": [dict(r) for r in estimates.mappings()],
        "invoices": [dict(r) for r in invoices.mappings()],
    }


@router.post("/invoices/{invoice_id}/issue")
async def issue(invoice_id: UUID, scope: Scope):
    invoice, ticket = await invoice_access(scope, invoice_id, True)
    if invoice["status"] == "issued":
        return await invoice_detail(invoice_id, scope)
    if invoice["status"] != "draft":
        raise HTTPException(409, "Draft invoice required")
    await scope[0].execute(
        text(
            "update invoices set status='issued',issued_at=now(),updated_at=now() where id=:id"
        ),
        {"id": invoice_id},
    )
    await record_event(
        scope, ticket, "invoice.issued", json.dumps({"invoiceId": str(invoice_id)})
    )
    return await invoice_detail(invoice_id, scope)


class DemoPayment(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("/invoices/{invoice_id}/demo-payments", status_code=201)
async def demo_payment(
    invoice_id: UUID, body: DemoPayment, request: Request, scope: Scope
):
    if not request.app.state.settings.demo_mode:
        raise HTTPException(409, "Synthetic payments are available only in local demo")
    invoice, ticket = await invoice_access(scope, invoice_id, True)
    tenant = (
        await scope[0].execute(text("select current_setting('app.tenant_id')"))
    ).scalar_one()
    pid = uuid5(
        NAMESPACE_URL,
        f"payment:{tenant}:{invoice_id}:{scope[1]}:{body.idempotency_key}",
    )
    old = (
        (
            await scope[0].execute(
                text("select id,amount from payments where id=:id"), {"id": pid}
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["amount"] != body.amount:
            raise HTTPException(409, "Payment key already used")
        return {
            "paymentId": pid,
            "mode": "synthetic-database",
            "invoice": await invoice_detail(invoice_id, scope),
        }
    if invoice["status"] != "issued":
        raise HTTPException(409, "Issued invoice required")
    summary = await invoice_detail(invoice_id, scope)
    if body.amount > summary["outstandingAmount"]:
        raise HTTPException(409, "Payment exceeds outstanding amount")
    intent = uuid5(NAMESPACE_URL, f"demo-intent:{pid}")
    await scope[0].execute(
        text(
            f"insert into payment_intents(id,tenant_id,invoice_id,provider,merchant_account_ref,idempotency_key,amount,currency,status,expires_at,paid_at) values(:id,{TENANT},:invoice,'demo','local-demo',:key,:amount,'VND','succeeded',now()+interval '1 hour',now())"
        ),
        {"id": intent, "invoice": invoice_id, "key": str(pid), "amount": body.amount},
    )
    await scope[0].execute(
        text(
            f"insert into payments(id,tenant_id,invoice_id,intent_id,provider,merchant_account_ref,provider_transaction_id,amount,currency,settled_at,reconciliation_status) values(:id,{TENANT},:invoice,:intent,'demo','local-demo',:transaction,:amount,'VND',now(),'confirmed')"
        ),
        {
            "id": pid,
            "invoice": invoice_id,
            "intent": intent,
            "transaction": str(pid),
            "amount": body.amount,
        },
    )
    await scope[0].execute(
        text(
            f"insert into payment_allocations(tenant_id,payment_id,invoice_id,amount,allocated_at,idempotency_key) values({TENANT},:payment,:invoice,:amount,now(),:key)"
        ),
        {"payment": pid, "invoice": invoice_id, "amount": body.amount, "key": str(pid)},
    )
    await record_event(
        scope,
        ticket,
        "payment.demo_recorded",
        json.dumps({"paymentId": str(pid), "amount": str(body.amount)}),
    )
    return {
        "paymentId": pid,
        "mode": "synthetic-database",
        "invoice": await invoice_detail(invoice_id, scope),
    }
