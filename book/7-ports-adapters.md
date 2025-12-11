# Chapter 7: Ports & Adapters (Hexagonal Architecture)

We have use cases from Chapter 6. `BookClassUseCase` orchestrates the booking workflow. The Command/Result pattern gives us clear contracts. Transaction boundaries are explicit. The application layer is clean and focused.

But we have a critical problem that we identified at the end of Chapter 6.

## Where We Left Off

In Chapter 6, we built formalized use cases with clear structure:

```python
# application/use_cases/book_class_use_case.py
class BookClassUseCase:
    def __init__(self, member_repository, class_repository, 
                 booking_repository, notification_service):
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, command: BookClassCommand) -> BookingResult:
        # Load entities
        member = self.member_repository.get_by_id(command.member_id)
        fitness_class = self.class_repository.get_by_id(command.class_id)
        
        # Orchestrate domain logic
        member.deduct_credit()
        fitness_class.add_booking(command.member_id)
        booking = Booking(generate_id(), command.member_id, command.class_id)
        
        # Save changes
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # Notify
        self.notification_service.send_confirmation(member, fitness_class)
        
        return BookingResult(success=True, booking_id=booking.id)
```

**What works:**
- Clear orchestration logic
- Separated from domain business rules
- Structured Commands and Results
- Testable workflows

**The problem we identified:**
Use cases depend on **concrete implementations**:
- `SqliteMemberRepository` (specific database)
- `SMTPNotificationService` (specific email provider)

This creates cascading issues.

## The New Challenge (From Chapter 6)

Try to test this use case:

```python
def test_booking_deducts_credit():
    # Need a real database
    db = sqlite3.connect('test.db')
    member_repo = SqliteMemberRepository(db)
    class_repo = SqliteFitnessClassRepository(db)
    booking_repo = SqliteBookingRepository(db)
    
    # Need a real email service (or mock it, coupling test to implementation)
    email_service = SMTPNotificationService('localhost', 587)
    
    use_case = BookClassUseCase(member_repo, class_repo, booking_repo, email_service)
    
    # Now we can test... but we've set up a database and email server
    # just to verify that booking deducts a credit
```

To test a simple business rule, you need infrastructure. Database. Email server. Or you need mocks, which couple your tests to implementation details.

Now try to swap implementations:

```python
# Currently using SQLite
class BookClassUseCase:
    def __init__(self, member_repo, class_repo, booking_repo, notification):
        # What types are these? Nowhere specified.
        # They're concrete: SqliteMemberRepository, etc.
        self.member_repository = member_repo
        # ...
```

Want to switch from SQLite to PostgreSQL? You change the infrastructure, but because use cases **depend on concrete implementations**, you also have to change how you instantiate them. Want to use in-memory repositories for testing? Same problem.

The dependency points the wrong way:

```
Application Layer (BookClassUseCase)
        ↓ depends on
Infrastructure Layer (SqliteMemberRepository, SMTPNotificationService)
```

This is backwards. High-level policy (use cases) shouldn't depend on low-level details (database choice). Infrastructure should depend on application, not the other way around.

**Concrete problems this causes:**

1. **Can't test without infrastructure:** Every test needs database setup and cleanup
2. **Can't swap implementations easily:** Changing databases requires changing use cases
3. **Can't deploy flexibly:** Want to run in AWS Lambda with DynamoDB? Use cases are coupled to SQLite
4. **Violates dependency rule:** Application layer depends on infrastructure layer

The code is asking for abstraction. Not because abstractions are "clean," but because this coupling is making change expensive.

**We need ports and adapters.**

A **port** is an abstraction that defines **what** the application needs from infrastructure, without specifying **how** it's provided. An **adapter** is a concrete implementation that fulfills that contract using real infrastructure.

Use cases depend on ports (abstractions). Adapters implement ports (concrete infrastructure). Dependencies point inward.

This chapter does three things:

1. **Defines ports**—abstract interfaces that specify contracts between layers
2. **Implements adapters**—concrete classes that connect to real infrastructure
3. **Wires everything together**—dependency injection that assembles a working system

By the end, you'll have a complete hexagonal architecture. Not just theory—a running application you can test, deploy, and extend.

## What Is a Port?

Remember Dependency Inversion from Chapter 2? We need abstractions so high-level code (application layer) doesn't depend on low-level code (infrastructure). 

A port is that abstraction. It's an interface that defines what the application needs, without specifying how it's provided.

Instead of this:

```
BookClassUseCase → PostgresMemberRepository (concrete)
```

We do this:

```
BookClassUseCase → MemberRepository (port/abstraction)
                            ↑
                PostgresMemberRepository (adapter)
```

The use case depends on the port. Infrastructure implements the port. Dependencies point inward.

A port is an abstract interface that defines **what** the application needs from infrastructure, without specifying **how** it's provided. In Python, a port is typically an ABC (Abstract Base Class) with abstract methods.

Ports define methods—the interface—but don't implement them. They declare what operations are available, not how they work.

Here's a repository port for member persistence:

```python
from abc import ABC, abstractmethod
from typing import Optional

from domain.entities import Member


class MemberRepository(ABC):
    """
    Repository port for member persistence.
    
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

Two methods: `get_by_id()` and `save()`. This is all the application needs.

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
    """Repository port for member persistence."""
    
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
    """Repository port for fitness class persistence."""
    
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
    """Repository port for booking persistence."""
    
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

**Note on Complex Queries:** As your repository ports grow, you may need more sophisticated querying capabilities—filtering by multiple criteria, sorting, pagination, or complex joins. For repositories with these needs, patterns like Specification or Query Objects can help keep your port interfaces clean while supporting rich queries. See **Appendix D: Repository Query Patterns** for detailed exploration of these advanced patterns.

One more repository—waitlist entries:

```python
from domain.entities import WaitlistEntry


class WaitlistRepository(ABC):
    """Repository port for waitlist persistence."""
    
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
    """Repository port for member persistence."""
    
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
    """Repository port for fitness class persistence."""
    
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
    """Repository port for booking persistence."""
    
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
    """Repository port for waitlist persistence."""
    
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


**Project Evolution:**
- In Chapter 1, our code was tightly coupled to SQLite
- In Chapter 2, we separated classes but they still knew about databases
- In Chapter 3, we wrote tests but they required real infrastructure
- In Chapter 4, we created layers but dependencies pointed the wrong way
- In Chapter 5, we built a rich domain but use cases depended on concrete repositories
- In Chapter 6, we created use cases but couldn't test them without databases
- Now in Chapter 7, we've inverted dependencies with ports—use cases depend on abstractions, adapters implement them
- This change enables fast tests, swappable infrastructure, and true separation of concerns
        
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
        
        # 2. Check if there's space
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
    """In-memory repository adapter for testing."""
    
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
    membership = MembershipType.PREMIUM
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
    membership = MembershipType.PREMIUM
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

Our application is well-structured. Use cases depend on ports. Ports define clean contracts. Dependencies point inward. But we can't run it. The ports are abstract base classes—you can't instantiate `MemberRepository()` or `NotificationService()`. We've defined the contracts. We haven't fulfilled them.

This is deliberate. The architecture forces us to provide real implementations. We can't skip infrastructure. We need concrete adapters that implement these ports using actual databases, email services, and APIs. That's what we're going to build in the next section.

## When You Don't Need Ports

Ports add indirection. They add files. They add abstraction. Before you define ports for everything, ask: do you need them?

**You don't need ports if:**

- You have a single, stable infrastructure that will never change (e.g., a company-mandated database)
- Your application is small and simple (< 500 lines, a few operations)
- You're building a proof-of-concept that might be thrown away
- The infrastructure IS your application (e.g., a database migration script)
- You only have one implementation and no plans for alternatives
- Testing with real infrastructure is fast and easy
- Your team is unfamiliar with abstraction and the learning curve is too steep

In these cases, **depending directly on concrete infrastructure is fine:**

```python
# No port needed - just use the repository directly
from infrastructure.sqlite_member_repository import SqliteMemberRepository

class BookClassUseCase:
    def __init__(self):
        self.member_repo = SqliteMemberRepository('gym.db')
    
    def execute(self, member_id: str, class_id: str):
        member = self.member_repo.get_by_id(member_id)
        # ...
```

Simple. Direct. No abstraction overhead. If you're never swapping SQLite for PostgreSQL, why abstract it?

**You DO need ports when you see these signals:**

- You want to test use cases without infrastructure setup
- You need to support multiple implementations (SQLite for dev, PostgreSQL for prod)
- Infrastructure is slow and makes tests painful
- You might migrate databases or services in the future
- You're deploying to different environments with different infrastructure
- Use cases are hard to test because of infrastructure coupling
- You're building a library or framework that others will integrate with different backends

These signals indicate that coupling to concrete infrastructure is causing pain.

**Common misconception:** "Ports are always better because they're more flexible."

Not true. Flexibility has a cost. More files. More indirection. More concepts to understand. If you don't need the flexibility, you're paying for nothing.

**The right approach:** Start without ports. Depend directly on concrete implementations. When you feel the pain of coupling (hard to test, hard to swap, hard to deploy), introduce ports. Let the need emerge from real problems, not theoretical ones.

We created ports for `MemberRepository` and `NotificationService` because we demonstrated concrete pain: couldn't test without database, couldn't swap implementations, violated dependency rule. If we only ever used SQLite and never tested, we might not need the abstraction yet.

**One exception:** If you're building a system that will definitely need multiple implementations (documented requirement, not speculation), start with ports. But be honest about "definitely."

Architecture responds to reality. Start simple. Abstract when it hurts.

## Ports: A Checkpoint

We've completed the first half of this chapter. Let's recap what we've built before moving on to adapters.

Use cases need infrastructure. But depending on infrastructure violates the dependency rule.

The solution is ports—abstractions that define what the application needs without specifying how it's provided. Ports are contracts expressed as abstract base classes or protocols.

We defined repository ports for persistence: `MemberRepository`, `FitnessClassRepository`, `BookingRepository`, `WaitlistRepository`. Each port declares the methods the application needs—load, save, query—without implementation.

We defined service ports for external concerns: `NotificationService` for sending emails, `PaymentService` for processing payments. Again, just contracts.

We refactored our use cases from earlier in this chapter to depend on these ports. The constructors now accept `MemberRepository`, not concrete implementations. The imports changed from infrastructure to ports. But the logic stayed the same.

This inverts dependencies. High-level policy (use cases) no longer depends on low-level details (databases, email). Both depend on abstractions (ports).

Testing became trivial. We created fake implementations—`InMemoryMemberRepository`, `FakeNotificationService`—that fulfill the port contracts without real infrastructure. Tests run fast. Tests run independently. Tests verify business logic.

The structure we built is hexagonal architecture. Application at the center. Ports at the edges. Infrastructure outside, plugging in through adapters.

But we can't run the application yet. The ports have no implementations. We've defined the contracts. We haven't fulfilled them.

The dependencies are inverted. The use cases depend on abstractions, not concrete implementations. This solves the testing problem and the flexibility problem.

But it creates a new problem: we can't run the application.

Try to create a use case:

```python
# Try to create a use case
use_case = BookClassUseCase(
    member_repository=MemberRepository(),  # Error: Can't instantiate abstract class
    class_repository=FitnessClassRepository(),  # Error: Can't instantiate abstract class
    booking_repository=BookingRepository(),  # Error: Can't instantiate abstract class
    notification_service=NotificationService()  # Error: Can't instantiate abstract class
)
```

Abstract classes can't be instantiated. Ports have no behaviour. They're interfaces, not implementations. We've defined what we need, but we haven't provided it.

**We can't run the application.** We can't execute a booking. We can't save data. We can't send notifications. The architecture is beautiful, but it does nothing.

This is the gap between design and reality. Ports define the contract. Adapters fulfill it.

**The second half of this chapter makes the system real.** We're going to implement adapters—concrete classes that plug into our ports and connect the application to infrastructure. SQLite databases. JSON files. SMTP email servers. Everything the application needs to work.

From abstract to concrete. From design to implementation. Let's build the adapters.

## Implementing Adapters

We've completed the first part of this chapter: defining ports and inverting dependencies. Now for the second part: building the concrete implementations that make the system work.

We've established the contracts—now we need to fulfill them. This is where **adapters** come in.

### What Is an Adapter?

An adapter is a concrete implementation of a port that translates between the application and infrastructure.

The application speaks in domain terms: `Member`, `Booking`, `FitnessClass`. Infrastructure speaks in technical terms: database rows, SQL queries, JSON payloads, SMTP protocols.

The adapter bridges the gap. It implements the port's contract using infrastructure primitives. It takes domain objects and persists them. It loads data and reconstructs domain objects. It translates between two worlds that don't understand each other.

Here's what that looks like for `MemberRepository`:

```python
# The port (defined earlier in this chapter)
class MemberRepository(ABC):
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def save(self, member: Member) -> None:
        pass

# The adapter (concrete implementation)
class SqliteMemberRepository(MemberRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        # SQL query to load member data
        # Reconstruct Member domain object
        pass
    
    def save(self, member: Member) -> None:
        # Extract data from Member
        # SQL query to persist it
        pass
```

The adapter inherits from the port. It implements the abstract methods. It knows about SQL and database sessions. But the use cases don't. They just see `MemberRepository`, the abstraction.

This is the adapter pattern. The port defines the interface the application expects. The adapter implements it using infrastructure the application knows nothing about.

### Building Repository Adapters

The beauty of ports and adapters is swappability. The application depends on `MemberRepository`, an abstraction. We can implement that abstraction with any persistence mechanism we want. SQLite. JSON files. In-memory dictionaries. PostgreSQL. The application doesn't care.

Why build multiple implementations? Because different contexts need different infrastructure. Tests need speed and isolation—in-memory is perfect. Local development needs persistence without external dependencies—JSON files work. Production needs reliability and scale—databases fit. Same port, different adapters, each optimized for its context.

To demonstrate this flexibility, we'll build three different repository adapters for the same port:

1. **In-memory repository adapter**: Simple dictionaries. Fast. Perfect for testing. Zero setup.
2. **JSON file repository adapter**: Persistent but simple. No external dependencies. Good for prototyping.
3. **SQLite repository adapter**: Real database using Python's standard library. Production-ready for small to medium apps.

Same repository port. Same contract. Three different adapter implementations. This is the power of the adapter pattern—choose the infrastructure that fits your needs without changing application code.

#### Implementation 1: In-Memory Repository

Why start here? Because it's the simplest. No files. No network. No setup. Just Python data structures. This makes it perfect for tests—fast, isolated, and predictable.

Let's build it:

```python
# infrastructure/persistence/in_memory_member_repository.py
from typing import Optional, List, Dict

from domain.entities import Member
from application.ports.repositories import MemberRepository


class InMemoryMemberRepository(MemberRepository):
    """
    In-memory repository adapter for MemberRepository port.
    
    Stores members in a dictionary. Fast and simple.
    Perfect for testing. Data doesn't persist across restarts.
    """
    
    def __init__(self):
        self._members: Dict[str, Member] = {}
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """Retrieve a member by ID."""
        return self._members.get(member_id)
    
    def save(self, member: Member) -> None:
        """Save a member to the in-memory store."""
        self._members[member.id] = member
    
    def find_by_email(self, email: str) -> Optional[Member]:
        """Find a member by email address."""
        for member in self._members.values():
            if member.email.value == email:
                return member
        return None
    
    def list_all(self) -> List[Member]:
        """Return all members."""
        return list(self._members.values())
```

No database. No SQL. No ORM. Just a Python dictionary. The adapter implements the port's interface using whatever infrastructure makes sense.

Why does this work? Because the use cases don't know how storage works. They call `repository.save(member)`. Could be a dictionary. Could be a file. Could be a database. The port abstracts it. The adapter implements it.

#### Implementation 2: JSON File Repository

In-memory is great for tests, but the data disappears when the program ends. What if you want persistence without installing a database? JSON files. Still simple. Still no dependencies. But your data survives restarts.

This is perfect for prototyping, small tools, or local development where you want to poke around the data in a text editor.

```python
# infrastructure/persistence/json_member_repository.py
import json
from typing import Optional, List
from pathlib import Path

from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType
from application.ports.repositories import MemberRepository


class JsonMemberRepository(MemberRepository):
    """
    JSON file repository adapter for MemberRepository port.
    
    Stores members as JSON in a file. Simple persistence.
    No external dependencies—just Python's standard library.
    """
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._ensure_file_exists()
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """Load a member from the JSON file."""
        data = self._read_file()
        member_data = data.get(member_id)
        
        if not member_data:
            return None
        
        return self._to_domain(member_data)
    
    def save(self, member: Member) -> None:
        """Save a member to the JSON file."""
        data = self._read_file()
        data[member.id] = self._to_dict(member)
        self._write_file(data)
    
    def find_by_email(self, email: str) -> Optional[Member]:
        """Find a member by email."""
        data = self._read_file()
        
        for member_data in data.values():
            if member_data['email'] == email:
                return self._to_domain(member_data)
        
        return None
    
    def list_all(self) -> List[Member]:
        """Return all members."""
        data = self._read_file()
        return [self._to_domain(m) for m in data.values()]
    
    def _ensure_file_exists(self) -> None:
        """Create the JSON file if it doesn't exist."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_file({})
    
    def _read_file(self) -> dict:
        """Read and parse the JSON file."""
        with open(self.file_path, 'r') as f:
            return json.load(f)
    
    def _write_file(self, data: dict) -> None:
        """Write data to the JSON file."""
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _to_domain(self, data: dict) -> Member:
        """Convert JSON data to a Member entity."""
        email = EmailAddress(data['email'])
        membership = MembershipType(
            name=data['membership_type'],
            credits_per_month=data['membership_credits_per_month'],
            price=data['membership_price']
        )
        
        member = Member(
            member_id=data['id'],
            name=data['name'],
            email=email,
            membership_type=membership
        )
        
        # Restore credit state
        member._credits = data['credits']
        
        return member
    
    def _to_dict(self, member: Member) -> dict:
        """Convert a Member entity to JSON-serializable dict."""
        return {
            'id': member.id,
            'name': member.name,
            'email': member.email.value,
            'credits': member.credits,
            'membership_type': member.membership_type.name,
            'membership_price': member.membership_type.price,
            'membership_credits_per_month': member.membership_type.credits_per_month
        }
```

More infrastructure, same interface. The adapter handles file I/O. It serializes domain objects to JSON and deserializes them back. The application layer doesn't know this is happening. It just sees `MemberRepository`.

Notice the translation methods: `_to_domain()` and `_to_dict()`. They're the bridge between domain objects and JSON data. This translation is the adapter's job. Every adapter needs it. The specifics depend on the infrastructure—JSON needs dicts, databases need rows, APIs need HTTP.

#### Implementation 3: SQLite Repository

JSON files work for small data sets, but they get slow when you have thousands of records. Every query loads the entire file. Plus, no transactions, no concurrent writes, no SQL queries.

Time for a real database. SQLite is perfect here—it's included in Python, requires no server setup, and gives us proper database features. Production-ready for small to medium applications.

Now let's use a real database with Python's built-in `sqlite3` module:

```python
# infrastructure/persistence/sqlite_member_repository.py
import sqlite3
from typing import Optional, List

from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType
from application.ports.repositories import MemberRepository


class SqliteMemberRepository(MemberRepository):
    """
    SQLite repository adapter for MemberRepository port.
    
    Uses Python's built-in sqlite3 module. No external dependencies.
    Suitable for development and small-to-medium production deployments.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._create_table()
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """Load a member from the database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM members WHERE id = ?",
            (member_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._to_domain(row)
    
    def save(self, member: Member) -> None:
        """Save a member to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if member exists
        cursor.execute("SELECT id FROM members WHERE id = ?", (member.id,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update existing
            cursor.execute(
                """
                UPDATE members 
                SET name = ?, email = ?, credits = ?, 
                    membership_type = ?, membership_price = ?, 
                    membership_credits_per_month = ?
                WHERE id = ?
                """,
                (
                    member.name,
                    member.email.value,
                    member.credits,
                    member.membership_type.name,
                    member.membership_type.price,
                    member.membership_type.credits_per_month,
                    member.id
                )
            )
        else:
            # Insert new
            cursor.execute(
                """
                INSERT INTO members 
                (id, name, email, credits, membership_type, 
                 membership_price, membership_credits_per_month)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member.id,
                    member.name,
                    member.email.value,
                    member.credits,
                    member.membership_type.name,
                    member.membership_type.price,
                    member.membership_type.credits_per_month
                )
            )
        
        conn.commit()
        conn.close()
    
    def find_by_email(self, email: str) -> Optional[Member]:
        """Find a member by email."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM members WHERE email = ?",
            (email,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._to_domain(row)
    
    def list_all(self) -> List[Member]:
        """Return all members."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM members")
        rows = cursor.fetchall()
        conn.close()
        
        return [self._to_domain(row) for row in rows]
    
    def _create_table(self) -> None:
        """Create the members table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                credits INTEGER NOT NULL DEFAULT 0,
                membership_type TEXT NOT NULL,
                membership_price REAL NOT NULL,
                membership_credits_per_month INTEGER NOT NULL
            )
            """
        )
        
        conn.commit()
        conn.close()
    
    def _to_domain(self, row: sqlite3.Row) -> Member:
        """Convert a database row to a Member entity."""
        email = EmailAddress(row['email'])
        membership = MembershipType(
            name=row['membership_type'],
            credits_per_month=row['membership_credits_per_month'],
            price=row['membership_price']
        )
        
        member = Member(
            member_id=row['id'],
            name=row['name'],
            email=email,
            membership_type=membership
        )
        
        # Restore credit state
        member._credits = row['credits']
        
        return member
```

This is a real database adapter. SQL queries. Transactions. Row mapping. But the interface is identical to the in-memory and JSON versions.

Look at the pattern:

1. **Infrastructure details in the adapter**: Connection management, SQL, row mapping.
2. **Domain translation**: `_to_domain()` reconstructs domain objects from database rows.
3. **Port implementation**: Same methods as the other adapters.

The application doesn't know which implementation it's using. It just knows `MemberRepository`.

#### The Power of Swappability

Here's the remarkable thing. This code:

```python
# application/use_cases/register_member.py
class RegisterMember:
    def __init__(self, member_repository: MemberRepository):
        self.member_repository = member_repository
    
    def execute(self, name: str, email: str, membership_type: str):
        # ... domain logic ...
        self.member_repository.save(member)
```

Works with all three adapters. You can swap them at runtime:

```python
# Using in-memory for testing
repository = InMemoryMemberRepository()
use_case = RegisterMember(repository)

# Using JSON for simple persistence
repository = JsonMemberRepository("data/members.json")
use_case = RegisterMember(repository)

# Using SQLite for production
repository = SqliteMemberRepository("data/gym.db")
use_case = RegisterMember(repository)
```

Same use case. Same domain logic. Different infrastructure. This is architectural flexibility.

You can start with in-memory for development. Switch to JSON when you need persistence. Move to SQLite when you need queries. Eventually migrate to PostgreSQL if you need scale. The use cases don't change. The domain doesn't change. Only the adapter changes.

This is why we inverted the dependencies.

### Implementing Service Adapters

Repositories aren't the only infrastructure concern. We also need service adapters for notifications, payments, and external APIs.

Let's implement the notification service using SMTP:

```python
# infrastructure/services/email_notification_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from application.ports.services import NotificationService


class SMTPNotificationService(NotificationService):
    """
    Adapter implementing NotificationService using SMTP.
    
    Sends actual emails via SMTP server.
    """
    
    def __init__(self, smtp_host: str, smtp_port: int, 
                 username: str, password: str, from_email: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
    
    def send_booking_confirmation(self, email: str, name: str,
                                  class_name: str, time_slot) -> None:
        """Send booking confirmation email."""
        subject = f"Booking Confirmed: {class_name}"
        body = f"""
        Hi {name},
        
        Your booking for {class_name} has been confirmed!
        
        Class Details:
        - Name: {class_name}
        - Day: {time_slot.day.name}
        - Time: {time_slot.start_time.strftime('%H:%M')} - {time_slot.end_time.strftime('%H:%M')}
        
        We look forward to seeing you there!
        
        Best regards,
        Your Fitness Team
        """
        
        self._send_email(email, subject, body)
    
    def send_cancellation_confirmation(self, email: str, name: str,
                                       class_name: str, time_slot) -> None:
        """Send cancellation confirmation email."""
        subject = f"Booking Cancelled: {class_name}"
        body = f"""
        Hi {name},
        
        Your booking for {class_name} has been cancelled.
        
        Your credit has been refunded to your account.
        
        Best regards,
        Your Fitness Team
        """
        
        self._send_email(email, subject, body)
    
    def send_waitlist_confirmation(self, email: str, name: str,
                                   class_name: str) -> None:
        """Send waitlist confirmation."""
        subject = f"Added to Waitlist: {class_name}"
        body = f"""
        Hi {name},
        
        You've been added to the waitlist for {class_name}.
        
        We'll notify you if a spot becomes available.
        
        Best regards,
        Your Fitness Team
        """
        
        self._send_email(email, subject, body)
    
    def send_waitlist_booking_confirmation(self, email: str, name: str,
                                          class_name: str, time_slot) -> None:
        """Send notification that waitlist member got into class."""
        subject = f"You're In! Booking Confirmed: {class_name}"
        body = f"""
        Hi {name},
        
        Great news! A spot opened up in {class_name} and you've been booked in!
        
        Class Details:
        - Name: {class_name}
        - Day: {time_slot.day.name}
        - Time: {time_slot.start_time.strftime('%H:%M')} - {time_slot.end_time.strftime('%H:%M')}
        
        We look forward to seeing you there!
        
        Best regards,
        Your Fitness Team
        """
        
        self._send_email(email, subject, body)
    
    def send_waitlist_insufficient_credits(self, email: str, name: str,
                                          class_name: str) -> None:
        """Notify member they were skipped due to insufficient credits."""
        subject = f"Waitlist Update: {class_name}"
        body = f"""
        Hi {name},
        
        A spot opened up in {class_name}, but you don't have enough credits.
        
        Please add credits to your account to book classes.
        
        Best regards,
        Your Fitness Team
        """
        
        self._send_email(email, subject, body)
    
    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """Internal method to send email via SMTP."""
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
        except Exception as e:
            # In production, you'd want proper error handling and logging
            print(f"Failed to send email to {to_email}: {e}")
            raise
```

The adapter implements the port using SMTP. It knows about email protocols, MIME messages, and SMTP servers. The use cases don't. They just call `send_booking_confirmation()` and trust the infrastructure to handle it.

For development and testing, you might want a simpler implementation:

```python
# infrastructure/services/console_notification_service.py
from application.ports.services import NotificationService


class ConsoleNotificationService(NotificationService):
    """
    Adapter that prints notifications to console instead of sending emails.
    
    Useful for development and testing.
    """
    
    def send_booking_confirmation(self, email: str, name: str,
                                  class_name: str, time_slot) -> None:
        print(f"[EMAIL] To: {email}")
        print(f"[EMAIL] Subject: Booking Confirmed: {class_name}")
        print(f"[EMAIL] Hi {name}, your booking for {class_name} is confirmed!")
        print(f"[EMAIL] Time: {time_slot.day.name} at {time_slot.start_time}")
        print()
    
    def send_cancellation_confirmation(self, email: str, name: str,
                                       class_name: str, time_slot) -> None:
        print(f"[EMAIL] To: {email}")
        print(f"[EMAIL] Subject: Booking Cancelled: {class_name}")
        print(f"[EMAIL] Hi {name}, your booking for {class_name} has been cancelled.")
        print()
    
    def send_waitlist_confirmation(self, email: str, name: str,
                                   class_name: str) -> None:
        print(f"[EMAIL] To: {email}")
        print(f"[EMAIL] Subject: Added to Waitlist: {class_name}")
        print(f"[EMAIL] Hi {name}, you're on the waitlist for {class_name}.")
        print()
    
    def send_waitlist_booking_confirmation(self, email: str, name: str,
                                          class_name: str, time_slot) -> None:
        print(f"[EMAIL] To: {email}")
        print(f"[EMAIL] Subject: You're In! {class_name}")
        print(f"[EMAIL] Hi {name}, you got off the waitlist and into {class_name}!")
        print()
    
    def send_waitlist_insufficient_credits(self, email: str, name: str,
                                          class_name: str) -> None:
        print(f"[EMAIL] To: {email}")
        print(f"[EMAIL] Subject: Insufficient Credits")
        print(f"[EMAIL] Hi {name}, you don't have enough credits for {class_name}.")
        print()
```

Same port. Different adapter. One sends real emails. One prints to console. The use cases don't know or care.

This is the power of ports and adapters. Swap implementations without changing application logic.

### In-Memory Adapters for Testing

We've built several repository adapters (JSON files, SQLite databases) and service adapters (SMTP email). These are production adapters—they connect to real infrastructure.

But we also need test adapters. In the first half of this chapter, we used simple in-memory implementations to test our use cases. Those were adapters too, just optimized for a different purpose.

In-memory adapters are particularly valuable for testing because they:

1. **Run fast**: No I/O, no database setup
2. **Are isolated**: Each test starts with a clean state
3. **Are simple**: Easy to understand and debug
4. **Support test-specific methods**: Like `clear()` for cleanup

Let's formalize these test adapters as proper production code. They're infrastructure implementations, just like SQLite or SMTP—but their "infrastructure" is memory, not external systems.

```python
# infrastructure/adapters/in_memory/member_repository.py
from typing import Dict, Optional, List

from domain.entities import Member
from application.ports.repositories import MemberRepository


class InMemoryMemberRepository(MemberRepository):
    """
    In-memory repository adapter for MemberRepository port.
    
    Optimized for testing with additional helper methods.
    """
    
    def __init__(self):
        self._members: Dict[str, Member] = {}
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)
    
    def save(self, member: Member) -> None:
        # Store a copy to avoid external mutations
        self._members[member.id] = member
    
    def find_by_email(self, email: str) -> Optional[Member]:
        for member in self._members.values():
            if member.email.value == email:
                return member
        return None
    
    def list_all(self) -> List[Member]:
        return list(self._members.values())
    
    def clear(self) -> None:
        """Utility method for tests to reset state."""
        self._members.clear()
```

In-memory adapters are simpler than database adapters. No ORM. No SQL. Just dictionaries. They implement the same port, so use cases can't tell the difference.

You use database adapters in production. You use in-memory adapters in tests. Same code. Different infrastructure.

Complete the set with booking and class repositories:

```python
# infrastructure/adapters/in_memory/booking_repository.py
from typing import Dict, Optional, List

from domain.entities import Booking, BookingStatus
from application.ports.repositories import BookingRepository


class InMemoryBookingRepository(BookingRepository):
    """In-memory repository adapter for BookingRepository port."""
    
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}
    
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        return self._bookings.get(booking_id)
    
    def save(self, booking: Booking) -> None:
        self._bookings[booking.id] = booking
    
    def find_by_member(self, member_id: str) -> List[Booking]:
        return [b for b in self._bookings.values() if b.member_id == member_id]
    
    def find_by_class(self, class_id: str) -> List[Booking]:
        return [b for b in self._bookings.values() if b.class_id == class_id]
    
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        for booking in self._bookings.values():
            if (booking.member_id == member_id and 
                booking.class_id == class_id):
                return booking
        return None
    
    def find_by_status(self, status: BookingStatus) -> List[Booking]:
        return [b for b in self._bookings.values() if b.status == status]
    
    def clear(self) -> None:
        self._bookings.clear()


# infrastructure/adapters/in_memory/class_repository.py
from typing import Dict, Optional, List

from domain.entities import FitnessClass
from domain.value_objects import TimeSlot
from application.ports.repositories import FitnessClassRepository


class InMemoryFitnessClassRepository(FitnessClassRepository):
    """In-memory repository adapter for FitnessClassRepository port."""
    
    def __init__(self):
        self._classes: Dict[str, FitnessClass] = {}
    
    def get_by_id(self, class_id: str) -> Optional[FitnessClass]:
        return self._classes.get(class_id)
    
    def save(self, fitness_class: FitnessClass) -> None:
        self._classes[fitness_class.id] = fitness_class
    
    def find_by_time_slot(self, time_slot: TimeSlot) -> List[FitnessClass]:
        result = []
        for cls in self._classes.values():
            if (cls.time_slot.day == time_slot.day and 
                cls.time_slot.start_time == time_slot.start_time):
                result.append(cls)
        return result
    
    def list_all(self) -> List[FitnessClass]:
        return list(self._classes.values())
    
    def clear(self) -> None:
        self._classes.clear()
```

Clean. Simple. Fast. No infrastructure dependencies. Perfect for tests.

### Wiring It All Together: Dependency Injection

We have ports. We have adapters. Now we need to connect them.

This is dependency injection—providing implementations to components that depend on abstractions. The use cases declare what they need via constructor parameters. Something external provides the concrete implementations.

Here's a simple composition root that wires everything together:

```python
# infrastructure/composition.py
from application.use_cases.book_class import BookClassUseCase
from application.use_cases.cancel_booking import CancelBookingUseCase
from application.use_cases.process_waitlist import ProcessWaitlistUseCase
from infrastructure.persistence.sqlite_member_repository import SqliteMemberRepository
from infrastructure.persistence.sqlite_booking_repository import SqliteBookingRepository
from infrastructure.persistence.sqlite_class_repository import SqliteFitnessClassRepository
from infrastructure.services.email_notification_service import SMTPNotificationService
from infrastructure.services.console_notification_service import ConsoleNotificationService


class ApplicationContainer:
    """
    Dependency injection container.
    
    Wires together all the pieces of the application.
    Provides configured use cases ready to execute.
    """
    
    def __init__(self, db_path: str, use_real_email: bool = False):
        # Create repository adapters using SQLite
        self.member_repository = SqliteMemberRepository(db_path)
        self.booking_repository = SqliteBookingRepository(db_path)
        self.class_repository = SqliteFitnessClassRepository(db_path)
        
        # Create service adapters
        if use_real_email:
            self.notification_service = SMTPNotificationService(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                username="your-email@gmail.com",
                password="your-password",
                from_email="noreply@yourfitness.com"
            )
        else:
            self.notification_service = ConsoleNotificationService()
    
    def book_class_use_case(self) -> BookClassUseCase:
        """Create a fully-wired BookClassUseCase."""
        return BookClassUseCase(
            member_repository=self.member_repository,
            class_repository=self.class_repository,
            booking_repository=self.booking_repository,
            notification_service=self.notification_service
        )
    
    def cancel_booking_use_case(self) -> CancelBookingUseCase:
        """Create a fully-wired CancelBookingUseCase."""
        return CancelBookingUseCase(
            booking_repository=self.booking_repository,
            member_repository=self.member_repository,
            class_repository=self.class_repository,
            notification_service=self.notification_service
        )
    
    def process_waitlist_use_case(self) -> ProcessWaitlistUseCase:
        """Create a fully-wired ProcessWaitlistUseCase."""
        # Note: We'd need a WaitlistRepository adapter too
        return ProcessWaitlistUseCase(
            waitlist_repository=None,  # Would wire this up
            member_repository=self.member_repository,
            class_repository=self.class_repository,
            booking_repository=self.booking_repository,
            notification_service=self.notification_service
        )
    
    def cleanup(self):
        """Clean up resources (not needed for SQLite, but good practice)."""
        pass
```

The container creates everything in the right order. Database session first. Repositories next. Services after that. Use cases last.

Each use case gets the adapters it needs. The use cases don't create their dependencies. They receive them. This is dependency injection.

Now you can run the application:

```python
# main.py
from infrastructure.composition import ApplicationContainer


def main():
    # Create the container with production configuration
    container = ApplicationContainer(
        db_path="data/gym.db",
        use_real_email=False  # Use console notifications for now
    )
    
    try:
        # Get a use case
        book_class = container.book_class_use_case()
        
        # Execute it
        booking = book_class.execute(
            member_id="M001",
            class_id="C001"
        )
        
        print(f"Booking created: {booking.id}")
        print(f"Status: {booking.status}")
        
    finally:
        container.cleanup()


if __name__ == "__main__":
    main()
```

That's a working application. Load members from a database. Book them into classes. Send notifications. All through clean abstractions.

### Testing with Different Adapters

The power of this architecture shows in testing. You can test use cases with fast, in-memory adapters:

```python
# tests/test_book_class_use_case.py
import pytest
from datetime import time

from domain.entities import Member, FitnessClass
from domain.value_objects import EmailAddress, MembershipType, ClassCapacity, TimeSlot, DayOfWeek
from domain.exceptions import ClassFullException, InsufficientCreditsException
from application.use_cases.book_class import BookClassUseCase
from infrastructure.adapters.in_memory.member_repository import InMemoryMemberRepository
from infrastructure.adapters.in_memory.booking_repository import InMemoryBookingRepository
from infrastructure.adapters.in_memory.class_repository import InMemoryFitnessClassRepository
from infrastructure.services.console_notification_service import ConsoleNotificationService


class TestBookClassUseCase:
    """Test BookClassUseCase with in-memory adapters."""
    
    def setup_method(self):
        """Set up test fixtures before each test."""
        self.member_repo = InMemoryMemberRepository()
        self.class_repo = InMemoryFitnessClassRepository()
        self.booking_repo = InMemoryBookingRepository()
        self.notifications = ConsoleNotificationService()
        
        self.use_case = BookClassUseCase(
            member_repository=self.member_repo,
            class_repository=self.class_repo,
            booking_repository=self.booking_repo,
            notification_service=self.notifications
        )
    
    def test_successful_booking(self):
        """Test booking a member into a class successfully."""
        # Arrange: Create test data
        email = EmailAddress("sarah@example.com")
        membership = MembershipType.PREMIUM
        member = Member("M001", "Sarah", email, membership)
        
        capacity = ClassCapacity(15)
        time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))
        yoga_class = FitnessClass("C001", "Yoga", capacity, time_slot)
        
        self.member_repo.save(member)
        self.class_repo.save(yoga_class)
        
        # Act: Execute the use case
        booking = self.use_case.execute("M001", "C001")
        
        # Assert: Verify the outcome
        assert booking is not None
        assert booking.member_id == "M001"
        assert booking.class_id == "C001"
        
        # Verify member credits were deducted
        updated_member = self.member_repo.get_by_id("M001")
        assert updated_member.credits == 9
        
        # Verify class has the booking
        updated_class = self.class_repo.get_by_id("C001")
        assert updated_class.booking_count() == 1
    
    def test_booking_fails_when_class_is_full(self):
        """Test that booking fails when class is at capacity."""
        # Arrange
        email = EmailAddress("sarah@example.com")
        membership = MembershipType.PREMIUM
        member = Member("M001", "Sarah", email, membership)
        
        # Create a class with capacity of 1 and fill it
        capacity = ClassCapacity(1)
        time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))
        yoga_class = FitnessClass("C001", "Yoga", capacity, time_slot)
        yoga_class.add_booking("OTHER_MEMBER")
        
        self.member_repo.save(member)
        self.class_repo.save(yoga_class)
        
        # Act & Assert
        with pytest.raises(ClassFullException):
            self.use_case.execute("M001", "C001")
    
    def test_booking_fails_when_member_has_no_credits(self):
        """Test that booking fails when member has no credits."""
        # Arrange
        email = EmailAddress("sarah@example.com")
        membership = MembershipType.PREMIUM
        member = Member("M001", "Sarah", email, membership)
        member._credits = 0  # Deplete credits
        
        capacity = ClassCapacity(15)
        time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))
        yoga_class = FitnessClass("C001", "Yoga", capacity, time_slot)
        
        self.member_repo.save(member)
        self.class_repo.save(yoga_class)
        
        # Act & Assert
        with pytest.raises(InsufficientCreditsException):
            self.use_case.execute("M001", "C001")
```

These tests run in milliseconds. No database. No network. Just pure logic verification.

You can also write integration tests with real database adapters:

```python
# tests/integration/test_database_repositories.py
import pytest
import tempfile
import os

from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType
from infrastructure.persistence.sqlite_member_repository import SqliteMemberRepository


class TestSqliteMemberRepository:
    """Integration tests for SQLite repository."""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Create a test database before each test."""
        # Use a temporary file for testing
        self.db_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.db_file.name
        self.db_file.close()
        
        self.repository = SqliteMemberRepository(self.db_path)
        
        yield
        
        # Clean up
        os.unlink(self.db_path)
    
    def test_save_and_retrieve_member(self):
        """Test that we can save and retrieve a member."""
        # Arrange
        email = EmailAddress("sarah@example.com")
        membership = MembershipType.PREMIUM
        member = Member("M001", "Sarah", email, membership)
        
        # Act
        self.repository.save(member)
        retrieved = self.repository.get_by_id("M001")
        
        # Assert
        assert retrieved is not None
        assert retrieved.id == "M001"
        assert retrieved.name == "Sarah"
        assert retrieved.email.value == "sarah@example.com"
        assert retrieved.credits == 10
    
    def test_find_by_email(self):
        """Test finding a member by email."""
        # Arrange
        email = EmailAddress("sarah@example.com")
        membership = MembershipType.PREMIUM
        member = Member("M001", "Sarah", email, membership)
        self.repository.save(member)
        
        # Act
        found = self.repository.find_by_email("sarah@example.com")
        
        # Assert
        assert found is not None
        assert found.id == "M001"
```

Same port. Different adapters. Tests for both.

### A Complete Running Example

Let's build a simple CLI application that demonstrates everything working together:

```python
# cli.py
from datetime import time
from infrastructure.composition import ApplicationContainer
from domain.entities import Member, FitnessClass
from domain.value_objects import EmailAddress, MembershipType, ClassCapacity, TimeSlot, DayOfWeek


def setup_database(db_path: str):
    """Create database tables (SQLite creates them automatically)."""
    # SQLite repositories create tables in __init__
    # Just ensure the directory exists
    import os
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)


def seed_data(container: ApplicationContainer):
    """Add some initial test data."""
    # Create a member
    email = EmailAddress("sarah@example.com")
    membership = MembershipType.PREMIUM
    member = Member("M001", "Sarah", email, membership)
    container.member_repository.save(member)
    
    # Create a class
    capacity = ClassCapacity(15)
    time_slot = TimeSlot(DayOfWeek.MONDAY, time(10, 0), time(11, 0))
    yoga_class = FitnessClass("C001", "Morning Yoga", capacity, time_slot)
    container.class_repository.save(yoga_class)
    
    print("Test data created:")
    print(f"  Member: {member.name} ({member.email.value})")
    print(f"  Class: {yoga_class.name}")
    print()


def main():
    """Run the CLI application."""
    database_path = "fitness.db"
    
    # Set up database
    print("Setting up database...")
    setup_database(database_path)
    
    # Create application container
    container = ApplicationContainer(
        database_url=database_path,
        use_real_email=False
    )
    
    try:
        # Seed test data
        seed_data(container)
        
        # Get the use case
        book_class = container.book_class_use_case()
        
        # Book the member into the class
        print("Booking Sarah into Morning Yoga...")
        booking = book_class.execute("M001", "C001")
        
        print(f"✓ Booking successful!")
        print(f"  Booking ID: {booking.id}")
        print(f"  Status: {booking.status.value}")
        print()
        
        # Verify the state
        member = container.member_repository.get_by_id("M001")
        print(f"Member credits remaining: {member.credits}")
        
        yoga_class = container.class_repository.get_by_id("C001")
        print(f"Class booking count: {yoga_class.booking_count()}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        container.cleanup()


if __name__ == "__main__":
    main()
```

Run this and you'll see:

```
Setting up database...
Test data created:
  Member: Sarah (sarah@example.com)
  Class: Morning Yoga

Booking Sarah into Morning Yoga...
[EMAIL] To: sarah@example.com
[EMAIL] Subject: Booking Confirmed: Morning Yoga
[EMAIL] Hi Sarah, your booking for Morning Yoga is confirmed!
[EMAIL] Time: MONDAY at 10:00:00

✓ Booking successful!
  Booking ID: 550e8400-e29b-41d4-a716-446655440000
  Status: confirmed

Member credits remaining: 9
Class booking count: 1
```

The complete system working. Domain logic enforcing rules. Application layer orchestrating workflows. Infrastructure adapters handling persistence and notifications. All wired together through dependency injection.

From abstract ports to concrete adapters to a running application.

### Directory Structure

Here's what your complete codebase looks like now:

```
gym-booking/
├── domain/
│   ├── __init__.py
│   ├── entities.py           # Member, FitnessClass, Booking
│   ├── value_objects.py      # EmailAddress, TimeSlot, etc.
│   ├── exceptions.py         # Domain exceptions
│   └── services.py           # Domain services if needed
│
├── application/
│   ├── __init__.py
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── repositories.py   # Repository ports
│   │   └── services.py       # Service ports
│   └── use_cases/
│       ├── __init__.py
│       ├── book_class.py
│       ├── cancel_booking.py
│       └── process_waitlist.py
│
├── infrastructure/
│   ├── __init__.py
│   ├── composition.py        # Dependency injection container
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── in_memory_member_repository.py
│   │   ├── json_member_repository.py
│   │   ├── sqlite_member_repository.py
│   │   ├── sqlite_booking_repository.py
│   │   └── sqlite_class_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── email_notification_service.py
│   │   └── console_notification_service.py
│   └── adapters/
│       └── in_memory/
│           ├── __init__.py
│           ├── member_repository.py
│           ├── booking_repository.py
│           └── class_repository.py
│
├── tests/
│   ├── unit/
│   │   └── test_book_class_use_case.py
│   └── integration/
│       └── test_database_repositories.py
│
├── cli.py                    # Command-line interface
└── main.py                   # Application entry point
```

Every layer has its place. Domain at the core. Application orchestrating. Infrastructure on the outside. Dependencies pointing inward.

### Handling Errors in Adapters

Adapters sit at the boundary between your application and external systems. Networks fail. Databases go down. APIs return errors. Email servers timeout. Adapters need to handle all of this gracefully and translate failures into exceptions that the application layer can understand and respond to appropriately.

#### The Three Categories of Adapter Errors

Adapters encounter three types of errors:

1. **Infrastructure failures:** Database down, network timeout, disk full
2. **Data quality issues:** Invalid data from database, API returning malformed responses
3. **Domain validation failures:** Data that violates business rules when reconstructing domain objects

Each category requires different handling.

#### Infrastructure Exceptions

Define infrastructure-specific exceptions that represent technical failures:

```python
# infrastructure/exceptions.py

class InfrastructureException(Exception):
    """Base exception for all infrastructure-related errors."""
    pass


class RepositoryException(InfrastructureException):
    """Raised when repository operations fail."""
    pass


class ConnectionException(RepositoryException):
    """Raised when database connection fails."""
    pass


class PersistenceException(RepositoryException):
    """Raised when saving or updating data fails."""
    pass


class NotificationException(InfrastructureException):
    """Raised when notification delivery fails."""
    pass


class ExternalServiceException(InfrastructureException):
    """Raised when external API calls fail."""
    pass
```

These exceptions communicate *how* something failed (infrastructure), not *what* business rule was violated (domain).

#### Handling Database Errors in Repository Adapters

Repository adapters should catch database-specific exceptions and translate them to infrastructure exceptions:

```python
# infrastructure/persistence/sqlite_member_repository.py
import sqlite3
import logging
from typing import Optional

from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType
from domain.exceptions import InvalidEmailException
from application.ports.repositories import MemberRepository
from infrastructure.exceptions import RepositoryException, ConnectionException, PersistenceException

logger = logging.getLogger(__name__)


class SqliteMemberRepository(MemberRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        try:
            self._create_table()
        except sqlite3.Error as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise ConnectionException(f"Cannot connect to database at {db_path}: {e}")
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """
        Retrieve a member by ID.
        
        Returns:
            Member if found, None otherwise
            
        Raises:
            ConnectionException: If database connection fails
            RepositoryException: If query fails for other reasons
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM members WHERE id = ?", (member_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Convert database row to domain object
            try:
                return self._to_domain(row)
            except (ValueError, InvalidEmailException) as e:
                # Database contains invalid data - this is a data quality issue
                logger.error(f"Invalid member data in database for ID {member_id}: {e}")
                # You could either return None or raise - depends on your error handling strategy
                raise RepositoryException(
                    f"Member {member_id} has invalid data in database: {e}"
                )
                
        except sqlite3.OperationalError as e:
            # Database file not accessible, permissions issue, etc.
            logger.error(f"Database connection error: {e}")
            raise ConnectionException(f"Cannot access database: {e}")
        except sqlite3.DatabaseError as e:
            # Corruption, malformed database, etc.
            logger.error(f"Database error retrieving member {member_id}: {e}")
            raise RepositoryException(f"Database error: {e}")
    
    def save(self, member: Member) -> None:
        """
        Persist a member to the database.
        
        Raises:
            PersistenceException: If save operation fails
            ConnectionException: If database connection fails
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if member exists
            cursor.execute("SELECT id FROM members WHERE id = ?", (member.id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing member
                cursor.execute(
                    """
                    UPDATE members 
                    SET name = ?, email = ?, credits = ?, 
                        membership_type = ?, membership_price = ?, 
                        membership_credits_per_month = ?
                    WHERE id = ?
                    """,
                    (
                        member.name,
                        member.email.value,
                        member.credits,
                        member.membership_type.name,
                        member.membership_type.price,
                        member.membership_type.credits_per_month,
                        member.id
                    )
                )
            else:
                # Insert new member
                cursor.execute(
                    """
                    INSERT INTO members 
                    (id, name, email, credits, membership_type, 
                     membership_price, membership_credits_per_month)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        member.id,
                        member.name,
                        member.email.value,
                        member.credits,
                        member.membership_type.name,
                        member.membership_type.price,
                        member.membership_type.credits_per_month
                    )
                )
            
            conn.commit()
            conn.close()
            
        except sqlite3.IntegrityError as e:
            # Unique constraint violation, foreign key violation, etc.
            logger.error(f"Integrity error saving member {member.id}: {e}")
            raise PersistenceException(
                f"Cannot save member {member.id}: data integrity violation"
            )
        except sqlite3.OperationalError as e:
            # Disk full, database locked, etc.
            logger.error(f"Operational error saving member {member.id}: {e}")
            raise ConnectionException(f"Database unavailable: {e}")
        except sqlite3.DatabaseError as e:
            # General database error
            logger.error(f"Database error saving member {member.id}: {e}")
            raise PersistenceException(f"Failed to save member: {e}")
    
    def _to_domain(self, row: sqlite3.Row) -> Member:
        """
        Convert a database row to a Member domain entity.
        
        This method can raise ValueError or domain exceptions if the data
        is invalid. The caller should catch these and decide how to handle them.
        """
        # Reconstruct value objects - these may raise exceptions
        email = EmailAddress(row['email'])  # May raise InvalidEmailException
        membership = MembershipType(
            name=row['membership_type'],
            credits_per_month=row['membership_credits_per_month'],
            price=row['membership_price']
        )
        
        # Reconstruct the entity
        member = Member(
            member_id=row['id'],
            name=row['name'],
            email=email,
            membership_type=membership
        )
        
        # Restore state that isn't in the constructor
        member._credits = row['credits']
        
        return member
    
    def _create_table(self) -> None:
        """Create the members table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                credits INTEGER NOT NULL DEFAULT 0,
                membership_type TEXT NOT NULL,
                membership_price REAL NOT NULL,
                membership_credits_per_month INTEGER NOT NULL
            )
            """
        )
        
        conn.commit()
        conn.close()
```

**Key principles:**

- **Catch database-specific exceptions:** SQLite raises `sqlite3.Error` and its subclasses
- **Translate to infrastructure exceptions:** Application layer shouldn't know about SQLite
- **Log with appropriate severity:** Critical for connection failures, error for data issues
- **Distinguish failure types:** Connection failures vs. data corruption vs. constraint violations
- **Handle data quality issues:** Invalid data from database should be logged and handled gracefully

#### Handling Service Failures with Retries

Service adapters (email, payment processors, external APIs) should implement retry logic for transient failures:

```python
# infrastructure/services/email_notification_service.py
import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from application.ports.services import NotificationService
from infrastructure.exceptions import NotificationException

logger = logging.getLogger(__name__)


class SMTPNotificationService(NotificationService):
    def __init__(self, smtp_host: str, smtp_port: int, 
                 username: str, password: str, from_email: str,
                 max_retries: int = 3):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.max_retries = max_retries
    
    def send_booking_confirmation(self, email: str, name: str,
                                   class_name: str, time_slot) -> None:
        """
        Send booking confirmation email with retry logic.
        
        Raises:
            NotificationException: If email fails after all retries
        """
        subject = f"Booking Confirmed: {class_name}"
        body = f"""
        Hi {name},
        
        Your booking for {class_name} has been confirmed!
        
        Class Details:
        - Name: {class_name}
        - Day: {time_slot.day.name}
        - Time: {time_slot.start_time.strftime('%H:%M')} - {time_slot.end_time.strftime('%H:%M')}
        
        We look forward to seeing you there!
        
        Best regards,
        Your Fitness Team
        """
        
        self._send_email_with_retry(email, subject, body)
    
    def _send_email_with_retry(self, to_email: str, subject: str, body: str) -> None:
        """
        Send email with exponential backoff retry logic.
        
        Transient errors (network timeouts, temporary server unavailability) are retried.
        Permanent errors (invalid email, authentication failure) fail immediately.
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                self._send_email(to_email, subject, body)
                if attempt > 0:
                    logger.info(
                        f"Email sent successfully on attempt {attempt + 1} to {to_email}"
                    )
                return  # Success
                
            except smtplib.SMTPAuthenticationError as e:
                # Permanent error - wrong credentials
                logger.error(f"SMTP authentication failed: {e}")
                raise NotificationException(f"Email authentication failed: {e}")
                
            except smtplib.SMTPRecipientsRefused as e:
                # Permanent error - invalid recipient
                logger.error(f"Invalid email recipient {to_email}: {e}")
                raise NotificationException(f"Invalid email address {to_email}: {e}")
                
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, 
                    TimeoutError, ConnectionError) as e:
                # Transient error - retry
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Email send failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Email send failed after {self.max_retries} attempts: {e}"
                    )
                    
            except smtplib.SMTPException as e:
                # Other SMTP errors
                last_exception = e
                logger.error(f"SMTP error sending to {to_email}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        # All retries exhausted
        raise NotificationException(
            f"Failed to send email to {to_email} after {self.max_retries} attempts: "
            f"{last_exception}"
        )
    
    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """Internal method to send a single email (no retry logic)."""
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
```

**Key principles:**

- **Distinguish transient from permanent failures:** Retry network errors, don't retry authentication failures
- **Implement exponential backoff:** Wait longer between each retry (1s, 2s, 4s)
- **Set reasonable retry limits:** 3 attempts is usually enough for transient failures
- **Log retry attempts:** Track which notifications are struggling
- **Raise infrastructure exceptions:** Let application layer decide if notification failure is critical

#### Converting Infrastructure Errors to Domain Exceptions

Sometimes infrastructure errors reveal domain constraint violations. When this happens, convert to domain exceptions:

```python
# infrastructure/persistence/sqlite_member_repository.py
from domain.exceptions import DuplicateEmailException

class SqliteMemberRepository(MemberRepository):
    def save(self, member: Member) -> None:
        try:
            # ... save logic ...
            cursor.execute("INSERT INTO members (...) VALUES (...)", ...)
            conn.commit()
            
        except sqlite3.IntegrityError as e:
            # Check if this is a unique constraint violation on email
            if 'UNIQUE constraint failed: members.email' in str(e):
                logger.warning(f"Duplicate email attempted: {member.email.value}")
                # This is actually a domain constraint violation
                raise DuplicateEmailException(
                    f"A member with email {member.email.value} already exists"
                )
            else:
                # Other integrity errors are infrastructure issues
                logger.error(f"Database integrity error: {e}")
                raise PersistenceException(f"Data integrity error: {e}")
```

**When to convert:**

- **Database unique constraints represent business rules:** Duplicate email is a domain concept
- **Foreign key violations represent domain relationships:** Can't book non-existent class
- **Data type mismatches reveal validation failures:** String too long is a domain constraint

**When not to convert:**

- **Connection failures are infrastructure:** Database down isn't a business rule violation
- **Timeout errors are infrastructure:** Network slow isn't a domain concept
- **Disk full errors are infrastructure:** Storage issues aren't business logic

#### Circuit Breaker Pattern for External Services

For frequently-called external services, implement a circuit breaker to avoid cascading failures:

```python
# infrastructure/services/payment_service.py
import time
import logging
from enum import Enum
from typing import Optional

from application.ports.services import PaymentService
from infrastructure.exceptions import ExternalServiceException

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures when external service is down.
    
    - CLOSED: Normal operation, requests go through
    - OPEN: Service failing, reject immediately without trying
    - HALF_OPEN: Testing if service recovered, allow one request
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # Seconds before trying again
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time: Optional[float] = None
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_failure_time >= self.timeout:
                logger.info("Circuit breaker entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                # Still in timeout period, reject immediately
                raise ExternalServiceException(
                    "Circuit breaker OPEN - service unavailable"
                )
        
        try:
            result = func(*args, **kwargs)
            # Success - reset failure count
            if self.state == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker closing - service recovered")
                self.state = CircuitState.CLOSED
            self.failure_count = 0
            return result
            
        except Exception as e:
            # Failure
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"Circuit breaker opening after {self.failure_count} failures"
                )
                self.state = CircuitState.OPEN
            
            raise


class StripePaymentService(PaymentService):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)
    
    def charge_membership(self, member_id: str, amount: float) -> str:
        """
        Charge a member for their membership with circuit breaker protection.
        
        Raises:
            ExternalServiceException: If payment fails or circuit is open
        """
        try:
            return self.circuit_breaker.call(
                self._charge_stripe, member_id, amount
            )
        except ExternalServiceException:
            raise  # Circuit breaker rejection
        except Exception as e:
            logger.error(f"Payment failed for member {member_id}: {e}")
            raise ExternalServiceException(f"Payment processing failed: {e}")
    
    def _charge_stripe(self, member_id: str, amount: float) -> str:
        """Actual Stripe API call."""
        # In real implementation, call Stripe API
        import stripe
        stripe.api_key = self.api_key
        
        try:
            charge = stripe.Charge.create(
                amount=int(amount * 100),  # Stripe uses cents
                currency='usd',
                description=f'Membership for {member_id}'
            )
            return charge.id
        except stripe.error.CardError as e:
            # Card was declined - this is a domain issue, not infrastructure
            raise PaymentDeclinedException(f"Card declined: {e.user_message}")
        except (stripe.error.APIConnectionError, stripe.error.APIError) as e:
            # Infrastructure failure
            raise ExternalServiceException(f"Stripe API error: {e}")
```

**Key principles:**

- **Fail fast when service is down:** Don't wait for timeout if we know it's failing
- **Automatically recover:** Test if service is back up after timeout period
- **Protect your application:** Prevent one failing service from bringing down your entire system
- **Log state transitions:** Track when circuit opens/closes for monitoring

#### Error Handling Summary for Infrastructure Layer

**Infrastructure exceptions represent technical failures:**
- Database connection errors
- Network timeouts
- Disk full errors
- External API failures

**Domain exceptions represent business rule violations:**
- Duplicate email (unique constraint from database)
- Invalid credit card (from payment processor)
- Email address format (from validation during reconstruction)

**Application exceptions represent application-level concerns:**
- Resource not found
- Unauthorized access
- Invalid request format

**Adapters should:**

1. **Catch infrastructure-specific exceptions** (SQLite, SMTP, Stripe errors)
2. **Translate to infrastructure exceptions** (RepositoryException, NotificationException)
3. **Convert to domain exceptions when appropriate** (duplicate email → DuplicateEmailException)
4. **Log with appropriate severity** (critical for failures, warning for retries)
5. **Implement retry logic for transient failures** (network errors, temporary unavailability)
6. **Fail fast for permanent errors** (authentication failures, invalid input)
7. **Use circuit breakers for external services** (prevent cascading failures)

The use cases (application layer) decide how to handle these exceptions. The adapters just raise them appropriately, with enough context for the application to make informed decisions.

### When to Create New Adapters

You create a new adapter when:

**You need a different storage mechanism.** PostgreSQL for production. SQLite for local development. In-memory for tests.

**You need different behaviour in different environments.** Real email in production. Console output in development. Fake in tests.

**You're integrating with a new external system.** Stripe for payments initially. PayPal added later. Both implement `PaymentService`.

**You're optimising for different concerns.** Database repository for durability. Cache repository for speed. Both implement the same port.

You don't create a new adapter when:

**The logic is domain-specific.** That belongs in the domain layer, not infrastructure.

**It's just a variation in configuration.** Use dependency injection to pass different config, not different adapters.

**You're adding new operations.** Extend the port first, then implement it in all adapters.

Adapters translate between domains. If you're not translating, you probably don't need an adapter.

### When You Don't Need Multiple Adapters

We built three repository adapters (in-memory, JSON, and SQLite) and multiple service adapters (SMTP, console). This demonstrates flexibility. But do you always need it?

**You don't need multiple adapters if:**

- You have one infrastructure that will never change (e.g., company-mandated PostgreSQL)
- Your application is simple with no testing complexity
- Building a prototype that might be thrown away
- The effort to create multiple implementations exceeds the benefit
- You're a solo developer and swappability isn't a priority
- Testing with real infrastructure is fast and painless

In these cases, **one concrete adapter is enough:**

```python
# Just implement the port once
# Repository port
class MemberRepository(ABC):
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass

# Single production repository adapter
class PostgresMemberRepository(MemberRepository):
    def get_by_id(self, member_id: str) -> Optional[Member]:
        # PostgreSQL implementation
        pass

# Use it everywhere - dev, test, production
use_case = BookClassUseCase(
    PostgresMemberRepository(connection_string)
)
```

You still have ports (for dependency inversion), but only one adapter. That's fine.

**You DO need multiple adapters when:**

- Testing with real infrastructure is slow or complex
- You deploy to different environments (dev, staging, production) with different backends
- You need fast, isolated tests without infrastructure setup
- Infrastructure isn't stable or might change
- Different use cases need different implementations (cache vs. database)
- You're building a library others will integrate with various backends

These signals indicate that one implementation isn't enough.

**Common misconception:** "I need in-memory, JSON, SQLite, PostgreSQL, MongoDB implementations."

Not true. That's over-engineering. Most applications need two implementations: **one for production, one for testing.** We showed three to demonstrate the pattern, not to suggest you need all of them.

**The right approach:**

1. Start with one adapter (production infrastructure)
2. When tests get slow or complex, add a test adapter (usually in-memory)
3. When you need to swap infrastructure, add another production adapter
4. Don't create implementations you don't use

We built three repository adapters for each repository port because we wanted to demonstrate swappability and show that no external dependencies are needed. Your application might only need one SQLite adapter for production and one in-memory adapter for tests. Build what you need, when you need it.

Architecture serves the problem. Not the pattern collection.

## The Complete Picture

Let's step back and see what we've built.

We started this chapter with a dependency problem. Use cases were coupled to infrastructure. We couldn't test without databases. We couldn't swap implementations without changing application code.

We solved it in two parts:

**Part 1: Ports**—We defined abstract interfaces that specify what the application needs from infrastructure. `MemberRepository` declares `get_by_id()` and `save()`. `NotificationService` declares `send_booking_confirmation()`. Use cases depend on these abstractions, inverting the traditional dependency flow.

**Part 2: Adapters**—We implemented concrete classes that fulfill the port contracts. We built repository adapters (SQLite, JSON files, in-memory storage) and service adapters (SMTP email, console output). Each adapter translates between domain concepts and infrastructure primitives.

The result is hexagonal architecture:

1. **Domain layer**: Entities and business rules that don't depend on anything
2. **Application layer**: Use cases that depend only on ports
3. **Ports**: Abstract interfaces that define contracts
4. **Adapters**: Concrete implementations that connect to infrastructure
5. **Dependency injection**: Configuration that wires it all together

The dependencies flow inward. Infrastructure depends on application. Application depends on domain. Nothing flows outward.

This isn't just theory. We've built a working system. You can test use cases in milliseconds with in-memory adapters. You can swap from SQLite to PostgreSQL by changing one line in the dependency injection container. You can deploy the same application code with different infrastructure configurations.

You started with tightly coupled use cases that couldn't be tested or flexibly deployed.

You defined ports—abstractions that specify what the application needs without dictating how it's provided.

You've now implemented adapters—concrete classes that fulfill those contracts using real infrastructure.

The dependency graph looks like this:

```
┌─────────────────────────────────────────────┐
│           Application Layer                  │
│         (Use Cases + Ports)                  │
│                                              │
│  BookClassUseCase ──→ MemberRepository       │
│                  ──→ NotificationService     │
└──────────────────┬───────────────────────────┘
                   │ depends on (abstraction)
         ┌─────────▼──────────┬─────────────────┐
         │                    │                  │
┌────────▼──────────┐  ┌──────▼────────┐  ┌────▼──────────┐
│ SqliteMember      │  │ SMTPNotif     │  │ InMemoryMember│
│ Repository        │  │ Service       │  │ Repository    │
│ (Production)      │  │ (Production)  │  │ (Tests)       │
└───────────────────┘  └───────────────┘  └───────────────┘
```

Dependencies point inward. High-level policy doesn't depend on low-level details. Both depend on abstractions.

You can swap in-memory for SQLite without touching use cases. You can swap SQLite for PostgreSQL without changing application logic. You can test with in-memory repositories without needing infrastructure.

This is hexagonal architecture fully realised. This is ports and adapters in practice. This is clean architecture applied.

Your codebase is organised. Your domain is pure. Your application is decoupled from infrastructure. Your tests are fast and focused.

The architecture serves the business logic. Not the other way around.

## What We Have Now

Let's take stock. We've achieved complete hexagonal architecture:

**Our system now has:**
1. **Ports (abstractions) defining contracts:**
   - `MemberRepository` (port)
   - `FitnessClassRepository` (port)
   - `BookingRepository` (port)
   - `NotificationService` (port)

2. **Multiple adapters for each port:**
   - `InMemoryMemberRepository`, `SqliteMemberRepository` (adapters)
   - `ConsoleNotificationService`, `SMTPNotificationService` (adapters)
   - Can add `PostgresMemberRepository` without touching use cases

3. **Dependency inversion achieved:**
   - Use cases depend on ports (abstractions)
   - Adapters implement ports (concrete infrastructure)
   - Dependencies point inward toward domain

4. **Complete testability:**
   - Tests use `InMemoryRepository` adapters (fast, no setup)
   - Production uses `SqliteRepository` adapters
   - Same use cases, different infrastructure

**Updated structure:**
```
gym_booking/
  ├── domain/
  │   ├── entities/...
  │   └── value_objects/...
  ├── application/
  │   ├── ports/
  │   │   ├── member_repository.py      # Port (interface)
  │   │   ├── class_repository.py       # Port (interface)
  │   │   └── notification_service.py   # Port (interface)
  │   └── use_cases/
  │       └── book_class_use_case.py    # Depends on ports!
  ├── infrastructure/
  │   ├── adapters/
  │   │   ├── sqlite_member_repository.py    # Adapter
  │   │   ├── inmemory_member_repository.py  # Adapter
  │   │   └── smtp_notification_service.py   # Adapter
  │   └── container.py  # Dependency injection
  ├── interface/
  │   └── cli.py  # Still using old CLI
  └── tests/
      └── test_book_class_use_case.py  # Uses InMemory adapters!
```

**What we gained:**
- Can swap SQLite → PostgreSQL by changing one line in container
- Tests run in milliseconds (no database)
- Use cases are pure orchestration (no infrastructure knowledge)
- New adapters don't affect existing code
- True dependency inversion achieved

**But we still have:**
- Old CLI interface from Chapter 1 (still works but not updated)
- Only one interface (command-line)
- Interface layer not leveraging hexagonal architecture

**Current state:**
We have a beautiful hexagonal core (domain + application + adapters), but we're still using the simple CLI from early chapters. The CLI talks directly to use cases, which is fine, but we haven't demonstrated the full power of having multiple interfaces.

## Transition to Chapter 8

Our hexagonal architecture is complete. The core is clean. Adapters are swappable. Tests are fast. But look at our interface layer—we're still using the simple CLI from Chapter 1:

```python
# interface/cli.py
def main():
    while True:
        command = input("> ").strip().split()
        if command[0] == "book":
            # Direct instantiation, mixed with UI logic
            member_id = command[1]
            class_id = command[2]
            # ...
```

This works, but it doesn't showcase what hexagonal architecture enables: **multiple interfaces using the same core.**

The power of hexagonal architecture isn't just testability—it's that the core is independent of how it's accessed. Want a CLI? Build one. Want a REST API? Build one. Want a GraphQL endpoint? Build one. Want all three? They all use the same use cases.

In Chapter 8, we'll build a proper **Interface Layer**. We'll:
- Clean up the CLI interface (make it a proper adapter)
- Build a REST API interface (Flask-based)
- Show both interfaces using the same use cases
- Demonstrate how HTTP concerns stay in the interface layer
- Prove that the core is truly independent

**The challenge:** "We need a REST API so our mobile app can access the booking system. The CLI should still work. How do we add this without duplicating business logic?"

That's next.

## Chapter Summary

This chapter covered the complete ports and adapters pattern, building hexagonal architecture from the ground up.

**Ports** are abstract interfaces that define what the application needs from infrastructure. They invert dependencies so use cases don't depend on concrete implementations like databases or email servers. Instead, they depend on abstractions—contracts that specify behavior without dictating implementation.

**Adapters** implement ports using concrete infrastructure. They translate between the domain's language and the infrastructure's technical details.

We built three different repository adapters for the same repository port:

1. **In-memory repository adapters** using Python dictionaries—fast, simple, perfect for testing
2. **JSON file repository adapters** using Python's standard library—persistent but simple, no external dependencies
3. **SQLite repository adapters** using Python's built-in `sqlite3`—real database with SQL, still no external dependencies

All three adapters implement the same repository port (e.g., `MemberRepository`). All three work with the same use cases. All three are swappable at runtime. This demonstrates the power of ports and adapters—choose the infrastructure that fits your needs without changing application code.

We built service adapters for notifications—`SMTPNotificationService` for production and `ConsoleNotificationService` for development. Same port, different implementations, swappable at runtime.

We wired everything together with dependency injection through an `ApplicationContainer`. The container creates adapters and injects them into use cases. Configuration happens in one place. The rest of the application just receives what it needs.

We demonstrated error handling in adapters—distinguishing between domain violations, infrastructure failures, and transient errors. Each type gets handled appropriately.

The complete system works. You can run it. You can test it. You can swap implementations without changing application code. You don't need frameworks or external dependencies to build well-architected software.

The architecture is no longer theoretical. It's practical. It's real. It works.

You've built a system where business logic lives in the domain, orchestration lives in the application, and technical details live in infrastructure. Clean boundaries. Clear responsibilities. Maintainable structure.

This is intentional architecture. This is software that adapts to change instead of fighting it.

The foundation is solid. The patterns are proven. The system is ready to grow.
