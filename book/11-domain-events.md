# Chapter 11: Domain Events

## Introduction

**Domain Events** are things that happen in the domain that domain experts care about. They represent significant state changes or business occurrences: "Order was placed," "Payment was received," "Item was shipped."

Events enable loose coupling between different parts of your system. Instead of one component directly calling another, it publishes an event. Other components listen for events and react accordingly. This makes the system more flexible, testable, and easier to extend.

## The Problem

Direct coupling between components makes systems rigid and hard to change.

**Symptoms:**
- One action triggers cascade of tightly coupled operations
- Difficult to add new behaviors without modifying existing code
- Hard to test components in isolation
- Unclear what happens when an action completes
- Circular dependencies between modules
- God classes that "do everything"

**Example of the problem:**

```python
class EmailService:
    def send_email(self, to, subject, body):
        print(f"Sending email to {to}: {subject}")


class InventoryService:
    def __init__(self):
        self.stock = {'product-1': 10, 'product-2': 5}
    
    def reserve_items(self, items):
        for item_id, quantity in items.items():
            self.stock[item_id] -= quantity
            print(f"Reserved {quantity} of {item_id}")


class ShippingService:
    def create_shipment(self, order_id, address):
        print(f"Creating shipment for order {order_id} to {address}")


class OrderService:
    """Tightly coupled to all downstream services."""
    
    def __init__(self, email_service, inventory_service, shipping_service):
        self.email_service = email_service
        self.inventory_service = inventory_service
        self.shipping_service = shipping_service
    
    def place_order(self, order_id, customer_email, items, shipping_address):
        """
        Placing an order requires knowing about ALL downstream operations.
        """
        # Process order
        print(f"Order {order_id} placed")
        
        # Now must explicitly call each service
        self.inventory_service.reserve_items(items)
        self.shipping_service.create_shipment(order_id, shipping_address)
        self.email_service.send_email(
            to=customer_email,
            subject="Order Confirmation",
            body=f"Your order {order_id} has been placed"
        )
        
        # Later: add loyalty points - must modify this method!
        # Even later: send to analytics - modify again!
        # Even later: notify warehouse - modify again!


# Usage shows tight coupling
email = EmailService()
inventory = InventoryService()
shipping = ShippingService()
order_service = OrderService(email, inventory, shipping)

order_service.place_order(
    "ORD-123",
    "customer@example.com",
    {'product-1': 2},
    "123 Main St"
)
```

**Problems:**
- `OrderService` knows about email, inventory, shipping, etc.
- Adding new behavior (analytics, loyalty points) requires modifying `OrderService`
- Can't test order placement without all services
- Order of operations hardcoded
- Circular dependencies if shipping needs to notify inventory
- Violates Open/Closed Principle - not open to extension without modification

## The Pattern

**Domain Event:** A record of something that happened in the domain.

Instead of Component A directly calling Component B, A publishes an event and B listens for it.

### Key Concepts

**Event:** Immutable record of something that happened
- Named in past tense: `OrderPlaced`, `PaymentReceived`, `ItemShipped`
- Contains data about what happened
- Includes timestamp
- Immutable

**Event Publisher/Dispatcher:** Publishes events to interested listeners
**Event Handler/Listener:** Responds to events

### Flow

```
1. Order is placed → OrderService publishes OrderPlacedEvent
2. Event dispatcher notifies all registered handlers
3. InventoryService listens for OrderPlacedEvent → reserves items
4. EmailService listens for OrderPlacedEvent → sends confirmation
5. ShippingService listens for OrderPlacedEvent → creates shipment
6. (Future) AnalyticsService listens for OrderPlacedEvent → tracks metrics
```

Each handler is independent. Order service doesn't know they exist.

## Implementation

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Callable, Dict, Any
from abc import ABC


@dataclass(frozen=True)
class DomainEvent(ABC):
    """
    Base class for all domain events.
    
    Events are immutable records of things that happened.
    """
    occurred_at: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: f"evt-{datetime.now().timestamp()}")


@dataclass(frozen=True)
class OrderPlacedEvent(DomainEvent):
    """Event published when an order is placed."""
    order_id: str
    customer_email: str
    items: Dict[str, int]  # product_id -> quantity
    shipping_address: str
    total_amount: float


@dataclass(frozen=True)
class PaymentReceivedEvent(DomainEvent):
    """Event published when payment is received."""
    order_id: str
    amount: float
    payment_method: str


@dataclass(frozen=True)
class OrderShippedEvent(DomainEvent):
    """Event published when order ships."""
    order_id: str
    tracking_number: str
    carrier: str


class EventDispatcher:
    """
    Central event dispatcher.
    
    Handlers register for event types. When event is published,
    all registered handlers are notified.
    """
    
    def __init__(self):
        self._handlers: Dict[type, List[Callable]] = {}
    
    def register(self, event_type: type, handler: Callable[[DomainEvent], None]) -> None:
        """
        Register a handler for an event type.
        
        Args:
            event_type: The event class to listen for
            handler: Function to call when event occurs
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all registered handlers.
        
        Args:
            event: The event that occurred
        """
        event_type = type(event)
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    # In production: log error, continue with other handlers
                    print(f"Error in handler {handler.__name__}: {e}")


class OrderService:
    """
    Order service that publishes events.
    
    Doesn't know about downstream services - just publishes events.
    """
    
    def __init__(self, event_dispatcher: EventDispatcher):
        self.event_dispatcher = event_dispatcher
        self.orders = {}
    
    def place_order(
        self, 
        order_id: str, 
        customer_email: str, 
        items: Dict[str, int],
        shipping_address: str,
        total_amount: float
    ) -> None:
        """
        Place an order and publish event.
        
        This method only handles order placement logic.
        Everything else happens via event handlers.
        """
        # Process order
        self.orders[order_id] = {
            'customer_email': customer_email,
            'items': items,
            'address': shipping_address,
            'total': total_amount,
            'status': 'placed'
        }
        
        print(f"[OrderService] Order {order_id} placed")
        
        # Publish event - that's it!
        event = OrderPlacedEvent(
            order_id=order_id,
            customer_email=customer_email,
            items=items,
            shipping_address=shipping_address,
            total_amount=total_amount
        )
        self.event_dispatcher.publish(event)


class InventoryService:
    """
    Inventory service that listens for order events.
    
    No direct dependency on OrderService.
    """
    
    def __init__(self):
        self.stock = {'product-1': 100, 'product-2': 50}
    
    def handle_order_placed(self, event: OrderPlacedEvent) -> None:
        """React to order being placed."""
        print(f"[InventoryService] Reserving items for order {event.order_id}")
        for product_id, quantity in event.items.items():
            if product_id in self.stock:
                self.stock[product_id] -= quantity
                print(f"  Reserved {quantity} of {product_id}")


class EmailService:
    """Email service that listens for various events."""
    
    def handle_order_placed(self, event: OrderPlacedEvent) -> None:
        """Send confirmation email when order placed."""
        print(f"[EmailService] Sending confirmation to {event.customer_email}")
        print(f"  Order {event.order_id} - Total: ${event.total_amount:.2f}")
    
    def handle_order_shipped(self, event: OrderShippedEvent) -> None:
        """Send shipping notification."""
        print(f"[EmailService] Sending shipping notification for {event.order_id}")
        print(f"  Tracking: {event.tracking_number}")


class ShippingService:
    """Shipping service that listens for order events."""
    
    def handle_order_placed(self, event: OrderPlacedEvent) -> None:
        """Create shipment when order placed."""
        print(f"[ShippingService] Creating shipment for {event.order_id}")
        print(f"  Destination: {event.shipping_address}")


class AnalyticsService:
    """
    Analytics service - can be added without modifying existing code!
    
    This demonstrates the Open/Closed Principle via events.
    """
    
    def __init__(self):
        self.events_tracked = []
    
    def handle_order_placed(self, event: OrderPlacedEvent) -> None:
        """Track order for analytics."""
        print(f"[AnalyticsService] Tracking order {event.order_id}")
        self.events_tracked.append(event)
        print(f"  Total orders tracked: {len(self.events_tracked)}")


# Usage example
if __name__ == "__main__":
    # Create event dispatcher
    dispatcher = EventDispatcher()
    
    # Create services
    order_service = OrderService(dispatcher)
    inventory_service = InventoryService()
    email_service = EmailService()
    shipping_service = ShippingService()
    analytics_service = AnalyticsService()
    
    # Register event handlers
    dispatcher.register(OrderPlacedEvent, inventory_service.handle_order_placed)
    dispatcher.register(OrderPlacedEvent, email_service.handle_order_placed)
    dispatcher.register(OrderPlacedEvent, shipping_service.handle_order_placed)
    dispatcher.register(OrderPlacedEvent, analytics_service.handle_order_placed)
    
    print("=== Placing Order ===\n")
    
    # Place order - triggers all handlers automatically
    order_service.place_order(
        order_id="ORD-123",
        customer_email="customer@example.com",
        items={'product-1': 2, 'product-2': 1},
        shipping_address="123 Main St, Springfield",
        total_amount=99.99
    )
    
    print("\n=== Adding New Feature (No Code Changes to OrderService!) ===\n")
    
    # We can add new functionality without modifying OrderService
    class LoyaltyPointsService:
        def __init__(self):
            self.points = {}
        
        def handle_order_placed(self, event: OrderPlacedEvent) -> None:
            print(f"[LoyaltyPointsService] Awarding points for {event.order_id}")
            points = int(event.total_amount)  # 1 point per dollar
            email = event.customer_email
            self.points[email] = self.points.get(email, 0) + points
            print(f"  Customer {email} now has {self.points[email]} points")
    
    loyalty_service = LoyaltyPointsService()
    dispatcher.register(OrderPlacedEvent, loyalty_service.handle_order_placed)
    
    # Place another order - now includes loyalty points automatically!
    order_service.place_order(
        order_id="ORD-124",
        customer_email="customer@example.com",
        items={'product-1': 1},
        shipping_address="123 Main St, Springfield",
        total_amount=49.99
    )
```

## Explanation

### Events Are Immutable

Domain events are immutable records using `@dataclass(frozen=True)`:

```python
@dataclass(frozen=True)
class OrderPlacedEvent(DomainEvent):
    order_id: str
    customer_email: str
    items: Dict[str, int]
    # Cannot be modified after creation
```

### Loose Coupling

`OrderService` doesn't know about inventory, email, or shipping:

```python
def place_order(self, ...):
    # Process order
    self.orders[order_id] = {...}
    
    # Just publish event
    event = OrderPlacedEvent(...)
    self.event_dispatcher.publish(event)
    # Done! Doesn't know what happens next
```

### Multiple Handlers

Many services can handle the same event:

```python
dispatcher.register(OrderPlacedEvent, inventory_service.handle_order_placed)
dispatcher.register(OrderPlacedEvent, email_service.handle_order_placed)
dispatcher.register(OrderPlacedEvent, shipping_service.handle_order_placed)
```

### Easy Extension

Adding new features doesn't require modifying existing code:

```python
# Add loyalty points - no changes to OrderService!
loyalty = LoyaltyPointsService()
dispatcher.register(OrderPlacedEvent, loyalty.handle_order_placed)
```

### Error Isolation

If one handler fails, others still execute:

```python
def publish(self, event):
    for handler in self._handlers[event_type]:
        try:
            handler(event)
        except Exception:
            # Log and continue - don't break other handlers
            pass
```

## Benefits

**1. Loose Coupling**

Components don't depend on each other directly. They only depend on the event contract:

```python
# OrderService doesn't know about EmailService
# EmailService doesn't know about OrderService
# They communicate via events
```

**2. Open/Closed Principle**

Add new behavior without modifying existing code:

```python
# Add analytics - no changes to OrderService
analytics = AnalyticsService()
dispatcher.register(OrderPlacedEvent, analytics.handle_order_placed)
```

**3. Easier Testing**

Test components in isolation by using a test event dispatcher:

```python
def test_order_service():
    fake_dispatcher = FakeEventDispatcher()
    order_service = OrderService(fake_dispatcher)
    
    order_service.place_order(...)
    
    assert fake_dispatcher.published_events[0].order_id == "ORD-123"
```

**4. Clear Audit Trail**

Events provide a log of everything that happened:

```python
event_log = []
dispatcher.register(DomainEvent, lambda e: event_log.append(e))
# Now have complete history of all domain events
```

**5. Temporal Decoupling**

Publishers and handlers don't need to run at the same time. Events can be queued and processed later.

## Trade-offs

**When NOT to use domain events:**

**1. Simple Workflows**

For simple, linear workflows, events add complexity:

```python
# Overkill for simple workflow
def create_user(name, email):
    user = User(name, email)
    save_user(user)
    send_welcome_email(user)  # Just call directly
```

**2. Performance-Critical Paths**

Events add overhead (dispatching, handler execution). For performance-critical code, direct calls might be better.

**3. Strong Consistency Required**

Events typically provide eventual consistency. If you need strong consistency within a transaction, events complicate things:

```python
# Events make atomicity harder
# Easier to just call directly in a transaction
with transaction:
    place_order(...)
    reserve_inventory(...)
    # Both succeed or both fail
```

**4. Complexity**

Events add:
- Event dispatcher infrastructure
- More indirection (harder to trace flow)
- Need to manage handler registration
- Debugging complexity

**5. Ordering Dependencies**

If handlers must run in specific order, events might not be the right choice. Direct calls give you explicit control.

## Testing

```python
import pytest
from typing import List


class FakeEventDispatcher(EventDispatcher):
    """Test double for event dispatcher."""
    
    def __init__(self):
        super().__init__()
        self.published_events: List[DomainEvent] = []
    
    def publish(self, event: DomainEvent) -> None:
        self.published_events.append(event)
        super().publish(event)


def test_order_service_publishes_event():
    """Test that placing order publishes OrderPlacedEvent."""
    dispatcher = FakeEventDispatcher()
    order_service = OrderService(dispatcher)
    
    order_service.place_order(
        "ORD-123",
        "test@example.com",
        {'prod-1': 2},
        "123 Main St",
        99.99
    )
    
    assert len(dispatcher.published_events) == 1
    event = dispatcher.published_events[0]
    assert isinstance(event, OrderPlacedEvent)
    assert event.order_id == "ORD-123"


def test_multiple_handlers_receive_event():
    """Test that multiple handlers receive the same event."""
    dispatcher = EventDispatcher()
    
    handler1_calls = []
    handler2_calls = []
    
    def handler1(event):
        handler1_calls.append(event)
    
    def handler2(event):
        handler2_calls.append(event)
    
    dispatcher.register(OrderPlacedEvent, handler1)
    dispatcher.register(OrderPlacedEvent, handler2)
    
    event = OrderPlacedEvent("ORD-123", "test@example.com", {}, "Address", 99.99)
    dispatcher.publish(event)
    
    assert len(handler1_calls) == 1
    assert len(handler2_calls) == 1
    assert handler1_calls[0] == event
    assert handler2_calls[0] == event


def test_handler_error_doesnt_stop_other_handlers():
    """Test that one handler failing doesn't prevent others from running."""
    dispatcher = EventDispatcher()
    
    successful_calls = []
    
    def failing_handler(event):
        raise Exception("Handler error")
    
    def successful_handler(event):
        successful_calls.append(event)
    
    dispatcher.register(OrderPlacedEvent, failing_handler)
    dispatcher.register(OrderPlacedEvent, successful_handler)
    
    event = OrderPlacedEvent("ORD-123", "test@example.com", {}, "Address", 99.99)
    dispatcher.publish(event)
    
    # Successful handler still ran despite failing handler
    assert len(successful_calls) == 1


def test_inventory_service_handles_order_placed():
    """Test that inventory service reserves items when order placed."""
    inventory = InventoryService()
    initial_stock = inventory.stock['product-1']
    
    event = OrderPlacedEvent(
        "ORD-123",
        "test@example.com",
        {'product-1': 3},
        "Address",
        99.99
    )
    
    inventory.handle_order_placed(event)
    
    assert inventory.stock['product-1'] == initial_stock - 3


def test_event_is_immutable():
    """Test that events cannot be modified."""
    event = OrderPlacedEvent("ORD-123", "test@example.com", {}, "Address", 99.99)
    
    with pytest.raises(AttributeError):
        event.order_id = "ORD-456"


def test_can_add_new_handlers_without_modifying_existing_code():
    """Test open/closed principle - extend without modifying."""
    dispatcher = EventDispatcher()
    order_service = OrderService(dispatcher)
    
    # Original handlers
    inventory = InventoryService()
    dispatcher.register(OrderPlacedEvent, inventory.handle_order_placed)
    
    # Add new handler without modifying OrderService
    new_handler_calls = []
    def new_handler(event):
        new_handler_calls.append(event)
    
    dispatcher.register(OrderPlacedEvent, new_handler)
    
    # Place order
    order_service.place_order("ORD-123", "test@example.com", {'product-1': 1}, "Address", 50.0)
    
    # New handler was called
    assert len(new_handler_calls) == 1
```

## Common Mistakes

**1. Events That Are Too Technical**

Events should represent domain concepts, not technical details:

```python
# Bad - technical implementation detail
class DatabaseRecordInsertedEvent:
    table: str
    record_id: int

# Good - domain concept
class OrderPlacedEvent:
    order_id: str
    customer_email: str
```

**2. Synchronous Events Used for Asynchronous Operations**

Don't use synchronous event handlers for long-running operations:

```python
# Bad - blocks until email sent
def handle_order_placed(event):
    send_email(...)  # Synchronous, slow operation

# Good - queue for async processing
def handle_order_placed(event):
    email_queue.enqueue(event)  # Returns immediately
```

**3. Events With Too Much Data**

Events should contain just enough data for handlers to do their work:

```python
# Bad - entire customer object
class OrderPlacedEvent:
    customer: Customer  # Too much data
    order: Order

# Good - just identifiers and relevant data
class OrderPlacedEvent:
    order_id: str
    customer_id: str
    items: Dict[str, int]
```

**4. Mutable Events**

Events must be immutable:

```python
# Bad - mutable
class OrderPlacedEvent:
    def __init__(self, order_id):
        self.order_id = order_id  # Can be changed

# Good - immutable
@dataclass(frozen=True)
class OrderPlacedEvent:
    order_id: str
```

## Related Patterns

- **Chapter 5 (Open/Closed):** Events enable extending behavior without modification
- **Chapter 8 (Dependency Inversion):** Event handlers depend on event abstractions
- **Chapter 10 (Aggregates):** Aggregates publish events when state changes
- **Chapter 17 (CQRS):** Commands trigger events; events update read models
- **Chapter 18 (Event Sourcing):** Store events as the source of truth

## Summary

Domain events represent significant things that happen in your domain. Components publish events when important state changes occur, and other components listen and react. This creates loose coupling, makes systems easier to extend, and clearly expresses domain concepts.

Use domain events when you have multiple components that need to react to the same occurrence, when you want to extend behavior without modifying existing code, or when you need an audit trail. Avoid events for simple workflows, performance-critical paths, or when strong consistency within a transaction is required.

## Further Reading

- Fowler, Martin. "Domain Event." martinfowler.com, 2005.
- Evans, Eric. *Domain-Driven Design*. Addison-Wesley, 2003.
- Vernon, Vaughn. *Implementing Domain-Driven Design*. Addison-Wesley, 2013. (Chapter 8: Domain Events)
- Young, Greg. "CQRS and Event Sourcing." Video presentation, 2014.
- Richardson, Chris. *Microservices Patterns*. Manning, 2018. (Event-driven architecture)
