# Chapter 8: Putting It All Together

You've learned the pieces. TDD guides your design. SOLID shapes your classes. Layers organize your codebase. Domain models enforce business rules. Use cases orchestrate workflows. Ports and adapters decouple infrastructure.

Now we build something complete.

This chapter shows how all these patterns work together by building a real feature from start to finish: **premium members get waitlist priority.**

We'll follow the full workflow:
1. Start with a user story
2. Drive design with tests (TDD)
3. Model the domain (entities, value objects)
4. Apply SOLID principles
5. Respect layer boundaries
6. Orchestrate with use cases
7. Implement infrastructure with ports and adapters
8. Verify with comprehensive testing

By the end, you'll see how architecture emerges from intentional decisions, not from following templates.

## The User Story

**As a premium member, I want priority access to waitlisted classes so that I can attend popular sessions even when they're full.**

Business rules:
- When a class is full, premium members can join a waitlist
- When a spot opens up (cancellation), the first premium member on the waitlist is automatically booked
- Basic members cannot join waitlists—they get a "class full" error
- Waitlist members are notified when they're promoted to confirmed

This feature touches everything: domain logic, persistence, orchestration, and external communication.

## Step 1: Start with Tests (TDD)

We begin with tests that define the behavior we want.

```python
# tests/unit/domain/test_waitlist.py
import pytest
from domain.member import Member, MembershipType
from domain.fitness_class import FitnessClass
from domain.value_objects import EmailAddress
from domain.exceptions import ClassFullException

def test_premium_member_joins_waitlist_when_class_full():
    """Premium members can join waitlist when class is at capacity."""
    member = Member(
        member_id="M001",
        name="Alice Johnson",
        email=EmailAddress("alice@example.com"),
        membership_type=MembershipType.PREMIUM
    )
    
    fitness_class = FitnessClass(
        class_id="C001",
        name="Yoga Flow",
        capacity=2,
        day="Monday",
        start_time="09:00"
    )
    
    # Fill the class
    fitness_class.add_booking("M100")
    fitness_class.add_booking("M101")
    
    # Premium member should be able to join waitlist
    fitness_class.add_to_waitlist(member)
    
    assert member.id in fitness_class.waitlist
    assert len(fitness_class.waitlist) == 1


def test_basic_member_cannot_join_waitlist():
    """Basic members get an error when trying to book a full class."""
    member = Member(
        member_id="M002",
        name="Bob Smith",
        email=EmailAddress("bob@example.com"),
        membership_type=MembershipType.BASIC
    )
    
    fitness_class = FitnessClass(
        class_id="C001",
        name="Yoga Flow",
        capacity=1,
        day="Monday",
        start_time="09:00"
    )
    
    # Fill the class
    fitness_class.add_booking("M100")
    
    # Basic member cannot join waitlist
    with pytest.raises(ClassFullException):
        fitness_class.add_to_waitlist(member)


def test_cancellation_promotes_waitlisted_member():
    """When someone cancels, the first waitlisted member gets the spot."""
    premium_member = Member(
        member_id="M001",
        name="Alice",
        email=EmailAddress("alice@example.com"),
        membership_type=MembershipType.PREMIUM
    )
    
    fitness_class = FitnessClass(
        class_id="C001",
        name="Yoga",
        capacity=1,
        day="Monday",
        start_time="09:00"
    )
    
    # Fill the class
    fitness_class.add_booking("M100")
    
    # Premium member joins waitlist
    fitness_class.add_to_waitlist(premium_member)
    
    # Spot opens up
    promoted = fitness_class.remove_booking("M100")
    
    # Waitlisted member should be promoted
    assert promoted == premium_member.id
    assert premium_member.id in fitness_class.bookings
    assert len(fitness_class.waitlist) == 0
```

**Red.** These tests fail because the functionality doesn't exist.

## Step 2: Model the Domain

The tests reveal what we need: members with membership types, classes with waitlists, and promotion logic.

### Value Object: MembershipType

Membership type is a concept that deserves its own representation. It's not just a string—it has behavior (can join waitlist or not).

```python
# domain/member.py
from enum import Enum

class MembershipType(Enum):
    BASIC = ("basic", 10, 25.0)
    PREMIUM = ("premium", 20, 50.0)
    
    def __init__(self, display_name: str, credits_per_month: int, price: float):
        self._display_name = display_name
        self._credits_per_month = credits_per_month
        self._price = price
    
    @property
    def display_name(self) -> str:
        return self._display_name
    
    @property
    def credits_per_month(self) -> int:
        return self._credits_per_month
    
    @property
    def price(self) -> float:
        return self._price
    
    def can_join_waitlist(self) -> bool:
        """Only premium members can join waitlists."""
        return self == MembershipType.PREMIUM
```

This is a value object. It represents a concept from the domain. It enforces rules (only premium can waitlist). It makes invalid states impossible—you can't have a membership type that's not defined.

### Entity: Member (Enhanced)

We're building on the `Member` entity from Chapter 5. Recall that it uses encapsulated attributes with properties for controlled access:

```python
# domain/member.py
from typing import Optional
from datetime import datetime, timedelta
from domain.value_objects import EmailAddress

class Member:
    """A gym member who can book classes."""
    
    def __init__(self, member_id: str, name: str, email: EmailAddress, 
                 membership_type: MembershipType, credits: Optional[int] = None):
        if not member_id:
            raise ValueError("Member ID is required")
        if not name or not name.strip():
            raise ValueError("Member name cannot be empty")
        
        self._id = member_id
        self._name = name
        self._email = email
        self._membership_type = membership_type
        self._credits = credits if credits is not None else membership_type.credits_per_month
    
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
        return self._credits
    
    def can_join_waitlist(self) -> bool:
        """Delegate to membership type."""
        return self._membership_type.can_join_waitlist()
    
    def deduct_credit(self) -> None:
        """Remove one credit from member's account."""
        if self._credits <= 0:
            raise ValueError("Insufficient credits")
        self._credits -= 1
    
    def refund_credit(self) -> None:
        """Return one credit to member's account."""
        self._credits += 1
```

**Notice:** The `Member` doesn't know about waitlists or bookings. It knows about credits and membership types. Single Responsibility Principle (Chapter 2) in action.

**From Chapter 5:** We use properties to encapsulate internal state (e.g., `self._credits`), allowing us to add validation or business logic to getters/setters later without changing the interface.

### Entity: FitnessClass (Enhanced with Waitlist)

```python
# domain/fitness_class.py
from typing import List, Optional
from domain.member import Member
from domain.exceptions import ClassFullException

class FitnessClass:
    """A fitness class that members can book."""
    
    def __init__(self, class_id: str, name: str, capacity: int, 
                 day: str, start_time: str):
        if not class_id:
            raise ValueError("Class ID is required")
        if not name or not name.strip():
            raise ValueError("Class name cannot be empty")
        if capacity < 1 or capacity > 50:
            raise ValueError("Capacity must be between 1 and 50")
        
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._day = day
        self._start_time = start_time
        self._bookings: List[str] = []  # member IDs
        self._waitlist: List[str] = []  # member IDs
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def bookings(self) -> List[str]:
        """Return copy of bookings to prevent external modification."""
        return self._bookings.copy()
    
    @property
    def waitlist(self) -> List[str]:
        """Return copy of waitlist to prevent external modification."""
        return self._waitlist.copy()
    
    def is_full(self) -> bool:
        """Check if class is at capacity."""
        return len(self._bookings) >= self._capacity
    
    def add_booking(self, member_id: str) -> None:
        """Add a member to the class."""
        if self.is_full():
            raise ClassFullException(f"Class {self._name} is at capacity")
        
        if member_id in self._bookings:
            raise ValueError("Member already booked")
        
        self._bookings.append(member_id)
    
    def add_to_waitlist(self, member: Member) -> None:
        """
        Add a member to the waitlist if they're eligible.
        
        Note: Takes full Member object (not just ID) because we need to check
        member.can_join_waitlist() to enforce business rules. Only premium
        members can join waitlists.
        """
        if not self.is_full():
            raise ValueError("Class is not full; no need for waitlist")
        
        if not member.can_join_waitlist():
            raise ClassFullException(
                f"Class {self._name} is full and member type "
                f"{member.membership_type.value} cannot join waitlist"
            )
        
        if member.id in self._waitlist:
            raise ValueError("Member already on waitlist")
        
        self._waitlist.append(member.id)
    
    def remove_booking(self, member_id: str) -> Optional[str]:
        """
        Remove a booking and promote first waitlisted member if any.
        Returns the ID of the promoted member, or None.
        """
        if member_id not in self._bookings:
            raise ValueError("Member not found in bookings")
        
        self._bookings.remove(member_id)
        
        # Promote first waitlisted member
        if self._waitlist:
            promoted_id = self._waitlist.pop(0)
            self._bookings.append(promoted_id)
            return promoted_id
        
        return None
```

**Notice:** The class enforces its own invariants through `__init__` validation (from Chapter 5). You can't add someone to the waitlist if the class isn't full. You can't add a basic member to the waitlist. The domain protects itself.

Run the unit tests. **Green.** The domain model works.

## Step 3: Apply SOLID Principles

Let's verify we're following SOLID:

**Single Responsibility:**
- `Member` handles member data and credit management
- `FitnessClass` handles class capacity and waitlist logic
- `MembershipType` handles membership rules

✅ Each class has one reason to change.

**Open/Closed:**
- Want a new membership type? Add a new enum value and implement `can_join_waitlist()`
- Want different waitlist rules? Override the method

✅ Extensible without modifying existing code.

**Liskov Substitution:**
- Not applicable here—we're using value objects and entities, not inheritance hierarchies

**Interface Segregation:**
- `Member` has focused methods: `can_join_waitlist()`, `deduct_credit()`, `refund_credit()`
- `FitnessClass` has focused methods: `add_booking()`, `add_to_waitlist()`, `remove_booking()`

✅ No bloated interfaces forcing unused methods.

**Dependency Inversion:**
- The domain doesn't depend on infrastructure
- It doesn't know about databases, APIs, or email services

✅ High-level policy (domain) independent of low-level details.

## Step 4: Build the Use Case (Application Layer)

The domain handles the rules. Now we need a use case to orchestrate the workflow: "Book a class with waitlist support."

```python
# application/book_class_use_case.py
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from domain.member import Member
from domain.fitness_class import FitnessClass
from domain.booking import Booking, BookingStatus
from domain.exceptions import ClassFullException
from application.ports import (
    MemberRepository,
    FitnessClassRepository,
    BookingRepository,
    NotificationService
)


@dataclass
class BookClassCommand:
    """Input data for booking a class."""
    member_id: str
    class_id: str


@dataclass
class BookClassResult:
    """Result of booking operation."""
    booking: Booking
    was_waitlisted: bool


class BookClassUseCase:
    """
    Use case: Book a member into a fitness class.
    
    If class is full and member is premium, add to waitlist.
    If class has space, create confirmed booking.
    """
    
    def __init__(
        self,
        member_repo: MemberRepository,
        class_repo: FitnessClassRepository,
        booking_repo: BookingRepository,
        notification_service: NotificationService
    ):
        self._member_repo = member_repo
        self._class_repo = class_repo
        self._booking_repo = booking_repo
        self._notifications = notification_service
    
    def execute(self, command: BookClassCommand) -> BookClassResult:
        """Execute the booking workflow."""
        # Load domain objects
        member = self._member_repo.get_by_id(command.member_id)
        if not member:
            raise ValueError(f"Member {command.member_id} not found")
        
        fitness_class = self._class_repo.get_by_id(command.class_id)
        if not fitness_class:
            raise ValueError(f"Class {command.class_id} not found")
        
        # Try to book
        was_waitlisted = False
        
        try:
            # Attempt normal booking
            member.deduct_credit()
            fitness_class.add_booking(member.id)
            status = BookingStatus.CONFIRMED
            
        except ClassFullException:
            # Class is full - try waitlist
            fitness_class.add_to_waitlist(member)
            status = BookingStatus.WAITLISTED
            was_waitlisted = True
            # Don't deduct credit for waitlisted bookings
        
        # Create booking record
        booking = Booking.create(
            member_id=member.id,
            class_id=fitness_class.id,
            status=status
        )
        
        # Persist changes
        self._member_repo.save(member)
        self._class_repo.save(fitness_class)
        self._booking_repo.save(booking)
        
        # Notify member
        if was_waitlisted:
            self._notifications.send_waitlist_notification(member, fitness_class)
        else:
            self._notifications.send_booking_confirmation(member, fitness_class)
        
        return BookClassResult(booking=booking, was_waitlisted=was_waitlisted)
```

**Notice:** The use case:
- Loads domain objects from repositories (ports)
- Lets domain objects enforce their rules
- Coordinates the workflow
- Persists changes
- Triggers notifications

It contains **no business logic**. All logic lives in the domain.

## Step 5: Define Ports (Hexagonal Architecture)

The use case depends on abstractions, not concrete implementations.

```python
# application/ports.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.member import Member
from domain.fitness_class import FitnessClass
from domain.booking import Booking


class MemberRepository(ABC):
    """Port for member persistence."""
    
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def save(self, member: Member) -> None:
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
    def list_available(self, day: str) -> List[FitnessClass]:
        pass


class BookingRepository(ABC):
    """Port for booking persistence."""
    
    @abstractmethod
    def save(self, booking: Booking) -> None:
        pass
    
    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    def get_by_member(self, member_id: str) -> List[Booking]:
        pass


class NotificationService(ABC):
    """Port for sending notifications."""
    
    @abstractmethod
    def send_booking_confirmation(self, member: Member, 
                                   fitness_class: FitnessClass) -> None:
        pass
    
    @abstractmethod
    def send_waitlist_notification(self, member: Member,
                                    fitness_class: FitnessClass) -> None:
        pass
    
    @abstractmethod
    def send_promotion_notification(self, member: Member,
                                     fitness_class: FitnessClass) -> None:
        pass
```

These are **ports**—contracts that define what the application needs, without specifying how it's provided.

## Step 6: Implement Adapters (Infrastructure Layer)

Now we implement the ports using real infrastructure.

### SQLite Repository Adapter

```python
# infrastructure/sqlite_member_repository.py
import sqlite3
from typing import Optional
from application.ports import MemberRepository
from domain.member import Member, MembershipType
from domain.value_objects import EmailAddress


class SqliteMemberRepository(MemberRepository):
    """SQLite implementation of member persistence."""
    
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._create_table()
    
    def _create_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                membership_type TEXT NOT NULL,
                credits INTEGER NOT NULL
            )
        """)
        self._conn.commit()
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        cursor = self._conn.execute(
            "SELECT id, name, email, membership_type, credits FROM members WHERE id = ?",
            (member_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Convert stored string back to enum
        membership_type = (MembershipType.PREMIUM if row[3] == "premium" 
                          else MembershipType.BASIC)
        
        return Member(
            member_id=row[0],
            name=row[1],
            email=EmailAddress(row[2]),
            membership_type=membership_type,
            credits=row[4]
        )
    
    def save(self, member: Member) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO members (id, name, email, membership_type, credits)
            VALUES (?, ?, ?, ?, ?)
            """,
            (member.id, member.name, str(member.email), 
             member.membership_type.display_name, member.credits)
        )
        self._conn.commit()
```

### Email Notification Adapter

```python
# infrastructure/email_notification_service.py
import smtplib
from email.mime.text import MIMEText
from application.ports import NotificationService
from domain.member import Member
from domain.fitness_class import FitnessClass


class EmailNotificationService(NotificationService):
    """Email implementation of notification service."""
    
    def __init__(self, smtp_host: str, smtp_port: int, 
                 from_email: str, password: str):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._from_email = from_email
        self._password = password
    
    def send_booking_confirmation(self, member: Member, 
                                   fitness_class: FitnessClass) -> None:
        subject = f"Booking Confirmed: {fitness_class.name}"
        body = f"""
        Hi {member.name},
        
        Your booking for {fitness_class.name} has been confirmed!
        
        Class Details:
        - Name: {fitness_class.name}
        - Time: {fitness_class.day} at {fitness_class.start_time}
        
        See you there!
        """
        
        self._send_email(str(member.email), subject, body)
    
    def send_waitlist_notification(self, member: Member,
                                    fitness_class: FitnessClass) -> None:
        subject = f"Added to Waitlist: {fitness_class.name}"
        body = f"""
        Hi {member.name},
        
        The class {fitness_class.name} is currently full.
        
        As a premium member, you've been added to the waitlist.
        We'll notify you if a spot opens up!
        """
        
        self._send_email(str(member.email), subject, body)
    
    def send_promotion_notification(self, member: Member,
                                     fitness_class: FitnessClass) -> None:
        subject = f"You're In! {fitness_class.name}"
        body = f"""
        Hi {member.name},
        
        Great news! A spot opened up in {fitness_class.name}.
        You've been automatically booked.
        
        See you at {fitness_class.day} at {fitness_class.start_time}!
        """
        
        self._send_email(str(member.email), subject, body)
    
    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self._from_email
        msg['To'] = to_email
        
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            server.starttls()
            server.login(self._from_email, self._password)
            server.send_message(msg)
```

### Test Adapter (In-Memory)

For testing, we use in-memory implementations:

```python
# infrastructure/in_memory_member_repository.py
from typing import Optional, Dict
from application.ports import MemberRepository
from domain.member import Member


class InMemoryMemberRepository(MemberRepository):
    """In-memory implementation for testing."""
    
    def __init__(self):
        self._members: Dict[str, Member] = {}
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        return self._members.get(member_id)
    
    def save(self, member: Member) -> None:
        self._members[member.id] = member
```

**This is the power of ports and adapters.** The same use case works with SQLite, PostgreSQL, or in-memory storage. Just swap the adapter.

## Step 7: Wire It Together (Dependency Injection)

Now we assemble everything:

```python
# main.py
import sqlite3
from application.book_class_use_case import BookClassUseCase, BookClassCommand
from infrastructure.sqlite_member_repository import SqliteMemberRepository
from infrastructure.sqlite_class_repository import SqliteFitnessClassRepository
from infrastructure.sqlite_booking_repository import SqliteBookingRepository
from infrastructure.email_notification_service import EmailNotificationService


def main():
    # Set up infrastructure
    db_connection = sqlite3.connect('gym.db')
    
    member_repo = SqliteMemberRepository(db_connection)
    class_repo = SqliteFitnessClassRepository(db_connection)
    booking_repo = SqliteBookingRepository(db_connection)
    
    notification_service = EmailNotificationService(
        smtp_host='smtp.gmail.com',
        smtp_port=587,
        from_email='gym@example.com',
        password='your-password'
    )
    
    # Create use case
    book_class = BookClassUseCase(
        member_repo=member_repo,
        class_repo=class_repo,
        booking_repo=booking_repo,
        notification_service=notification_service
    )
    
    # Execute
    command = BookClassCommand(member_id='M001', class_id='C001')
    result = book_class.execute(command)
    
    if result.was_waitlisted:
        print("Added to waitlist")
    else:
        print("Booking confirmed!")


if __name__ == "__main__":
    main()
```

**Notice:** Configuration happens in one place. Swapping databases or email providers means changing a few lines in `main()`, not touching the use case.

## Step 8: Comprehensive Testing

Now we test at all levels of the pyramid.

### Unit Tests (Domain)

```python
# tests/unit/domain/test_fitness_class.py
def test_waitlist_promotion_on_cancellation():
    """Waitlist members are promoted when spot opens."""
    fitness_class = FitnessClass.create("C001", "Yoga", 1, "Monday", "09:00")
    member = Member.create("M001", "Alice", "alice@example.com", 
                          MembershipType.PREMIUM)
    
    fitness_class.add_booking("M100")
    fitness_class.add_to_waitlist(member)
    
    promoted = fitness_class.remove_booking("M100")
    
    assert promoted == "M001"
    assert "M001" in fitness_class.bookings
```

### Integration Tests (Application + Infrastructure)

```python
# tests/integration/test_booking_workflow.py
def test_complete_waitlist_workflow():
    """End-to-end test of waitlist feature with real repositories."""
    # Use test database
    conn = sqlite3.connect(':memory:')
    member_repo = SqliteMemberRepository(conn)
    class_repo = SqliteFitnessClassRepository(conn)
    booking_repo = SqliteBookingRepository(conn)
    notification_service = FakeNotificationService()
    
    # Set up data
    member = Member.create("M001", "Alice", "alice@example.com", 
                          MembershipType.PREMIUM, credits=10)
    member_repo.save(member)
    
    fitness_class = FitnessClass.create("C001", "Yoga", 1, "Monday", "09:00")
    fitness_class.add_booking("M100")  # Fill it
    class_repo.save(fitness_class)
    
    # Execute use case
    use_case = BookClassUseCase(member_repo, class_repo, booking_repo, 
                                notification_service)
    result = use_case.execute(BookClassCommand("M001", "C001"))
    
    # Verify
    assert result.was_waitlisted
    assert notification_service.waitlist_sent
    
    # Verify persistence
    loaded_class = class_repo.get_by_id("C001")
    assert "M001" in loaded_class.waitlist
```

### End-to-End Tests (Full System)

```python
# tests/e2e/test_api.py
def test_waitlist_via_api():
    """Test waitlist through REST API."""
    # Assuming a Flask/FastAPI app
    response = client.post('/bookings', json={
        'member_id': 'M001',
        'class_id': 'C001'
    })
    
    assert response.status_code == 201
    assert response.json['status'] == 'waitlisted'
```

## Evolution of the Codebase

Let's see how our architecture made this feature easy to add.

### Before (Chapter 1 Script)

```python
def book_class(booking_id, member_id, class_id):
    # Everything tangled together
    if member_id not in members:
        raise ValueError("Member not found")
    
    member = members[member_id]
    fitness_class = classes[class_id]
    
    if len(fitness_class['bookings']) >= fitness_class['capacity']:
        # No waitlist support - just fail
        raise ValueError("Class is full")
    
    # ... rest of booking logic
```

**To add waitlists:** You'd need to modify this function, add waitlist storage, handle member types, implement promotion logic—all in one place. Testing would require mocking dictionaries.

### After (Chapter 8 Architecture)

**To add waitlists:** 
1. Add `add_to_waitlist()` to `FitnessClass` (domain)
2. Add `can_join_waitlist()` to `MembershipType` (domain)
3. Update `BookClassUseCase` to catch `ClassFullException` (application)
4. Add `send_waitlist_notification()` to notification port (application)
5. Implement notification in adapter (infrastructure)

Each change is localized. Each layer has a clear responsibility. Tests exist at every level.

**Cost-benefit analysis:**
- More files? Yes. But each file has one purpose.
- More abstractions? Yes. But they enable flexibility.
- More upfront work? Yes. But changes become easier.

For a 20-line script you'll run once? Overkill.
For a system that'll evolve over months? Essential.

## Running the Complete Application

Here's the full directory structure:

```
gym-booking-system/
├── domain/
│   ├── __init__.py
│   ├── member.py              # Member entity
│   ├── fitness_class.py       # FitnessClass entity
│   ├── booking.py             # Booking entity
│   ├── value_objects.py       # EmailAddress, TimeSlot
│   └── exceptions.py          # Domain exceptions
│
├── application/
│   ├── __init__.py
│   ├── ports.py               # Abstract interfaces
│   ├── book_class_use_case.py
│   ├── cancel_booking_use_case.py
│   └── list_classes_use_case.py
│
├── infrastructure/
│   ├── __init__.py
│   ├── sqlite_member_repository.py
│   ├── sqlite_class_repository.py
│   ├── sqlite_booking_repository.py
│   ├── email_notification_service.py
│   └── in_memory_repositories.py  # For testing
│
├── interface/
│   ├── __init__.py
│   ├── api.py                 # REST API (Flask/FastAPI)
│   └── cli.py                 # Command-line interface
│
├── tests/
│   ├── unit/
│   │   └── domain/
│   ├── integration/
│   └── e2e/
│
├── main.py                    # Dependency injection setup
└── requirements.txt
```

### Dependency Injection Container

```python
# container.py
from dataclasses import dataclass
import sqlite3
from application.book_class_use_case import BookClassUseCase
from infrastructure.sqlite_member_repository import SqliteMemberRepository
# ... other imports


@dataclass
class Container:
    """Dependency injection container."""
    
    # Repositories
    member_repository: MemberRepository
    class_repository: FitnessClassRepository
    booking_repository: BookingRepository
    
    # Services
    notification_service: NotificationService
    
    # Use cases
    book_class: BookClassUseCase
    
    @classmethod
    def create(cls, db_path: str, email_config: dict) -> 'Container':
        """Factory method to create container with all dependencies."""
        conn = sqlite3.connect(db_path)
        
        # Repositories
        member_repo = SqliteMemberRepository(conn)
        class_repo = SqliteFitnessClassRepository(conn)
        booking_repo = SqliteBookingRepository(conn)
        
        # Services
        notification = EmailNotificationService(**email_config)
        
        # Use cases
        book_class = BookClassUseCase(
            member_repo, class_repo, booking_repo, notification
        )
        
        return cls(
            member_repository=member_repo,
            class_repository=class_repo,
            booking_repository=booking_repo,
            notification_service=notification,
            book_class=book_class
        )
```

### Configuration Management

```python
# config.py
from dataclasses import dataclass
import os


@dataclass
class Config:
    database_path: str
    smtp_host: str
    smtp_port: int
    email_from: str
    email_password: str
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        return cls(
            database_path=os.getenv('DB_PATH', 'gym.db'),
            smtp_host=os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            email_from=os.getenv('EMAIL_FROM'),
            email_password=os.getenv('EMAIL_PASSWORD')
        )
```

## Key Takeaways

1. **TDD drives design:** Tests revealed the domain model we needed
2. **Domain enforces rules:** Business logic lives in entities and value objects
3. **SOLID guides structure:** Each class has one reason to change
4. **Layers separate concerns:** Domain, application, infrastructure are independent
5. **Use cases orchestrate:** They coordinate without containing business logic
6. **Ports enable flexibility:** Swap infrastructure without touching application code
7. **Tests provide safety:** Change confidently knowing tests catch regressions

This is intentional architecture. Not following templates, but making deliberate decisions driven by constraints and requirements.

Start simple. Add structure when complexity demands it. Let tests guide your design. Apply patterns when they solve real problems.

Architecture isn't something you impose. It's something that emerges when you make intentional decisions.
