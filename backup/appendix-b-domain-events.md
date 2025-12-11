# Appendix B: Domain Events

You've built a clean architecture. The domain enforces business rules. Use cases orchestrate workflows. Ports decouple infrastructure. Tests give you confidence to change.

Then a new requirement arrives: when someone cancels a booking, automatically promote the next waitlisted member.

Simple enough. You open `CancelBookingUseCase` and add the logic:

```python
class CancelBookingUseCase:
    def execute(self, booking_id: str) -> None:
        # Cancel the booking
        booking = self.booking_repository.get_by_id(booking_id)
        booking.cancel(class_start_time)
        
        # Refund the credit
        member = self.member_repository.get_by_id(booking.member_id)
        member.add_credits(1, expiry_days=30)
        
        # Remove from class
        fitness_class = self.class_repository.get_by_id(booking.class_id)
        fitness_class.remove_booking(booking.member_id)
        
        # NEW: Check for waitlisted members
        waitlist_entries = self.waitlist_repository.get_by_class(booking.class_id)
        if waitlist_entries:
            next_member_id = waitlist_entries[0].member_id
            next_member = self.member_repository.get_by_id(next_member_id)
            
            # Book them into the class
            next_member.deduct_credit()
            fitness_class.add_booking(next_member_id)
            new_booking = Booking(generate_id(), next_member_id, booking.class_id)
            
            # Clean up waitlist
            self.waitlist_repository.remove(waitlist_entries[0])
            
            # Notify everyone
            self.notification_service.send_confirmation(next_member, fitness_class)
            self.notification_service.send_off_waitlist(next_member, fitness_class)
        
        # Save everything
        self.booking_repository.save(booking)
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.notification_service.send_cancellation(member, fitness_class)
```

It works. But now `CancelBookingUseCase` knows about waitlists, member credits, bookings, and notifications. It orchestrates two different workflows—cancellation and promotion—in one method. It violates the Single Responsibility Principle. It's hard to test. When waitlist rules change, you have to modify cancellation code.

You could extract a `ProcessWaitlistUseCase` and call it from here:

```python
class CancelBookingUseCase:
    def execute(self, booking_id: str) -> None:
        # Cancel the booking...
        
        # Then process waitlist
        self.process_waitlist_use_case.execute(booking.class_id)
```

But now use cases call other use cases. That's coupling. `CancelBookingUseCase` depends on `ProcessWaitlistUseCase`. If waitlist processing fails, should the cancellation fail? How do you handle transactions across use cases? The dependencies tangle.

**This is the problem domain events solve.**

Cancelling a booking and promoting from a waitlist are related but separate workflows. They shouldn't be tangled together. But they need to coordinate—a cancellation triggers waitlist promotion.

Domain events let you make that coordination explicit: "when a booking is cancelled, something might need to react." The cancellation doesn't need to know what. The waitlist processing doesn't need to know what triggered it. They're decoupled, but they work together.

This appendix shows you how.

## What Is a Domain Event?

A domain event is a record of something that happened in the domain.

Not "something is happening" or "something will happen." Something **already happened**. It's an immutable fact about the past.

Events are named in past tense:
- `BookingCancelled` — a booking was cancelled
- `MemberJoinedWaitlist` — a member joined a waitlist
- `ClassSpotBecameAvailable` — a spot opened up in a class
- `MemberPromotedFromWaitlist` — a member was promoted

Each event captures just enough data for interested parties to react:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class BookingCancelled:
    """A booking was cancelled."""
    booking_id: str
    member_id: str
    class_id: str
    cancelled_at: datetime
    reason: Optional[str] = None
```

Notice what's **not** in this event:
- The entire `Booking` object (too much data)
- The member's email or credits (not relevant)
- What should happen next (that's for handlers to decide)

The event just states the fact: "this booking was cancelled at this time." Anyone interested in cancelled bookings can listen and react.

**Domain events are different from:**

**Infrastructure events** (message queue events, Kafka topics): Those are mechanisms for distributed systems. Domain events are concepts from your business domain. You might publish domain events to infrastructure, but they're not the same thing.

**Application events** (UI state changes, notifications): Those are technical concerns. "The save button was clicked." "The screen should refresh." Domain events represent business facts. "A booking was created." "Payment was received."

**Database triggers or webhooks**: Those are implementation details. Domain events are part of your model—they express domain concepts, regardless of how you implement them.

Domain events make implicit domain behavior explicit. Instead of hiding the fact that cancellation triggers waitlist promotion inside one big method, you make it visible: "when `BookingCancelled` happens, `WaitlistPromotionHandler` reacts." The domain behavior is documented in code.

## Implementing Domain Events: The Foundation

Let's build a simple, foundational implementation. No frameworks. No external dependencies. Just enough structure to make domain events work within our clean architecture.

**Step 1: Define a base domain event**

Every domain event shares common characteristics: when it happened, maybe a correlation ID for tracking. We'll capture that in a base class:

```python
# domain/events.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """
    Base class for all domain events.
    
    Domain events are immutable facts about things that happened in the domain.
    They're named in past tense and contain just enough data for interested
    parties to react.
    """
    event_id: str
    occurred_at: datetime
    
    def __post_init__(self):
        """Ensure event_id and occurred_at are always set."""
        if not self.event_id:
            object.__setattr__(self, 'event_id', str(uuid4()))
        if not self.occurred_at:
            object.__setattr__(self, 'occurred_at', datetime.now())
```

We use `@dataclass(frozen=True)` to make events immutable. Once created, they can't be modified. Events are facts about the past—you can't change the past.

**Step 2: Create concrete events**

Now we define specific events for our gym booking domain:

```python
# domain/events.py (continued)

@dataclass(frozen=True)
class BookingCancelled(DomainEvent):
    """A booking was cancelled."""
    booking_id: str
    member_id: str
    class_id: str
    reason: Optional[str] = None
    
    event_id: str = ""
    occurred_at: Optional[datetime] = None


@dataclass(frozen=True)
class ClassSpotBecameAvailable(DomainEvent):
    """A spot became available in a class (e.g., due to cancellation)."""
    class_id: str
    previous_booking_id: Optional[str] = None
    
    event_id: str = ""
    occurred_at: Optional[datetime] = None


@dataclass(frozen=True)
class MemberPromotedFromWaitlist(DomainEvent):
    """A member was promoted from waitlist to confirmed booking."""
    member_id: str
    class_id: str
    booking_id: str
    waitlist_entry_id: str
    
    event_id: str = ""
    occurred_at: Optional[datetime] = None
```

Each event contains exactly what happened. `BookingCancelled` doesn't know or care what happens next. It just records the fact: this booking was cancelled.

## Entities Collecting Events

Entities are where domain behavior lives. When something significant happens in the domain, the entity records it as an event.

Let's modify our `Booking` entity to collect events when it's cancelled:

```python
# domain/entities.py
from datetime import datetime
from typing import List, Optional
from enum import Enum

from domain.events import BookingCancelled, DomainEvent


class BookingStatus(Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Booking:
    """
    A booking represents a member's reservation for a fitness class.
    """
    
    def __init__(self, booking_id: str, member_id: str, class_id: str):
        self._id = booking_id
        self._member_id = member_id
        self._class_id = class_id
        self._status = BookingStatus.CONFIRMED
        self._created_at = datetime.now()
        self._cancelled_at: Optional[datetime] = None
        
        # Events that have occurred on this entity
        self._domain_events: List[DomainEvent] = []
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def member_id(self) -> str:
        return self._member_id
    
    @property
    def class_id(self) -> str:
        return self._class_id
    
    @property
    def status(self) -> BookingStatus:
        return self._status
    
    def cancel(self, class_start_time: datetime, reason: Optional[str] = None) -> None:
        """
        Cancel this booking.
        
        Business rule: Cannot cancel within 2 hours of class start.
        
        Raises:
            BookingNotCancellableException: If cancellation not allowed
        """
        if self._status == BookingStatus.CANCELLED:
            raise ValueError("Booking is already cancelled")
        
        # Enforce the 2-hour cancellation window
        now = datetime.now()
        hours_until_class = (class_start_time - now).total_seconds() / 3600
        
        if hours_until_class < 2:
            from domain.exceptions import BookingNotCancellableException
            raise BookingNotCancellableException(
                f"Cannot cancel booking within 2 hours of class start. "
                f"Class starts in {hours_until_class:.1f} hours."
            )
        
        # Update state
        self._status = BookingStatus.CANCELLED
        self._cancelled_at = now
        
        # Record what happened as a domain event
        self._domain_events.append(BookingCancelled(
            booking_id=self._id,
            member_id=self._member_id,
            class_id=self._class_id,
            reason=reason
        ))
    
    def get_domain_events(self) -> List[DomainEvent]:
        """Return all domain events that occurred on this entity."""
        return list(self._domain_events)  # Return a copy
    
    def clear_domain_events(self) -> None:
        """Clear all domain events. Called after events are dispatched."""
        self._domain_events.clear()
```

**What changed:**
1. Added `_domain_events` list to collect events
2. When `cancel()` is called, it appends a `BookingCancelled` event
3. Added methods to retrieve and clear events

The entity still enforces business rules (2-hour cancellation window). But now it also records what happened. The event contains the facts: which booking, which member, which class, when it was cancelled.

Similarly, we can add events to `FitnessClass`:

```python
# domain/entities.py (continued)
from domain.events import ClassSpotBecameAvailable


class FitnessClass:
    """
    A fitness class with capacity limits and bookings.
    """
    
    def __init__(self, class_id: str, name: str, capacity: int):
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._bookings: List[str] = []  # List of member IDs
        self._domain_events: List[DomainEvent] = []
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    def is_full(self) -> bool:
        return len(self._bookings) >= self._capacity
    
    def add_booking(self, member_id: str) -> None:
        """Add a member to this class."""
        if self.is_full():
            raise ValueError("Class is at capacity")
        if member_id in self._bookings:
            raise ValueError("Member already booked in this class")
        self._bookings.append(member_id)
    
    def remove_booking(self, member_id: str, cancelled_booking_id: Optional[str] = None) -> None:
        """
        Remove a member from this class.
        
        This typically happens when a booking is cancelled.
        """
        if member_id not in self._bookings:
            raise ValueError(f"Member {member_id} is not booked in this class")
        
        self._bookings.remove(member_id)
        
        # Record that a spot became available
        self._domain_events.append(ClassSpotBecameAvailable(
            class_id=self._id,
            previous_booking_id=cancelled_booking_id
        ))
    
    def get_domain_events(self) -> List[DomainEvent]:
        """Return all domain events that occurred on this entity."""
        return list(self._domain_events)
    
    def clear_domain_events(self) -> None:
        """Clear all domain events. Called after events are dispatched."""
        self._domain_events.clear()
```

Now when a booking is removed from a class, the class records that a spot became available. Other parts of the system can react to that fact.

## Use Cases Collecting and Dispatching Events

Entities collect events. Use cases collect events from entities and dispatch them. This keeps the domain pure—entities don't need to know about event dispatching, repositories, or infrastructure. They just record facts.

Here's how `CancelBookingUseCase` changes:

```python
# application/use_cases.py
from datetime import datetime
from typing import Protocol

from domain.entities import Booking, Member, FitnessClass
from domain.events import DomainEvent


class EventDispatcher(Protocol):
    """Interface for dispatching domain events."""
    def dispatch(self, events: list[DomainEvent]) -> None:
        """Dispatch a list of domain events to registered handlers."""
        ...


class CancelBookingUseCase:
    """
    Cancel a booking and refund the member's credit.
    
    When a booking is cancelled, this use case:
    1. Enforces cancellation rules (via domain)
    2. Refunds the member's credit
    3. Removes the member from the class
    4. Dispatches domain events for interested parties to react
    """
    
    def __init__(
        self,
        booking_repository,
        member_repository,
        class_repository,
        notification_service,
        event_dispatcher: EventDispatcher
    ):
        self.booking_repository = booking_repository
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.notification_service = notification_service
        self.event_dispatcher = event_dispatcher
    
    def execute(self, booking_id: str, reason: str = None) -> None:
        """
        Cancel a booking.
        
        Raises:
            ValueError: If booking or class not found
            BookingNotCancellableException: If booking cannot be cancelled
        """
        # Load the booking
        booking = self.booking_repository.get_by_id(booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        
        # Load the class to check the schedule
        fitness_class = self.class_repository.get_by_id(booking.class_id)
        if not fitness_class:
            raise ValueError(f"Class {booking.class_id} not found")
        
        # Calculate class start time (simplified)
        class_start_time = self._get_next_class_occurrence(fitness_class)
        
        # Let the domain enforce cancellation rules and record the event
        booking.cancel(class_start_time, reason)
        
        # Refund the credit
        member = self.member_repository.get_by_id(booking.member_id)
        if member:
            member.add_credits(1, expiry_days=30)
            self.member_repository.save(member)
        
        # Remove member from the class
        fitness_class.remove_booking(booking.member_id, booking.id)
        
        # Persist changes
        self.booking_repository.save(booking)
        self.class_repository.save(fitness_class)
        
        # Collect all domain events
        events = []
        events.extend(booking.get_domain_events())
        events.extend(fitness_class.get_domain_events())
        
        # Clear events from entities (they're now being handled)
        booking.clear_domain_events()
        fitness_class.clear_domain_events()
        
        # Dispatch events to handlers
        self.event_dispatcher.dispatch(events)
        
        # Send cancellation notification
        if member:
            self.notification_service.send_cancellation_confirmation(
                member.email.value,
                member.name,
                fitness_class.name
            )
    
    def _get_next_class_occurrence(self, fitness_class) -> datetime:
        """Calculate next occurrence of this class (simplified)."""
        # In a real system, this would use the class schedule
        from datetime import timedelta
        return datetime.now() + timedelta(days=1)
```

**What changed:**

1. **Added `EventDispatcher` dependency**: The use case doesn't know how events are dispatched—that's infrastructure. It just depends on the interface.

2. **Collect events after domain operations**: After the booking is cancelled and removed from the class, we collect events from both entities.

3. **Clear events from entities**: Once collected, we clear them. Events belong to the use case execution, not to the entity's long-term state.

4. **Dispatch events**: Send all events to the dispatcher, which will route them to registered handlers.

The use case is now focused on its single responsibility: cancel a booking. It doesn't know about waitlists. It doesn't know what happens when a booking is cancelled. It just orchestrates the cancellation and announces what happened.

## Event Handlers: Reacting to Domain Events

Event handlers are application-layer services that react to domain events. They're like mini-use-cases, triggered by events instead of by users.

Here's a handler that promotes waitlisted members when a spot becomes available:

```python
# application/event_handlers.py
from typing import Protocol

from domain.events import ClassSpotBecameAvailable
from domain.entities import Booking


class WaitlistPromotionHandler:
    """
    Handles promotion of waitlisted members when spots become available.
    
    Listens for: ClassSpotBecameAvailable
    
    When a spot opens up (e.g., due to cancellation), this handler:
    1. Checks if anyone is waitlisted for that class
    2. Promotes the first premium member on the waitlist
    3. Creates a booking for them
    4. Notifies them
    """
    
    def __init__(
        self,
        waitlist_repository,
        member_repository,
        class_repository,
        booking_repository,
        notification_service
    ):
        self.waitlist_repository = waitlist_repository
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def handle(self, event: ClassSpotBecameAvailable) -> None:
        """
        Handle a class spot becoming available.
        
        Promotes the first waitlisted member if any are waiting.
        """
        # Check for waitlisted members
        waitlist_entries = self.waitlist_repository.get_by_class(
            event.class_id,
            order_by="created_at"
        )
        
        if not waitlist_entries:
            # No one is waiting, nothing to do
            return
        
        # Get the first waitlisted member
        next_entry = waitlist_entries[0]
        member = self.member_repository.get_by_id(next_entry.member_id)
        
        if not member:
            # Member no longer exists, remove entry and try next
            self.waitlist_repository.remove(next_entry)
            return
        
        # Check if member still has credits
        if member.credits < 1:
            # Member doesn't have credits, skip them
            # In a real system, you might notify them or remove them
            return
        
        # Load the class
        fitness_class = self.class_repository.get_by_id(event.class_id)
        if not fitness_class:
            return
        
        # Promote the member: deduct credit, add to class, create booking
        member.deduct_credit()
        fitness_class.add_booking(member.id)
        
        from uuid import uuid4
        booking = Booking(
            booking_id=str(uuid4()),
            member_id=member.id,
            class_id=event.class_id
        )
        
        # Persist changes
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # Remove from waitlist
        self.waitlist_repository.remove(next_entry)
        
        # Notify the member
        self.notification_service.send_waitlist_promotion(
            member.email.value,
            member.name,
            fitness_class.name
        )
```

**Key points:**

1. **Handlers are independent use cases**: `WaitlistPromotionHandler` has its own dependencies (repositories, services). It doesn't depend on `CancelBookingUseCase`.

2. **Handlers contain orchestration, not business rules**: The handler coordinates multiple aggregates (member, class, booking, waitlist), but domain rules (like credit deduction) live in entities.

3. **Handlers can fail gracefully**: If the member doesn't exist or doesn't have credits, the handler handles it. The original operation (cancellation) has already succeeded.

4. **Decoupled from triggers**: This handler doesn't know it was triggered by a cancellation. It just knows a spot became available. It could be triggered by increasing class capacity, or admin intervention, or anything else that makes a spot available.

## The Event Dispatcher

The event dispatcher connects events to handlers. It's infrastructure—a mechanism for routing events to interested parties.

Here's a simple, synchronous, in-process implementation:

```python
# infrastructure/event_dispatcher.py
from typing import Callable, Dict, List, Type

from domain.events import DomainEvent


class InMemoryEventDispatcher:
    """
    Simple in-process event dispatcher.
    
    Handlers are registered for specific event types. When an event is
    dispatched, all registered handlers for that event type are called
    synchronously.
    
    This is suitable for:
    - Single-process applications
    - Learning and testing
    - Synchronous event handling
    
    Not suitable for:
    - Distributed systems (use message queue)
    - Asynchronous processing (use task queue)
    - Event sourcing (use event store)
    """
    
    def __init__(self):
        # Map from event type to list of handler functions
        self._handlers: Dict[Type[DomainEvent], List[Callable]] = {}
    
    def register(self, event_type: Type[DomainEvent], handler: Callable) -> None:
        """
        Register a handler for a specific event type.
        
        Example:
            dispatcher.register(BookingCancelled, waitlist_handler.handle)
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def dispatch(self, events: List[DomainEvent]) -> None:
        """
        Dispatch a list of events to all registered handlers.
        
        Events are processed in order. Each event is sent to all handlers
        registered for its type.
        
        If a handler raises an exception, it's propagated and event
        processing stops. This ensures handlers are executed within
        the same transaction as the use case.
        """
        for event in events:
            event_type = type(event)
            
            if event_type not in self._handlers:
                # No handlers registered for this event type
                continue
            
            for handler in self._handlers[event_type]:
                # Call each registered handler
                handler(event)
```

This dispatcher is deliberately simple:
- **Synchronous**: Handlers run immediately, in the same transaction
- **In-process**: No network calls, no message queues
- **Fail-fast**: If a handler fails, the whole operation fails

**Usage in application setup:**

```python
# application/bootstrap.py
from infrastructure.event_dispatcher import InMemoryEventDispatcher
from application.event_handlers import WaitlistPromotionHandler
from domain.events import ClassSpotBecameAvailable


def setup_event_handlers(
    dispatcher: InMemoryEventDispatcher,
    waitlist_repository,
    member_repository,
    class_repository,
    booking_repository,
    notification_service
):
    """
    Register all event handlers with the dispatcher.
    
    This is where you wire up which handlers react to which events.
    """
    # Create handlers
    waitlist_handler = WaitlistPromotionHandler(
        waitlist_repository=waitlist_repository,
        member_repository=member_repository,
        class_repository=class_repository,
        booking_repository=booking_repository,
        notification_service=notification_service
    )
    
    # Register handlers for events
    dispatcher.register(ClassSpotBecameAvailable, waitlist_handler.handle)
    
    # Could register multiple handlers for the same event
    # dispatcher.register(ClassSpotBecameAvailable, analytics_handler.handle)
    # dispatcher.register(ClassSpotBecameAvailable, audit_log_handler.handle)
```

Now when `CancelBookingUseCase` dispatches a `ClassSpotBecameAvailable` event, the dispatcher routes it to `WaitlistPromotionHandler`. The two are connected by configuration, not by code.

## Before and After: Seeing the Difference

Let's compare the two approaches side by side.

**Before: Coupled use cases**

```python
class CancelBookingUseCase:
    def execute(self, booking_id: str) -> None:
        # Cancel booking
        booking = self.booking_repository.get_by_id(booking_id)
        booking.cancel(class_start_time)
        
        # Refund credit
        member = self.member_repository.get_by_id(booking.member_id)
        member.add_credits(1, expiry_days=30)
        
        # Remove from class
        fitness_class = self.class_repository.get_by_id(booking.class_id)
        fitness_class.remove_booking(booking.member_id)
        
        # Save everything
        self.booking_repository.save(booking)
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        
        # NOW ALSO handle waitlist promotion
        waitlist_entries = self.waitlist_repository.get_by_class(booking.class_id)
        if waitlist_entries:
            next_member = self.member_repository.get_by_id(waitlist_entries[0].member_id)
            next_member.deduct_credit()
            fitness_class.add_booking(next_member.id)
            # ... more waitlist logic ...
        
        # Send notifications
        self.notification_service.send_cancellation(member, fitness_class)
```

**Problems:**
- Cancellation and waitlist promotion are tangled
- Violates Single Responsibility Principle
- Hard to test in isolation
- Changes to waitlist logic require editing cancellation code
- Can't reuse waitlist promotion for other scenarios (capacity increase, admin actions)

**After: Decoupled with events**

```python
# CancelBookingUseCase - focused on cancellation only
class CancelBookingUseCase:
    def execute(self, booking_id: str) -> None:
        # Cancel booking
        booking = self.booking_repository.get_by_id(booking_id)
        booking.cancel(class_start_time)  # Records BookingCancelled event
        
        # Refund credit
        member = self.member_repository.get_by_id(booking.member_id)
        member.add_credits(1, expiry_days=30)
        
        # Remove from class
        fitness_class = self.class_repository.get_by_id(booking.class_id)
        fitness_class.remove_booking(booking.member_id)  # Records ClassSpotBecameAvailable
        
        # Save everything
        self.booking_repository.save(booking)
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        
        # Collect and dispatch events
        events = booking.get_domain_events() + fitness_class.get_domain_events()
        self.event_dispatcher.dispatch(events)
        
        # Send notification
        self.notification_service.send_cancellation(member, fitness_class)


# WaitlistPromotionHandler - focused on promotion only
class WaitlistPromotionHandler:
    def handle(self, event: ClassSpotBecameAvailable) -> None:
        # Check for waitlisted members
        waitlist_entries = self.waitlist_repository.get_by_class(event.class_id)
        if not waitlist_entries:
            return
        
        # Promote first member
        next_entry = waitlist_entries[0]
        next_member = self.member_repository.get_by_id(next_entry.member_id)
        
        # Deduct credit and create booking
        next_member.deduct_credit()
        # ... complete promotion logic ...
```

**Benefits:**
- **Single Responsibility**: Each component does one thing
- **Decoupled**: Cancellation doesn't depend on waitlist code
- **Reusable**: Waitlist promotion works for any scenario that creates available spots
- **Testable**: Can test cancellation and promotion independently
- **Explicit**: The event makes the relationship visible and documented
- **Extensible**: Want to track cancellations for analytics? Add another handler.

## Testing with Domain Events

Domain events make testing easier. You can test that events are raised, test handlers in isolation, and test the dispatcher separately.

**Testing that events are raised:**

```python
# tests/unit/domain/test_booking_events.py
from datetime import datetime, timedelta
import pytest

from domain.entities import Booking
from domain.events import BookingCancelled


def test_cancel_booking_raises_event():
    """Cancelling a booking should raise a BookingCancelled event."""
    # Arrange
    booking = Booking(
        booking_id="B001",
        member_id="M001",
        class_id="C001"
    )
    class_start = datetime.now() + timedelta(hours=3)  # More than 2 hours away
    
    # Act
    booking.cancel(class_start, reason="Schedule conflict")
    
    # Assert
    events = booking.get_domain_events()
    assert len(events) == 1
    
    event = events[0]
    assert isinstance(event, BookingCancelled)
    assert event.booking_id == "B001"
    assert event.member_id == "M001"
    assert event.class_id == "C001"
    assert event.reason == "Schedule conflict"


def test_cancel_within_2_hours_does_not_raise_event():
    """If cancellation fails, no event should be raised."""
    booking = Booking(
        booking_id="B001",
        member_id="M001",
        class_id="C001"
    )
    class_start = datetime.now() + timedelta(hours=1)  # Less than 2 hours
    
    # Cancellation should fail
    from domain.exceptions import BookingNotCancellableException
    with pytest.raises(BookingNotCancellableException):
        booking.cancel(class_start)
    
    # No event should be raised
    events = booking.get_domain_events()
    assert len(events) == 0
```

**Testing handlers in isolation:**

```python
# tests/unit/application/test_waitlist_handler.py
from unittest.mock import Mock
import pytest

from domain.events import ClassSpotBecameAvailable
from application.event_handlers import WaitlistPromotionHandler


def test_promotes_waitlisted_member_when_spot_available():
    """Handler should promote the first waitlisted member."""
    # Arrange
    waitlist_entry = Mock(member_id="M001", class_id="C001")
    member = Mock(id="M001", credits=5)
    fitness_class = Mock(id="C001")
    
    waitlist_repo = Mock()
    waitlist_repo.get_by_class.return_value = [waitlist_entry]
    
    member_repo = Mock()
    member_repo.get_by_id.return_value = member
    
    class_repo = Mock()
    class_repo.get_by_id.return_value = fitness_class
    
    booking_repo = Mock()
    notification_service = Mock()
    
    handler = WaitlistPromotionHandler(
        waitlist_repository=waitlist_repo,
        member_repository=member_repo,
        class_repository=class_repo,
        booking_repository=booking_repo,
        notification_service=notification_service
    )
    
    event = ClassSpotBecameAvailable(class_id="C001")
    
    # Act
    handler.handle(event)
    
    # Assert
    member.deduct_credit.assert_called_once()
    fitness_class.add_booking.assert_called_once_with("M001")
    booking_repo.save.assert_called_once()
    waitlist_repo.remove.assert_called_once_with(waitlist_entry)
    notification_service.send_waitlist_promotion.assert_called_once()


def test_does_nothing_when_no_waitlist():
    """Handler should do nothing if no one is waitlisted."""
    # Arrange
    waitlist_repo = Mock()
    waitlist_repo.get_by_class.return_value = []  # Empty waitlist
    
    handler = WaitlistPromotionHandler(
        waitlist_repository=waitlist_repo,
        member_repository=Mock(),
        class_repository=Mock(),
        booking_repository=Mock(),
        notification_service=Mock()
    )
    
    event = ClassSpotBecameAvailable(class_id="C001")
    
    # Act
    handler.handle(event)
    
    # Assert
    waitlist_repo.get_by_class.assert_called_once_with("C001", order_by="created_at")
    # No other actions should be taken
```

**Testing the dispatcher:**

```python
# tests/unit/infrastructure/test_event_dispatcher.py
from unittest.mock import Mock

from infrastructure.event_dispatcher import InMemoryEventDispatcher
from domain.events import BookingCancelled


def test_dispatches_event_to_registered_handler():
    """Dispatcher should call handlers registered for event type."""
    # Arrange
    dispatcher = InMemoryEventDispatcher()
    handler = Mock()
    
    dispatcher.register(BookingCancelled, handler)
    
    event = BookingCancelled(
        booking_id="B001",
        member_id="M001",
        class_id="C001"
    )
    
    # Act
    dispatcher.dispatch([event])
    
    # Assert
    handler.assert_called_once_with(event)


def test_dispatches_to_multiple_handlers():
    """Multiple handlers can be registered for the same event."""
    dispatcher = InMemoryEventDispatcher()
    handler1 = Mock()
    handler2 = Mock()
    
    dispatcher.register(BookingCancelled, handler1)
    dispatcher.register(BookingCancelled, handler2)
    
    event = BookingCancelled(
        booking_id="B001",
        member_id="M001",
        class_id="C001"
    )
    
    dispatcher.dispatch([event])
    
    handler1.assert_called_once_with(event)
    handler2.assert_called_once_with(event)


def test_ignores_events_with_no_handlers():
    """Dispatcher should not fail if no handlers are registered."""
    dispatcher = InMemoryEventDispatcher()
    
    event = BookingCancelled(
        booking_id="B001",
        member_id="M001",
        class_id="C001"
    )
    
    # Should not raise an exception
    dispatcher.dispatch([event])
```

These tests are fast, focused, and don't require a database or external dependencies. You can test domain logic, handler logic, and dispatcher logic independently.

## Where Events Fit in Clean Architecture

Domain events touch multiple layers of clean architecture. Understanding where each piece lives helps maintain clean separation.

**Domain Layer:**
- **Domain events themselves** (`BookingCancelled`, `ClassSpotBecameAvailable`)
- **Event collection in entities** (`.get_domain_events()`, `.clear_domain_events()`)
- These are domain concepts—they represent business facts

**Application Layer:**
- **Event handlers** (`WaitlistPromotionHandler`)
- **Use cases collecting and dispatching events** (`CancelBookingUseCase`)
- Handlers are like use cases—they orchestrate domain objects

**Infrastructure Layer:**
- **Event dispatcher implementation** (`InMemoryEventDispatcher`)
- **Event persistence** (if you're storing events)
- **Message queue integration** (if you're publishing events externally)
- The mechanism for handling events is infrastructure

**Interface Layer:**
- Doesn't interact with events directly
- Calls use cases, which handle events internally

Here's the flow:

```
┌─────────────────────────────────────────────────────────────┐
│ Interface Layer                                             │
│  - Controller calls CancelBookingUseCase                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Application Layer                                           │
│  - CancelBookingUseCase orchestrates domain                 │
│  - Collects events from entities                            │
│  - Dispatches events via EventDispatcher interface          │
│                                                              │
│  - WaitlistPromotionHandler reacts to events                │
│  - Orchestrates domain objects                              │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────────────┐   ┌─────────────────────────┐
│ Domain Layer                │   │ Infrastructure Layer    │
│  - Booking entity           │   │  - InMemoryEventDispatcher
│  - Raises BookingCancelled  │   │  - Routes events to handlers
│  - Collects events          │   │                         │
│                             │   │                         │
│  - FitnessClass entity      │   └─────────────────────────┘
│  - Raises ClassSpotAvailable│
│  - Collects events          │
└─────────────────────────────┘
```

**Key points:**

1. **Domain events are domain concepts**: They live in the domain layer because they represent business facts. "A booking was cancelled" is a domain concept.

2. **Entities raise events, use cases dispatch them**: Entities record what happened. Use cases handle the coordination of getting those events to interested parties.

3. **Handlers are application-layer**: They orchestrate domain objects just like use cases. They're triggered by events instead of by user actions.

4. **Dispatcher is infrastructure**: The mechanism for routing events—in-memory, message queue, event store—is a technical detail.

5. **Interface layer is unaware**: Controllers call use cases. Use cases handle everything internally, including events.

This separation keeps concerns clean. The domain knows about domain concepts. The application orchestrates. Infrastructure provides mechanisms.

## When to Use Domain Events

Domain events solve specific problems. Use them when you encounter these scenarios:

**Cross-aggregate communication**: When one aggregate needs to trigger behavior in another, but they shouldn't be directly coupled.

Example: Cancelling a booking (Booking aggregate) triggers waitlist promotion (Waitlist aggregate). These are separate concerns that need coordination.

**Making implicit behavior explicit**: When your system has workflows that span multiple operations but aren't obvious from the code.

Example: Without events, the fact that "cancellation triggers waitlist promotion" is hidden in code. With events, it's explicit: "`BookingCancelled` event is handled by `WaitlistPromotionHandler`."

**Audit trails and history**: When you need a record of what happened in your system.

Example: Events are immutable facts. Storing `BookingCancelled` events gives you a complete audit trail of all cancellations, when they happened, and why.

**Eventual consistency**: When operations don't need to happen synchronously, but you want to ensure they eventually happen.

Example: Sending emails doesn't need to be synchronous with booking cancellation. An event handler can send the email asynchronously (though our simple implementation is synchronous).

**Decoupling features**: When you want to add new behavior without modifying existing code.

Example: Want to track cancellations for analytics? Add a new handler. Want to notify admins when classes are cancelled? Add a new handler. The original cancellation code doesn't change.

**Multiple reactions to the same action**: When multiple different things need to happen in response to the same domain change.

Example: When a booking is cancelled, you might need to: promote waitlist, send notification, update analytics, log for audit, adjust pricing based on demand. Each is a separate handler.

## When NOT to Use Domain Events

Domain events add complexity. Don't use them unless you have the problems they solve.

**Simple CRUD applications**: If you're just saving and retrieving data with no complex workflows, you don't need events.

Example: A simple contact form that saves to a database. No domain logic, no coordination, no events needed.

**Within a single aggregate**: If the behavior is all within one aggregate, just use methods.

Example: Calculating a booking's total cost based on member type and class type. This is all within the booking's logic—no need for events.

**Synchronous operations that must succeed together**: If two operations must both succeed or both fail as a single transaction, don't use events. Use direct method calls.

Example: Transferring money between accounts. Debit and credit must happen together, atomically. Don't use events—they could get partially processed.

**Premature optimization**: Don't add events "just in case" or because they seem sophisticated.

Example: You have a simple booking system with no cross-aggregate workflows. Don't add events because "maybe someday we'll need them." Start simple. Add events when you feel the pain of coupling.

**Small, focused use cases**: If a use case naturally handles one simple workflow, keep it simple.

Example: Creating a member. Load data, create entity, save. No coordination, no events needed.

**When you're still learning the domain**: Events make relationships explicit, but you need to understand the domain first to know what those relationships are.

Example: In early development, you're still figuring out what "booking a class" means. Keep things flexible. Once the domain stabilizes, introduce events where they help.

Domain events are a tool for managing complexity. If you don't have complexity, you don't need the tool. Start simple. When you notice use cases getting tangled, when changes ripple across unrelated code, when testing becomes hard—that's when events help.

## What We're NOT Covering

This appendix taught you the foundations of domain events: what they are, how to implement them within a monolithic application, and when to use them.

But domain events are a deep topic. There are advanced patterns and techniques we're deliberately not covering here:

**Event Sourcing**: Instead of storing current state in a database, store all events that happened and rebuild state by replaying them. This is a fundamental shift in how you persist data. It enables time travel, perfect audit trails, and new kinds of analysis—but it's complex and has significant tradeoffs.

**CQRS (Command Query Responsibility Segregation)**: Separate your read model from your write model. Events make this easier—writes produce events, reads are built from events—but CQRS is a significant architectural pattern that goes beyond events.

**Distributed events / Message queues**: Publishing events to external systems (Kafka, RabbitMQ, AWS SNS). This enables microservices communication and async processing, but introduces eventual consistency, failure handling, ordering concerns, and operational complexity.

**Saga patterns**: Coordinating distributed transactions across multiple services using events and compensating actions. Essential for microservices, but far more complex than in-process events.

**Event versioning**: As your system evolves, event schemas change. Handling different versions of the same event type is critical in production systems but adds significant complexity.

**Event storage and replay**: Persisting events to an event store, replaying events to rebuild state, projecting events into different read models. This is the foundation of event sourcing but requires specialized infrastructure.

**Advanced error handling**: What happens when an event handler fails? Retry policies, dead letter queues, compensating transactions. In our simple implementation, failure propagates. Production systems need more sophistication.

These are all powerful patterns. But they're advanced topics that build on the foundation you've learned here. Domain events within a monolith—collecting events from entities, dispatching them to handlers within the same transaction—is where you start.

Once you're comfortable with that foundation, you can explore these advanced patterns. But don't jump ahead. The simple in-process event system you've learned is enough for most applications. It gives you decoupling, explicit domain behavior, and testability without distributed systems complexity.

Get comfortable with the basics first. The advanced patterns will be there when you need them.

---

You now understand domain events. You know the problem they solve: cross-aggregate coordination without tight coupling. You know how to implement them: entities collect events, use cases dispatch them, handlers react. You know when to use them and when not to.

This pattern builds on everything you learned in the main book. Entities still enforce business rules. Use cases still orchestrate. Layers still separate concerns. Tests still give you confidence. Domain events just make coordination between aggregates explicit and decoupled.

Add them to your toolkit. Use them when you see tangled use cases that coordinate multiple aggregates. Skip them when your use cases are simple and focused.

Architecture is about making intentional decisions. Now you can decide whether domain events solve your specific problem.
