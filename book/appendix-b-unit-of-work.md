# Appendix B: Unit of Work Pattern

We've been handwaving something important throughout Chapters 6 and 7. Look at this use case again:

```python
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        member.deduct_credit()
        fitness_class.add_booking(member_id)
        booking = Booking.create(member_id, class_id)
        
        # Multiple saves - what if one fails?
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        return booking
```

Three separate `.save()` calls. What happens if the second one fails? The member already lost their credit. The booking never got created. We have inconsistent data—a member charged for a booking that doesn't exist.

This isn't theoretical. It happens. Database connections drop. Disk fills up. Constraint violations occur. When you're making multiple changes across different aggregates, you need them to succeed together or fail together. All or nothing.

That's what the Unit of Work pattern solves.

This appendix introduces the pattern—what it is, why it matters, how to implement it within clean architecture, and when you should (and shouldn't) use it.

## The Problem: No Transaction Boundaries

Let's be specific about what can go wrong. Here's a realistic scenario:

```python
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        # Business logic executes successfully
        member.deduct_credit()  # Member now has 9 credits instead of 10
        fitness_class.add_booking(member_id)  # Class booking list updated
        booking = Booking.create(member_id, class_id)
        
        # First save succeeds
        self.member_repository.save(member)  # ✓ Member saved with 9 credits
        
        # Second save fails - database connection lost
        self.class_repository.save(fitness_class)  # ✗ FAILS
        
        # Third save never runs
        self.booking_repository.save(booking)  # Never executed
        
        return booking
```

**What just happened:**

1. Member lost a credit (saved to database)
2. Class booking list not updated (failed to save)
3. No booking record exists (never attempted)
4. Member paid for a booking that doesn't exist
5. Class has capacity but member can't attend

This is a **consistency problem**. Our domain enforced all the rules correctly—the member had credits, the class had capacity, everything validated. But the persistence layer failed partway through, leaving us in an inconsistent state.

We need **atomicity**: all these changes happen together, or none of them happen.

You might think, "Just catch the exception and manually undo the member save." That's error-prone and doesn't scale:

```python
def execute(self, member_id: str, class_id: str):
    member = self.member_repository.get_by_id(member_id)
    # ... business logic ...
    
    try:
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
    except Exception:
        # How do we rollback member? We already saved it.
        # Load original? What if that fails?
        # Manual compensation gets messy fast.
        raise
```

Manual rollback is fragile. You need to track what succeeded, reverse each operation, handle failures in the rollback itself. This is complexity we shouldn't be managing in our use cases.

**We need a better abstraction.**

## What Is the Unit of Work Pattern?

The Unit of Work pattern maintains a list of objects affected by a business transaction and coordinates writing those changes to ensure atomicity.

From Martin Fowler's *Patterns of Enterprise Application Architecture*:

> "Maintains a list of objects affected by a business transaction and coordinates the writing out of changes and the resolution of concurrency problems."

Think of it as a transaction coordinator. Instead of calling `.save()` on multiple repositories, you:

1. Make changes to your domain objects (they're tracked automatically or manually)
2. Call `commit()` on the Unit of Work
3. All changes are persisted atomically, or none are

If anything fails, the entire transaction rolls back. No partial updates. No inconsistent state.

**Unit of Work vs. Repository:**

- **Repository**: Handles persistence for a single aggregate type (members, classes, bookings)
- **Unit of Work**: Coordinates persistence across multiple repositories within a transaction

Repositories manage individual aggregates. Unit of Work manages the transaction boundary.

## Where Unit of Work Fits in Clean Architecture

The Unit of Work pattern follows the same ports and adapters approach we used for repositories.

**Port (Application Layer):**
- Abstract interface defining the transaction boundary
- Exposes repository access
- Declares `commit()` and `rollback()` methods

**Adapter (Infrastructure Layer):**
- Concrete implementation managing database transactions
- Coordinates multiple repositories
- Handles connection management and cleanup

**Dependency Flow:**

```
Domain Layer
    ↑
Application Layer (Use Cases)
    ↑ depends on
UnitOfWork Port (Abstract Interface)
    ↑ implemented by
Infrastructure Layer (UnitOfWork Adapter)
    ↓ uses
Database / Persistence
```

Use cases depend on the `UnitOfWork` abstraction. Infrastructure provides the concrete implementation. This keeps our application layer independent of database specifics while giving us transaction guarantees.

## Defining the Unit of Work Port

Let's define the abstraction. The Unit of Work port needs to:

1. Provide access to repositories (so use cases can load and modify aggregates)
2. Commit all changes atomically
3. Rollback on failure
4. Support context manager protocol for automatic cleanup

Here's the interface:

```python
from abc import ABC, abstractmethod
from typing import Protocol

class UnitOfWork(ABC):
    """
    Coordinates persistence across multiple repositories within a transaction.
    
    Use as a context manager to ensure automatic commit/rollback:
    
        with unit_of_work:
            member = unit_of_work.members.get_by_id(member_id)
            member.deduct_credit()
            unit_of_work.commit()
    """
    
    # Repository access
    members: 'MemberRepository'
    fitness_classes: 'FitnessClassRepository'
    bookings: 'BookingRepository'
    waitlist: 'WaitlistRepository'
    
    @abstractmethod
    def commit(self) -> None:
        """
        Persist all changes made within this unit of work atomically.
        If any save fails, all changes are rolled back.
        """
        raise NotImplementedError
    
    @abstractmethod
    def rollback(self) -> None:
        """
        Discard all changes made within this unit of work.
        """
        raise NotImplementedError
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        # Don't suppress exceptions - let them propagate
        return False
```

**Key design decisions:**

1. **Repository access as properties**: Use cases access repositories through the UoW (`unit_of_work.members.get_by_id(...)`)
2. **Explicit commit**: Use cases must call `commit()` to persist changes
3. **Automatic rollback**: Context manager rolls back on exceptions
4. **Simple interface**: Just commit and rollback—everything else is in repositories

This interface works for both in-memory (testing) and database (production) implementations.

## Implementing the Unit of Work: In-Memory Adapter

Let's start with the simplest implementation—in-memory persistence for testing.

```python
from typing import Dict, Any

class InMemoryUnitOfWork(UnitOfWork):
    """
    In-memory Unit of Work for testing.
    
    Tracks changes and allows commit/rollback without a real database.
    Perfect for fast, isolated tests.
    """
    
    def __init__(self):
        # Each repository operates on shared in-memory storage
        self._member_data: Dict[str, Any] = {}
        self._class_data: Dict[str, Any] = {}
        self._booking_data: Dict[str, Any] = {}
        self._waitlist_data: Dict[str, Any] = {}
        
        # Create repositories that share the same data
        self.members = InMemoryMemberRepository(self._member_data)
        self.fitness_classes = InMemoryFitnessClassRepository(self._class_data)
        self.bookings = InMemoryBookingRepository(self._booking_data)
        self.waitlist = InMemoryWaitlistRepository(self._waitlist_data)
        
        # Snapshots for rollback
        self._snapshots: Dict[str, Dict[str, Any]] = {}
    
    def __enter__(self):
        # Take snapshot of current state for potential rollback
        self._snapshots = {
            'members': dict(self._member_data),
            'classes': dict(self._class_data),
            'bookings': dict(self._booking_data),
            'waitlist': dict(self._waitlist_data),
        }
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        return False
    
    def commit(self) -> None:
        """
        For in-memory, commit is a no-op since changes are already applied.
        We're just marking that this transaction completed successfully.
        """
        # Clear snapshots - we're committed now
        self._snapshots = {}
    
    def rollback(self) -> None:
        """
        Restore all data to the state it was in when the context manager started.
        """
        if self._snapshots:
            self._member_data.clear()
            self._member_data.update(self._snapshots['members'])
            
            self._class_data.clear()
            self._class_data.update(self._snapshots['classes'])
            
            self._booking_data.clear()
            self._booking_data.update(self._snapshots['bookings'])
            
            self._waitlist_data.clear()
            self._waitlist_data.update(self._snapshots['waitlist'])
```

**How it works:**

1. All repositories share the same in-memory dictionaries
2. On `__enter__`, we snapshot the current state
3. Use cases modify objects through repositories
4. On `commit()`, we accept the changes (no-op since already in memory)
5. On exception, `__exit__` calls `rollback()` which restores the snapshot

This gives us real transaction semantics in memory—fast, deterministic, perfect for tests.

## Implementing the Unit of Work: SQLite Adapter

Now the real implementation—managing database transactions.

```python
import sqlite3
from typing import Optional

class SqliteUnitOfWork(UnitOfWork):
    """
    SQLite-based Unit of Work managing database transactions.
    
    All repositories share the same database connection and transaction.
    Commit persists changes atomically; rollback discards them.
    """
    
    def __init__(self, connection_string: str = ':memory:'):
        self._connection_string = connection_string
        self._connection: Optional[sqlite3.Connection] = None
        
        # Repositories will be created when we enter the context
        self.members: Optional[SqliteMemberRepository] = None
        self.fitness_classes: Optional[SqliteFitnessClassRepository] = None
        self.bookings: Optional[SqliteBookingRepository] = None
        self.waitlist: Optional[SqliteWaitlistRepository] = None
    
    def __enter__(self):
        # Open connection and start transaction
        self._connection = sqlite3.connect(self._connection_string)
        # SQLite is in autocommit by default; we need to start a transaction
        self._connection.execute('BEGIN')
        
        # Create repositories that share this connection
        self.members = SqliteMemberRepository(self._connection)
        self.fitness_classes = SqliteFitnessClassRepository(self._connection)
        self.bookings = SqliteBookingRepository(self._connection)
        self.waitlist = SqliteWaitlistRepository(self._connection)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        
        # Always close the connection
        if self._connection:
            self._connection.close()
        
        return False
    
    def commit(self) -> None:
        """
        Commit the database transaction.
        All repository saves are persisted atomically.
        """
        if self._connection:
            self._connection.commit()
    
    def rollback(self) -> None:
        """
        Roll back the database transaction.
        All changes made through repositories are discarded.
        """
        if self._connection:
            self._connection.rollback()
```

**How it works:**

1. `__enter__`: Opens database connection, starts transaction, creates repositories
2. Repositories all share the same connection (same transaction)
3. When use cases call `repository.save()`, changes are written but not committed
4. `commit()`: Commits the database transaction (all changes persist)
5. `rollback()`: Rolls back the transaction (all changes discarded)
6. `__exit__`: Closes connection regardless of success/failure

The key insight: **repositories don't manage transactions**. They write to the connection, but the Unit of Work controls when those writes become permanent.

## Refactoring Use Cases with Unit of Work

Let's see the transformation. Here's our original use case:

**Before (Multiple Repository Dependencies):**

```python
class BookClassUseCase:
    def __init__(
        self,
        member_repository: MemberRepository,
        class_repository: FitnessClassRepository,
        booking_repository: BookingRepository,
        notification_service: NotificationService
    ):
        self.member_repository = member_repository
        self.class_repository = class_repository
        self.booking_repository = booking_repository
        self.notification_service = notification_service
    
    def execute(self, member_id: str, class_id: str) -> Booking:
        # Load aggregates
        member = self.member_repository.get_by_id(member_id)
        fitness_class = self.class_repository.get_by_id(class_id)
        
        # Execute domain logic
        member.deduct_credit()
        fitness_class.add_booking(member_id)
        booking = Booking.create(member_id, class_id)
        
        # Multiple saves - no transaction guarantee
        self.member_repository.save(member)
        self.class_repository.save(fitness_class)
        self.booking_repository.save(booking)
        
        # Side effect happens even if a save failed
        self.notification_service.send_confirmation(member, fitness_class)
        
        return booking
```

**Problems:**
- Three repository dependencies
- Three separate save calls
- No atomicity
- Notification sent even if persistence fails
- No clear transaction boundary

**After (Unit of Work):**

```python
class BookClassUseCase:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        notification_service: NotificationService
    ):
        self.uow = unit_of_work
        self.notification_service = notification_service
    
    def execute(self, member_id: str, class_id: str) -> Booking:
        with self.uow:
            # Load aggregates through UoW repositories
            member = self.uow.members.get_by_id(member_id)
            fitness_class = self.uow.fitness_classes.get_by_id(class_id)
            
            # Execute domain logic
            member.deduct_credit()
            fitness_class.add_booking(member_id)
            booking = Booking.create(member_id, class_id)
            
            # Save changes (still in transaction)
            self.uow.members.save(member)
            self.uow.fitness_classes.save(fitness_class)
            self.uow.bookings.save(booking)
            
            # Commit transaction - all changes persist atomically
            self.uow.commit()
        
        # Side effect ONLY after successful commit
        self.notification_service.send_confirmation(member, fitness_class)
        
        return booking
```

**Improvements:**

1. **Single dependency**: Just `UnitOfWork` instead of three repositories
2. **Clear transaction boundary**: Everything in the `with` block is one transaction
3. **Automatic rollback**: If any operation fails, changes are rolled back
4. **Safe side effects**: Notification sent only after successful commit
5. **Explicit commit**: Clear point where we say "make these changes permanent"

If `fitness_class.add_booking()` raises an exception (class full), the context manager automatically rolls back. The member doesn't lose a credit. Nothing is saved.

If the database fails during commit, the exception propagates, nothing persists, and our data stays consistent.

## Testing with Unit of Work

The Unit of Work makes testing cleaner. Instead of mocking three repositories, we provide one in-memory UoW.

**Test: Successful Booking**

```python
def test_book_class_deducts_credit_and_creates_booking():
    # Arrange
    uow = InMemoryUnitOfWork()
    notification_service = FakeNotificationService()
    use_case = BookClassUseCase(uow, notification_service)
    
    # Set up test data
    member = Member(id="M1", name="Alice", credits=10)
    fitness_class = FitnessClass(id="C1", name="Yoga", capacity=20)
    
    with uow:
        uow.members.save(member)
        uow.fitness_classes.save(fitness_class)
        uow.commit()
    
    # Act
    booking = use_case.execute(member_id="M1", class_id="C1")
    
    # Assert
    with uow:
        saved_member = uow.members.get_by_id("M1")
        saved_class = uow.fitness_classes.get_by_id("C1")
        saved_booking = uow.bookings.get_by_id(booking.id)
        
        assert saved_member.credits == 9  # Credit deducted
        assert "M1" in saved_class.bookings  # Member added to class
        assert saved_booking is not None  # Booking created
        assert notification_service.sent  # Notification sent
```

**Test: Rollback on Failure**

```python
def test_booking_full_class_rolls_back_credit_deduction():
    # Arrange
    uow = InMemoryUnitOfWork()
    notification_service = FakeNotificationService()
    use_case = BookClassUseCase(uow, notification_service)
    
    member = Member(id="M1", name="Alice", credits=10)
    fitness_class = FitnessClass(id="C1", name="Yoga", capacity=1)
    
    # Fill the class
    fitness_class.add_booking("OTHER_MEMBER")
    
    with uow:
        uow.members.save(member)
        uow.fitness_classes.save(fitness_class)
        uow.commit()
    
    # Act & Assert
    with pytest.raises(ClassFullException):
        use_case.execute(member_id="M1", class_id="C1")
    
    # Verify rollback happened
    with uow:
        saved_member = uow.members.get_by_id("M1")
        assert saved_member.credits == 10  # Credit NOT deducted
        assert not notification_service.sent  # No notification
```

**What we're testing:**

1. All changes commit together (member, class, booking all updated)
2. Failures roll back all changes (credit not deducted if class full)
3. Side effects only happen after successful commit

The Unit of Work gives us **testable transaction boundaries** without touching a real database.

## Testing Transaction Boundaries

Here's a more sophisticated test that verifies the actual transaction behavior:

```python
def test_commit_failure_rolls_back_all_changes():
    """
    Verify that if commit fails, all changes are rolled back.
    This tests the atomicity guarantee.
    """
    # Arrange
    class FailingUnitOfWork(InMemoryUnitOfWork):
        def commit(self):
            raise Exception("Database connection lost")
    
    uow = FailingUnitOfWork()
    use_case = BookClassUseCase(uow, FakeNotificationService())
    
    member = Member(id="M1", name="Alice", credits=10)
    fitness_class = FitnessClass(id="C1", name="Yoga", capacity=20)
    
    with uow:
        uow.members.save(member)
        uow.fitness_classes.save(fitness_class)
        uow.commit()
    
    # Act - commit will fail
    with pytest.raises(Exception, match="Database connection lost"):
        use_case.execute(member_id="M1", class_id="C1")
    
    # Assert - verify rollback
    with uow:
        saved_member = uow.members.get_by_id("M1")
        assert saved_member.credits == 10  # Unchanged
        
        # No booking should exist
        with pytest.raises(NotFoundException):
            uow.bookings.get_by_id("any_id")
```

This test proves the Unit of Work provides atomicity even when the commit operation itself fails.

## Optional: Automatic Change Tracking

So far, we've been explicitly calling `.save()` on repositories:

```python
with self.uow:
    member = self.uow.members.get_by_id(member_id)
    member.deduct_credit()
    self.uow.members.save(member)  # Explicit save
    self.uow.commit()
```

A more advanced pattern automatically tracks changes. When you load an object through a repository, the UoW remembers it. When you commit, it automatically saves all modified objects:

```python
with self.uow:
    member = self.uow.members.get_by_id(member_id)
    member.deduct_credit()
    # No explicit save needed!
    self.uow.commit()  # Automatically saves modified member
```

**How it works:**

The Unit of Work maintains an **identity map**—a registry of all objects loaded during the transaction. On commit, it compares current state to original state and saves what changed.

```python
class UnitOfWorkWithTracking(UnitOfWork):
    def __init__(self):
        self._identity_map: Dict[str, Any] = {}
        self._snapshots: Dict[str, Any] = {}
    
    def register(self, entity):
        """Called by repositories when objects are loaded."""
        self._identity_map[entity.id] = entity
        self._snapshots[entity.id] = copy.deepcopy(entity)
    
    def commit(self):
        for entity_id, entity in self._identity_map.items():
            original = self._snapshots[entity_id]
            if entity != original:  # Entity was modified
                self._save(entity)
        # Then commit transaction
```

**Trade-offs:**

**Benefits:**
- Cleaner use case code (no manual saves)
- Can't forget to save a modified object
- Automatic dirty checking

**Costs:**
- More complex implementation
- Identity map overhead (memory)
- Requires deep copying for snapshots
- Harder to debug (implicit behavior)
- Need equality comparison for all entities

**When to use automatic tracking:**
- Large teams where forgetting `.save()` is common
- Complex use cases modifying many aggregates
- ORM-like experience is desired

**When explicit saves are better:**
- Simple use cases (the extra code is fine)
- Small teams (code review catches missing saves)
- Prefer explicit over implicit
- Don't want deep copy overhead

Most applications should start with explicit saves. Add automatic tracking only if missing saves becomes a real problem.

## Integration with Domain Events

Domain events represent things that happened in your domain—"member booked class," "booking cancelled," "waitlist processed." Entities collect these events:

```python
class Member:
    def __init__(self, id: str, name: str, credits: int):
        self.id = id
        self.name = name
        self.credits = credits
        self._events: List[DomainEvent] = []
    
    def deduct_credit(self):
        if self.credits <= 0:
            raise InsufficientCreditsException()
        self.credits -= 1
        self._events.append(CreditDeductedEvent(self.id, self.credits))
```

The Unit of Work is the perfect place to dispatch these events—**after** the transaction commits successfully:

```python
class UnitOfWorkWithEvents(UnitOfWork):
    def __init__(self, event_dispatcher: EventDispatcher):
        # ... repository setup ...
        self._event_dispatcher = event_dispatcher
        self._collected_events: List[DomainEvent] = []
    
    def commit(self):
        # Collect events from all modified entities
        for entity in self._identity_map.values():
            if hasattr(entity, '_events'):
                self._collected_events.extend(entity._events)
                entity._events.clear()
        
        # Commit the transaction first
        self._connection.commit()
        
        # Only dispatch events AFTER successful commit
        for event in self._collected_events:
            self._event_dispatcher.dispatch(event)
        
        self._collected_events.clear()
```

**Why this ordering matters:**

If you dispatch events before committing, you might trigger side effects (sending emails, calling external APIs) for changes that never persist. If the commit fails, those emails were sent for bookings that don't exist.

Dispatching events after commit ensures **consistency**: external systems only learn about changes that actually happened.

**Example:**

```python
with uow:
    member = uow.members.get_by_id(member_id)
    member.deduct_credit()  # Raises CreditDeductedEvent
    uow.members.save(member)
    uow.commit()  # Commits transaction, THEN dispatches event

# Event handler runs after commit succeeds
def handle_credit_deducted(event: CreditDeductedEvent):
    analytics_service.track_credit_usage(event.member_id)
    # Analytics service only sees successful credit deductions
```

This pattern ensures your events represent reality, not attempted changes.

## When to Use Unit of Work

The Unit of Work pattern solves specific problems. Use it when:

**1. Multiple aggregates are modified in one use case**

If you're updating a member and creating a booking, you need both to succeed together:

```python
# Need UoW - two aggregates
with uow:
    member.deduct_credit()
    booking = Booking.create(member_id, class_id)
    uow.members.save(member)
    uow.bookings.save(booking)
    uow.commit()
```

**2. You need transaction guarantees**

Financial operations, inventory management, anything where partial updates are dangerous:

```python
# Payment processing - absolutely need atomicity
with uow:
    member.charge_card(amount)
    subscription.activate()
    invoice.mark_paid()
    uow.commit()
```

**3. Complex workflows with multiple steps**

Processing waitlists, batch operations, multi-step business processes:

```python
# Waitlist processing - many changes must succeed together
with uow:
    for waitlist_entry in waitlist:
        member = uow.members.get_by_id(waitlist_entry.member_id)
        fitness_class = uow.fitness_classes.get_by_id(waitlist_entry.class_id)
        if fitness_class.has_capacity():
            fitness_class.add_booking(member.id)
            waitlist_entry.mark_processed()
    uow.commit()
```

**4. Testing requires transaction boundaries**

When you need to test that changes commit together or rollback together:

```python
def test_all_changes_rollback_on_error():
    with uow:
        # Multiple changes
        uow.members.save(member)
        uow.classes.save(fitness_class)
        # Simulate failure
        raise Exception("Something failed")
    # Verify both changes were rolled back
```

## When NOT to Use Unit of Work

Don't use Unit of Work when:

**1. Simple CRUD with single aggregate**

If you're just saving one thing, a repository is enough:

```python
# Don't need UoW - just one aggregate
class UpdateMemberNameUseCase:
    def execute(self, member_id: str, new_name: str):
        member = self.member_repository.get_by_id(member_id)
        member.update_name(new_name)
        self.member_repository.save(member)
        # Repository can handle its own transaction
```

**2. Read-only operations**

Queries don't modify state. No transaction needed:

```python
# Don't need UoW - just reading
class GetMemberBookingsUseCase:
    def execute(self, member_id: str):
        return self.booking_repository.find_by_member(member_id)
```

**3. Framework already provides transaction management**

If you're using Django or SQLAlchemy and their transaction management works for you, don't build your own:

```python
# Django already has transaction.atomic()
from django.db import transaction

@transaction.atomic
def book_class(member_id, class_id):
    member = Member.objects.get(id=member_id)
    member.credits -= 1
    member.save()
    # Django handles the transaction
```

**4. Very simple applications**

If your entire application has five use cases and you're never going to scale, the overhead might not be worth it:

```python
# Solo project - maybe just use the database directly
def book_class(member_id, class_id):
    conn = sqlite3.connect('gym.db')
    conn.execute('BEGIN')
    try:
        conn.execute('UPDATE members SET credits = credits - 1 WHERE id = ?', [member_id])
        conn.execute('INSERT INTO bookings ...')
        conn.commit()
    except:
        conn.rollback()
        raise
```

**5. The added complexity doesn't solve a real problem**

If you've never had consistency issues with multiple saves, you might not need this pattern. Don't add abstraction "just in case."

The rule: **use the Unit of Work when the pain of not having it is greater than the cost of implementing it.**

## Framework-Provided Unit of Work

Many frameworks provide their own Unit of Work implementation. Understanding the pattern helps you use them effectively.

**SQLAlchemy Session:**

SQLAlchemy's `Session` is a Unit of Work:

```python
from sqlalchemy.orm import Session

with Session() as session:
    member = session.query(Member).get(member_id)
    member.credits -= 1
    booking = Booking(member_id=member_id, class_id=class_id)
    session.add(booking)
    session.commit()  # Atomic commit
```

The session tracks changes automatically, commits atomically, and rolls back on exceptions. It's exactly the pattern we've described.

**Django ORM:**

Django provides `transaction.atomic()`:

```python
from django.db import transaction

with transaction.atomic():
    member = Member.objects.get(id=member_id)
    member.credits -= 1
    member.save()
    Booking.objects.create(member_id=member_id, class_id=class_id)
    # Automatic commit; rollback on exception
```

Django's context manager handles transactions the same way our Unit of Work does.

**When to use framework UoW:**

- You're heavily invested in the framework
- The framework UoW meets your needs
- You want to leverage framework features (migrations, admin, etc.)

**When to build your own:**

- You want independence from the framework (clean architecture)
- You need custom transaction logic
- You're using multiple data stores the framework doesn't support
- You want explicit control over repository interfaces

There's no right answer. Framework UoW is pragmatic and works. Custom UoW gives you control and independence. Choose based on your constraints.

## Project Structure

Here's where Unit of Work files live in a clean architecture project:

```
application/
  ports/
    unit_of_work.py          # UnitOfWork ABC - the port
    member_repository.py     # Repository ports
    booking_repository.py
  use_cases/
    book_class.py            # Uses UnitOfWork port

domain/
  entities/
    member.py
    booking.py
  events/
    credit_deducted.py

infrastructure/
  persistence/
    in_memory_uow.py         # InMemoryUnitOfWork - adapter
    sqlite_uow.py            # SqliteUnitOfWork - adapter
    in_memory_repositories.py
    sqlite_repositories.py

tests/
  unit/
    test_book_class.py       # Uses InMemoryUnitOfWork
  integration/
    test_sqlite_uow.py       # Tests SqliteUnitOfWork
```

**Key points:**

1. **Port in application layer**: `UnitOfWork` ABC defines the contract
2. **Adapters in infrastructure**: Concrete implementations (in-memory, SQLite, PostgreSQL)
3. **Use cases depend on port**: Never import concrete UoW implementations
4. **Tests use in-memory**: Fast, isolated unit tests
5. **Integration tests use real DB**: Verify database behavior

This structure keeps dependencies pointing inward. Domain knows nothing about UoW. Application depends on UoW abstraction. Infrastructure provides concrete implementations.

## Summary

The Unit of Work pattern coordinates persistence across multiple repositories within a transaction boundary.

**It solves these problems:**

- Multiple repository saves with no atomicity
- Inconsistent state from partial failures
- Unclear transaction boundaries
- Difficult testing of transactional behavior

**It provides these benefits:**

- All changes commit together or roll back together
- Explicit transaction boundaries in use cases
- Automatic rollback on exceptions
- Side effects only after successful commit
- Cleaner testing with in-memory implementation

**Use it when:**

- Multiple aggregates modified in one use case
- Transaction guarantees are essential
- Complex workflows need coordination
- Testing transaction boundaries

**Don't use it when:**

- Single aggregate CRUD operations
- Read-only queries
- Framework UoW is sufficient
- Added complexity doesn't solve a real problem

The Unit of Work isn't always necessary. But when you need atomicity across multiple aggregates, it's the right tool. It brings transactional integrity to clean architecture without coupling your application layer to database specifics.

Now you know what it is, how it works, and when to use it. That's enough to decide whether your application needs it.
