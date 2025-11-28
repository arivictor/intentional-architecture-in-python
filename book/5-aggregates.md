# Chapter 5: Aggregates

In Chapter 4, we built the foundation: entities with identity and behaviour, value objects that make invalid states impossible. We have `Member`, `FitnessClass`, `TimeSlot`, `EmailAddress`, and `ClassCapacity`. Each one knows its own rules and protects its own invariants.

But real business logic doesn't live in isolated objects. Members book classes. Classes have capacity limits that bookings must respect. Cancellations depend on time remaining before class starts. Multiple classes can't occupy the same room simultaneously.

These are rules that span multiple objects. They require coordination. They need consistency boundaries.

This chapter introduces aggregates and domain services—the patterns that let you model complex business logic while keeping your domain clean and focused. Aggregates define consistency boundaries. Domain services handle logic that doesn't naturally belong to any single entity. Together, they complete the picture of a rich domain model.

By the end of this chapter, you'll have a complete domain layer. One that enforces business rules, maintains consistency, and speaks the language of the business—without any dependency on databases, frameworks, or external services.

## Aggregates: Consistency Boundaries

Aggregates are clusters of entities and value objects treated as a single unit for data changes.

So far we have entities: `Member`, `FitnessClass`. We have value objects: `EmailAddress`, `TimeSlot`, `ClassCapacity`. But how do these relate? How do you ensure consistency when multiple objects need to change together?

This is where aggregates come in.

An aggregate is a boundary around one or more objects. One entity is the root—the entry point. All access to objects inside the aggregate goes through the root. The root enforces invariants for the entire aggregate.

In our gym system, a `Booking` is an aggregate. It's the combination of a member booking a specific class at a specific time. The booking has its own identity, its own lifecycle, and rules that span both member and class.

Here's the `Booking` aggregate:

```python
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class BookingStatus(Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    ATTENDED = "attended"
    NO_SHOW = "no_show"


class Booking:
    def __init__(self, booking_id: str, member_id: str, class_id: str, 
                 booked_at: Optional[datetime] = None):
        if not booking_id:
            raise ValueError("Booking ID is required")
        if not member_id:
            raise ValueError("Member ID is required")
        if not class_id:
            raise ValueError("Class ID is required")
        
        self._id = booking_id
        self._member_id = member_id
        self._class_id = class_id
        self._status = BookingStatus.CONFIRMED
        self._booked_at = booked_at or datetime.now()
        self._cancelled_at: Optional[datetime] = None
    
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
    
    @property
    def booked_at(self) -> datetime:
        return self._booked_at
    
    def is_cancellable(self, class_start_time: datetime) -> bool:
        if self._status != BookingStatus.CONFIRMED:
            return False
        
        # Cannot cancel less than 2 hours before class
        time_until_class = class_start_time - datetime.now()
        return time_until_class > timedelta(hours=2)
    
    def cancel(self, class_start_time: datetime):
        if not self.is_cancellable(class_start_time):
            raise BookingNotCancellableException(
                "Cannot cancel booking less than 2 hours before class"
            )
        
        self._status = BookingStatus.CANCELLED
        self._cancelled_at = datetime.now()
    
    def mark_attended(self):
        if self._status != BookingStatus.CONFIRMED:
            raise ValueError("Can only mark confirmed bookings as attended")
        
        self._status = BookingStatus.ATTENDED
    
    def mark_no_show(self):
        if self._status != BookingStatus.CONFIRMED:
            raise ValueError("Can only mark confirmed bookings as no-show")
        
        self._status = BookingStatus.NO_SHOW


class BookingNotCancellableException(Exception):
    pass
```

The `Booking` aggregate encapsulates the booking lifecycle. It knows the cancellation rules. It tracks status transitions. It enforces that you can't cancel a booking that's already cancelled, or mark a cancelled booking as attended.

The aggregate is the consistency boundary. When you modify a booking, all changes happen through the booking's own methods. You don't reach in and modify its internal state directly. The aggregate protects its invariants.

Notice that `Booking` references `Member` and `FitnessClass` by ID, not by direct object reference. This is intentional. Aggregates should be small. They should reference other aggregates by identity, not by holding them in memory. This keeps the boundaries clear and avoids loading entire object graphs when you only need a booking.

If you need both the booking and the member, you load them separately and coordinate them at the application layer. The domain enforces rules within each aggregate. The application coordinates across aggregates.

### Understanding the Booking Aggregate Boundary

Let's be explicit about what makes `Booking` an aggregate and how it differs from other entities in our system.

**Why `Booking` is an aggregate:**

The `Booking` represents a complete business transaction—a member's commitment to attend a class. It has its own lifecycle that's independent of both the `Member` and the `FitnessClass`:

```
┌─────────────────────────────────────────────┐
│ Booking Aggregate                           │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │ Booking (root)                        │ │
│  │ - booking_id                          │ │
│  │ - member_id (reference)               │ │
│  │ - class_id (reference)                │ │
│  │ - status                              │ │
│  │ - booked_at                           │ │
│  │ - cancelled_at                        │ │
│  │                                       │ │
│  │ Methods:                              │ │
│  │ - is_cancellable()                    │ │
│  │ - cancel()                            │ │
│  │ - mark_attended()                     │ │
│  │ - mark_no_show()                      │ │
│  └───────────────────────────────────────┘ │
│                                             │
│  References (by ID only):                  │
│  → Member aggregate                        │
│  → FitnessClass entity                     │
└─────────────────────────────────────────────┘
```

**Key characteristics:**

1. **Independent Identity**: A booking can exist even if the class is cancelled or the member leaves
2. **Own Lifecycle**: Bookings transition through states (CONFIRMED → CANCELLED/ATTENDED/NO_SHOW)
3. **Business Rules**: The 2-hour cancellation policy belongs to the booking, not to the member or class
4. **References by ID**: Storing only IDs prevents tight coupling and keeps the aggregate small

**Contrast with `FitnessClass._bookings`:**

You might notice that `FitnessClass` has a `_bookings` list that stores member IDs. This is a **denormalised cache for capacity checking**, not the authoritative source of booking data. Here's why:

- `FitnessClass._bookings` exists only to answer: "Is this class full?"
- The true booking state (status, timestamps, cancellation) lives in `Booking` aggregates
- When a booking is cancelled, the `Booking` aggregate changes status, and we remove the member ID from `FitnessClass._bookings`
- This is a pragmatic trade-off: we accept some data duplication to avoid loading all bookings just to check capacity

**Design Decision:**

We could have made `Booking` a child within a larger `FitnessClass` aggregate, but that would force us to load the entire class and all its bookings every time we want to cancel a single booking. By making `Booking` its own aggregate, we can:

- Cancel bookings without loading the class
- Query booking history for a member without loading classes
- Handle concurrent bookings more efficiently (different aggregates can be modified independently)

The application layer coordinates between these aggregates when necessary, but each aggregate maintains its own consistency.

### The Waitlist Entity

When a class is full, members need a way to queue up for available spots. This is where the waitlist comes in.

A `WaitlistEntry` is a simple entity that tracks a member's position in line for a specific class. It has identity (its own ID), references other aggregates by ID (member and class), and tracks when the entry was created:

```python
from datetime import datetime
from typing import Optional


class WaitlistEntry:
    def __init__(self, entry_id: str, member_id: str, class_id: str,
                 added_at: Optional[datetime] = None):
        if not entry_id:
            raise ValueError("Waitlist entry ID is required")
        if not member_id:
            raise ValueError("Member ID is required")
        if not class_id:
            raise ValueError("Class ID is required")
        
        self._id = entry_id
        self._member_id = member_id
        self._class_id = class_id
        self._added_at = added_at or datetime.now()
    
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
    def added_at(self) -> datetime:
        return self._added_at
```

Unlike `Booking`, which enforces complex cancellation rules and status transitions, `WaitlistEntry` is deliberately simple. It's a record of intent: "This member wants to join this class when space becomes available."

The business rules around waitlists—who gets priority, how long entries remain valid, whether members can be on multiple waitlists—live in the application layer or in domain services, not in this entity. The entity just represents the fact that someone is waiting.

Notice how it references `Member` and `FitnessClass` by ID, following the same pattern as `Booking`. This keeps aggregates independent. The waitlist processing logic will load and coordinate these objects as needed, but the entity itself stays focused on representing a single concept: a person waiting for a class.

## Domain Services: Logic That Doesn't Fit

Not all business logic belongs in entities or value objects. Sometimes logic involves multiple objects or concepts that don't naturally fit into any single class.

Consider class scheduling. You need to ensure two classes don't overlap in the same room. That's business logic. But does it belong in `FitnessClass`? Not really—it involves two classes and a room. Does it belong in `Room`? Maybe, but rooms aren't the primary concept here.

This is where domain services come in. They're stateless objects that implement business logic that doesn't naturally belong to any entity.

Here's `ClassSchedulingService`:

```python
from typing import List


class Room:
    def __init__(self, room_id: str, name: str, capacity: int):
        if not room_id:
            raise ValueError("Room ID is required")
        if not name:
            raise ValueError("Room name cannot be empty")
        if capacity < 1:
            raise ValueError("Room capacity must be at least 1")
        
        self._id = room_id
        self._name = name
        self._capacity = capacity
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def capacity(self) -> int:
        return self._capacity


class ClassSchedulingService:
    def can_schedule_class(self, fitness_class: FitnessClass, room: Room,
                          existing_classes: List[FitnessClass]) -> bool:
        # Check if room has enough capacity
        if fitness_class.capacity.value > room.capacity:
            return False
        
        # Check for time conflicts in the same room
        for existing_class in existing_classes:
            if fitness_class.conflicts_with(existing_class):
                return False
        
        return True
    
    def find_conflicts(self, fitness_class: FitnessClass, 
                      existing_classes: List[FitnessClass]) -> List[FitnessClass]:
        conflicts = []
        for existing_class in existing_classes:
            if fitness_class.conflicts_with(existing_class):
                conflicts.append(existing_class)
        return conflicts
```

The `ClassSchedulingService` contains logic that involves multiple domain objects. It doesn't belong to `FitnessClass` because it's not about a single class—it's about how classes relate to each other and to rooms.

Domain services are different from application services. Application services coordinate use cases ("book a class"). Domain services implement business logic that crosses entity boundaries ("can this class be scheduled in this room?").

Use domain services sparingly. Most logic should live in entities or value objects. But when logic genuinely doesn't fit, don't force it. Create a domain service.

## Business Rules vs Application Policies

There's a distinction worth making: business rules are truths about the domain. Application policies are decisions about how you use the domain.

"A class cannot exceed its capacity" is a business rule. It's invariant. It's true regardless of how you access the system—through an API, a CLI, or a batch job. This belongs in the domain.

"When a booking is confirmed, send an email notification" is an application policy. It's about how you respond to domain events, not about domain truth. This belongs in the application layer.

Keeping these separate matters. The domain should be pure business logic. If you removed all infrastructure—no database, no email server, no HTTP—the domain should still make sense. It should still enforce its rules. It should still represent the business accurately.

Application policies can change more freely. You might start with email notifications, then add SMS, then add push notifications. Those are application concerns. The domain doesn't care how you notify members. It just knows that a booking was made.

This is why our `Member` entity doesn't send emails when the email address changes. It doesn't log events when credits expire. It just manages member state and enforces member rules. The application layer can listen for changes and react accordingly. But the domain stays pure.

## From Anemic to Rich

Most codebases start with anemic domain models. Classes that are little more than property bags:

```python
class Booking:
    def __init__(self):
        self.id = None
        self.member_id = None
        self.class_id = None
        self.status = "confirmed"
        self.booked_at = None
        self.cancelled_at = None
```

All the logic lives elsewhere—in services, in controllers, in whatever layer needs it:

```python
class BookingService:
    def cancel_booking(self, booking, class_start_time):
        # Check cancellation policy
        time_until_class = class_start_time - datetime.now()
        if time_until_class <= timedelta(hours=2):
            raise ValueError("Cannot cancel less than 2 hours before class")
        
        # Check current status
        if booking.status != "confirmed":
            raise ValueError("Booking is not confirmed")
        
        # Update booking
        booking.status = "cancelled"
        booking.cancelled_at = datetime.now()
```

This works. It gets the job done. But it scatters business logic. The rules about cancellation don't live in `Booking`. They live in `BookingService`. If you have multiple services that cancel bookings, you duplicate this logic or extract it to yet another service.

Now compare to the rich version we built earlier:

```python
class Booking:
    def cancel(self, class_start_time: datetime):
        if not self.is_cancellable(class_start_time):
            raise BookingNotCancellableException(
                "Cannot cancel booking less than 2 hours before class"
            )
        
        self._status = BookingStatus.CANCELLED
        self._cancelled_at = datetime.now()
```

The logic lives where it belongs. In the domain object. The object knows its own rules. It enforces them. It doesn't trust external services to check invariants. It doesn't rely on someone else to maintain consistency.

This is the difference between anemic and rich. Anemic objects are passive data. Rich objects are active participants in business logic.

Does this mean anemic models are always wrong? No. If you're building a simple CRUD application, an anemic model might be perfectly fine. The complexity doesn't justify rich objects. But if you have complex business rules, behaviour that changes based on state, invariants that must be maintained—that's when richness pays off.

The richer your domain, the more your code reflects reality. The more your tests read like business requirements. The less logic gets lost in service layers.

## Domain Exceptions

When business rules are violated, throw domain exceptions. Not generic `ValueError` or `Exception`. Specific exceptions that communicate what went wrong in business terms.

We've already created several:

```python
class ClassFullException(Exception):
    pass


class InsufficientCreditsException(Exception):
    pass


class BookingNotCancellableException(Exception):
    pass
```

These exceptions are part of your domain language. They express business scenarios. When you catch `ClassFullException`, you know exactly what happened. The class reached capacity. You can respond appropriately—maybe add the member to a waiting list, or suggest a different time.

Contrast this with catching a generic `ValueError("Class is full")`. You have to parse the message. Different parts of the code might throw `ValueError` for different reasons. The exception type doesn't communicate business meaning.

Domain exceptions also make your application layer clearer:

```python
# In application layer
try:
    booking_service.book_class(member, fitness_class)
except ClassFullException:
    # Handle the specific case: class is full
    notification_service.notify_class_full(member, fitness_class)
except InsufficientCreditsException:
    # Handle the specific case: member needs more credits
    notification_service.notify_insufficient_credits(member)
```

Each exception represents a distinct business scenario. Your application layer can respond differently to each one. The code becomes a clear expression of business processes.

Keep domain exceptions in the domain layer. They're part of the business logic, not infrastructure concerns.

## Putting It All Together

Let's see how all these pieces work together. Here's a complete flow: a member wants to book a class.

The domain has everything it needs to enforce the rules:

```python
from datetime import datetime, time, timedelta


# Create value objects
email = EmailAddress("sarah@example.com")
premium_membership = MembershipType("Premium", credits_per_month=20, price=50)
capacity = ClassCapacity(15)
time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))

# Create entities
member = Member("M001", "Sarah", email, premium_membership)
yoga_class = FitnessClass("C001", "Yoga", capacity, time_slot)

# Create a booking
booking = Booking("B001", member.id, yoga_class.id)

# Business logic flows through domain objects
try:
    # Check if member has credits
    if member.credits <= 0:
        raise InsufficientCreditsException("No credits available")
    
    # Check if class is available
    if yoga_class.is_full():
        raise ClassFullException("Class is at capacity")
    
    # Both checks pass - proceed with booking
    yoga_class.add_booking(member.id)
    member.deduct_credit()
    
    print(f"Booking confirmed: {booking.id}")
    print(f"Member credits remaining: {member.credits}")
    print(f"Class bookings: {yoga_class.booking_count()}/{yoga_class.capacity.value}")

except ClassFullException as e:
    print(f"Cannot book: {e}")
except InsufficientCreditsException as e:
    print(f"Cannot book: {e}")
```

Everything is checked. Everything is validated. The domain enforces its own rules. No external service needs to remember to check capacity or credits—the domain objects handle it themselves.

If the member wants to cancel:

```python
# Simulate class starting time (3 hours from now for this example)
class_start = datetime.now() + timedelta(hours=3)

try:
    # Check if cancellable through the booking aggregate
    if booking.is_cancellable(class_start):
        booking.cancel(class_start)
        yoga_class.remove_booking(member.id)
        member.add_credits(1)  # Refund the credit
        
        print(f"Booking cancelled: {booking.id}")
        print(f"Status: {booking.status.value}")
    else:
        print("Booking cannot be cancelled (too close to class time)")

except BookingNotCancellableException as e:
    print(f"Cannot cancel: {e}")
```

The booking knows its cancellation rules. The class manages its bookings. The member's credits are updated. The domain coordinates itself.

This is a rich domain model. Business logic lives in domain objects. Rules are enforced by the types themselves. Impossible states are prevented by construction. The code reads like the business.

## Summary

We've completed the domain layer. Not just entities and value objects, but aggregates, domain services, and a complete picture of how business logic lives and breathes in your code.

Aggregates define consistency boundaries. `Booking` is an aggregate root that manages the booking lifecycle independently of `Member` and `FitnessClass`. It references other aggregates by ID, keeping boundaries clear and preventing tightly coupled object graphs. The aggregate enforces its invariants—you can't cancel a booking less than 2 hours before class time, and you can't mark a cancelled booking as attended.

Domain services handle logic that doesn't fit naturally into entities. `ClassSchedulingService` coordinates class scheduling across multiple objects and rooms. It's still domain logic, just not tied to a single entity. Use domain services sparingly, but don't force logic where it doesn't belong.

We distinguished business rules from application policies. "A class cannot exceed capacity" is a business rule—it lives in the domain. "Send an email when a booking is confirmed" is an application policy—it lives in the application layer. The domain stays pure, focused only on business truth.

Domain exceptions speak the language of the business. `ClassFullException`, `InsufficientCreditsException`, `BookingNotCancellableException`—these aren't technical errors, they're business scenarios. The application layer can respond to each one appropriately.

Most importantly, we've built a rich domain model. From the anemic data containers we started with, we've created objects that understand and enforce business rules. The domain isn't just a passive data holder. It's an active participant in business logic.

Your domain is pure. It has no database code. No HTTP. No external dependencies. Just business logic. You can test it with nothing but Python itself. You can understand it by reading the code. It speaks the language of the people who use it.

Together with Chapter 4, you now have a complete foundation:
- **Entities** with identity and lifecycle (Member, FitnessClass)
- **Value objects** that make invalid states impossible (TimeSlot, EmailAddress, ClassCapacity, MembershipType)
- **Aggregates** that define consistency boundaries (Booking)
- **Domain services** for cross-entity logic (ClassSchedulingService)
- **Domain exceptions** for business scenarios (ClassFullException, InsufficientCreditsException, BookingNotCancellableException)
- **Clear file organisation** that reflects domain structure

In the next chapter, we'll build the application layer on top of this domain. Use cases. Orchestration. How to combine these rich domain objects to fulfil actual business workflows. The domain provides the instruments. The application layer plays the music.

The foundation is solid. Now let's make it sing.
