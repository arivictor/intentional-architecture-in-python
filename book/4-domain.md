# Chapter 4: Domain

We have layers. Domain logic lives in the domain layer, separated from infrastructure and interface. The structure is solid. But the domain itself is still shallow.

**Terminology note:** This chapter uses three related but distinct terms:
- **Domain** = the business problem we're solving (gym booking, scheduling, memberships)
- **Domain layer** = the architectural layer containing domain code (`domain/` directory)
- **Domain model** = the entities, value objects, and services that represent the domain

The domain (business) is modeled by the domain model (code), which lives in the domain layer (architecture).

New requirements arrive that expose this shallowness:

**Complex booking rules:** Members can't cancel bookings within 2 hours of class time. Premium members get priority when classes are full. Members can only book one class per time slot.

**Credit system complexity:** Member credits expire after 30 days. Premium members get 10 credits per month, basic members get 5. Credits are deducted on booking and refunded on cancellation (with rules).

**Time slot conflicts:** Classes run at specific days and times. A member can't book two classes that overlap. The system needs to detect conflicts.

**Data validation:** Email addresses must be valid. Class capacity must be between 1 and 50. Member names can't be empty. These rules need to be enforced everywhere.

Where does this logic go? Right now, our domain classes are simple data holders:

```python
# domain/member.py
class Member:
    def __init__(self, member_id: str, name: str, email: str, pricing_strategy):
        self.id = member_id
        self.name = name
        self.email = email
        self.pricing_strategy = pricing_strategy
        self.credits = 10  # Where do we enforce expiry? Valid range?
    
    def get_class_price(self) -> float:
        return self.pricing_strategy.calculate_price()
```

This class can't enforce the credit rules. It doesn't understand expiry. It doesn't validate that email addresses are valid. It's a data container with no behavior—an anemic domain model.

We could add validation to the application layer:

```python
# application/booking_service.py
class BookingService:
    def book_class(self, member_id: str, class_id: str):
        member = self.member_repo.get(member_id)
        fitness_class = self.class_repo.get(class_id)
        
        # Validation scattered in the application layer
        if member.credits <= 0:
            raise ValueError("Insufficient credits")
        
        if len(fitness_class.bookings) >= fitness_class.capacity:
            raise ValueError("Class is full")
        
        # Check time slot conflicts
        for booking in member.bookings:
            existing_class = self.class_repo.get(booking.class_id)
            if self._times_overlap(existing_class.time, fitness_class.time):
                raise ValueError("Time slot conflict")
        
        # More validation...
        # Then create booking
```

But now the business rules are scattered. Half the validation is here, some might be in the API layer, some in other services. There's no single source of truth about what makes a valid booking.

**This is the problem with anemic domain models.** The objects hold data, but the logic lives everywhere else. Rules are duplicated. Invariants aren't protected. You can create invalid states.

The code is asking for a richer domain.

**This chapter builds that domain.** We'll move from data containers to intelligent objects that understand and enforce business rules. We'll introduce entities with identity, value objects that make invalid states impossible, and aggregates that maintain consistency.

The domain will stop being a passive data holder and become an active participant in business logic.

## What Makes a Domain Rich?

A rich domain model is one where business logic lives in the domain objects themselves (entities, value objects, domain services), not scattered across use cases and controllers.

Consider the `FitnessClass` from Chapter 3:

```python
class FitnessClass:
    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        self.bookings = []
    
    def is_full(self) -> bool:
        return len(self.bookings) >= self.capacity
    
    def can_accept_booking(self) -> bool:
        return not self.is_full()
```

This is moving toward richness. The class knows its own capacity rule. It can answer questions about itself. But it's still incomplete. What happens if someone tries to create a class with negative capacity? What if the name is empty? What if someone directly modifies `self.bookings` to exceed capacity?

The class doesn't protect itself. It trusts everyone else to do the right thing. That's fragile.

A rich domain model enforces its own constraints:

```python
class ClassCapacity:
    def __init__(self, value: int):
        if value < 1:
            raise ValueError("Class capacity must be at least 1")
        if value > 50:
            raise ValueError("Class capacity cannot exceed 50")
        self._value = value
    
    @property
    def value(self) -> int:
        return self._value
    
    def is_exceeded_by(self, current_bookings: int) -> bool:
        return current_bookings >= self._value


class FitnessClass:
    def __init__(self, class_id: str, name: str, capacity: ClassCapacity):
        if not class_id:
            raise ValueError("Class ID is required")
        if not name or not name.strip():
            raise ValueError("Class name cannot be empty")
        
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._bookings = []
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def capacity(self) -> ClassCapacity:
        return self._capacity
    
    def is_full(self) -> bool:
        return self._capacity.is_exceeded_by(len(self._bookings))
    
    def add_booking(self, member_id: str):
        if self.is_full():
            raise ClassFullException(f"Class {self._name} is at capacity")
        
        if member_id in self._bookings:
            raise ValueError(f"Member {member_id} already booked in this class")
        
        self._bookings.append(member_id)
    
    def remove_booking(self, member_id: str):
        if member_id not in self._bookings:
            raise ValueError(f"Member {member_id} not found in class {self._name}")
        
        self._bookings.remove(member_id)
    
    def booking_count(self) -> int:
        return len(self._bookings)


class ClassFullException(Exception):
    pass
```

Now the domain protects itself. Invalid states are impossible. You can't create a class with zero capacity. You can't add bookings beyond the limit. You can't accidentally modify internal state. The class enforces its own invariants.

This is what richness means: the domain understands the rules and refuses to break them.

## Entities: Identity and Lifecycle

Entities have identity; value objects don't. Two members named "Sarah" are different people (entities). Two time slots from 10-11am on Monday are identical (value objects).

Entities are objects defined by their identity, not their attributes. A member with ID "M001" named "Sarah" is still the same member even if she changes her email, updates her membership type, or modifies her name. The identity persists through changes.

Two members with the name "Sarah" and email "sarah@example.com" are not the same member. They're different people who happen to share attributes. What distinguishes them is identity—an ID, a unique identifier that tracks them through their lifecycle.

Here's `Member` evolved from Chapter 3 into a proper entity:

```python
from datetime import datetime, timedelta
from typing import Optional


class MembershipType:
    def __init__(self, name: str, credits_per_month: int, price: float):
        if not name:
            raise ValueError("Membership type name cannot be empty")
        if credits_per_month < 0:
            raise ValueError("Credits per month cannot be negative")
        if price < 0:
            raise ValueError("Price cannot be negative")
        
        self._name = name
        self._credits_per_month = credits_per_month
        self._price = price
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def credits_per_month(self) -> int:
        return self._credits_per_month
    
    @property
    def price(self) -> float:
        return self._price
    
    def __eq__(self, other):
        if not isinstance(other, MembershipType):
            return False
        return (self._name == other._name and 
                self._credits_per_month == other._credits_per_month and
                self._price == other._price)


class EmailAddress:
    def __init__(self, value: str):
        if not value or '@' not in value:
            raise ValueError("Invalid email address")
        self._value = value.lower().strip()
    
    @property
    def value(self) -> str:
        return self._value
    
    def __eq__(self, other):
        if not isinstance(other, EmailAddress):
            return False
        return self._value == other._value
    
    def __str__(self):
        return self._value


class Member:
    def __init__(self, member_id: str, name: str, email: EmailAddress, 
                 membership_type: MembershipType):
        if not member_id:
            raise ValueError("Member ID is required")
        if not name or not name.strip():
            raise ValueError("Member name cannot be empty")
        
        self._id = member_id
        self._name = name
        self._email = email
        self._membership_type = membership_type
        self._credits = membership_type.credits_per_month
        self._credits_expiry: Optional[datetime] = None
        self._joined_at = datetime.now()
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def email(self) -> EmailAddress:
        return self._email
    
    @property
    def membership_type(self) -> MembershipType:
        return self._membership_type
    
    @property
    def credits(self) -> int:
        # Check if credits have expired
        if self._credits_expiry and datetime.now() > self._credits_expiry:
            return 0
        return self._credits
    
    def update_email(self, new_email: EmailAddress):
        self._email = new_email
    
    def deduct_credit(self):
        if self.credits <= 0:
            raise InsufficientCreditsException(
                f"Member {self._name} has no credits remaining"
            )
        self._credits -= 1
    
    def add_credits(self, amount: int, expiry_days: int = 30):
        if amount < 0:
            raise ValueError("Cannot add negative credits")
        
        self._credits += amount
        self._credits_expiry = datetime.now() + timedelta(days=expiry_days)
    
    def renew_membership(self):
        self._credits = self._membership_type.credits_per_month
        self._credits_expiry = datetime.now() + timedelta(days=30)


class InsufficientCreditsException(Exception):
    pass
```

Notice what happened. `Member` isn't just a data holder anymore. It understands membership rules. Credits expire. You can't go negative. Renewal resets the credits. Email addresses must be valid.

The business logic lives in the entity. Not in some external service. If the rule involves member state, it belongs here.

The same applies to `FitnessClass`. It's an entity. It has identity (the `class_id`). Two yoga classes scheduled at different times are different classes, even if they share the same name and capacity.

Entities are distinguished by identity. They evolve. They protect their invariants.

## Value Objects: Concepts Without Identity

Value objects are the opposite of entities: they're defined entirely by their attributes, not by identity.

Consider a time slot: 10:00 AM to 11:00 AM on Monday. If you have two time slots with those exact values, they're the same time slot. There's no "identity" to track—no ID, no lifecycle. The attributes are the thing. If the attributes match, the value objects are identical and interchangeable.

These are value objects. They're immutable. They're interchangeable. Two value objects with the same attributes are equal, by definition.

Here's `TimeSlot`:

```python
from datetime import time, datetime
from enum import Enum


class DayOfWeek(Enum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


class TimeSlot:
    def __init__(self, day: DayOfWeek, start_time: time, end_time: time):
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")
        
        self._day = day
        self._start_time = start_time
        self._end_time = end_time
    
    @property
    def day(self) -> DayOfWeek:
        return self._day
    
    @property
    def start_time(self) -> time:
        return self._start_time
    
    @property
    def end_time(self) -> time:
        return self._end_time
    
    def duration_minutes(self) -> int:
        start = datetime.combine(datetime.today(), self._start_time)
        end = datetime.combine(datetime.today(), self._end_time)
        return int((end - start).total_seconds() / 60)
    
    def overlaps_with(self, other: 'TimeSlot') -> bool:
        if self._day != other._day:
            return False
        
        return (self._start_time < other._end_time and 
                self._end_time > other._start_time)
    
    def __eq__(self, other):
        if not isinstance(other, TimeSlot):
            return False
        return (self._day == other._day and 
                self._start_time == other._start_time and
                self._end_time == other._end_time)
    
    def __hash__(self):
        return hash((self._day, self._start_time, self._end_time))
    
    def __str__(self):
        return f"{self._day.name} {self._start_time.strftime('%H:%M')}-{self._end_time.strftime('%H:%M')}"
```

Value objects are immutable. There's no `set_start_time()` method. If you want a different time slot, you create a new one. This makes them safe to share. Multiple classes can reference the same `TimeSlot` without worrying about one class changing it on another.

Value objects also encapsulate logic that belongs to the concept. A time slot knows how to calculate its duration. It knows how to check for overlap. This logic doesn't belong in `FitnessClass`—it belongs in `TimeSlot`.

Here's how we use it to enhance `FitnessClass`:

```python
class FitnessClass:
    def __init__(self, class_id: str, name: str, capacity: ClassCapacity, 
                 time_slot: TimeSlot):
        if not class_id:
            raise ValueError("Class ID is required")
        if not name or not name.strip():
            raise ValueError("Class name cannot be empty")
        
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._time_slot = time_slot
        self._bookings = []
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def capacity(self) -> ClassCapacity:
        return self._capacity
    
    @property
    def time_slot(self) -> TimeSlot:
        return self._time_slot
    
    def conflicts_with(self, other: 'FitnessClass') -> bool:
        return self._time_slot.overlaps_with(other._time_slot)
    
    def is_full(self) -> bool:
        return self._capacity.is_exceeded_by(len(self._bookings))
    
    def add_booking(self, member_id: str):
        if self.is_full():
            raise ClassFullException(f"Class {self._name} is at capacity")
        
        if member_id in self._bookings:
            raise ValueError(f"Member already booked in this class")
        
        self._bookings.append(member_id)
    
    def remove_booking(self, member_id: str):
        if member_id not in self._bookings:
            raise ValueError(f"Member not found in class")
        
        self._bookings.remove(member_id)
    
    def booking_count(self) -> int:
        return len(self._bookings)
```

Now a fitness class has a proper time slot. Not just strings or separate hour/minute fields. A rich value object that knows what a time slot means.

Value objects make your domain expressive. Instead of primitive obsession (strings, ints, floats everywhere), you use types that reflect business concepts. `EmailAddress` instead of `str`. `ClassCapacity` instead of `int`. `TimeSlot` instead of separate date/time fields.

This makes impossible states impossible. You can't have an invalid email. You can't have a negative capacity. You can't have a time slot where the start comes after the end. The type system enforces business rules.

## Project Structure: Where Does the Code Actually Live?

You've built entities and value objects. Now where do they go? A flat `domain/` folder gets cluttered past 10 classes. Nested subdirectories by aggregate add complexity before you understand the domain.

We'll use a **hybrid approach**—organize by building block type (entity, value object, service):

```
domain/
    entities/
        __init__.py
        member.py          # Member entity
        fitness_class.py   # FitnessClass entity  
        booking.py         # Booking aggregate root (covered in 4b)
        room.py            # Room entity (covered in 4b)
    value_objects/
        __init__.py
        time_slot.py       # TimeSlot, DayOfWeek
        capacity.py        # ClassCapacity
        email.py           # EmailAddress
        membership.py      # MembershipType
    services/
        __init__.py
        scheduling.py      # ClassSchedulingService (covered in 4b)
    exceptions.py          # All domain exceptions
    __init__.py
```

**Why this works:** Clear separation between building blocks. Easy to find things. Doesn't require deep domain understanding upfront. Avoids flat-folder clutter while staying simple.

Small related classes can share files (`DayOfWeek` and `TimeSlot` in `time_slot.py`). Entities get their own files.

We'll use `__init__.py` to re-export classes for cleaner imports:

```python
# domain/entities/__init__.py
from domain.entities.member import Member
from domain.entities.fitness_class import FitnessClass

__all__ = ["Member", "FitnessClass"]
```

This lets you write `from domain.entities import Member` instead of `from domain.entities.member import Member`.

**The complete structure:**

```
domain/
    entities/
        __init__.py          # Re-exports Member, FitnessClass, Booking, Room, WaitlistEntry
        member.py            # Member entity (covered in this chapter)
        fitness_class.py     # FitnessClass entity (covered in this chapter)
        booking.py           # Booking aggregate (covered in 4b)
        room.py              # Room entity (covered in 4b)
        waitlist_entry.py    # WaitlistEntry entity (covered in 4b)
    value_objects/
        __init__.py          # Re-exports all value objects
        time_slot.py         # TimeSlot and DayOfWeek (covered in this chapter)
        capacity.py          # ClassCapacity (covered in this chapter)
        email.py             # EmailAddress (covered in this chapter)
        membership.py        # MembershipType (covered in this chapter)
    services/
        __init__.py          # Re-exports ClassSchedulingService
        scheduling.py        # ClassSchedulingService (covered in 4b)
    exceptions.py            # All domain exceptions
    __init__.py              # Re-exports the most commonly used classes
```

Start with this structure. Refactor to fully nested (subdirectories per aggregate) if you grow to 20+ domain classes or have multiple bounded contexts.

## Aggregates

In the first section of this chapter, we built the foundation: entities with identity and behaviour, value objects that make invalid states impossible. We have `Member`, `FitnessClass`, `TimeSlot`, `EmailAddress`, and `ClassCapacity`. Each one knows its own rules and protects its own invariants.

But real business logic doesn't live in isolated objects. Members book classes. Classes have capacity limits that bookings must respect. Cancellations depend on time remaining before class starts. Multiple classes can't occupy the same room simultaneously.

These are rules that span multiple objects. They require coordination. They need consistency boundaries.

This chapter introduces aggregates and domain services—the patterns that let you model complex business logic while keeping your domain clean and focused. Aggregates define consistency boundaries. Domain services handle logic that doesn't naturally belong to any single entity. Together, they complete the picture of a rich domain model.

By the end of this chapter, you'll have a complete domain layer. One that enforces business rules, maintains consistency, and speaks the language of the business—without any dependency on databases, frameworks, or external services.

### Consistency Boundaries

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

#### Understanding the Booking Aggregate Boundary

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

#### The Waitlist Entity

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

### Domain Services: Logic That Doesn't Fit

Not all business logic belongs in entities or value objects. Sometimes logic involves multiple objects or concepts that don't naturally fit into any single class.

Consider class scheduling. You need to ensure two classes don't overlap in the same room. That's business logic. But does it belong in `FitnessClass`? No—it involves two classes and a room. Does it belong in `Room`? Maybe, but rooms aren't the primary concept here.

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

Domain services are different from use cases. Use cases coordinate workflows ("book a class"). Domain services implement business logic that crosses entity boundaries ("can this class be scheduled in this room?").

Use domain services sparingly. Most logic should live in entities or value objects. But when logic genuinely doesn't fit, don't force it. Create a domain service.

### Business Rules vs Application Policies

There's a distinction worth making: business rules are truths about the domain. Application policies are decisions about how you use the domain.

"A class cannot exceed its capacity" is a business rule. It's invariant. It's true regardless of how you access the system—through an API, a CLI, or a batch job. This belongs in the domain.

"When a booking is confirmed, send an email notification" is an application policy. It's about how you respond to domain events, not about domain truth. This belongs in the application layer.

Keeping these separate matters. The domain should be pure business logic. If you removed all infrastructure—no database, no email server, no HTTP—the domain should still make sense. It should still enforce its rules. It should still represent the business accurately.

Application policies can change more freely. You might start with email notifications, then add SMS, then add push notifications. Those are application concerns. The domain doesn't care how you notify members. It just knows that a booking was made.

This is why our `Member` entity doesn't send emails when the email address changes. It doesn't log events when credits expire. It just manages member state and enforces member rules. The application layer can listen for changes and react accordingly. But the domain stays pure.

### From Anemic to Rich

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

### Domain Exceptions

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

### Putting It All Together

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

## When You Don't Need Rich Domain Models

Rich domain models have costs. Value objects add complexity. Aggregates require discipline. Domain services need careful boundaries. Before you rush to build a rich domain, ask: do you need it?

**You don't need a rich domain model if:**

- You're building a simple CRUD application (create, read, update, delete with minimal business logic)
- Your business rules are straightforward validations (required fields, format checks, basic ranges)
- You have a small, stable domain that rarely changes
- You're building an internal tool or admin interface with minimal complexity
- The application is primarily about data transformation or reporting, not business processes
- Your team is unfamiliar with DDD and the learning curve outweighs the benefits
- You're prototyping and domain understanding is still evolving

In these cases, **simple data classes with validation are enough:**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Member:
    id: str
    name: str
    email: str
    credits: int = 0
    
    def __post_init__(self):
        if self.credits < 0:
            raise ValueError("Credits cannot be negative")
```

No value objects. No aggregates. No domain services. Just data with basic validation. This is perfectly fine for many applications.

**You DO need a rich domain model when you see these signals:**

- Business rules are complex and scattered across multiple services
- The same validation logic is duplicated in many places
- Invalid states are possible despite validation attempts
- Business concepts aren't clearly represented in code
- Domain experts struggle to recognize their terminology in your code
- Rules change frequently and each change touches many files
- You find yourself writing lots of defensive code ("this should never happen, but...")
- Testing business logic requires understanding infrastructure

These signals indicate that an anemic domain model is causing pain. The cure is richness.

**Common misconception:** "Rich domain models are always better."

Not true. They add complexity. They require more thought upfront. They have a learning curve. For simple domains, they're overkill. A user management system with basic CRUD operations doesn't need value objects for every field.

**The right approach:** Start simple. Use plain classes with basic validation. When you feel the pain of scattered logic and duplicated rules, refactor toward richness. Let complexity drive the solution, not the other way around.

We built a rich domain for the gym booking system because the requirements demanded it: credit expiry, time slot conflicts, cancellation rules, capacity management. These are genuinely complex business rules that deserve representation in the domain. Your application might not need this level of sophistication.

Architecture serves the problem. Not the resume.

## Summary

We've built a complete domain layer. Not just data containers, but a rich model where objects understand and enforce business rules.

**Entities** have identity. `Member` and `FitnessClass` are distinguished by their IDs, not their attributes. They change over time while maintaining continuity. They protect their own invariants—you can't create a member without an ID, and you can't modify credits arbitrarily.

**Value objects** are defined by their attributes. `TimeSlot`, `EmailAddress`, `ClassCapacity`, and `MembershipType` have no identity. Two time slots with the same day and times are identical. Value objects are immutable and make invalid states impossible to construct.

**Aggregates** define consistency boundaries. `Booking` is an aggregate root that manages the booking lifecycle independently of `Member` and `FitnessClass`. It references other aggregates by ID, keeping boundaries clear and preventing tightly coupled object graphs. The aggregate enforces its invariants—you can't cancel a booking less than 2 hours before class time, and you can't mark a cancelled booking as attended.

**Domain services** handle logic that doesn't fit naturally into entities. `ClassSchedulingService` coordinates class scheduling across multiple objects and rooms. It's still domain logic, just not tied to a single entity. Use domain services sparingly, but don't force logic where it doesn't belong.

**Domain exceptions** speak the language of the business. `ClassFullException`, `InsufficientCreditsException`, `BookingNotCancellableException`—these aren't technical errors, they're business scenarios. The application layer can respond to each one appropriately.

We organised our domain code using a hybrid structure. Entities live in `domain/entities/`. Value objects live in `domain/value_objects/`. Exceptions are collected in `domain/exceptions.py`. This structure is simple enough to understand immediately but organised enough to scale as the domain grows.

We distinguished business rules from application policies. "A class cannot exceed capacity" is a business rule—it lives in the domain. "Send an email when a booking is confirmed" is an application policy—it lives in the application layer. The domain stays pure, focused only on business truth.

Most importantly, we moved from anemic data holders to intelligent domain objects. The `Member` class doesn't just store credits—it knows expiry rules and enforces non-negative balances. The `FitnessClass` doesn't just hold a capacity number—it uses a `ClassCapacity` value object that guarantees valid ranges and provides meaningful operations. The domain isn't just a passive data holder. It's an active participant in business logic.

Your domain is pure. It has no database code. No HTTP. No external dependencies. Just business logic. You can test it with nothing but Python itself. You can understand it by reading the code. It speaks the language of the people who use it.

In the next chapter, we'll build the application layer on top of this domain. Use cases. Orchestration. How to combine these rich domain objects to fulfil actual business workflows. The domain provides the instruments. The application layer plays the music.

The foundation is solid. Now let's make it sing.
