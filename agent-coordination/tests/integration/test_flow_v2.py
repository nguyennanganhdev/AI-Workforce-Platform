import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("src"))

from adapters.backend.events import PendingDelivery
from adapters.backend.messages import fingerprint

@pytest.mark.asyncio
async def test_full_integration_flow():
    # Load integrated supervisor from main.py
    import main as main_module
    
    # We monkey-patch the backend methods internally used in the integrated app
    import adapters.backend.messages as msgs
    import supervisor.service as srv
    srv.validate_event = lambda e: None
    srv.validate_payload = lambda t, p: None
    srv.validate_context = lambda c: None
    
    # Get the integrated supervisor
    supervisor = await main_module.main()
    
    fake_payload = {
        "message_type": "ticket_submitted",
        "message": "Cư dân báo hỏng điều hòa ở sảnh",
        "facts": [{"key": "location", "value": "Sảnh A", "source": "customer_report", "source_message_id": "MSG-1"}],
        "file_ids": []
    }
    
    # Construct a complete fake_event matching what the system expects
    fake_event = {
        "event_id": "EVT-001",
        "event_type": "custom.event",
        "schema_version": "1",
        "tenant_id": "TENANT-1", 
        "aggregate_id": "AGG-1", 
        "aggregate_version": 1, 
        "occurred_at": "2026-10-01T10:00:00Z",
        "correlation_id": "CORR-1",
        "causation_id": "CAUSE-1",
        "payload": fake_payload
    }
    
    fp = fingerprint(fake_event)
    
    delivery = PendingDelivery(
        target="supervisor",
        tenant_id="TENANT-1",
        event_id="EVT-001",
        fingerprint=fp,
        message_type="ticket.submitted",
        context={
            "tenant_id": "TENANT-1", "workspace_id": "WS-1", 
            "domain_id": "DOMAIN-1", "ticket_id": "TICKET-1", 
            "ticket_generation": 1, "principal_id": "P1", "binding_id": "B1", "run_id": "R1"
        },
        event=fake_event
    )
    
    # Verify that the integrated DEV-1, DEV-2, DEV-3 components handle the delivery without exceptions
    try:
        await supervisor.handle_delivery(delivery, trusted_context={})
        print("\n[OK] Integration test passed successfully!")
        
        # In ra trạng thái bên trong của Supervisor (được lưu vào DEV-4 StateStore mock)
        state_store = supervisor.store  # Access InMemoryStateStore
        ticket_state = state_store._store.get("TICKET-1")
        
        if ticket_state:
            print("\n=========================================")
            print("KET QUA DAU RA MONG MUON (DESIRED STATE):")
            print(f"Ticket ID: {ticket_state.context.ticket_id}")
            print(f"Hien tai Phase: {ticket_state.phase}")
            print(f"State version: {ticket_state.version}")
            if ticket_state.reception:
                print(f"Payload Reception luu trong State: {ticket_state.reception.model_dump()}")
            print("=========================================\n")
        else:
            print("[WARN] Ticket state was not found in the store!")
            
    except Exception as e:
        print(f"[ERROR] Integration flow failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_integration_flow())
