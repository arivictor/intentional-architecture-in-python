# Appendix A: Aggregate Design & Boundary Decisions

Chapter 5 introduced aggregates as "clusters of entities and value objects treated as a single unit for data changes." We built a `Booking` aggregate, separated it from `Member` and `FitnessClass`, and established that aggregates reference each other by ID rather than holding direct object references.

But the hardest question was left unanswered: **how do you decide where to draw aggregate boundaries in the first place?**

This is the question that haunts every Domain-Driven Design implementation. Is `Booking` part of the `Member` aggregate or separate? Should `Waitlist` be part of `FitnessClass` or standalone? When do you split aggregates versus keeping them together? What even qualifies as a "consistency boundary"?

Get these decisions wrong and you face one of two problems:
- **Aggregates too large**: Loading massive object graphs for simple operations. Concurrent updates constantly conflict. Changes to one part require understanding the whole. Performance degrades as the aggregate grows.
- **Aggregates too small**: Business invariants span multiple aggregates, forcing you to enforce them in the application layer. Consistency becomes application responsibility instead of domain guarantee. Domain logic scatters.

This appendix teaches you how to make these decisions. We'll examine the gym booking system from Chapter 5 and walk through the actual thought process for drawing aggregate boundaries. We'll look at common mistakes, refactoring strategies, and decision frameworks.

By the end, you'll have a practical understanding of when to split aggregates, when to keep them together, and how to recognize when your boundaries are wrong.

## The Core Problem: What Makes an Aggregate?

Before we can draw boundaries, we need to understand what an aggregate actually is.

**An aggregate is a consistency boundary.** It's the scope within which business invariants must be maintained transactionally. Everything inside the aggregate must be consistent at the end of each transaction. Everything outside the aggregate can be eventually consistent.

This matters because transactions have costs:
- They lock resources
- They serialize operations
- They limit concurrency
- They increase coupling

The larger your aggregate, the more you lock, the less concurrent operations you can handle, and the tighter your coupling becomes.

But consistency also matters. Some business rules genuinely require multiple objects to change together atomically. Breaking these apart compromises correctness.

**The art of aggregate design is finding the smallest boundary that maintains necessary invariants.**

Let's see this with our gym booking system. Consider this business rule:

> "A fitness class cannot exceed its capacity."

Is this an invariant that requires an aggregate? Let's explore both options.

### Option 1: Large Aggregate — FitnessClass Contains Bookings

```python
class FitnessClass:
    def __init__(self, class_id: str, name: str, capacity: ClassCapacity, 
                 time_slot: TimeSlot):
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._time_slot = time_slot
        self._bookings: List[Booking] = []  # Bookings as children
    
    def add_booking(self, booking: Booking):
        if len(self._bookings) >= self._capacity.value:
            raise ClassFullException(f"Class {self._name} is at capacity")
        
        self._bookings.append(booking)
    
    def remove_booking(self, booking_id: str):
        self._bookings = [b for b in self._bookings if b.id != booking_id]
```

In this design, `FitnessClass` is the aggregate root. `Booking` objects are children contained within it. The capacity invariant is enforced directly: you cannot add a booking without loading the class and checking its count.

**Benefits:**
- Strong consistency guarantee: capacity can never be violated
- Atomic operations: adding a booking and incrementing count happen together
- Clear ownership: the class "owns" its bookings

**Costs:**
- Must load the entire class and all its bookings to cancel one booking
- Concurrent bookings serialize: only one person can book at a time
- Class entity grows unbounded as bookings accumulate
- Querying booking history for a member requires loading all classes they've attended

### Option 2: Separate Aggregates — Booking References FitnessClass

```python
class Booking:
    def __init__(self, booking_id: str, member_id: str, class_id: str):
        self._id = booking_id
        self._member_id = member_id  # Reference by ID
        self._class_id = class_id    # Reference by ID
        self._status = BookingStatus.CONFIRMED
        self._booked_at = datetime.now()


class FitnessClass:
    def __init__(self, class_id: str, name: str, capacity: ClassCapacity):
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._current_bookings = 0  # Denormalized count
    
    def can_accept_booking(self) -> bool:
        return self._current_bookings < self._capacity.value
    
    def increment_bookings(self):
        if self._current_bookings >= self._capacity.value:
            raise ClassFullException("Class is at capacity")
        self._current_bookings += 1
    
    def decrement_bookings(self):
        if self._current_bookings > 0:
            self._current_bookings -= 1
```

In this design, `Booking` and `FitnessClass` are separate aggregates. The capacity invariant is enforced through a denormalized count rather than by containing the full booking collection.

**Benefits:**
- Cancel a booking without loading the class
- Concurrent bookings possible (different aggregates can be modified in parallel)
- Query a member's booking history efficiently (just load their bookings)
- Each aggregate stays focused and bounded

**Costs:**
- Eventual consistency: the count might briefly be wrong during concurrent operations
- Application layer must coordinate: increment count when creating booking, decrement when cancelling
- Risk of inconsistency if coordination fails (booking exists but count wasn't updated)

**Which is correct?**

Neither is universally right. The answer depends on your specific constraints and requirements.

## Decision Framework: Questions to Ask

When facing an aggregate boundary decision, ask these questions in order:

### 1. What invariants must be protected?

Identify the business rules that must never be violated. Not "should be enforced" or "would be nice to maintain." Must. What happens if this rule is broken?

For our gym booking system:

**Must-never-violate invariants:**
- A class cannot exceed its capacity (safety issue, legal liability)
- A member cannot book two classes at the same time (physical impossibility)
- A member cannot book without sufficient credits (financial rule)

**Nice-to-enforce but not critical:**
- Waitlist entries should be in order of signup (user expectation, not business rule)
- Cancelled bookings should notify members (service quality, not correctness)

The must-never-violate invariants define your aggregate boundaries. Everything else can be eventually consistent.

### 2. What is the transactional scope?

What needs to happen atomically? What must be all-or-nothing?

For booking a class:
- Deduct member credit + create booking + increment class count = atomic
- If any step fails, all must roll back

This suggests that booking creation might need to coordinate across `Member`, `Booking`, and `FitnessClass`. But that doesn't mean they must be the same aggregate. It means the **application layer** needs to handle the transaction.

Aggregates define what must be consistent **within a single object graph**. Application-level transactions coordinate **across aggregates**.

### 3. What are the performance implications?

How often will this aggregate be accessed? How large will it grow? What operations need to be concurrent?

For `FitnessClass`:
- Classes are booked frequently (high concurrency)
- Popular classes might have 50+ bookings (large object graph)
- Most operations (view class, cancel booking) don't need the full booking list

If `FitnessClass` contained all bookings, we'd load and lock that entire collection for every booking operation. With 100 members trying to book simultaneously, 99 would wait.

This performance reality argues for smaller aggregates.

### 4. What are the consistency requirements?

Does this need immediate consistency or can it be eventual?

**Immediate consistency needed:**
- Capacity limits (can't overbook even briefly)

**Eventual consistency acceptable:**
- Booking confirmation emails (can be sent seconds later)
- Waitlist position updates (order matters, but not sub-second precision)
- Analytics about class popularity (can be stale)

Immediate consistency demands aggregates or domain services. Eventual consistency allows separate aggregates with application coordination.

### 5. What is the lifecycle and identity?

Do these objects have independent lifecycles? Can one exist without the other?

**Independent lifecycles suggest separate aggregates:**
- A `Booking` can exist after a `FitnessClass` is cancelled (historical record)
- A `Member` exists before and after specific bookings
- A `WaitlistEntry` might become irrelevant when the class is full

**Dependent lifecycles suggest same aggregate:**
- A `LineItem` only makes sense within an `Order`
- An `Address` might only exist as part of a `Customer`
- A `PaymentMethod` on file belongs to a `Member`

For our gym system, `Booking`, `Member`, and `FitnessClass` all have independent lifecycles. This is a strong signal they should be separate aggregates.

## Real Examples: Gym Booking System Decisions

Let's walk through the actual aggregate boundary decisions for the gym booking system, applying the framework above.

### Decision 1: Is Booking Part of Member or Separate?

**The question:** Should `Member` contain all its bookings as children, or should `Booking` be a separate aggregate?

**Invariants:**
- A member cannot book without credits ✓ (must enforce)
- A member's booking history must be accurate ✓ (important but can be eventually consistent)

**Transactional scope:**
- When booking, we need: check credits + deduct credit + create booking
- When cancelling, we need: refund credit + update booking status
- These operations span `Member` and `Booking`

**Performance:**
- Members might have dozens or hundreds of historical bookings
- Most member operations (check credits, update profile) don't need booking list
- Booking operations (cancel, mark attended) don't need full member object

**Consistency requirements:**
- Credit deduction must be atomic with booking creation (immediate)
- Booking list can be eventually consistent (query at read time)

**Lifecycle:**
- Bookings can exist after a member account is deactivated (historical record)
- Members exist long before their first booking
- They have independent identity and purpose

**Decision: Separate Aggregates**

`Member` and `Booking` should be separate aggregate roots. The credit-deduction invariant is enforced within the `Member` aggregate. The booking creation is handled by the `Booking` aggregate. The application layer coordinates between them using a transaction.

```python
# Application layer (use case)
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        with transaction():
            member = self.member_repo.get(member_id)
            fitness_class = self.class_repo.get(class_id)
            
            # Check invariants across aggregates
            if not member.has_credits():
                raise InsufficientCreditsException()
            
            if not fitness_class.can_accept_booking():
                raise ClassFullException()
            
            # Modify aggregates independently
            member.deduct_credit()
            booking = Booking.create(member.id, fitness_class.id)
            fitness_class.increment_bookings()
            
            # Persist changes
            self.member_repo.save(member)
            self.booking_repo.save(booking)
            self.class_repo.save(fitness_class)
```

This keeps each aggregate focused and small while maintaining correctness through application-layer coordination.

### Decision 2: Should Waitlist Be Part of FitnessClass or Standalone?

**The question:** When a class is full, members join a waitlist. Should `WaitlistEntry` be part of the `FitnessClass` aggregate or separate?

**Invariants:**
- Members should be added to waitlist in order (important for fairness)
- When a spot opens, the first waitlisted member should be offered it (business policy)

**Transactional scope:**
- Adding to waitlist: just create entry
- Offering spot: remove from waitlist + create booking
- These operations happen at different times

**Performance:**
- Waitlists might have 20-50 entries for popular classes
- Most class operations don't involve the waitlist
- Waitlist processing happens in batches, not real-time

**Consistency requirements:**
- Order must be consistent (but eventual consistency acceptable)
- Offering spots can happen seconds or minutes after space opens (not real-time)

**Lifecycle:**
- Waitlist entries expire or become irrelevant when the class occurs
- They might be removed manually by members
- They exist independently of whether the member ever gets in

**Decision: Separate Aggregate, Coordinated by Domain Service**

`WaitlistEntry` should be a separate entity, not contained in `FitnessClass`. The ordering and processing logic belongs to a domain service.

```python
class WaitlistEntry:
    def __init__(self, entry_id: str, member_id: str, class_id: str,
                 added_at: datetime):
        self._id = entry_id
        self._member_id = member_id
        self._class_id = class_id
        self._added_at = added_at


class WaitlistService:
    def add_to_waitlist(self, member_id: str, class_id: str):
        entry = WaitlistEntry(
            generate_id(),
            member_id,
            class_id,
            datetime.now()
        )
        self.waitlist_repo.save(entry)
    
    def get_next_in_line(self, class_id: str) -> Optional[WaitlistEntry]:
        entries = self.waitlist_repo.find_by_class(class_id)
        return min(entries, key=lambda e: e.added_at) if entries else None
    
    def offer_spot(self, class_id: str):
        next_entry = self.get_next_in_line(class_id)
        if next_entry:
            # Application layer would create booking and remove entry
            return next_entry
        return None
```

This keeps `FitnessClass` focused on capacity and scheduling while allowing waitlist operations to happen independently.

### Decision 3: Booking Cancellation — Who Enforces the 2-Hour Rule?

**The question:** The rule "cannot cancel within 2 hours of class start" involves both `Booking` and `FitnessClass`. Where does it belong?

**Invariants:**
- The cancellation window must be enforced (business policy)
- Booking status must transition correctly (CONFIRMED → CANCELLED)

**Transactional scope:**
- Check class start time + check current time + update booking status = atomic
- But class start time rarely changes after scheduling

**Knowledge:**
- The booking knows when it was made and its status
- The class knows when it starts
- The rule involves both pieces of information

**Decision: Booking Aggregate with Class Start Time Passed In**

The `Booking` aggregate enforces the rule, but requires the class start time to be passed in. This keeps the booking in control of its own lifecycle while respecting information from other aggregates.

```python
class Booking:
    def is_cancellable(self, class_start_time: datetime) -> bool:
        if self._status != BookingStatus.CONFIRMED:
            return False
        
        time_until_class = class_start_time - datetime.now()
        return time_until_class > timedelta(hours=2)
    
    def cancel(self, class_start_time: datetime):
        if not self.is_cancellable(class_start_time):
            raise BookingNotCancellableException(
                "Cannot cancel less than 2 hours before class"
            )
        
        self._status = BookingStatus.CANCELLED
        self._cancelled_at = datetime.now()
```

The application layer loads both aggregates and coordinates:

```python
class CancelBookingUseCase:
    def execute(self, booking_id: str):
        booking = self.booking_repo.get(booking_id)
        fitness_class = self.class_repo.get(booking.class_id)
        
        # Pass information from one aggregate to another
        booking.cancel(fitness_class.start_time)
        
        # Coordinate the refund
        member = self.member_repo.get(booking.member_id)
        member.add_credits(1)
        fitness_class.decrement_bookings()
        
        self.booking_repo.save(booking)
        self.member_repo.save(member)
        self.class_repo.save(fitness_class)
```

This design keeps each aggregate small and focused while maintaining the business rule through coordination.

## Common Mistakes and How to Fix Them

### Mistake 1: Aggregates Too Large (God Aggregates)

**Symptom:** Loading one object requires loading dozens of related objects. Every operation locks large portions of data. Concurrent operations constantly conflict.

**Example:**

```python
class Member:
    def __init__(self, member_id: str, name: str):
        self._id = member_id
        self._name = name
        self._bookings: List[Booking] = []  # All bookings
        self._payments: List[Payment] = []  # All payments
        self._preferences: MemberPreferences = None
        self._emergency_contacts: List[EmergencyContact] = []
        self._attendance_history: List[AttendanceRecord] = []
        # ... and so on
```

Loading a member to check their credits now loads hundreds of historical bookings, payments, and records. Updating preferences locks the entire member aggregate, blocking concurrent booking operations.

**How to fix:**

Identify subsets that have independent lifecycles or don't need immediate consistency. Extract them into separate aggregates.

```python
class Member:
    def __init__(self, member_id: str, name: str):
        self._id = member_id
        self._name = name
        self._credits = 0
        self._membership_type = None
        # Only essential member identity and state


# Separate aggregates
class Booking:
    def __init__(self, booking_id: str, member_id: str, class_id: str):
        # References member by ID, not contained


class MemberPreferences:
    def __init__(self, member_id: str):
        # Separate aggregate for preferences


class Payment:
    def __init__(self, payment_id: str, member_id: str):
        # Financial records separate from member identity
```

**Refactoring strategy:**
1. Identify the core "must-be-consistent" state (identity, credits, active status)
2. Move historical records to separate aggregates (bookings, payments)
3. Move infrequently-accessed data to separate aggregates (preferences, emergency contacts)
4. Use queries to reconstruct full views when needed

### Mistake 2: Aggregates Too Small (Distributed Invariants)

**Symptom:** Business rules that span multiple aggregates. Application layer full of complex coordination logic. Risk of inconsistency if coordination fails.

**Example:**

```python
# Every field is its own aggregate
class MemberId:
    def __init__(self, value: str):
        self._value = value


class MemberName:
    def __init__(self, member_id: str, value: str):
        self._member_id = member_id
        self._value = value


class MemberCredits:
    def __init__(self, member_id: str, amount: int):
        self._member_id = member_id
        self._amount = amount
```

Now simple operations require coordinating across multiple aggregates:

```python
# Just to deduct a credit!
def deduct_credit(member_id: str):
    credits = credit_repo.get(member_id)
    if credits.amount <= 0:
        raise InsufficientCreditsException()
    
    credits.amount -= 1
    credit_repo.save(credits)
    
    # But what if this fails? Credits deducted but booking not created
    # Invariant is split across aggregates
```

**How to fix:**

Identify invariants that must be enforced atomically. Combine those pieces into a single aggregate.

```python
class Member:
    def __init__(self, member_id: str, name: str, credits: int):
        self._id = member_id
        self._name = name
        self._credits = credits
    
    def deduct_credit(self):
        if self._credits <= 0:
            raise InsufficientCreditsException()
        self._credits -= 1
        # Invariant enforced atomically within the aggregate
```

**Refactoring strategy:**
1. Identify invariants that must hold immediately (not eventually)
2. Group related data that changes together
3. Combine aggregates that are always loaded together
4. Keep the aggregate boundary at the smallest scope that maintains invariants

### Mistake 3: Aggregates Referencing by Object Instead of ID

**Symptom:** Loading one aggregate loads all related aggregates recursively. Object graphs grow unbounded. Serialization and persistence become complex.

**Example:**

```python
class Booking:
    def __init__(self, member: Member, fitness_class: FitnessClass):
        self._member = member  # Direct object reference
        self._fitness_class = fitness_class  # Direct object reference
```

Loading a booking loads the full `Member` (with their history) and full `FitnessClass` (with all its bookings). If those bookings reference members, you've loaded half the database.

**How to fix:**

Reference other aggregates by ID only. Load them separately when needed.

```python
class Booking:
    def __init__(self, member_id: str, class_id: str):
        self._member_id = member_id  # Reference by ID
        self._class_id = class_id    # Reference by ID
    
    @property
    def member_id(self) -> str:
        return self._member_id


# Application layer loads separately when needed
booking = booking_repo.get(booking_id)
member = member_repo.get(booking.member_id)
fitness_class = class_repo.get(booking.class_id)
```

**Refactoring strategy:**
1. Replace direct object references with ID fields
2. Update methods to accept needed data as parameters
3. Make the application layer responsible for loading related aggregates
4. Use value objects to pass data between aggregates without coupling

### Mistake 4: Making Everything an Aggregate Root

**Symptom:** Every entity becomes an aggregate root, even simple child entities. No clear containment relationships. Application layer coordinates everything.

**Example:**

```python
# Address is its own aggregate, even though it only makes sense with Member
class Address:
    def __init__(self, address_id: str, street: str, city: str):
        self._id = address_id  # Unnecessary identity
        self._street = street
        self._city = city


# Application coordinates Member and Address
member = member_repo.get(member_id)
address = address_repo.get(member.address_id)
```

But address has no independent meaning. It only exists in the context of a member. It's not queried independently. It has no separate lifecycle.

**How to fix:**

Use value objects or contained entities for data that only makes sense within an aggregate.

```python
class Address:
    def __init__(self, street: str, city: str, zip_code: str):
        # No ID - it's a value object
        self._street = street
        self._city = city
        self._zip_code = zip_code
    
    def __eq__(self, other):
        return (isinstance(other, Address) and
                self._street == other._street and
                self._city == other._city)


class Member:
    def __init__(self, member_id: str, name: str, address: Address):
        self._id = member_id
        self._name = name
        self._address = address  # Contained as value object
```

**Refactoring strategy:**
1. Ask: "Does this have independent lifecycle and identity?"
2. If no → Make it a value object or contained entity
3. If yes → Make it a separate aggregate root
4. When in doubt, start contained and extract later if needed

## Refactoring Aggregate Boundaries

Aggregate boundaries are not set in stone. As you understand your domain better, or as requirements change, you'll need to adjust them.

### When to Refactor

**Signals that boundaries are wrong:**

1. **Performance problems**
   - Loading aggregates is slow
   - Operations block each other unnecessarily
   - Database queries load more data than needed

2. **Consistency problems**
   - Business rules are enforced in application layer
   - Race conditions in concurrent operations
   - Data becomes inconsistent during failures

3. **Complexity problems**
   - Application layer has complex coordination logic
   - Aggregates are difficult to understand
   - Changes ripple across multiple aggregates

4. **Testing problems**
   - Tests require elaborate setup
   - Mocking becomes excessive
   - Unit tests feel like integration tests

### Refactoring Strategy: Split Large Aggregates

**Starting point:** `FitnessClass` contains all bookings as children.

```python
class FitnessClass:
    def __init__(self):
        self._bookings: List[Booking] = []  # Large collection
    
    def add_booking(self, member_id: str):
        booking = Booking(generate_id(), member_id, self._id)
        self._bookings.append(booking)
```

**Step 1: Identify the invariant that needs protection**

The only real invariant is: "booking count cannot exceed capacity."

We don't actually need the full `Booking` objects to enforce this. We just need the count.

**Step 2: Extract the child aggregate**

Make `Booking` its own aggregate root with its own repository.

```python
class Booking:
    def __init__(self, booking_id: str, member_id: str, class_id: str):
        self._id = booking_id
        self._member_id = member_id
        self._class_id = class_id


class BookingRepository:
    def save(self, booking: Booking):
        # Persist independently
        pass
    
    def find_by_class(self, class_id: str) -> List[Booking]:
        # Query bookings for a class
        pass
```

**Step 3: Add denormalized data to maintain the invariant**

```python
class FitnessClass:
    def __init__(self):
        self._current_bookings = 0  # Just the count
    
    def can_accept_booking(self) -> bool:
        return self._current_bookings < self._capacity.value
    
    def increment_bookings(self):
        if not self.can_accept_booking():
            raise ClassFullException()
        self._current_bookings += 1
```

**Step 4: Update the application layer to coordinate**

```python
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        fitness_class = self.class_repo.get(class_id)
        
        if not fitness_class.can_accept_booking():
            raise ClassFullException()
        
        booking = Booking(generate_id(), member_id, class_id)
        fitness_class.increment_bookings()
        
        self.booking_repo.save(booking)
        self.class_repo.save(fitness_class)
```

**Step 5: Add eventual consistency reconciliation**

```python
class ReconcileBookingCounts:
    def execute(self):
        for fitness_class in self.class_repo.all():
            actual_count = self.booking_repo.count_by_class(fitness_class.id)
            
            if fitness_class.current_bookings != actual_count:
                fitness_class.set_booking_count(actual_count)
                self.class_repo.save(fitness_class)
```

This reconciliation can run periodically to catch any inconsistencies from failed transactions.

### Refactoring Strategy: Merge Small Aggregates

**Starting point:** Every piece of member data is its own aggregate.

```python
class Member:
    def __init__(self, member_id: str):
        self._id = member_id


class MemberProfile:
    def __init__(self, member_id: str, name: str):
        self._member_id = member_id
        self._name = name


class MemberCredits:
    def __init__(self, member_id: str):
        self._member_id = member_id
        self._credits = 0
```

**Step 1: Identify related invariants**

- Credits must be non-negative
- Name cannot be empty
- Email must be valid
- These all relate to member identity and state

**Step 2: Identify what changes together**

When booking a class:
- Credits decrease
- Booking is created

When renewing membership:
- Credits reset
- Membership type updates

Credits and membership are tightly coupled.

**Step 3: Merge into single aggregate**

```python
class Member:
    def __init__(self, member_id: str, name: str, email: EmailAddress,
                 membership_type: MembershipType):
        self._id = member_id
        self._name = name
        self._email = email
        self._membership_type = membership_type
        self._credits = membership_type.credits_per_month
    
    def deduct_credit(self):
        if self._credits <= 0:
            raise InsufficientCreditsException()
        self._credits -= 1
    
    def renew_membership(self):
        self._credits = self._membership_type.credits_per_month
```

Now related invariants are enforced atomically within a single aggregate.

**Step 4: Keep historical data separate**

```python
class Member:
    # Current state only
    pass


class BookingHistory:
    # Historical records remain separate
    def __init__(self, member_id: str):
        self._member_id = member_id
    
    def add_entry(self, booking: Booking):
        pass
```

This keeps the member aggregate focused on current state while allowing efficient queries of historical data.

## Practical Guidelines

After examining the theory, mistakes, and refactoring strategies, here are practical rules of thumb for aggregate design:

### Rule 1: Start Small, Extract When Needed

**Default:** Make entities their own aggregates until you have a clear reason to combine them.

**Combine when:**
- You always load them together
- They share invariants that must be enforced atomically
- Their lifecycles are truly dependent

**Keep separate when:**
- They can be queried independently
- They have different access patterns
- They change for different reasons

### Rule 2: One Aggregate Root, One Transaction

Each business operation should modify **at most one aggregate per transaction** when possible.

If you need to modify multiple aggregates atomically, that's a signal you might have the boundaries wrong. Consider:
- Are these really separate concepts, or is one contained in the other?
- Can the invariant be enforced with eventual consistency instead?
- Should there be a domain service coordinating this?

There are legitimate cases for multi-aggregate transactions (booking requires member + class + booking), but they should be the exception, not the rule.

### Rule 3: Reference by ID, Not by Object

Aggregates should reference other aggregates by ID only:

```python
# Good
class Booking:
    def __init__(self, member_id: str, class_id: str):
        self._member_id = member_id
        self._class_id = class_id

# Bad
class Booking:
    def __init__(self, member: Member, fitness_class: FitnessClass):
        self._member = member
        self._fitness_class = fitness_class
```

This keeps aggregates independent and prevents loading entire object graphs.

### Rule 4: Protect Invariants at the Aggregate Root

All modifications to anything inside the aggregate should go through the root:

```python
# Good
class FitnessClass:
    def add_booking(self, member_id: str):
        if self.is_full():
            raise ClassFullException()
        self._bookings.append(member_id)

# Bad - direct access bypasses invariants
fitness_class._bookings.append(member_id)  # No capacity check!
```

Make internal collections private and provide methods for safe modification.

### Rule 5: Keep Aggregates Focused

An aggregate should represent a single concept with a clear boundary:

- `Member` → Member identity and account state
- `Booking` → A booking transaction
- `FitnessClass` → A scheduled class with capacity

Not:
- `MemberWithAllTheirBookingsAndPaymentsAndPreferences` → Too broad

If your aggregate name is a compound or needs "and," it's probably too large.

### Rule 6: Use Domain Events for Cross-Aggregate Communication

When one aggregate needs to react to changes in another, use domain events instead of direct references:

```python
class Booking:
    def cancel(self, class_start_time: datetime):
        self._status = BookingStatus.CANCELLED
        self._events.append(BookingCancelledEvent(
            booking_id=self._id,
            member_id=self._member_id,
            class_id=self._class_id
        ))

# Application layer handles the event
class BookingCancelledHandler:
    def handle(self, event: BookingCancelledEvent):
        member = self.member_repo.get(event.member_id)
        member.add_credits(1)
        
        fitness_class = self.class_repo.get(event.class_id)
        fitness_class.decrement_bookings()
```

This keeps aggregates decoupled while maintaining coordination.

### Rule 7: Eventual Consistency Is Often Good Enough

Not every business rule needs immediate, transactional consistency. Ask:

- What's the real-world consequence of brief inconsistency?
- How often will this actually happen?
- Can we detect and fix inconsistencies after the fact?

For many rules, eventual consistency (with reconciliation) is simpler and more scalable than complex aggregate boundaries.

## Summary

Aggregate boundary decisions are the hardest part of domain modeling. Too large and you sacrifice performance and concurrency. Too small and you lose consistency guarantees.

**The key questions:**
1. What invariants must be protected immediately?
2. What needs to happen atomically?
3. What are the performance implications?
4. What can be eventually consistent?
5. What are the lifecycle and identity relationships?

**For the gym booking system:**
- `Member`, `Booking`, and `FitnessClass` are separate aggregates (independent lifecycles, different access patterns)
- `Booking` enforces its own cancellation rules but needs class start time passed in
- `WaitlistEntry` is separate from `FitnessClass` (processed independently)
- The application layer coordinates across aggregates using transactions

**Common mistakes:**
- Aggregates too large (loading unnecessary data, blocking concurrency)
- Aggregates too small (invariants in application layer, consistency risks)
- Referencing by object instead of ID (loading object graphs)
- Making everything an aggregate root (no clear containment)

**Refactoring strategies:**
- Split large aggregates by extracting historical data and using denormalized counts
- Merge small aggregates when invariants span them
- Use eventual consistency with reconciliation
- Let domain events handle cross-aggregate reactions

**Practical guidelines:**
- Start small, extract when needed
- One aggregate per transaction when possible
- Reference by ID, not by object
- Protect invariants at the root
- Keep aggregates focused on single concepts
- Use domain events for cross-aggregate communication
- Eventual consistency is often sufficient

Aggregate design is learned through practice. Make decisions deliberately, observe the consequences, and refactor when you feel the pain. The boundaries that work emerge from understanding your specific domain, requirements, and constraints—not from following rigid rules.

Your domain will teach you where the boundaries belong. Listen to it.
