# Chapter 6: Use Cases & Application Layer

We have a rich domain from Chapter 5. `Member`, `FitnessClass`, and `Booking` entities enforce business rules. Value objects like `TimeSlot` and `EmailAddress` make invalid states impossible. The domain layer is solid.

Now we need to build the application layer that orchestrates it.

A use case is a single place that defines one complete workflow. "Book a class." "Cancel a booking." "Process waitlist." Each use case coordinates domain objects to accomplish a specific goal.

This chapter builds those use cases.

## What Is a Use Case?

A use case is a single action that accomplishes a specific goal from a user's perspective.

Not "save a booking to the database." That's too technical. Not "update member credits and check class capacity and send email and log the event." That's too granular.

"Book a member into a fitness class." That's a use case. It's what the user wants. The outcome they care about. Everything else is implementation detail.

Use cases are:
- **Goal-oriented**: They accomplish something meaningful for a user
- **Orchestrating**: They coordinate domain objects but don't contain business logic
- **Transaction boundaries**: They define what happens together or not at all
- **Application-specific**: Different applications using the same domain might have different use cases

Use cases are not:
- **Business rules**: Those belong in the domain
- **CRUD operations**: "Create a booking" is too generic—what are you trying to accomplish?
- **Infrastructure concerns**: Saving to a database is a detail, not a use case
- **UI actions**: "Click the book button" describes interaction, not intent

Here's the distinction in practice. Business logic belongs in the domain:

```python
# Domain layer - business rules
class FitnessClass:
    def add_booking(self, member_id: str):
        if self.is_full():
            raise ClassFullException(f"Class {self._name} is at capacity")
        
        if member_id in self._bookings:
            raise ValueError("Member already booked in this class")
        
        self._bookings.append(member_id)
```

Orchestration belongs in the application layer:

```python
# Application layer - use case orchestration
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        # Load the objects we need
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        # Let the domain enforce its rules
        member.deduct_credit()
        fitness_class.add_booking(member_id)
        
        # Create the booking aggregate
        booking = Booking(generate_id(), member_id, class_id)
        
        # Persist the changes
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # Notify the member
        self.notification_service.send_confirmation(member, fitness_class)
        
        return booking
```

The domain knows *what* the rules are. The application layer knows *how* to orchestrate them into complete workflows.

## Starting with BookClassUseCase

**Naming Note:** In Chapter 2, we called these "services" (e.g., `BookingService`). Now we call them "use cases" (e.g., `BookClassUseCase`). The terms are similar but have nuance:
- **Service** is a general term for objects that perform operations
- **Use case** specifically means "a single user goal-oriented workflow"

Use case is more precise. It emphasizes that each class represents one complete user action, not just a collection of related operations. Going forward, we'll use "use case" for application-layer orchestration and reserve "service" for domain services (Chapter 5) and infrastructure services (email, payment, etc.).

Let's build the most fundamental use case in our gym booking system: booking a member into a fitness class.

From the user's perspective, this is simple: "I want to attend this class." But internally, there's coordination required:

1. Load the member and verify they exist
2. Load the class and verify it exists
3. Check if the member has enough credits
4. Check if the class has capacity
5. Deduct a credit from the member
6. Add the member to the class
7. Create a booking record
8. Save everything
9. Send a confirmation

The domain handles steps 3-6. The application layer handles everything else.

Here's our first use case:

```python
from datetime import datetime
from typing import Optional
from uuid import uuid4

from domain.entities import Member, FitnessClass, Booking, BookingStatus
from domain.exceptions import ClassFullException, InsufficientCreditsException


def generate_id() -> str:
    """Generate a unique ID for domain entities."""
    return str(uuid4())


class BookClassUseCase:
    def __init__(self, member_repository, class_repository, 
                 booking_repository, notification_service):
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
        member.deduct_credit()  # Raises InsufficientCreditsException if no credits
        fitness_class.add_booking(member_id)  # Raises ClassFullException if full
        
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

Look at what this use case does and doesn't do.

**It does:**
- Load objects from persistence
- Coordinate the sequence of operations
- Create new aggregates
- Save changes
- Trigger notifications

**It doesn't:**
- Check if the class is full (that's `FitnessClass.add_booking()`)
- Validate credit balance (that's `Member.deduct_credit()`)
- Know how to calculate credits (that's in the domain)
- Know how emails are sent (that's abstracted behind `notification_service`)
- Know what database is used (that's abstracted behind repositories)

The business rules stay in the domain. The orchestration happens here.

### Using the BookClassUseCase: Error Handling in Practice

The use case raises domain exceptions when business rules are violated. Here's how you'd use it in practice, handling the different scenarios that can occur:

```python
from domain.exceptions import ClassFullException, InsufficientCreditsException

# In your interface layer (CLI, API, etc.)
try:
    booking = book_class_use_case.execute("M001", "C001")
    print(f"Success! Booking confirmed: {booking.id}")
    print("Your booking is confirmed!")
    
except ValueError as e:
    # Member or class not found
    print(f"Booking failed: {e}")
    # Perhaps show available classes or search for member
    
except InsufficientCreditsException as e:
    # Member needs more credits
    print(f"Sorry, you don't have enough credits: {e}")
    print("Purchase more credits to continue")
    # Redirect to purchase flow
    
except ClassFullException as e:
    # Class is at capacity
    print(f"This class is full: {e}")
    print("Would you like to join the waitlist?")
    # Offer waitlist option
```

Notice how each exception represents a distinct business scenario. Your interface layer can respond appropriately to each one—showing different messages, offering different next actions, logging different metrics.

The use case doesn't catch these exceptions. It lets them bubble up. Why? Because the use case shouldn't decide how to present errors to users. That's an interface concern. The use case's job is to enforce business rules and report violations. How those violations are communicated to users depends on the interface—CLI, web API, mobile app—and that's decided higher up.

This separation matters. The same use case can be called from a REST API (which returns HTTP 400 with JSON), a CLI (which prints error messages), or a background job (which logs to a monitoring service). Each interface handles errors differently, but the use case stays the same.

## Handling Cancellations

Cancelling a booking is more nuanced. There are time restrictions. There are state transitions. There are refunds. Let's build `CancelBookingUseCase`:

```python
from datetime import datetime, timedelta

from domain.entities import Booking, BookingStatus
from domain.exceptions import BookingNotCancellableException


class CancelBookingUseCase:
    def __init__(self, booking_repository, member_repository, 
                 class_repository, notification_service):
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
        # In a real system, this would come from the class's actual scheduled datetime
        # For now, we'll use a simplified approach
        class_start_time = self._get_next_class_occurrence(fitness_class.time_slot)
        
        # 4. Let the domain enforce cancellation rules
        booking.cancel(class_start_time)  # Raises BookingNotCancellableException
        
        # 5. Load the member and refund the credit
        member = self.member_repository.get_by_id(booking.member_id)
        if member:  # Member might have been deleted, handle gracefully
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
        """
        Find the next occurrence of this time slot.
        
        NOTE: This helper demonstrates the workflow, but in a production system,
        this date calculation logic should live in the domain layer—either as a
        method on TimeSlot value object or in a domain service. Use cases should
        orchestrate, not implement business logic like time calculations.
        
        Simplified for example purposes.
        """
        now = datetime.now()
        
        # Calculate days until the next occurrence of this day
        current_day = now.weekday() + 1  # Python's weekday is 0-6, our enum is 1-7
        target_day = time_slot.day.value
        days_ahead = (target_day - current_day) % 7
        
        if days_ahead == 0:
            days_ahead = 7  # If it's today, assume we mean next week
        
        next_date = now + timedelta(days=days_ahead)
        
        # Combine the date with the class start time
        return datetime.combine(
            next_date.date(),
            time_slot.start_time
        )
```

**Project Evolution:**
- In Chapter 1, cancellation was a simple function that refunded credits
- In Chapter 2, we separated concerns but logic was still scattered
- In Chapter 3, we wrote tests that defined cancellation behavior
- In Chapter 4, we separated cancellation logic into layers
- In Chapter 5, we added `Booking.cancel()` to enforce business rules (2-hour limit)
- Now in Chapter 6, the use case orchestrates the workflow: load entities, call domain methods, persist changes, send notifications
- This separation means we can test cancellation rules in the domain without touching repositories or notification services


This use case demonstrates several important patterns:

**Defensive loading**: Check if objects exist before operating on them. The domain can't enforce rules on objects that aren't there.

**Graceful degradation**: If the member has been deleted but the booking exists, we still cancel the booking. Real systems have data inconsistencies. Handle them.

**Domain-first validation**: The booking's `cancel()` method enforces the 2-hour rule. The use case doesn't duplicate that logic—it just calls the method and handles the exception if it fails.

**Coordinated state changes**: Multiple aggregates need updating (booking, member, class). The use case coordinates them. If any step fails, the whole operation should fail. This is where transaction boundaries matter, but that's an infrastructure concern we'll address later.

## Cross-Aggregate Coordination

Sometimes use cases need to coordinate across multiple aggregates in more complex ways. Consider a waitlist scenario: when someone cancels, we want to automatically offer the spot to the next person on the waitlist.

This involves multiple members, multiple bookings, and a class. No single aggregate knows about this workflow—it's pure orchestration.

Here's `ProcessWaitlistUseCase`:

```python
from typing import Optional

from domain.entities import Member, FitnessClass, Booking, BookingStatus


class ProcessWaitlistUseCase:
    def __init__(self, waitlist_repository, member_repository,
                 class_repository, booking_repository, notification_service):
        self.waitlist_repository = waitlist_repository
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, class_id: str) -> Optional[Booking]:
        """
        Process the waitlist for a class when a spot becomes available.
        
        Returns the booking created, or None if no one on waitlist.
        """
        # 1. Load the class
        fitness_class = self.class_repository.get_by_id(class_id)
        if not fitness_class:
            raise ValueError(f"Class {class_id} not found")
        
        # 2. Check if there's space
        if fitness_class.is_full():
            return None  # No space available, nothing to do
        
        # 3. Get the next person on the waitlist
        next_in_line = self.waitlist_repository.get_next_for_class(class_id)
        if not next_in_line:
            return None  # Waitlist is empty
        
        # 4. Load the member
        member = self.member_repository.get_by_id(next_in_line.member_id)
        if not member:
            # Member no longer exists, remove from waitlist and try next
            self.waitlist_repository.remove(next_in_line)
            # Recursively process next person in waitlist
            # NOTE: In production, consider iterative approach to avoid stack overflow
            # with long waitlists, or add a max recursion depth parameter
            return self.execute(class_id)
        
        # 5. Check if member still has credits
        try:
            member.deduct_credit()
        except InsufficientCreditsException:
            # Member has no credits, remove from waitlist and try next
            self.waitlist_repository.remove(next_in_line)
            self.notification_service.send_waitlist_insufficient_credits(
                member.email.value,
                member.name,
                fitness_class.name
            )
            # Recursively process next person in waitlist
            # NOTE: See recursion note above
            return self.execute(class_id)
        
        # 6. Book the member into the class
        try:
            fitness_class.add_booking(member.id)
        except ClassFullException:
            # Race condition: class filled while we were processing
            # Refund the credit and stop
            member.add_credits(1, expiry_days=30)
            self.member_repository.save(member)
            return None
        
        # 7. Create the booking
        booking = Booking(generate_id(), member.id, class_id)
        
        # 8. Remove from waitlist
        self.waitlist_repository.remove(next_in_line)
        
        # 9. Persist everything
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # 10. Notify the member they got off the waitlist
        self.notification_service.send_waitlist_booking_confirmation(
            member.email.value,
            member.name,
            fitness_class.name,
            fitness_class.time_slot
        )
        
        return booking
```

This use case shows the complexity that can emerge even with simple business rules:

**Error recovery**: If the next person on the waitlist has no credits or doesn't exist anymore, remove them and try the next person. The domain enforces the rules; the use case handles the coordination.

**Race conditions**: Between checking if the class has space and booking, another process might fill the spot. The use case handles this by catching `ClassFullException` and rolling back the credit deduction.

**Recursive processing**: Processing the waitlist is inherently recursive—if one person can't be booked, try the next. The use case orchestrates this flow.

Notice what we're not doing: we're not putting this logic in `FitnessClass`. The class doesn't know about waitlists. We're not putting it in `Member`. The member doesn't know about waitlists. We're not putting it in `Booking`. The booking doesn't know about waitlists.

The waitlist processing is a workflow that coordinates multiple aggregates. That's exactly what use cases are for.

## The Structure of the Application Layer

Let's organise these use cases into a proper application layer structure:

```
application/
    use_cases/
        __init__.py
        book_class.py         # BookClassUseCase
        cancel_booking.py     # CancelBookingUseCase
        process_waitlist.py   # ProcessWaitlistUseCase
    __init__.py
```

Each use case gets its own file. This keeps them focused and easy to find. You could also group related use cases:

```
application/
    use_cases/
        __init__.py
        booking/
            __init__.py
            book_class.py
            cancel_booking.py
        waitlist/
            __init__.py
            process_waitlist.py
            add_to_waitlist.py
    __init__.py
```

Either works. The flat structure is simpler for small applications. The grouped structure scales better as you add more use cases. Start flat, refactor when it gets crowded.

The key is that each use case is isolated. They don't call each other. They don't share state. Each one is an independent entry point into the application.

## Common Mistakes

Now that you've seen how to build use cases, let's look at how not to build them.

### Mistake 1: Business Logic in Use Cases

This is the most common mistake. It's tempting to put business rules in use cases because they're right there, in the same function as the workflow.

**Wrong:**

```python
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        # DON'T DO THIS - business logic in the use case
        if member.credits <= 0:
            raise InsufficientCreditsException("No credits")
        
        if fitness_class.booking_count() >= fitness_class.capacity.value:
            raise ClassFullException("Class is full")
        
        member._credits -= 1  # Directly modifying state
        fitness_class._bookings.append(member_id)
        
        # ...
```

Now the business rules are duplicated. Every use case that needs to check credits has to implement the same logic. Every use case that needs to add a booking has to check capacity. When the rules change, you change every use case.

**Right:**

```python
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        # Let the domain enforce its own rules
        member.deduct_credit()  # Knows how to handle credit logic
        fitness_class.add_booking(member_id)  # Knows how to handle capacity
        
        # ...
```

The business rules live in one place: the domain. The use case just calls them.

### Mistake 2: Use Cases Calling Use Cases

It's tempting to reuse use cases by having them call each other.

**Wrong:**

```python
class BookClassWithWaitlistUseCase:
    def __init__(self, book_class_use_case, add_to_waitlist_use_case):
        self.book_class = book_class_use_case
        self.add_to_waitlist = add_to_waitlist_use_case
    
    def execute(self, member_id: str, class_id: str):
        try:
            return self.book_class.execute(member_id, class_id)
        except ClassFullException:
            self.add_to_waitlist.execute(member_id, class_id)
```

This creates coupling between use cases. Now you can't change `BookClassUseCase` without considering `BookClassWithWaitlistUseCase`. You can't test them independently. You create hidden dependencies.

**Right:**

Use cases should be independent. If you need to book *or* waitlist, create a single use case that handles both scenarios:

```python
from domain.entities import WaitlistEntry  # Part of domain model

class BookClassOrWaitlistUseCase:
    def execute(self, member_id: str, class_id: str):
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        if fitness_class.is_full():
            # Add to waitlist
            waitlist_entry = WaitlistEntry(generate_id(), member_id, class_id)
            self.waitlist_repository.save(waitlist_entry)
            self.notification_service.send_waitlist_confirmation(...)
        else:
            # Book directly
            member.deduct_credit()
            fitness_class.add_booking(member_id)
            booking = Booking(generate_id(), member_id, class_id)
            # ...
```

Duplicate the orchestration if needed. Use cases are cheap. Coupling is expensive.

### Mistake 3: Anemic Use Cases

Sometimes developers create use cases that are just pass-throughs:

**Wrong:**

```python
class GetMemberUseCase:
    def execute(self, member_id: str) -> Member:
        return self.member_repository.get_by_id(member_id)
```

This isn't a use case. It's a repository method with extra steps. Use cases should orchestrate workflows, not just delegate to a single operation.

If you find yourself creating use cases that just call one method, you don't need a use case. Just call the method directly from your interface layer.

Use cases exist to coordinate complexity. If there's no complexity to coordinate, skip the use case.

## Error Handling in Use Cases

Use cases are where domain exceptions meet application concerns. Understanding how to handle exceptions properly in this layer is critical to building robust applications.

### The Three Types of Exceptions

Use cases deal with three categories of exceptions:

1. **Domain exceptions:** Business rule violations (from the domain layer)
2. **Infrastructure exceptions:** Technical failures (from repositories, external services)
3. **Application exceptions:** Use case-specific errors (validation, not found, etc.)

Each type requires different handling.

### Handling Domain Exceptions

Domain exceptions signal business rule violations. They're expected conditions that the business has defined. The use case should generally let these propagate to the interface layer, possibly after taking some application-level action:

```python
# application/use_cases/book_class.py
from domain.exceptions import ClassFullException, InsufficientCreditsException

class BookClassUseCase:
    def execute(self, member_id: str, class_id: str) -> Booking:
        member = self.member_repository.get_by_id(member_id)
        if not member:
            raise ValueError(f"Member {member_id} not found")
        
        fitness_class = self.class_repository.get_by_id(class_id)
        if not fitness_class:
            raise ValueError(f"Class {class_id} not found")
        
        try:
            # Domain enforces business rules
            member.deduct_credit()
            fitness_class.add_booking(member_id)
        except InsufficientCreditsException:
            # Log for analytics, but let it propagate
            logger.info(f"Booking attempt failed: member {member_id} has no credits")
            raise  # Re-raise for interface layer to handle
        except ClassFullException:
            # Different business scenario - potentially take different action
            logger.info(f"Booking attempt failed: class {class_id} is full")
            # Could automatically add to waitlist here if that's a business rule
            raise
        
        # Create booking and save
        booking = Booking(generate_id(), member_id, class_id)
        self.booking_repository.save(booking)
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        
        # Send notification
        self.notification_service.send_booking_confirmation(
            member.email.value, member.name, fitness_class.name, fitness_class.time_slot
        )
        
        return booking
```

**Key principles:**

- **Don't suppress domain exceptions:** They represent legitimate business scenarios
- **Log for observability:** Track which business rules are being triggered
- **Re-raise for the interface layer:** Let the interface decide how to present the error
- **Take application actions if needed:** Like logging, analytics, or cascading operations

### Handling Infrastructure Exceptions

Infrastructure exceptions signal technical failures—database down, network timeout, email service unavailable. These are different from business rule violations. The use case needs to decide: retry, compensate, or fail?

```python
# application/use_cases/book_class.py
from domain.exceptions import InsufficientCreditsException, ClassFullException
from infrastructure.exceptions import RepositoryException, NotificationException

class BookClassUseCase:
    def execute(self, member_id: str, class_id: str) -> Booking:
        try:
            # Load entities
            member = self.member_repository.get_by_id(member_id)
            fitness_class = self.class_repository.get_by_id(class_id)
            
            if not member:
                raise ValueError(f"Member {member_id} not found")
            if not fitness_class:
                raise ValueError(f"Class {class_id} not found")
            
            # Execute domain logic
            member.deduct_credit()
            fitness_class.add_booking(member_id)
            
            # Create booking
            booking = Booking(generate_id(), member_id, class_id)
            
        except RepositoryException as e:
            # Infrastructure failed while reading - can't proceed
            logger.error(f"Repository failure during booking: {e}")
            raise ApplicationException("Unable to process booking due to system error")
        
        # Persist changes
        try:
            self.booking_repository.save(booking)
            self.member_repository.save(member)
            self.class_repository.save(fitness_class)
        except RepositoryException as e:
            # Critical: we've modified domain state but can't persist
            logger.critical(f"Failed to persist booking {booking.id}: {e}")
            # In a real system, this would trigger transaction rollback
            raise ApplicationException("Booking could not be saved. Please try again.")
        
        # Send notification (non-critical - can fail)
        try:
            self.notification_service.send_booking_confirmation(
                member.email.value, member.name, 
                fitness_class.name, fitness_class.time_slot
            )
        except NotificationException as e:
            # Log but don't fail the booking
            logger.warning(f"Failed to send confirmation for booking {booking.id}: {e}")
            # Booking succeeded even though notification failed
        
        return booking
```

**Key principles:**

- **Distinguish critical from non-critical failures:** Database write failures are critical; notification failures aren't
- **Log infrastructure errors with appropriate severity:** Critical for data persistence, warning for notifications
- **Translate to application exceptions when appropriate:** Don't expose infrastructure details to the interface layer
- **Consider compensation:** If part of the operation fails, can you roll back or retry?

### Application-Level Validation

Some validation doesn't belong in the domain (it's not a business rule) but needs to happen before domain logic executes:

```python
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str) -> Booking:
        # Application-level validation
        if not member_id or not member_id.strip():
            raise ValueError("Member ID cannot be empty")
        if not class_id or not class_id.strip():
            raise ValueError("Class ID cannot be empty")
        
        # Check existence
        member = self.member_repository.get_by_id(member_id)
        if not member:
            raise MemberNotFoundException(f"Member {member_id} not found")
        
        fitness_class = self.class_repository.get_by_id(class_id)
        if not fitness_class:
            raise ClassNotFoundException(f"Class {class_id} not found")
        
        # Check for duplicate booking
        existing = self.booking_repository.find_by_member_and_class(member_id, class_id)
        if existing and existing.status == BookingStatus.CONFIRMED:
            raise DuplicateBookingException(
                f"Member {member_id} already has a confirmed booking for class {class_id}"
            )
        
        # Domain logic proceeds...
        member.deduct_credit()
        fitness_class.add_booking(member_id)
        # ...
```

Define application exceptions for these cases:

```python
# application/exceptions.py

class ApplicationException(Exception):
    """Base exception for application layer errors."""
    pass


class ResourceNotFoundException(ApplicationException):
    """Raised when a requested resource doesn't exist."""
    pass


class MemberNotFoundException(ResourceNotFoundException):
    """Raised when a member is not found."""
    
    def __init__(self, member_id: str):
        self.member_id = member_id
        super().__init__(f"Member {member_id} not found")


class ClassNotFoundException(ResourceNotFoundException):
    """Raised when a class is not found."""
    
    def __init__(self, class_id: str):
        self.class_id = class_id
        super().__init__(f"Class {class_id} not found")


class DuplicateBookingException(ApplicationException):
    """Raised when attempting to create a duplicate booking."""
    
    def __init__(self, member_id: str, class_id: str):
        self.member_id = member_id
        self.class_id = class_id
        super().__init__(
            f"Member {member_id} already has a booking for class {class_id}"
        )
```

**Key principles:**

- **Create application-specific exceptions:** They're not domain exceptions (not business rules) but they're not infrastructure exceptions either
- **Validate before domain logic:** Catch issues early before mutating domain state
- **Provide structured context:** Exception attributes make error handling easier

### Complete Error Handling Example

Here's a use case with comprehensive error handling:

```python
# application/use_cases/book_class.py
import logging
from typing import Optional
from uuid import uuid4

from domain.entities import Member, FitnessClass, Booking
from domain.exceptions import ClassFullException, InsufficientCreditsException
from application.exceptions import (
    MemberNotFoundException, 
    ClassNotFoundException,
    DuplicateBookingException
)
from infrastructure.exceptions import RepositoryException, NotificationException

logger = logging.getLogger(__name__)


class BookClassUseCase:
    def __init__(self, member_repository, class_repository, 
                 booking_repository, notification_service):
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, member_id: str, class_id: str) -> Booking:
        """
        Book a member into a fitness class.
        
        Raises:
            MemberNotFoundException: Member doesn't exist
            ClassNotFoundException: Class doesn't exist
            DuplicateBookingException: Member already booked
            InsufficientCreditsException: Member has no credits (domain exception)
            ClassFullException: Class at capacity (domain exception)
            ApplicationException: System error occurred
        """
        # Input validation
        if not member_id or not member_id.strip():
            raise ValueError("Member ID is required")
        if not class_id or not class_id.strip():
            raise ValueError("Class ID is required")
        
        try:
            # Load entities
            member = self.member_repository.get_by_id(member_id)
            if not member:
                raise MemberNotFoundException(member_id)
            
            fitness_class = self.class_repository.get_by_id(class_id)
            if not fitness_class:
                raise ClassNotFoundException(class_id)
            
            # Check for duplicate
            existing = self.booking_repository.find_by_member_and_class(
                member_id, class_id
            )
            if existing and existing.status == BookingStatus.CONFIRMED:
                raise DuplicateBookingException(member_id, class_id)
                
        except RepositoryException as e:
            logger.error(f"Repository error loading data: {e}")
            raise ApplicationException("Unable to load booking data")
        
        # Execute domain logic (may raise domain exceptions)
        try:
            member.deduct_credit()
            fitness_class.add_booking(member_id)
        except InsufficientCreditsException:
            logger.info(f"Booking failed: insufficient credits for member {member_id}")
            raise  # Re-raise domain exception
        except ClassFullException:
            logger.info(f"Booking failed: class {class_id} is full")
            raise  # Re-raise domain exception
        
        # Create booking
        booking = Booking(str(uuid4()), member_id, class_id)
        
        # Persist changes (critical path)
        try:
            self.booking_repository.save(booking)
            self.member_repository.save(member)
            self.class_repository.save(fitness_class)
            logger.info(f"Booking created: {booking.id}")
        except RepositoryException as e:
            logger.critical(f"Failed to persist booking: {e}")
            raise ApplicationException("Booking could not be saved")
        
        # Send notification (non-critical)
        try:
            self.notification_service.send_booking_confirmation(
                member.email.value,
                member.name,
                fitness_class.name,
                fitness_class.time_slot
            )
        except NotificationException as e:
            # Log warning but don't fail the booking
            logger.warning(
                f"Failed to send confirmation for booking {booking.id}: {e}"
            )
        
        return booking
```

This use case demonstrates:

- **Input validation** before touching infrastructure
- **Existence checks** with application-specific exceptions
- **Repository exception handling** with appropriate logging
- **Domain exception propagation** for business rule violations
- **Critical vs. non-critical failure handling** (persist vs. notify)
- **Comprehensive logging** for observability

### Error Handling Anti-Patterns

**Anti-pattern 1: Catching everything**

```python
# DON'T DO THIS
def execute(self, member_id: str, class_id: str):
    try:
        # ... all the logic ...
    except Exception as e:
        logger.error(f"Booking failed: {e}")
        return None  # Swallows all errors
```

This hides business rule violations, infrastructure failures, and bugs indiscriminately.

**Anti-pattern 2: Converting domain exceptions to generic errors**

```python
# DON'T DO THIS
try:
    member.deduct_credit()
except InsufficientCreditsException:
    raise ValueError("Booking failed")  # Lost the business meaning
```

The interface layer can't distinguish "insufficient credits" from "invalid input" from "member not found."

**Anti-pattern 3: Not distinguishing critical from non-critical failures**

```python
# DON'T DO THIS
try:
    self.booking_repository.save(booking)
    self.notification_service.send_email(member.email)
except Exception as e:
    raise  # Treats email failure the same as database failure
```

If email fails, the booking should still succeed. This treats all failures equally.

**Pattern: Proper exception handling**

```python
# DO THIS
# Let domain exceptions propagate
try:
    member.deduct_credit()
except InsufficientCreditsException:
    logger.info(f"Credit check failed for member {member_id}")
    raise  # Preserve the domain exception

# Handle infrastructure critically
try:
    self.booking_repository.save(booking)
except RepositoryException as e:
    logger.critical(f"Failed to save booking: {e}")
    raise ApplicationException("System error")

# Handle non-critical gracefully
try:
    self.notification_service.send_email(member.email)
except NotificationException as e:
    logger.warning(f"Notification failed: {e}")
    # Don't raise - booking succeeded
```

Different exceptions, different handling, appropriate to each concern.

## The Problem We Haven't Solved

Look at this line from our use cases:

```python
member = self.member_repository.get_by_id(member_id)
```

What is `member_repository`? Right now, it's a concrete object—probably `PostgresMemberRepository` or `SqliteMemberRepository`. Our use case depends on infrastructure.

Look at the constructor:

```python
def __init__(self, member_repository, class_repository, 
             booking_repository, notification_service):
    self.member_repository = member_repository
    self.class_repository = class_repository
    self.booking_repository = booking_repository
    self.notification_service = notification_service
```

The application layer depends on infrastructure. This violates the dependency rule from Chapter 3 and the Dependency Inversion Principle from Chapter 2. The dependency points the wrong way.

To test `BookClassUseCase`, you need a real database. Or elaborate mocks that break when the real implementation changes.

Remember Dependency Inversion? High-level modules (application) shouldn't depend on low-level modules (infrastructure). Both should depend on abstractions.

We need abstractions. That's where ports come in.

## When You Don't Need Use Cases

Use cases add structure. They centralize orchestration. They create clear entry points. But they also add files, abstraction, and overhead. Before you extract every workflow into a use case, ask: do you need them?

**You don't need explicit use cases if:**

- Your application has only one or two operations (e.g., a simple webhook handler)
- The operations are trivial (basic CRUD with no orchestration)
- You have no code duplication between entry points
- There's only one way to trigger each operation (e.g., only a REST API, no admin panel or CLI)
- The workflow is a single domain method call with no coordination
- You're building a prototype and the workflows might change completely
- Your team is small and everyone understands the entire codebase

In these cases, **calling domain methods directly from your interface layer is fine:**

```python
# Simple enough to not need a use case
@app.route('/members', methods=['POST'])
def create_member():
    data = request.json
    member = Member(
        member_id=generate_id(),
        name=data['name'],
        email=EmailAddress(data['email']),
        membership_type=MembershipType.BASIC
    )
    member_repo.save(member)
    return jsonify({'id': member.id}), 201
```

No orchestration. No multiple steps. No duplication risk. A use case would just be a wrapper with no value.

**You DO need use cases when you see these signals:**

- The same workflow appears in multiple places (API, admin panel, CLI, background job)
- Operations require multiple steps that must happen together
- You need transaction-like behavior (all succeed or all fail)
- There's orchestration logic beyond a single domain method
- Testing requires understanding the entire interface layer
- Business workflows are hard to find in the codebase
- You're about to copy-paste orchestration code

These signals indicate that orchestration needs a home. Use cases provide it.

**Common mistake:** Creating a use case for every single database operation.

```python
# Don't do this - overkill
class GetMemberByIdUseCase:
    def execute(self, member_id: str) -> Member:
        return self.member_repository.get_by_id(member_id)
```

This is just a pass-through. It adds a file with no value. If you're only loading an object, call the repository directly. Use cases are for **workflows**, not simple queries.

**The right approach:** Start without use cases. Call domain and repository methods directly from your interface layer. When you notice duplication or complex orchestration, extract a use case. Let the need emerge from real pain, not from following a pattern blindly.

We created `BookClassUseCase` because the booking workflow was duplicated across API, admin panel, and waitlist processing. That duplication was the signal. If we only had one way to book classes, we might not need the use case yet.

Architecture responds to reality. Start simple. Extract when it hurts.

## Summary

The application layer orchestrates domain objects to fulfil use cases. It's where business workflows come to life.

Use cases are single actions that accomplish specific goals from a user's perspective. They coordinate domain logic without duplicating business rules. They define transaction boundaries. They represent what users want to accomplish.

We built three use cases: `BookClassUseCase` handles the core booking workflow. `CancelBookingUseCase` demonstrates business rule enforcement and refunds. `ProcessWaitlistUseCase` shows complex cross-aggregate coordination.

Use cases should orchestrate, not implement. Business logic stays in the domain. Infrastructure is abstracted behind interfaces. Each use case is an independent entry point—they don't call each other, they don't share state.

Common mistakes to avoid: putting business logic in use cases, having use cases call other use cases, and creating anemic use cases that just delegate to a single method.

But we exposed a critical problem: use cases need infrastructure. They need to load and save data. They need to send notifications. Right now, they depend on concrete implementations. This violates the dependency rule. We can't test use cases independently. We can't swap implementations without changing code.

The solution is ports—abstractions that define *what* the application needs without specifying *how* it's provided. Infrastructure will implement these abstractions, inverting the dependency so that high-level policy doesn't depend on low-level details.

The domain is pure. The application layer orchestrates. Now we need to connect them to the real world. Properly.

Next: ports.
