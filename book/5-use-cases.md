# Chapter 5: Use Cases

We have a rich domain. `Member`, `FitnessClass`, and `Booking` entities enforce business rules. Value objects like `TimeSlot` and `EmailAddress` make invalid states impossible. The domain layer is solid.

But now we need to actually use it. The gym wants multiple ways to book classes:

**Web API:** Users book through a REST endpoint  
**Admin panel:** Staff books classes on behalf of members  
**Automated system:** Process waitlist when someone cancels  
**Bulk import:** Load bookings from a CSV file

Each of these needs the same workflow: verify the member exists, check they have credits, verify class capacity, deduct credit, add booking, save changes, send notification. But where does this orchestration live?

Right now, we're duplicating it everywhere:

```python
# In the REST API handler
@app.route('/bookings', methods=['POST'])
def book_class_api():
    data = request.json
    
    # Load domain objects
    member = member_repo.get_by_id(data['member_id'])
    fitness_class = class_repo.get_by_id(data['class_id'])
    
    # Orchestrate the workflow
    if not member or not fitness_class:
        return jsonify({'error': 'Not found'}), 404
    
    member.deduct_credit()
    fitness_class.add_booking(member.id)
    
    booking = Booking(generate_id(), member.id, fitness_class.id)
    
    member_repo.save(member)
    class_repo.save(fitness_class)
    booking_repo.save(booking)
    
    email_service.send_confirmation(member, fitness_class)
    
    return jsonify({'booking_id': booking.id}), 201


# In the admin panel
def admin_book_class(member_id, class_id):
    # Same workflow duplicated
    member = member_repo.get_by_id(member_id)
    fitness_class = class_repo.get_by_id(class_id)
    
    if not member or not fitness_class:
        raise ValueError("Not found")
    
    member.deduct_credit()
    fitness_class.add_booking(member.id)
    
    booking = Booking(generate_id(), member.id, fitness_class.id)
    
    member_repo.save(member)
    class_repo.save(fitness_class)
    booking_repo.save(booking)
    
    email_service.send_confirmation(member, fitness_class)
    
    return booking


# In the waitlist processor
def process_waitlist_entry(waitlist_entry):
    # Same workflow duplicated AGAIN
    member = member_repo.get_by_id(waitlist_entry.member_id)
    fitness_class = class_repo.get_by_id(waitlist_entry.class_id)
    
    # ... exact same logic repeated
```

This is a mess:

1. **Duplication everywhere:** The booking workflow is copied in three places
2. **No single source of truth:** Change the workflow? Update it in every location
3. **Inconsistent behavior:** Easy to forget a step in one place but not another
4. **Hard to test:** Have to test the workflow three times in three different contexts
5. **No clear entry points:** Where do you look to understand "how does booking work?"

We separated domain from infrastructure with layers. We enriched the domain with entities and value objects. But we haven't separated **orchestration** from **presentation**.

The workflow logic (load → validate → domain operations → save → notify) doesn't belong in API handlers or admin interfaces. Those are just different ways to trigger the same operation.

**The code is asking for use cases.**

A use case is a single place that defines one complete workflow. "Book a class." "Cancel a booking." "Process waitlist." Each use case orchestrates domain objects and infrastructure to accomplish a specific goal. Interface layers call use cases. They don't duplicate orchestration logic.

This chapter extracts those use cases from the scattered duplication and creates clear entry points to your application.

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
- **CRUD operations**: "Create a booking" is too generic—what are you actually trying to accomplish?
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
        
        # 2. Check if there's actually space
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
            return self.execute(class_id)  # Recursive call for next person
        
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
            return self.execute(class_id)  # Recursive call for next person
        
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

**Race conditions**: Between checking if the class has space and actually booking, another process might fill the spot. The use case handles this by catching `ClassFullException` and rolling back the credit deduction.

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
from domain.entities import WaitlistEntry  # Defined in Chapter 4b

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

## The Problem We Haven't Solved

Look back at all the use cases we've built. They work. They orchestrate domain logic cleanly. They handle errors. They coordinate multiple aggregates.

But there's a problem. A big one.

Look at this line:

```python
member = self.member_repository.get_by_id(member_id)
```

What is `member_repository`? Where does it come from? What does it do?

It loads a member from somewhere. Probably a database. Maybe a file. Maybe an external API. We don't know, and that's the point—the use case doesn't care *how* members are loaded. It just needs to load them.

But here's the issue: `member_repository` is infrastructure. It's a concrete implementation that talks to a database. And our use case depends on it.

Look at the constructor:

```python
def __init__(self, member_repository, class_repository, 
             booking_repository, notification_service):
    self.member_repository = member_repository
    self.class_repository = class_repository
    self.booking_repository = booking_repository
    self.notification_service = notification_service
```

We're passing in concrete objects. These objects know about databases. They know about SQL. They know about email APIs. And our application layer—which is supposed to be pure business orchestration—depends on them.

This violates the dependency rule. Remember from Chapter 3:

**Domain depends on nothing. Application depends on domain. Infrastructure depends on domain and application.**

But right now, our application layer depends on infrastructure. We've broken the rule.

Here's what that looks like in practice. Suppose you want to test `BookClassUseCase`. You write a test:

```python
def test_booking_class():
    # But what do we pass here?
    use_case = BookClassUseCase(
        member_repository=???,  # This needs a database connection
        class_repository=???,   # This too
        booking_repository=???, # And this
        notification_service=???  # And this needs email configuration
    )
    
    use_case.execute("M001", "C001")
```

To test the use case, you need a real database. You need a real email server. Or you need to create mocks. But the mocks need to match the exact interface of the real implementations. Any time the real implementation changes, your mocks break.

This is tight coupling. The application layer can't exist without infrastructure. You can't test it independently. You can't swap implementations without changing the use case code.

And there's a worse problem: the direction of dependency is wrong.

Infrastructure should depend on application, not the other way around. High-level policy (business orchestration) should not depend on low-level details (database access). But right now, it does.

We need a way for the application layer to express what it needs—"I need to load members"—without depending on how it's provided—"from a PostgreSQL database with this specific connection string."

We need abstractions. Interfaces. Contracts that define *what* the application needs, letting infrastructure provide *how* it's done.

We need ports.

## The "Uh Oh" Moment

You built a beautiful domain model. Rich objects. Clear boundaries. Business logic where it belongs.

You built clean use cases. They orchestrate without duplicating logic. They handle errors. They coordinate workflows.

But you can't ship this code.

Try it. Try to deploy `BookClassUseCase` to production. What database do you connect to? Where's the connection string? How do you configure the email service? What happens when you want to run tests—do you need a real database running?

You can't run any of it without infrastructure. And depending on infrastructure couples you to implementation details you wanted to avoid.

**This is the problem that breaks most architectural attempts.**

You follow the rules. You structure your code carefully. You separate concerns. And then you hit the wall: the use cases need to persist data. They need to send emails. They need to talk to the outside world.

Look at this constructor again:

```python
def __init__(self, member_repository, class_repository, 
             booking_repository, notification_service):
```

What types are these? Right now, they're concrete implementations. `PostgresMemberRepository`. `SMTPNotificationService`. Your application layer is hardcoded to specific infrastructure choices.

Want to switch databases? Change the use case.  
Want to test without a database? Change the use case.  
Want to run in a different environment? Change the use case.

This isn't loose coupling. This is tight coupling with extra steps.

You need infrastructure. But you don't want to depend on it.

This tension is the heart of hexagonal architecture, ports and adapters, dependency inversion—all those patterns exist to solve this one problem: how do you use infrastructure without depending on it?

The answer is simple in concept: depend on abstractions, not implementations.

But what does that actually mean? How do you define the abstractions? Where do they live? How do you wire everything together? And crucially: how do you do this without creating more complexity than you're solving?

That's what the next chapter is for.

We've built the domain. We've built the application layer. Now we need to connect them to the real world without breaking the dependency rule.

We need ports.

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
        membership_type=MembershipType('basic', 5, 10.0)
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
