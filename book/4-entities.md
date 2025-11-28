# Chapter 4: Entities

The layers give you structure. The domain gives you meaning with entities and value objects.

In Chapter 3, we organised our gym booking system into four layers. We created boundaries. We separated concerns. But the domain layer itself remained simple. Basic entities. Straightforward logic. Just enough to demonstrate where business rules belong.

That was intentional. Structure first, depth second. But now it's time to go deeper.

The domain layer is the heart of your system. It's where the business lives. Not the database, not the API, not the framework—the actual concepts that make your system valuable. Members. Classes. Bookings. Capacity. Time. Rules about what can happen and when.

Most developers treat the domain as a collection of data containers. Classes with properties and getters. Anemic objects that hold state but do nothing with it. The logic lives elsewhere—in services, in controllers, in whatever layer happens to need it. The domain becomes a passive victim of external manipulation.

This chapter teaches you to build a rich domain. A domain that understands itself. That enforces its own rules. That speaks the language of the business. We'll take the simple entities from Chapter 3 and give them depth. Identity. Behaviour. Constraints. We'll introduce value objects. We'll make the domain intelligent.

This is the first part of two chapters on domain modelling. Here, we'll focus on entities and value objects—the fundamental building blocks. In Chapter 4b, we'll explore aggregates, domain services, and more advanced patterns.

When you're done with both chapters, your domain won't just hold data. It will embody business logic.

## What Makes a Domain Rich?

A rich domain model is one where business logic lives in the domain objects themselves, not scattered across services and controllers.

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

Entities are objects defined by their identity, not their attributes.

Two members with the name "Sarah" and email "sarah@example.com" are not the same member. They're different people who happen to share attributes. What distinguishes them is identity—an ID, a unique identifier that tracks them through their lifecycle.

Entities have identity. They change over time. They have continuity. You can modify a member's email address, but they're still the same member.

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

Not everything needs identity. Some concepts are defined entirely by their attributes.

Consider a time slot: 10:00 AM to 11:00 AM on Monday. If you have two time slots with those exact values, they're the same time slot. There's no distinction. No identity to track. The attributes are the thing.

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

This makes impossible states actually impossible. You can't have an invalid email. You can't have a negative capacity. You can't have a time slot where the start comes after the end. The type system enforces business rules.

## Project Structure: Where Does the Code Actually Live?

Understanding domain concepts is one thing. Knowing where to put the actual files is another.

You've seen `Member`, `FitnessClass`, and several value objects. But where do they go? Do you create `member.py` and `fitness_class.py` in a flat `domain/` folder? Or do you create `domain/member/member.py` with nested subdirectories? What about value objects—do they get their own files or share one?

These aren't just organisational questions. The structure you choose affects how easy it is to find code, understand boundaries, and navigate the codebase.

### Flat vs Nested Structure

You have two main approaches:

**Flat structure (good for small domains):**
```
domain/
    member.py
    fitness_class.py
    booking.py
    time_slot.py
    email_address.py
    membership_type.py
    exceptions.py
```

Everything in one directory. Simple. No deep import paths. Easy to scan.

**Nested structure (good for larger domains):**
```
domain/
    member/
        __init__.py
        member.py
        membership_type.py
        exceptions.py
    booking/
        __init__.py
        booking.py
        booking_status.py
        exceptions.py
    fitness_class/
        __init__.py
        fitness_class.py
        time_slot.py
        capacity.py
    shared/
        email_address.py
```

Each aggregate or entity gets its own package. Related concepts grouped together. Clear boundaries.

### The Trade-offs

**Flat structure:**
- ✅ Easier to navigate when starting out—everything is in one place
- ✅ No question about where things go—just add another file
- ✅ Fewer import path levels: `from domain.member import Member`
- ✅ Works well for 5-10 domain classes
- ❌ Gets cluttered past ~10 entities
- ❌ Related concepts scattered across files alphabetically
- ❌ Harder to see aggregate boundaries
- ❌ No clear ownership when multiple developers work on domain

**Nested structure:**
- ✅ Clear aggregate boundaries—each folder is a consistency boundary
- ✅ Scales better as the domain grows
- ✅ Related concepts grouped together naturally
- ✅ Easier to see what belongs with what
- ❌ More upfront decisions about grouping
- ❌ Deeper import paths: `from domain.member.member import Member`
- ❌ Can lead to over-organization (folders with one file)
- ❌ Premature structure before you understand the domain

### Our Approach for the Gym Booking System

For this book, we'll use a **hybrid approach** that balances organisation with simplicity:

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

We're grouping by *type of building block* (entity, value object, service) rather than by aggregate or subdomain.

**Why this works:**
- Clear separation between entities and value objects
- Easy to find what you're looking for based on what it is
- Doesn't require deep domain understanding upfront
- Avoids the "everything in one folder" clutter
- Room to grow without restructuring

**How imports look:**

```python
from domain.entities.member import Member
from domain.entities.fitness_class import FitnessClass
from domain.value_objects.time_slot import TimeSlot, DayOfWeek
from domain.value_objects.email import EmailAddress
from domain.exceptions import ClassFullException, InsufficientCreditsException
```

Clear, explicit, and searchable.

### One File or Many?

Another question: should related classes share a file?

**Small value objects can share:**
```python
# domain/value_objects/time_slot.py
from enum import Enum
from datetime import time

class DayOfWeek(Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    # ...

class TimeSlot:
    def __init__(self, day: DayOfWeek, start: time, end: time):
        # ...
```

`DayOfWeek` and `TimeSlot` are used together. They're small. Keeping them in one file makes sense.

**Entities typically get their own file:**
```python
# domain/entities/member.py
class Member:
    # ...
```

Even though `MembershipType` is closely related to `Member`, it's actually a value object, so it goes in the value_objects folder.

**The rule:** If two classes are always used together and one doesn't make sense without the other, they can share a file. Otherwise, separate them.

### When to Refactor Your Structure

Don't start with the perfect structure. Start simple and refactor as you learn.

**Start flat when:**
- You have fewer than 8 domain classes
- You're still figuring out the domain
- It's a new project and structure is premature

**Move to hybrid (our approach) when:**
- You have 8-15 domain classes
- You understand the main concepts
- You want some organisation without deep nesting

**Move to fully nested when:**
- You have multiple bounded contexts
- You have distinct subdomains (member management, class scheduling, billing)
- Different teams own different parts of the domain
- You have 20+ domain classes

The structure should serve the code, not the other way around. If you're spending more time deciding where to put a file than writing it, your structure is too complex.

### What About `__init__.py`?

Each folder needs an `__init__.py` to be a Python package, but what goes inside?

**Option 1: Empty (simplest)**
```python
# domain/entities/__init__.py
# Empty file
```

Imports are explicit: `from domain.entities.member import Member`

**Option 2: Re-export key classes (convenient)**
```python
# domain/entities/__init__.py
from domain.entities.member import Member
from domain.entities.fitness_class import FitnessClass

__all__ = ["Member", "FitnessClass"]
```

Now you can import: `from domain.entities import Member, FitnessClass`

**We'll use Option 2** because it makes imports cleaner and explicitly declares the public API of each package. If a class isn't in `__all__`, it's an internal implementation detail.

### The Final Structure

Here's what our complete domain layer looks like on disk after both chapters 4 and 5:

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

The root `domain/__init__.py` can make common imports even easier:

```python
# domain/__init__.py
from domain.entities import Member, FitnessClass
from domain.value_objects import TimeSlot, EmailAddress
from domain.exceptions import (
    ClassFullException,
    InsufficientCreditsException
)

__all__ = [
    "Member",
    "FitnessClass", 
    "TimeSlot",
    "EmailAddress",
    "ClassFullException",
    "InsufficientCreditsException",
]
```

Now application code can use: `from domain import Member, FitnessClass, ClassFullException`

This is clean, discoverable, and maintainable. The structure reflects the domain concepts. Finding code is straightforward. Adding new classes has a clear pattern.

Start here. Refactor when it stops serving you.

## Summary

We've laid the foundation for a rich domain model. Not just data containers, but objects that understand and enforce business rules.

Entities have identity. `Member` and `FitnessClass` are distinguished by their IDs, not their attributes. They change over time while maintaining continuity. They protect their own invariants—you can't create a member without an ID, and you can't modify credits arbitrarily.

Value objects are defined by their attributes. `TimeSlot`, `EmailAddress`, `ClassCapacity`, and `MembershipType` have no identity. Two time slots with the same day and times are identical. Value objects are immutable and make invalid states impossible to construct.

We organised our domain code using a hybrid structure. Entities live in `domain/entities/`. Value objects live in `domain/value_objects/`. Exceptions are collected in `domain/exceptions.py`. This structure is simple enough to understand immediately but organised enough to scale as the domain grows.

Most importantly, we moved from anemic data holders to intelligent domain objects. The `Member` class doesn't just store credits—it knows expiry rules and enforces non-negative balances. The `FitnessClass` doesn't just hold a capacity number—it uses a `ClassCapacity` value object that guarantees valid ranges and provides meaningful operations.

Your domain is starting to speak the language of the business. It understands members, classes, time slots, and capacity. It enforces the rules that make those concepts meaningful.

But we're not done. In the next chapter, we'll explore aggregates—clusters of entities that maintain consistency as a unit. We'll introduce domain services for logic that spans multiple entities. We'll see how to handle cross-cutting concerns like scheduling. And we'll complete the transformation from scattered logic to a cohesive, self-protecting domain model.

The building blocks are in place. Now let's assemble them into something greater.
