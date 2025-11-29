# Chapter 6: Ports

You can't run the application without infrastructure. But you shouldn't depend on it.

In Chapter 6, we built use cases that orchestrate domain logic. `BookClassUseCase` coordinates members, classes, and bookings. `CancelBookingUseCase` handles refunds and notifications. `ProcessWaitlistUseCase` manages complex cross-aggregate workflows.

They work. The logic is clean. The domain stays pure. But there's a problem we deliberately exposed: the use cases need infrastructure. They need to load data. They need to save changes. They need to send notifications.

Look at this line again:

```python
member = self.member_repository.get_by_id(member_id)
```

What is `member_repository`? Right now, it's a concrete implementation. It knows about databases. It knows about SQL. It knows about connection strings and transactions. And our application layer—which should be pure business orchestration—depends on it.

This violates the dependency rule. High-level policy shouldn't depend on low-level details. The application layer shouldn't care whether members come from PostgreSQL, MongoDB, or a CSV file. But right now, it does.

This chapter solves that problem. We're going to define what the application needs without specifying how it's provided. We're going to create abstractions—ports—that let the application express its requirements while keeping infrastructure at arm's length.

By the end, your use cases won't depend on concrete repositories or services. They'll depend on contracts. And those contracts will point dependencies inward, not outward.

## The Dependency Problem

Let's make the problem concrete. Here's our `BookClassUseCase` from Chapter 6:

```python
class BookClassUseCase:
    def __init__(self, member_repository, class_repository, 
                 booking_repository, notification_service):
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, member_id: str, class_id: str) -> Booking:
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        # ... orchestration logic
```

What types are `member_repository` and `notification_service`? We never specified. Python doesn't require it. But in practice, they're concrete classes:

```python
# Hypothetical concrete implementations
class PostgresMemberRepository:
    def __init__(self, connection_string: str):
        self.db = create_engine(connection_string)
    
    def get_by_id(self, member_id: str) -> Member:
        # SQL query to fetch member
        pass

class SMTPNotificationService:
    def __init__(self, smtp_host: str, smtp_port: int):
        self.smtp = smtplib.SMTP(smtp_host, smtp_port)
    
    def send_booking_confirmation(self, email, name, class_name, time_slot):
        # Send email via SMTP
        pass
```

Now look at the dependency graph:

```
Application Layer (BookClassUseCase)
        ↓ depends on
Infrastructure Layer (PostgresMemberRepository, SMTPNotificationService)
```

This is backwards. Infrastructure should depend on application, not the other way around. The direction of dependency is wrong.

Why does this matter?

**You can't test the use case without infrastructure.** Want to test booking logic? You need a database. You need an email server. Or you need to mock them, which couples your tests to implementation details.

**You can't swap implementations.** Want to switch from PostgreSQL to MongoDB? You change the infrastructure. But because the application depends on the infrastructure, you also have to change the application. The coupling propagates upward.

**You can't deploy flexibly.** Want to run the use case in a Lambda function with DynamoDB instead of PostgreSQL? Too bad. The use case is hardcoded to PostgreSQL.

The dependency points the wrong direction. We need to invert it.

## Dependency Inversion: The Principle

The Dependency Inversion Principle says:

**High-level modules should not depend on low-level modules. Both should depend on abstractions.**

High-level modules are your business logic—domain and application layers. Low-level modules are your infrastructure—databases, email services, external APIs.

Right now, high-level depends on low-level:

```
BookClassUseCase → PostgresMemberRepository
```

We need both to depend on an abstraction:

```
BookClassUseCase → MemberRepository (abstraction)
                            ↑
                PostgresMemberRepository
```

The abstraction sits between them. The use case depends on the abstraction. The infrastructure implements the abstraction. Dependencies point inward.

This is dependency inversion. And the abstractions we create are called ports.

## What Is a Port?

A port is a contract that defines what the application needs from infrastructure without specifying how it's provided.

In Python, we express ports using abstract base classes or protocols. They define methods—the interface—but don't implement them. They declare what operations are available, not how they work.

Here's a port for member persistence:

```python
from abc import ABC, abstractmethod
from typing import Optional

from domain.entities import Member


class MemberRepository(ABC):
    """
    Port for member persistence.
    
    Defines what the application needs to load and save members,
    without specifying how they're stored.
    """
    
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """Retrieve a member by their ID. Returns None if not found."""
        pass
    
    @abstractmethod
    def save(self, member: Member) -> None:
        """Persist a member. Creates new or updates existing."""
        pass
```

That's it. Two methods. `get_by_id()` and `save()`. That's all the application needs.

**Note on typing.Protocol:** If you're using Python 3.8+, you can use `typing.Protocol` instead of `ABC`. 

Protocols use structural subtyping—duck typing with type checking. You don't need to explicitly inherit from the port. Any class with matching methods automatically satisfies the contract. 

We use `ABC` here because it's more explicit: implementations must inherit from the port. This makes the relationship visible. But `Protocol` is equally valid. Choose based on your preference for explicit inheritance vs structural typing.

Notice what's not here:
- No database connection
- No SQL queries
- No ORM imports
- No knowledge of how members are stored

The port defines what, not how. It's a contract between the application and infrastructure.

Now our use case can depend on this abstraction:

```python
class BookClassUseCase:
    def __init__(self, member_repository: MemberRepository,
                 class_repository, booking_repository, notification_service):
        self.member_repository = member_repository
        # ...
```

We've added a type hint: `member_repository: MemberRepository`. The use case now depends on the port, not a concrete implementation.

Infrastructure will provide the implementation. But the use case doesn't know about it. Doesn't care. It just knows the contract.

Dependencies inverted. Problem solved.

## Defining Repository Ports

Let's define all the repository ports our use cases need. Start with `MemberRepository`, which we've already seen:

```python
from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities import Member


class MemberRepository(ABC):
    """Port for member persistence."""
    
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """Retrieve a member by their ID."""
        pass
    
    @abstractmethod
    def save(self, member: Member) -> None:
        """Persist a member."""
        pass
    
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Member]:
        """Find a member by email address."""
        pass
    
    @abstractmethod
    def list_all(self) -> List[Member]:
        """Retrieve all members."""
        pass
```

We've added `find_by_email()` because user interfaces often look up members by email. We've added `list_all()` for administrative views. But these are still just contracts. No implementation.

Next, `FitnessClassRepository`:

```python
from domain.entities import FitnessClass


class FitnessClassRepository(ABC):
    """Port for fitness class persistence."""
    
    @abstractmethod
    def get_by_id(self, class_id: str) -> Optional[FitnessClass]:
        """Retrieve a fitness class by ID."""
        pass
    
    @abstractmethod
    def save(self, fitness_class: FitnessClass) -> None:
        """Persist a fitness class."""
        pass
    
    @abstractmethod
    def find_by_time_slot(self, time_slot) -> List[FitnessClass]:
        """Find all classes scheduled in a given time slot."""
        pass
    
    @abstractmethod
    def list_all(self) -> List[FitnessClass]:
        """Retrieve all fitness classes."""
        pass
```

Same pattern. Load by ID. Save. Query by criteria. The application defines what it needs. Infrastructure will figure out how to provide it.

Now `BookingRepository`:

```python
from domain.entities import Booking, BookingStatus


class BookingRepository(ABC):
    """Port for booking persistence."""
    
    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        """Retrieve a booking by ID."""
        pass
    
    @abstractmethod
    def save(self, booking: Booking) -> None:
        """Persist a booking."""
        pass
    
    @abstractmethod
    def find_by_member(self, member_id: str) -> List[Booking]:
        """Find all bookings for a specific member."""
        pass
    
    @abstractmethod
    def find_by_class(self, class_id: str) -> List[Booking]:
        """Find all bookings for a specific class."""
        pass
    
    @abstractmethod
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        """Find a specific booking for a member in a class."""
        pass
    
    @abstractmethod
    def find_by_status(self, status: BookingStatus) -> List[Booking]:
        """Find all bookings with a given status."""
        pass
```

More methods because bookings are queried in more ways. By member. By class. By status. By the combination of member and class. Each method represents something the application needs to do.

But still: no SQL. No database code. Just contracts.

One more repository—waitlist entries:

```python
from domain.entities import WaitlistEntry


class WaitlistRepository(ABC):
    """Port for waitlist persistence."""
    
    @abstractmethod
    def save(self, entry: WaitlistEntry) -> None:
        """Add or update a waitlist entry."""
        pass
    
    @abstractmethod
    def remove(self, entry: WaitlistEntry) -> None:
        """Remove a waitlist entry."""
        pass
    
    @abstractmethod
    def get_next_for_class(self, class_id: str) -> Optional[WaitlistEntry]:
        """Get the next person waiting for a class."""
        pass
    
    @abstractmethod
    def find_by_member(self, member_id: str) -> List[WaitlistEntry]:
        """Find all waitlist entries for a member."""
        pass
```

Now we have complete repository ports for all our persistence needs.

## Defining Service Ports

Repositories aren't the only infrastructure concern. Use cases also need to send notifications. That's infrastructure too.

Let's define a port for notifications:

```python
from abc import ABC, abstractmethod


class NotificationService(ABC):
    """Port for sending notifications to members."""
    
    @abstractmethod
    def send_booking_confirmation(self, email: str, name: str,
                                  class_name: str, time_slot) -> None:
        """Send a booking confirmation to a member."""
        pass
    
    @abstractmethod
    def send_cancellation_confirmation(self, email: str, name: str,
                                       class_name: str, time_slot) -> None:
        """Send a cancellation confirmation to a member."""
        pass
    
    @abstractmethod
    def send_waitlist_confirmation(self, email: str, name: str,
                                   class_name: str) -> None:
        """Notify a member they've been added to the waitlist."""
        pass
    
    @abstractmethod
    def send_waitlist_booking_confirmation(self, email: str, name: str,
                                          class_name: str, time_slot) -> None:
        """Notify a member they got off the waitlist and into the class."""
        pass
    
    @abstractmethod
    def send_waitlist_insufficient_credits(self, email: str, name: str,
                                          class_name: str) -> None:
        """Notify a member they were skipped in the waitlist due to insufficient credits."""
        pass
```

Each method corresponds to a notification scenario in our domain. The use cases call these methods when appropriate. But they don't know how notifications are sent. Email? SMS? Push notification? The port doesn't care.

Infrastructure will implement the port. Maybe with SMTP. Maybe with SendGrid. Maybe with a message queue. The use case doesn't need to know.

If you need payment processing, you'd define a `PaymentService` port:

```python
class PaymentService(ABC):
    """Port for processing payments."""
    
    @abstractmethod
    def charge_membership(self, member_id: str, amount: float) -> str:
        """
        Charge a member for their membership.
        Returns a transaction ID.
        """
        pass
    
    @abstractmethod
    def refund_booking(self, member_id: str, booking_id: str, 
                      amount: float) -> None:
        """Refund a member for a cancelled booking."""
        pass
```

Same pattern. What does the application need? Charge a membership. Refund a booking. How is it done? Not the application's concern.

## Where Do Ports Live?

This is a practical question with architectural implications. Where in your directory structure do you put these port definitions?

**Decision: We're placing ports in the application layer.**

The application defines what it needs. Infrastructure provides it. Ports are contracts owned by the application. So they live with the application.

Here are the two options we considered:

**Option 1: Application layer**
```
application/
    ports/
        __init__.py
        member_repository.py
        booking_repository.py
        notification_service.py
    use_cases/
        book_class.py
        cancel_booking.py
```

Ports live with the application because the application defines its needs. This emphasises that ports belong to the application, not infrastructure.

**Option 2: Dedicated ports layer**
```
ports/
    __init__.py
    repositories.py      # All repository ports
    services.py          # All service ports
application/
    use_cases/
        book_class.py
```

Ports get their own layer between application and infrastructure. This makes the boundary explicit.

**We chose Option 1.** Why? It makes the ownership explicit. The application declares its requirements. Infrastructure fulfills them. Ports are the application's contracts, so they live in the application layer.

Here's our structure:

```
application/
    ports/
        __init__.py
        repositories.py    # MemberRepository, BookingRepository, etc.
        services.py        # NotificationService, PaymentService
    use_cases/
        __init__.py
        book_class.py
        cancel_booking.py
        process_waitlist.py
    __init__.py
```

The complete `repositories.py` file:

```python
from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities import Member, FitnessClass, Booking, BookingStatus, WaitlistEntry


class MemberRepository(ABC):
    """Port for member persistence."""
    
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def save(self, member: Member) -> None:
        pass
    
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def list_all(self) -> List[Member]:
        pass


class FitnessClassRepository(ABC):
    """Port for fitness class persistence."""
    
    @abstractmethod
    def get_by_id(self, class_id: str) -> Optional[FitnessClass]:
        pass
    
    @abstractmethod
    def save(self, fitness_class: FitnessClass) -> None:
        pass
    
    @abstractmethod
    def find_by_time_slot(self, time_slot) -> List[FitnessClass]:
        pass
    
    @abstractmethod
    def list_all(self) -> List[FitnessClass]:
        pass


class BookingRepository(ABC):
    """Port for booking persistence."""
    
    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    def save(self, booking: Booking) -> None:
        pass
    
    @abstractmethod
    def find_by_member(self, member_id: str) -> List[Booking]:
        pass
    
    @abstractmethod
    def find_by_class(self, class_id: str) -> List[Booking]:
        pass
    
    @abstractmethod
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    def find_by_status(self, status: BookingStatus) -> List[Booking]:
        pass


class WaitlistRepository(ABC):
    """Port for waitlist persistence."""
    
    @abstractmethod
    def save(self, entry: WaitlistEntry) -> None:
        pass
    
    @abstractmethod
    def remove(self, entry: WaitlistEntry) -> None:
        pass
    
    @abstractmethod
    def get_next_for_class(self, class_id: str) -> Optional[WaitlistEntry]:
        pass
    
    @abstractmethod
    def find_by_member(self, member_id: str) -> List[WaitlistEntry]:
        pass
```

And the complete `services.py`:

```python
from abc import ABC, abstractmethod


class NotificationService(ABC):
    """Port for sending notifications to members."""
    
    @abstractmethod
    def send_booking_confirmation(self, email: str, name: str,
                                  class_name: str, time_slot) -> None:
        pass
    
    @abstractmethod
    def send_cancellation_confirmation(self, email: str, name: str,
                                       class_name: str, time_slot) -> None:
        pass
    
    @abstractmethod
    def send_waitlist_confirmation(self, email: str, name: str,
                                   class_name: str) -> None:
        pass
    
    @abstractmethod
    def send_waitlist_booking_confirmation(self, email: str, name: str,
                                          class_name: str, time_slot) -> None:
        pass
    
    @abstractmethod
    def send_waitlist_insufficient_credits(self, email: str, name: str,
                                          class_name: str) -> None:
        pass
```

Clean. Organised. All the contracts in one place.

## Refactoring Use Cases to Depend on Ports

Now we update our use cases to depend on these ports instead of concrete implementations.

Here's `BookClassUseCase` refactored:

```python
from typing import Optional

from domain.entities import Member, FitnessClass, Booking, BookingStatus
from domain.exceptions import ClassFullException, InsufficientCreditsException
from application.ports.repositories import (
    MemberRepository, 
    FitnessClassRepository, 
    BookingRepository
)
from application.ports.services import NotificationService


def generate_id() -> str:
    """Generate a unique ID for domain entities."""
    from uuid import uuid4
    return str(uuid4())


class BookClassUseCase:
    def __init__(self, 
                 member_repository: MemberRepository,
                 class_repository: FitnessClassRepository,
                 booking_repository: BookingRepository,
                 notification_service: NotificationService):
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, member_id: str, class_id: str) -> Booking:
        """
        Book a member into a fitness class.
        
        Raises:
            ValueError: If member or class not found
            InsufficientCreditsException: If member has no credits
            ClassFullException: If class is at capacity
        """
        # 1. Load domain objects
        member = self.member_repository.get_by_id(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")
        
        fitness_class = self.class_repository.get_by_id(class_id)
        if not fitness_class:
            raise ValueError(f"Class {class_id} not found")
        
        # 2. Check for existing booking
        existing_booking = self.booking_repository.find_by_member_and_class(
            member_id, class_id
        )
        if existing_booking and existing_booking.status == BookingStatus.CONFIRMED:
            raise ValueError("Member already booked in this class")
        
        # 3. Let the domain enforce business rules
        member.deduct_credit()
        fitness_class.add_booking(member_id)
        
        # 4. Create the booking aggregate
        booking = Booking(generate_id(), member_id, class_id)
        
        # 5. Persist all changes
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # 6. Send confirmation
        self.notification_service.send_booking_confirmation(
            member.email.value,
            member.name,
            fitness_class.name,
            fitness_class.time_slot
        )
        
        return booking
```

Look at the changes. The constructor now has type hints: `member_repository: MemberRepository`. These are the port types, not concrete implementations.

The imports changed. We import from `application.ports.repositories` and `application.ports.services`, not from infrastructure.

The logic is identical. The orchestration hasn't changed. But the dependencies have. The use case depends on abstractions, not concretions.

`CancelBookingUseCase` gets the same treatment:

```python
from datetime import datetime, timedelta

from domain.entities import Booking, BookingStatus
from domain.exceptions import BookingNotCancellableException
from application.ports.repositories import (
    BookingRepository,
    MemberRepository,
    FitnessClassRepository
)
from application.ports.services import NotificationService


class CancelBookingUseCase:
    def __init__(self, 
                 booking_repository: BookingRepository,
                 member_repository: MemberRepository,
                 class_repository: FitnessClassRepository,
                 notification_service: NotificationService):
        self.booking_repository = booking_repository
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.notification_service = notification_service
    
    def execute(self, booking_id: str) -> None:
        """
        Cancel a booking and refund the member's credit.
        
        Raises:
            ValueError: If booking not found
            BookingNotCancellableException: If booking cannot be cancelled
        """
        # 1. Load the booking
        booking = self.booking_repository.get_by_id(booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        
        # 2. Load the class to check the schedule
        fitness_class = self.class_repository.get_by_id(booking.class_id)
        if not fitness_class:
            raise ValueError(f"Class {booking.class_id} not found")
        
        # 3. Calculate class start time
        class_start_time = self._get_next_class_occurrence(fitness_class.time_slot)
        
        # 4. Let the domain enforce cancellation rules
        booking.cancel(class_start_time)
        
        # 5. Load the member and refund the credit
        member = self.member_repository.get_by_id(booking.member_id)
        if member:
            member.add_credits(1, expiry_days=30)
            self.member_repository.save(member)
        
        # 6. Remove member from the class
        fitness_class.remove_booking(booking.member_id)
        
        # 7. Persist changes
        self.booking_repository.save(booking)
        self.class_repository.save(fitness_class)
        
        # 8. Notify the member
        if member:
            self.notification_service.send_cancellation_confirmation(
                member.email.value,
                member.name,
                fitness_class.name,
                fitness_class.time_slot
            )
    
    def _get_next_class_occurrence(self, time_slot) -> datetime:
        """Find the next occurrence of this time slot."""
        now = datetime.now()
        current_day = now.weekday() + 1
        target_day = time_slot.day.value
        days_ahead = (target_day - current_day) % 7
        
        if days_ahead == 0:
            days_ahead = 7
        
        next_date = now + timedelta(days=days_ahead)
        return datetime.combine(next_date.date(), time_slot.start_time)
```

And `ProcessWaitlistUseCase`:

```python
from typing import Optional
from uuid import uuid4

from domain.entities import Booking
from domain.exceptions import InsufficientCreditsException, ClassFullException
from application.ports.repositories import (
    WaitlistRepository,
    MemberRepository,
    FitnessClassRepository,
    BookingRepository
)
from application.ports.services import NotificationService


def generate_id() -> str:
    """Generate a unique ID for domain entities."""
    return str(uuid4())


class ProcessWaitlistUseCase:
    def __init__(self,
                 waitlist_repository: WaitlistRepository,
                 member_repository: MemberRepository,
                 class_repository: FitnessClassRepository,
                 booking_repository: BookingRepository,
                 notification_service: NotificationService):
        self.waitlist_repository = waitlist_repository
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, class_id: str) -> Optional[Booking]:
        """Process the waitlist for a class when a spot becomes available."""
        # 1. Load the class
        fitness_class = self.class_repository.get_by_id(class_id)
        if not fitness_class:
            raise ValueError(f"Class {class_id} not found")
        
        # 2. Check if there's actually space
        if fitness_class.is_full():
            return None
        
        # 3. Get the next person on the waitlist
        next_in_line = self.waitlist_repository.get_next_for_class(class_id)
        if not next_in_line:
            return None
        
        # 4. Load the member
        member = self.member_repository.get_by_id(next_in_line.member_id)
        if not member:
            self.waitlist_repository.remove(next_in_line)
            return self.execute(class_id)
        
        # 5. Check if member still has credits
        try:
            member.deduct_credit()
        except InsufficientCreditsException:
            self.waitlist_repository.remove(next_in_line)
            self.notification_service.send_waitlist_insufficient_credits(
                member.email.value,
                member.name,
                fitness_class.name
            )
            return self.execute(class_id)
        
        # 6. Book the member into the class
        try:
            fitness_class.add_booking(next_in_line.member_id)
        except ClassFullException:
            member.add_credits(1, expiry_days=30)
            self.member_repository.save(member)
            return None
        
        # 7. Create the booking
        booking = Booking(generate_id(), next_in_line.member_id, class_id)
        
        # 8. Remove from waitlist
        self.waitlist_repository.remove(next_in_line)
        
        # 9. Persist everything
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # 10. Notify the member
        self.notification_service.send_waitlist_booking_confirmation(
            member.email.value,
            member.name,
            fitness_class.name,
            fitness_class.time_slot
        )
        
        return booking
```

All three use cases now depend exclusively on ports. They import from `application.ports`, not from infrastructure. The dependencies point inward.

## Testing with Ports

Here's where ports prove their value. You can now test use cases without infrastructure.

Create a fake repository that implements the port:

```python
from typing import Dict, Optional, List

from domain.entities import Member
from application.ports.repositories import MemberRepository


class InMemoryMemberRepository(MemberRepository):
    """Fake implementation for testing."""
    
    def __init__(self):
        self._members: Dict[str, Member] = {}
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)
    
    def save(self, member: Member) -> None:
        self._members[member.id] = member
    
    def find_by_email(self, email: str) -> Optional[Member]:
        for member in self._members.values():
            if member.email.value == email:
                return member
        return None
    
    def list_all(self) -> List[Member]:
        return list(self._members.values())
```

It implements the port. It stores members in a dictionary. No database. No network. Just pure Python.

Do the same for other ports (showing key methods, with similar implementations for remaining port methods):

```python
class InMemoryBookingRepository(BookingRepository):
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}
    
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        return self._bookings.get(booking_id)
    
    def save(self, booking: Booking) -> None:
        self._bookings[booking.id] = booking
    
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        for booking in self._bookings.values():
            if (booking.member_id == member_id and 
                booking.class_id == class_id):
                return booking
        return None
    
    def find_by_member(self, member_id: str) -> List[Booking]:
        return [b for b in self._bookings.values() if b.member_id == member_id]
    
    def find_by_class(self, class_id: str) -> List[Booking]:
        return [b for b in self._bookings.values() if b.class_id == class_id]
    
    def find_by_status(self, status: BookingStatus) -> List[Booking]:
        return [b for b in self._bookings.values() if b.status == status]


class InMemoryFitnessClassRepository(FitnessClassRepository):
    """Fake fitness class repository for testing."""
    
    def __init__(self):
        self._classes: Dict[str, FitnessClass] = {}
    
    def get_by_id(self, class_id: str) -> Optional[FitnessClass]:
        return self._classes.get(class_id)
    
    def save(self, fitness_class: FitnessClass) -> None:
        self._classes[fitness_class.id] = fitness_class
    
    def find_by_time_slot(self, time_slot) -> List[FitnessClass]:
        result = []
        for cls in self._classes.values():
            if cls.time_slot == time_slot:
                result.append(cls)
        return result
    
    def list_all(self) -> List[FitnessClass]:
        return list(self._classes.values())


class FakeNotificationService(NotificationService):
    """Fake notification service that records calls instead of sending emails."""
    
    def __init__(self):
        self.sent_notifications = []
    
    def send_booking_confirmation(self, email: str, name: str,
                                  class_name: str, time_slot) -> None:
        self.sent_notifications.append({
            'type': 'booking_confirmation',
            'email': email,
            'name': name,
            'class_name': class_name
        })
    
    def send_cancellation_confirmation(self, email: str, name: str,
                                       class_name: str, time_slot) -> None:
        self.sent_notifications.append({
            'type': 'cancellation_confirmation',
            'email': email,
            'name': name,
            'class_name': class_name
        })
    
    def send_waitlist_confirmation(self, email: str, name: str,
                                   class_name: str) -> None:
        self.sent_notifications.append({
            'type': 'waitlist_confirmation',
            'email': email,
            'name': name,
            'class_name': class_name
        })
    
    def send_waitlist_booking_confirmation(self, email: str, name: str,
                                          class_name: str, time_slot) -> None:
        self.sent_notifications.append({
            'type': 'waitlist_booking_confirmation',
            'email': email,
            'name': name,
            'class_name': class_name
        })
    
    def send_waitlist_insufficient_credits(self, email: str, name: str,
                                          class_name: str) -> None:
        self.sent_notifications.append({
            'type': 'waitlist_insufficient_credits',
            'email': email,
            'name': name,
            'class_name': class_name
        })
```

Now write tests:

```python
import pytest
from datetime import time

from domain.entities import Member, FitnessClass, BookingStatus
from domain.value_objects import EmailAddress, MembershipType, ClassCapacity, TimeSlot, DayOfWeek
from domain.exceptions import ClassFullException, InsufficientCreditsException
from application.use_cases.book_class import BookClassUseCase


def test_booking_a_class_successfully():
    # Arrange: Create fake repositories
    member_repo = InMemoryMemberRepository()
    class_repo = InMemoryFitnessClassRepository()
    booking_repo = InMemoryBookingRepository()
    notification = FakeNotificationService()
    
    # Create test data
    email = EmailAddress("sarah@example.com")
    membership = MembershipType("Premium", credits_per_month=10, price=50)
    member = Member("M001", "Sarah", email, membership)
    
    capacity = ClassCapacity(15)
    time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))
    yoga_class = FitnessClass("C001", "Yoga", capacity, time_slot)
    
    member_repo.save(member)
    class_repo.save(yoga_class)
    
    # Act: Execute the use case
    use_case = BookClassUseCase(member_repo, class_repo, booking_repo, notification)
    booking = use_case.execute("M001", "C001")
    
    # Assert: Verify the outcome
    assert booking is not None
    assert booking.member_id == "M001"
    assert booking.class_id == "C001"
    assert booking.status == BookingStatus.CONFIRMED
    
    # Verify member credits were deducted
    updated_member = member_repo.get_by_id("M001")
    assert updated_member.credits == 9
    
    # Verify class has the booking
    updated_class = class_repo.get_by_id("C001")
    assert updated_class.booking_count() == 1
    
    # Verify notification was sent
    assert len(notification.sent_notifications) == 1
    assert notification.sent_notifications[0]['type'] == 'booking_confirmation'


def test_booking_fails_when_class_is_full():
    # Arrange
    member_repo = InMemoryMemberRepository()
    class_repo = InMemoryFitnessClassRepository()
    booking_repo = InMemoryBookingRepository()
    notification = FakeNotificationService()
    
    # Create a class with capacity of 1
    capacity = ClassCapacity(1)
    time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))
    yoga_class = FitnessClass("C001", "Yoga", capacity, time_slot)
    yoga_class.add_booking("OTHER_MEMBER")  # Fill the class
    class_repo.save(yoga_class)
    
    # Create a member
    email = EmailAddress("sarah@example.com")
    membership = MembershipType("Premium", credits_per_month=10, price=50)
    member = Member("M001", "Sarah", email, membership)
    member_repo.save(member)
    
    # Act & Assert
    use_case = BookClassUseCase(member_repo, class_repo, booking_repo, notification)
    with pytest.raises(ClassFullException):
        use_case.execute("M001", "C001")
```

No database. No email server. Just pure unit tests that run in milliseconds.

The tests verify business logic. The fake repositories implement the ports. The use case doesn't know the difference.

This is the power of depending on abstractions.

## The Hexagonal Architecture Emerges

What we've built is the core of hexagonal architecture—also called ports and adapters.

The structure looks like this:

```
        ┌─────────────────────────┐
        │   Application Layer     │
        │   (Use Cases)           │
        └───────┬─────────────────┘
                │ depends on
        ┌───────▼─────────────────┐
        │   Ports                 │
        │   (Abstractions)        │
        └───────▲─────────────────┘
                │ implemented by
        ┌───────┴─────────────────┐
        │   Infrastructure Layer  │
        │   (Adapters)            │
        └─────────────────────────┘
```

The application defines ports. Infrastructure implements them. Dependencies point inward.

The application is the hexagon—the core business logic. Ports are the edges—the interfaces. Adapters plug into ports from the outside.

You can have multiple adapters for the same port:
- `PostgresMemberRepository` for production
- `InMemoryMemberRepository` for tests
- `MongoMemberRepository` for a different deployment

The use cases don't change. They depend on `MemberRepository`, the port. Which adapter is connected is decided at runtime, outside the application.

This is dependency injection. The application declares what it needs. Something external provides it.

## What We Can't Do Yet

Our application is well-structured. Use cases depend on ports. Ports define clean contracts. Dependencies point inward.

But we can't run it.

The ports have no implementations. `MemberRepository` is an abstract base class. You can't instantiate it. You can't call its methods.

We've defined what the application needs. We haven't provided how to fulfill those needs.

Try to create a use case:

```python
use_case = BookClassUseCase(
    member_repository=MemberRepository(),  # Error: Can't instantiate ABC
    class_repository=FitnessClassRepository(),  # Error: Can't instantiate ABC
    booking_repository=BookingRepository(),  # Error: Can't instantiate ABC
    notification_service=NotificationService()  # Error: Can't instantiate ABC
)
```

You can't. Abstract classes can't be instantiated. Here's what happens if you try:

```python
>>> from application.ports.repositories import MemberRepository
>>> repo = MemberRepository()
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: Can't instantiate abstract class MemberRepository with abstract methods get_by_id, save, find_by_email, list_all
```

Python refuses. The error is explicit: these are abstract methods. They have no implementation. There's nothing to run.

You could try to call a use case method, but you'd never get there. You can't create the dependencies it needs.

This is frustrating. We've built clean architecture. We've inverted dependencies. We've defined clear contracts. And we can't run a single line of business logic.

But this frustration is the point. The architecture forces us to provide real implementations. We can't fake it. We can't skip infrastructure. We have to fulfill the contracts.

We need concrete implementations.

We need adapters.

That's the next chapter. We've inverted the dependencies. We've created the contracts. Now we need to fulfill them with real infrastructure—databases, email services, APIs—while keeping the dependency direction correct.

The application doesn't know about infrastructure. But infrastructure will know about the application's ports. And it will implement them.

## Summary

Use cases need infrastructure. But depending on infrastructure violates the dependency rule.

The solution is ports—abstractions that define what the application needs without specifying how it's provided. Ports are contracts expressed as abstract base classes or protocols.

We defined repository ports for persistence: `MemberRepository`, `FitnessClassRepository`, `BookingRepository`, `WaitlistRepository`. Each port declares the methods the application needs—load, save, query—without implementation.

We defined service ports for external concerns: `NotificationService` for sending emails, `PaymentService` for processing payments. Again, just contracts.

We refactored our use cases from Chapter 6 to depend on these ports. The constructors now accept `MemberRepository`, not concrete implementations. The imports changed from infrastructure to ports. But the logic stayed the same.

This inverts dependencies. High-level policy (use cases) no longer depends on low-level details (databases, email). Both depend on abstractions (ports).

Testing became trivial. We created fake implementations—`InMemoryMemberRepository`, `FakeNotificationService`—that fulfill the port contracts without real infrastructure. Tests run fast. Tests run independently. Tests verify business logic.

The structure we built is hexagonal architecture. Application at the center. Ports at the edges. Infrastructure outside, plugging in through adapters.

But we can't run the application yet. The ports have no implementations. We've defined the contracts. We haven't fulfilled them.

Next: adapters. Real databases. Real email. Real infrastructure. Without breaking the dependency rule we just established.

The architecture is in place. Now we make it real.
