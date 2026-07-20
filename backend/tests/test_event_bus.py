import asyncio
import pytest
from app.schemas.events import Event
from app.services.event_bus import EventBus

@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    received_events = []

    async def subscriber(event: Event):
        received_events.append(event)

    await bus.subscribe(subscriber, "TestEvent")
    
    event = Event(event_type="TestEvent", source="Test", payload={"key": "value"})
    await bus.publish(event)
    
    assert len(received_events) == 1
    assert received_events[0].event_type == "TestEvent"
    assert received_events[0].payload == {"key": "value"}

@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    count = 0

    async def sub1(event: Event):
        nonlocal count
        count += 1

    async def sub2(event: Event):
        nonlocal count
        count += 1

    await bus.subscribe(sub1, "TestEvent")
    await bus.subscribe(sub2, "TestEvent")
    
    await bus.publish(Event(event_type="TestEvent", source="Test"))
    
    assert count == 2

@pytest.mark.asyncio
async def test_global_subscriber():
    bus = EventBus()
    received = []

    async def global_sub(event: Event):
        received.append(event.event_type)

    await bus.subscribe(global_sub) # No event type = global
    
    await bus.publish(Event(event_type="EventA", source="Test"))
    await bus.publish(Event(event_type="EventB", source="Test"))
    
    assert "EventA" in received
    assert "EventB" in received
    assert len(received) == 2

@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    async def sub(event: Event):
        received.append(event)

    await bus.subscribe(sub, "TestEvent")
    await bus.publish(Event(event_type="TestEvent", source="Test"))
    assert len(received) == 1
    
    await bus.unsubscribe(sub, "TestEvent")
    await bus.publish(Event(event_type="TestEvent", source="Test"))
    assert len(received) == 1 # Still 1

@pytest.mark.asyncio
async def test_error_handling():
    bus = EventBus()
    
    async def failing_sub(event: Event):
        raise ValueError("Boom")

    async def working_sub(event: Event):
        working_sub.called = True
    
    working_sub.called = False

    await bus.subscribe(failing_sub, "TestEvent")
    await bus.subscribe(working_sub, "TestEvent")
    
    # Should not raise exception
    await bus.publish(Event(event_type="TestEvent", source="Test"))
    
    assert working_sub.called is True
