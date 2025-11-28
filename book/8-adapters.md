# Chapter 8: Infrastructure Implementation

Ports define the contract. Adapters fulfill it.

In Chapter 7, we inverted the dependencies. We created ports—abstract interfaces that define what the application needs from infrastructure. `MemberRepository` declares `get_by_id()` and `save()`. `NotificationService` declares `send_booking_confirmation()`. The use cases depend on these abstractions, not on concrete implementations.

This solved the dependency problem. The application no longer knows about databases or email servers. It knows about contracts.

But we can't run the application yet. Abstract classes can't be instantiated. Ports have no behaviour. They're promises waiting to be fulfilled.

This chapter fulfills those promises. We're going to implement adapters—concrete classes that plug into our ports and connect the application to real infrastructure. PostgreSQL databases. SMTP email servers. File systems. External APIs. Whatever the application needs, adapters provide.

By the end, you'll have a complete, working system. Use cases orchestrating domain logic. Ports defining boundaries. Adapters connecting to infrastructure. Everything wired together through dependency injection. A system you can actually run.

From abstract to concrete. From design to implementation. Let's build the adapters.

## What Is an Adapter?

An adapter is a concrete implementation of a port that translates between the application and infrastructure.

The application speaks in domain terms: `Member`, `Booking`, `FitnessClass`. Infrastructure speaks in technical terms: database rows, SQL queries, JSON payloads, SMTP protocols.

The adapter bridges the gap. It implements the port's contract using infrastructure primitives. It takes domain objects and persists them. It loads data and reconstructs domain objects. It translates between two worlds that don't understand each other.

Here's what that looks like for `MemberRepository`:

```python
# The port (from Chapter 7)
class MemberRepository(ABC):
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def save(self, member: Member) -> None:
        pass

# The adapter (this chapter)
class PostgresMemberRepository(MemberRepository):
    def __init__(self, session):
        self.session = session
    
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

## Building Database Adapters with SQLAlchemy

Let's implement repository adapters using SQLAlchemy, a popular Python ORM. We'll connect to PostgreSQL, but the pattern works for any database.

First, we need to map our domain entities to database tables. SQLAlchemy uses declarative base classes for this:

```python
# infrastructure/database/models.py
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class MemberModel(Base):
    """SQLAlchemy model for Member persistence."""
    __tablename__ = 'members'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    credits = Column(Integer, nullable=False, default=0)
    membership_type = Column(String, nullable=False)
    membership_price = Column(Float, nullable=False)
    membership_credits_per_month = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class FitnessClassModel(Base):
    """SQLAlchemy model for FitnessClass persistence."""
    __tablename__ = 'fitness_classes'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    capacity = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 1=Monday, 7=Sunday
    start_time = Column(String, nullable=False)    # Store as "HH:MM"
    end_time = Column(String, nullable=False)
    bookings = Column(String)  # JSON array of member IDs


class BookingModel(Base):
    """SQLAlchemy model for Booking persistence."""
    __tablename__ = 'bookings'
    
    id = Column(String, primary_key=True)
    member_id = Column(String, ForeignKey('members.id'), nullable=False)
    class_id = Column(String, ForeignKey('fitness_classes.id'), nullable=False)
    status = Column(String, nullable=False)
    booked_at = Column(DateTime, default=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)
```

These are ORM models—database representations of our domain concepts. They're not the same as domain entities. Domain entities have behaviour and enforce rules. ORM models are data containers that map to tables.

Keeping them separate is crucial. The domain stays pure. Infrastructure handles persistence details.

Now we implement the adapter that translates between them:

```python
# infrastructure/database/member_repository.py
from typing import Optional, List
from sqlalchemy.orm import Session

from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType
from application.ports.repositories import MemberRepository
from infrastructure.database.models import MemberModel


class SQLAlchemyMemberRepository(MemberRepository):
    """
    Adapter implementing MemberRepository using SQLAlchemy.
    
    Translates between Member domain objects and database rows.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, member_id: str) -> Optional[Member]:
        """Load a member from the database and reconstruct domain object."""
        model = self.session.query(MemberModel).filter_by(id=member_id).first()
        
        if not model:
            return None
        
        return self._to_domain(model)
    
    def save(self, member: Member) -> None:
        """Persist a member domain object to the database."""
        model = self.session.query(MemberModel).filter_by(id=member.id).first()
        
        if model:
            # Update existing
            self._update_from_domain(model, member)
        else:
            # Create new
            model = self._to_model(member)
            self.session.add(model)
        
        self.session.commit()
    
    def find_by_email(self, email: str) -> Optional[Member]:
        """Find a member by email address."""
        model = self.session.query(MemberModel).filter_by(email=email).first()
        
        if not model:
            return None
        
        return self._to_domain(model)
    
    def list_all(self) -> List[Member]:
        """Retrieve all members."""
        models = self.session.query(MemberModel).all()
        return [self._to_domain(model) for model in models]
    
    def _to_domain(self, model: MemberModel) -> Member:
        """Convert database model to domain entity."""
        email = EmailAddress(model.email)
        membership = MembershipType(
            name=model.membership_type,
            credits_per_month=model.membership_credits_per_month,
            price=model.membership_price
        )
        
        member = Member(
            member_id=model.id,
            name=model.name,
            email=email,
            membership_type=membership
        )
        
        # Restore credit state
        member._credits = model.credits
        
        return member
    
    def _to_model(self, member: Member) -> MemberModel:
        """Convert domain entity to database model."""
        return MemberModel(
            id=member.id,
            name=member.name,
            email=member.email.value,
            credits=member.credits,
            membership_type=member.membership_type.name,
            membership_price=member.membership_type.price,
            membership_credits_per_month=member.membership_type.credits_per_month
        )
    
    def _update_from_domain(self, model: MemberModel, member: Member) -> None:
        """Update existing model from domain entity."""
        model.name = member.name
        model.email = member.email.value
        model.credits = member.credits
        model.membership_type = member.membership_type.name
        model.membership_price = member.membership_type.price
        model.membership_credits_per_month = member.membership_type.credits_per_month
```

Look at what's happening here. The adapter:

1. **Depends on the port**: `class SQLAlchemyMemberRepository(MemberRepository)`. It implements the abstraction.
2. **Knows about infrastructure**: SQLAlchemy session, queries, models. The application doesn't.
3. **Translates between worlds**: `_to_domain()` converts database rows to domain objects. `_to_model()` does the reverse.
4. **Handles persistence logic**: Creating vs updating. Committing transactions. Loading relationships.

The translation methods are crucial. `_to_domain()` reconstructs a `Member` entity with all its value objects. `_to_model()` extracts the data needed for persistence. The domain and infrastructure remain separate.

Let's implement the booking repository:

```python
# infrastructure/database/booking_repository.py
from typing import Optional, List
from sqlalchemy.orm import Session

from domain.entities import Booking, BookingStatus
from application.ports.repositories import BookingRepository
from infrastructure.database.models import BookingModel


class SQLAlchemyBookingRepository(BookingRepository):
    """Adapter implementing BookingRepository using SQLAlchemy."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        """Load a booking from the database."""
        model = self.session.query(BookingModel).filter_by(id=booking_id).first()
        
        if not model:
            return None
        
        return self._to_domain(model)
    
    def save(self, booking: Booking) -> None:
        """Persist a booking to the database."""
        model = self.session.query(BookingModel).filter_by(id=booking.id).first()
        
        if model:
            self._update_from_domain(model, booking)
        else:
            model = self._to_model(booking)
            self.session.add(model)
        
        self.session.commit()
    
    def find_by_member(self, member_id: str) -> List[Booking]:
        """Find all bookings for a specific member."""
        models = self.session.query(BookingModel).filter_by(member_id=member_id).all()
        return [self._to_domain(model) for model in models]
    
    def find_by_class(self, class_id: str) -> List[Booking]:
        """Find all bookings for a specific class."""
        models = self.session.query(BookingModel).filter_by(class_id=class_id).all()
        return [self._to_domain(model) for model in models]
    
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        """Find a specific booking for a member in a class."""
        model = self.session.query(BookingModel).filter_by(
            member_id=member_id,
            class_id=class_id
        ).first()
        
        if not model:
            return None
        
        return self._to_domain(model)
    
    def find_by_status(self, status: BookingStatus) -> List[Booking]:
        """Find all bookings with a given status."""
        models = self.session.query(BookingModel).filter_by(
            status=status.value
        ).all()
        return [self._to_domain(model) for model in models]
    
    def _to_domain(self, model: BookingModel) -> Booking:
        """Convert database model to domain entity."""
        booking = Booking(
            booking_id=model.id,
            member_id=model.member_id,
            class_id=model.class_id
        )
        
        # Restore status from database
        booking._status = BookingStatus(model.status)
        booking._booked_at = model.booked_at
        booking._cancelled_at = model.cancelled_at
        
        return booking
    
    def _to_model(self, booking: Booking) -> BookingModel:
        """Convert domain entity to database model."""
        return BookingModel(
            id=booking.id,
            member_id=booking.member_id,
            class_id=booking.class_id,
            status=booking.status.value,
            booked_at=booking._booked_at,
            cancelled_at=booking._cancelled_at
        )
    
    def _update_from_domain(self, model: BookingModel, booking: Booking) -> None:
        """Update existing model from domain entity."""
        model.status = booking.status.value
        model.cancelled_at = booking._cancelled_at
```

Same pattern. Implement the port. Translate between domain and database. Keep the layers separate.

One more repository—fitness classes:

```python
# infrastructure/database/class_repository.py
from typing import Optional, List
from datetime import time
import json
from sqlalchemy.orm import Session

from domain.entities import FitnessClass
from domain.value_objects import ClassCapacity, TimeSlot, DayOfWeek
from application.ports.repositories import FitnessClassRepository
from infrastructure.database.models import FitnessClassModel


class SQLAlchemyFitnessClassRepository(FitnessClassRepository):
    """Adapter implementing FitnessClassRepository using SQLAlchemy."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, class_id: str) -> Optional[FitnessClass]:
        """Load a fitness class from the database."""
        model = self.session.query(FitnessClassModel).filter_by(id=class_id).first()
        
        if not model:
            return None
        
        return self._to_domain(model)
    
    def save(self, fitness_class: FitnessClass) -> None:
        """Persist a fitness class to the database."""
        model = self.session.query(FitnessClassModel).filter_by(id=fitness_class.id).first()
        
        if model:
            self._update_from_domain(model, fitness_class)
        else:
            model = self._to_model(fitness_class)
            self.session.add(model)
        
        self.session.commit()
    
    def find_by_time_slot(self, time_slot: TimeSlot) -> List[FitnessClass]:
        """Find all classes in a given time slot."""
        models = self.session.query(FitnessClassModel).filter_by(
            day_of_week=time_slot.day.value,
            start_time=time_slot.start_time.strftime("%H:%M")
        ).all()
        
        return [self._to_domain(model) for model in models]
    
    def list_all(self) -> List[FitnessClass]:
        """Retrieve all fitness classes."""
        models = self.session.query(FitnessClassModel).all()
        return [self._to_domain(model) for model in models]
    
    def _to_domain(self, model: FitnessClassModel) -> FitnessClass:
        """Convert database model to domain entity."""
        capacity = ClassCapacity(model.capacity)
        
        # Parse time strings back to time objects
        start_time = time.fromisoformat(model.start_time)
        end_time = time.fromisoformat(model.end_time)
        day = DayOfWeek(model.day_of_week)
        
        time_slot = TimeSlot(day, start_time, end_time)
        
        fitness_class = FitnessClass(
            class_id=model.id,
            name=model.name,
            capacity=capacity,
            time_slot=time_slot
        )
        
        # Restore bookings from JSON
        if model.bookings:
            fitness_class._bookings = json.loads(model.bookings)
        
        return fitness_class
    
    def _to_model(self, fitness_class: FitnessClass) -> FitnessClassModel:
        """Convert domain entity to database model."""
        return FitnessClassModel(
            id=fitness_class.id,
            name=fitness_class.name,
            capacity=fitness_class.capacity.value,
            day_of_week=fitness_class.time_slot.day.value,
            start_time=fitness_class.time_slot.start_time.strftime("%H:%M"),
            end_time=fitness_class.time_slot.end_time.strftime("%H:%M"),
            bookings=json.dumps(fitness_class._bookings)
        )
    
    def _update_from_domain(self, model: FitnessClassModel, 
                           fitness_class: FitnessClass) -> None:
        """Update existing model from domain entity."""
        model.name = fitness_class.name
        model.capacity = fitness_class.capacity.value
        model.day_of_week = fitness_class.time_slot.day.value
        model.start_time = fitness_class.time_slot.start_time.strftime("%H:%M")
        model.end_time = fitness_class.time_slot.end_time.strftime("%H:%M")
        model.bookings = json.dumps(fitness_class._bookings)
```

Notice how we handle value objects. `ClassCapacity` wraps an integer. `TimeSlot` contains a day and times. The adapter extracts these components for storage and reconstructs them when loading.

This is the adapter's job: preserve domain richness while working with infrastructure constraints.

## Implementing Service Adapters

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

## In-Memory Adapters for Testing

Remember the fake repositories from Chapter 7? Those are adapters too. Let's implement them properly:

```python
# infrastructure/adapters/in_memory/member_repository.py
from typing import Dict, Optional, List

from domain.entities import Member
from application.ports.repositories import MemberRepository


class InMemoryMemberRepository(MemberRepository):
    """
    In-memory implementation of MemberRepository.
    
    Stores members in a dictionary. Fast, simple, perfect for testing.
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
    """In-memory implementation of BookingRepository."""
    
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
    """In-memory implementation of FitnessClassRepository."""
    
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

## Wiring It All Together: Dependency Injection

We have ports. We have adapters. Now we need to connect them.

This is dependency injection—providing implementations to components that depend on abstractions. The use cases declare what they need via constructor parameters. Something external provides the concrete implementations.

Here's a simple composition root that wires everything together:

```python
# infrastructure/composition.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from application.use_cases.book_class import BookClassUseCase
from application.use_cases.cancel_booking import CancelBookingUseCase
from application.use_cases.process_waitlist import ProcessWaitlistUseCase
from infrastructure.database.member_repository import SQLAlchemyMemberRepository
from infrastructure.database.booking_repository import SQLAlchemyBookingRepository
from infrastructure.database.class_repository import SQLAlchemyFitnessClassRepository
from infrastructure.services.email_notification_service import SMTPNotificationService
from infrastructure.services.console_notification_service import ConsoleNotificationService


class ApplicationContainer:
    """
    Dependency injection container.
    
    Wires together all the pieces of the application.
    Provides configured use cases ready to execute.
    """
    
    def __init__(self, database_url: str, use_real_email: bool = False):
        # Create database session
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        self.session = SessionLocal()
        
        # Create repository adapters
        self.member_repository = SQLAlchemyMemberRepository(self.session)
        self.booking_repository = SQLAlchemyBookingRepository(self.session)
        self.class_repository = SQLAlchemyFitnessClassRepository(self.session)
        
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
        # Note: We'd need a WaitlistRepository implementation too
        return ProcessWaitlistUseCase(
            waitlist_repository=None,  # Would wire this up
            member_repository=self.member_repository,
            class_repository=self.class_repository,
            booking_repository=self.booking_repository,
            notification_service=self.notification_service
        )
    
    def cleanup(self):
        """Clean up resources."""
        self.session.close()
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
        database_url="postgresql://user:password@localhost/fitness",
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

## Testing with Different Adapters

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
        membership = MembershipType("Premium", credits_per_month=10, price=50)
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
        membership = MembershipType("Premium", credits_per_month=10, price=50)
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
        membership = MembershipType("Premium", credits_per_month=10, price=50)
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType
from infrastructure.database.models import Base
from infrastructure.database.member_repository import SQLAlchemyMemberRepository


class TestSQLAlchemyMemberRepository:
    """Integration tests for database repository."""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Create a test database before each test."""
        # Use in-memory SQLite for tests
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(bind=engine)
        self.session = SessionLocal()
        self.repository = SQLAlchemyMemberRepository(self.session)
        
        yield
        
        self.session.close()
    
    def test_save_and_retrieve_member(self):
        """Test that we can save and retrieve a member."""
        # Arrange
        email = EmailAddress("sarah@example.com")
        membership = MembershipType("Premium", credits_per_month=10, price=50)
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
        membership = MembershipType("Premium", credits_per_month=10, price=50)
        member = Member("M001", "Sarah", email, membership)
        self.repository.save(member)
        
        # Act
        found = self.repository.find_by_email("sarah@example.com")
        
        # Assert
        assert found is not None
        assert found.id == "M001"
```

Same port. Different adapters. Tests for both.

## A Complete Running Example

Let's build a simple CLI application that demonstrates everything working together:

```python
# cli.py
from datetime import time
from infrastructure.composition import ApplicationContainer
from domain.entities import Member, FitnessClass
from domain.value_objects import EmailAddress, MembershipType, ClassCapacity, TimeSlot, DayOfWeek
from infrastructure.database.models import Base
from sqlalchemy import create_engine


def setup_database(database_url: str):
    """Create database tables."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


def seed_data(container: ApplicationContainer):
    """Add some initial test data."""
    # Create a member
    email = EmailAddress("sarah@example.com")
    membership = MembershipType("Premium", credits_per_month=10, price=50)
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
    database_url = "sqlite:///fitness.db"
    
    # Set up database
    print("Setting up database...")
    setup_database(database_url)
    
    # Create application container
    container = ApplicationContainer(
        database_url=database_url,
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

## Directory Structure

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
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   ├── member_repository.py
│   │   ├── booking_repository.py
│   │   └── class_repository.py
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

## Handling Errors in Adapters

Adapters sit at the boundary between your application and external systems. Networks fail. Databases go down. APIs return errors. You need to handle this gracefully.

The strategy depends on the error:

**For domain violations, throw domain exceptions:**

```python
def get_by_id(self, member_id: str) -> Optional[Member]:
    model = self.session.query(MemberModel).filter_by(id=member_id).first()
    
    if not model:
        return None  # Not found is a valid state
    
    try:
        return self._to_domain(model)
    except ValueError as e:
        # Database contains invalid data - this is a domain violation
        raise DomainValidationError(f"Invalid member data: {e}")
```

**For infrastructure failures, throw infrastructure exceptions:**

```python
def save(self, member: Member) -> None:
    try:
        model = self._to_model(member)
        self.session.add(model)
        self.session.commit()
    except SQLAlchemyError as e:
        self.session.rollback()
        raise RepositoryException(f"Failed to save member: {e}")
```

**For transient errors, retry with exponential backoff:**

```python
def _send_email(self, to_email: str, subject: str, body: str) -> None:
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return  # Success
        except smtplib.SMTPException as e:
            if attempt == max_retries - 1:
                raise NotificationException(f"Failed after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
```

The use cases decide how to handle these exceptions. The adapters just raise them appropriately.

## When to Create New Adapters

You create a new adapter when:

**You need a different storage mechanism.** PostgreSQL for production. SQLite for development. MongoDB for a microservice.

**You need different behaviour in different environments.** Real email in production. Console output in development. Fake in tests.

**You're integrating with a new external system.** Stripe for payments initially. PayPal added later. Both implement `PaymentService`.

**You're optimising for different concerns.** Database repository for durability. Cache repository for speed. Both implement the same port.

You don't create a new adapter when:

**The logic is domain-specific.** That belongs in the domain layer, not infrastructure.

**It's just a variation in configuration.** Use dependency injection to pass different config, not different adapters.

**You're adding new operations.** Extend the port first, then implement it in all adapters.

Adapters translate between domains. If you're not translating, you probably don't need an adapter.

## The Architecture Is Complete

You started with a problem: use cases need infrastructure, but depending on it violates the dependency rule.

You defined ports in Chapter 7—abstractions that specify what the application needs without dictating how it's provided.

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
│ SQLAlchemyMember  │  │ SMTPNotif     │  │ InMemoryMember│
│ Repository        │  │ Service       │  │ Repository    │
│ (Production)      │  │ (Production)  │  │ (Tests)       │
└───────────────────┘  └───────────────┘  └───────────────┘
```

Dependencies point inward. High-level policy doesn't depend on low-level details. Both depend on abstractions.

You can swap PostgreSQL for MongoDB without touching use cases. You can swap SMTP for SendGrid without changing application logic. You can test with in-memory fakes without needing infrastructure.

This is hexagonal architecture fully realised. This is ports and adapters in practice. This is clean architecture applied.

Your codebase is organised. Your domain is pure. Your application is decoupled from infrastructure. Your tests are fast and focused.

The architecture serves the business logic. Not the other way around.

## Summary

Adapters implement ports using concrete infrastructure. They translate between the domain's language and the infrastructure's technical details.

We built database adapters with SQLAlchemy—`SQLAlchemyMemberRepository`, `SQLAlchemyBookingRepository`, `SQLAlchemyFitnessClassRepository`. These adapters convert domain entities to ORM models and back. They handle queries, persistence, and transactions.

We built service adapters for notifications—`SMTPNotificationService` for production and `ConsoleNotificationService` for development. Same port, different implementations, swappable at runtime.

We created in-memory adapters for testing—simple dictionary-based repositories that implement the same ports as production adapters. Fast, deterministic, perfect for unit tests.

We wired everything together with dependency injection through an `ApplicationContainer`. The container creates adapters and injects them into use cases. Configuration happens in one place. The rest of the application just receives what it needs.

We demonstrated error handling in adapters—distinguishing between domain violations, infrastructure failures, and transient errors. Each type gets handled appropriately.

The complete system works. You can run it. You can test it. You can swap implementations without changing application code.

The architecture is no longer theoretical. It's practical. It's real. It works.

You've built a system where business logic lives in the domain, orchestration lives in the application, and technical details live in infrastructure. Clean boundaries. Clear responsibilities. Maintainable structure.

This is intentional architecture. This is software that adapts to change instead of fighting it.

The foundation is solid. The patterns are proven. The system is ready to grow.
