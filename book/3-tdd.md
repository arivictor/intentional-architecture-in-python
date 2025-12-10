# Chapter 3: Test-Driven Development

The SOLID principles from Chapter 2 gave you tools to write flexible code. But they don't tell you when to apply them. They don't guide the design process itself. They're reactive—you use them when code starts to hurt.

Test-Driven Development (TDD) is proactive. It shapes your design from the first line of code.

TDD isn't just about testing. It's a design discipline. When you write tests first, you're forced to think about how your code will be used before you write it. You define the interface before the implementation. You discover design problems early, when they're cheap to fix.

This chapter introduces TDD as the foundation for everything that follows. The layers, the domain modeling, the ports and adapters, all of these patterns emerge more naturally when you start with tests.

## Why TDD Before Architecture?

Architecture is about managing change. TDD is about enabling change.

When you write tests first, you build a safety net. Every test is a specification. Every test is documentation. Every test is executable proof that your code works as intended. This safety net lets you refactor confidently. You can change implementation details knowing that if you break something, the tests will tell you.

Without tests, refactoring is terrifying. You make a change, deploy it, and hope nothing breaks. With tests, refactoring is mechanical. You make a change, run the tests, and know immediately if you broke something.

This is why TDD comes before architectural patterns. The patterns we'll learn in later chapters—layers, domain models, ports and adapters—all require refactoring to implement. You can't refactor safely without tests. You can't implement good architecture without the ability to refactor.

TDD enables architecture.

## The Red-Green-Refactor Cycle

TDD follows a simple rhythm: Red, Green, Refactor.

**Red:** Write a failing test. The test describes what you want the code to do. It fails because the code doesn't exist yet.

**Green:** Write the simplest code that makes the test pass. Don't worry about elegance or architecture. Just make it work.

**Refactor:** Improve the code while keeping the tests green. Remove duplication. Apply SOLID principles. Introduce patterns as needed.

Then repeat. Each cycle is small, a few minutes at most. Each cycle adds a new behavior or improves the design. Over time, a well-tested, well-designed system emerges.

Let's see this in practice with our gym booking system.

## From User Stories to Tests

Before we dive into code, let's address a critical question: **How do you know what tests to write?**

Many developers struggle with TDD because they don't know where to start. They understand Red-Green-Refactor, but they don't understand how to break down a feature into testable scenarios.

Here's the process:

### Step 1: Start with the User Story or Business Rule

Every feature comes from somewhere: a user story, a business requirement, a bug report. For example:

> "As a gym member, I want to book fitness classes so that I can attend sessions."

This is too vague to test directly. We need to break it down.

### Step 2: Identify the Scenarios

Ask: "What are the different paths through this feature?"

For booking a class:
- **Happy path:** Member with credits books a class with available space → Success
- **No credits:** Member with zero credits tries to book → Error
- **Class full:** Member tries to book a full class → Error
- **Already booked:** Member tries to book the same class twice → Error

Each scenario represents a different behavior, and each behavior needs a test.

### Step 3: Pick the Simplest Scenario

Don't try to build everything at once. Pick the scenario that delivers the most value with the least complexity. Usually that's the happy path.

For our booking feature, we start with: "Member with credits books a class with available space."

### Step 4: Write a Test That Describes the Behavior

The test should read like a specification:

```python
def test_member_books_class_successfully():
    # Given: A member with credits and a class with space
    member = Member(credits=10)
    fitness_class = FitnessClass(capacity=20)
    
    # When: The member books the class
    booking = book_class(member, fitness_class)
    
    # Then: The booking is confirmed and credits are deducted
    assert booking.status == "confirmed"
    assert member.credits == 9
```

Notice the structure: **Given-When-Then**. This makes tests readable and forces you to think through the scenario.

### Step 5: Let the Test Drive the Design

When you write the test first, you're forced to answer design questions:
- What parameters does `book_class()` need?
- What does it return?
- How does `Member` track credits?
- How does `FitnessClass` track capacity?

These aren't implementation details—they're interface decisions. And TDD forces you to make them consciously, from the perspective of the code's user.

### Step 6: Repeat for Each Scenario

Once the happy path works, add tests for edge cases and error conditions. Each test adds a new behavior. Each behavior is verified independently.

**This is how TDD shapes architecture:** You start with user value (the story), break it into behaviors (scenarios), specify each behavior (tests), and let the implementation emerge from those specifications.

Let's see this process in action.

## Starting Simple: Our First Feature

We'll build the simplest possible feature: creating a member.

From a user's perspective: "I want to register a new gym member with a name and email address."

We start with a test. Not with the implementation. The test describes what we want.

**Note:** Python's built-in `unittest` module provides everything we need for testing. We'll use it throughout this book.

```python
# tests/test_member.py
def test_create_member():
    member = Member(
        member_id="M001",
        name="Alice Johnson",
        email="alice@example.com"
    )
    
    assert member.id == "M001"
    assert member.name == "Alice Johnson"
    assert member.email == "alice@example.com"
```

Run the test. It fails. `NameError: name 'Member' is not defined`. **Red.**

Now write the simplest code that makes it pass:

```python
# domain/member.py
class Member:
    def __init__(self, member_id: str, name: str, email: str):
        self.id = member_id
        self.name = name
        self.email = email
```

Run the test. It passes. **Green.**

Look at the code. Is there duplication? Can it be improved? Not yet. It's simple enough. We're done with this cycle.

**This is the TDD rhythm.** Test first. Make it pass. Clean it up. Move on.

## Adding Business Rules

Now we want validation. Email addresses must be valid. Names can't be empty.

Start with a test:

```python
def test_member_requires_valid_email():
    try:
        Member(
            member_id="M001",
            name="Alice Johnson",
            email="not-an-email"
        )
        assert False, "Expected ValueError to be raised"
    except ValueError as e:
        assert "Invalid email" in str(e)

def test_member_requires_non_empty_name():
    try:
        Member(
            member_id="M001",
            name="",
            email="alice@example.com"
        )
        assert False, "Expected ValueError to be raised"
    except ValueError as e:
        assert "Name cannot be empty" in str(e)
```

Run the tests. They fail. **Red.**

Make them pass:

```python
import re

class Member:
    def __init__(self, member_id: str, name: str, email: str):
        if not name:
            raise ValueError("Name cannot be empty")
        
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email")
        
        self.id = member_id
        self.name = name
        self.email = email
```

Run the tests. They pass. **Green.**

Refactor? The email validation is a business rule. It might be used elsewhere. Let's extract it:

```python
# domain/value_objects.py
import re

class EmailAddress:
    def __init__(self, email: str):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError("Invalid email")
        self._email = email
    
    def __str__(self):
        return self._email

# domain/member.py
class Member:
    def __init__(self, member_id: str, name: str, email: str):
        if not name:
            raise ValueError("Name cannot be empty")
        
        self.id = member_id
        self.name = name
        self.email = EmailAddress(email)
```

Run the tests. Still green. But now we have a value object that enforces email validity everywhere. This is refactoring guided by tests.

**Note:** This `EmailAddress` is a simple value object. Chapter 5 expands on value objects as a domain modeling pattern, showing how they make invalid states impossible and encapsulate business rules. For now, focus on how TDD's refactor step naturally leads to better abstractions.

## Building a Complete Feature: Booking a Class

Let's build something more complex: booking a member into a fitness class.

**Business rules:**
- The class must have available capacity
- The member must have sufficient credits
- A booking creates a record

Before we write the test, let's think through what we're building. This habit—analyzing before coding—is what separates TDD from "test-after development."

### What Does This Feature Actually Need to Do?

Looking at our business rules, we can identify the core scenario:
- **Happy path:** A member with credits books a class that has space

We also see implied failure scenarios:
- **No credits:** Member tries to book but has no credits left
- **Class full:** Member tries to book but the class is at capacity

Each scenario needs a test. But let's start with the happy path—the simplest case that delivers value.

### What Objects Do We Need?

From the business rules, three concepts emerge:
- **Member** - needs to track credits
- **FitnessClass** - needs to track capacity and current bookings
- **Booking** - a record that links member to class

### What Behavior Goes Where?

This is the key question TDD forces you to answer early:
- Should `book_class()` check credits, or should `Member`?
- Should `book_class()` check capacity, or should `FitnessClass`?

We'll discover the answer by writing the test and seeing what interface makes sense.

Start with the test:

```python
def test_book_class_success():
    member = Member(
        member_id="M001",
        name="Alice",
        email="alice@example.com",
        credits=10
    )
    
    fitness_class = FitnessClass(
        class_id="C001",
        name="Yoga Flow",
        capacity=20
    )
    
    booking = book_class(member, fitness_class)
    
    assert booking.member_id == "M001"
    assert booking.class_id == "C001"
    assert booking.status == "confirmed"
    assert member.credits == 9
    assert fitness_class.current_bookings == 1
```

**Red.** The function doesn't exist.

Make it pass:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Booking:
    booking_id: str
    member_id: str
    class_id: str
    status: str
    booked_at: datetime

def book_class(member: Member, fitness_class: FitnessClass) -> Booking:
    if member.credits <= 0:
        raise ValueError("Insufficient credits")
    
    if fitness_class.is_full():
        raise ValueError("Class is full")
    
    member.credits -= 1
    fitness_class.current_bookings += 1
    
    return Booking(
        booking_id=generate_booking_id(),
        member_id=member.id,
        class_id=fitness_class.id,
        status="confirmed",
        booked_at=datetime.now()
    )
```

**Green.** Tests pass.

But wait. This function directly modifies `member.credits` and `fitness_class.current_bookings`. That's fragile. What if we need to enforce rules about credit deduction? What if class capacity logic gets more complex?

Refactor:

```python
class Member:
    def __init__(self, member_id: str, name: str, email: str, credits: int):
        if not name:
            raise ValueError("Name cannot be empty")
        
        self.id = member_id
        self.name = name
        self.email = EmailAddress(email)
        self._credits = credits
    
    def deduct_credit(self):
        if self._credits <= 0:
            raise ValueError("Insufficient credits")
        self._credits -= 1
    
    @property
    def credits(self):
        return self._credits


class FitnessClass:
    def __init__(self, class_id: str, name: str, capacity: int):
        self.id = class_id
        self.name = name
        self._capacity = capacity
        self._bookings = []
    
    def add_booking(self, member_id: str):
        if self.is_full():
            raise ValueError("Class is full")
        self._bookings.append(member_id)
    
    def is_full(self) -> bool:
        return len(self._bookings) >= self._capacity
    
    @property
    def current_bookings(self):
        return len(self._bookings)


def book_class(member: Member, fitness_class: FitnessClass) -> Booking:
    member.deduct_credit()
    fitness_class.add_booking(member.id)
    
    return Booking(
        booking_id=generate_booking_id(),
        member_id=member.id,
        class_id=fitness_class.id,
        status="confirmed",
        booked_at=datetime.now()
    )
```

**Evolution Note:** We've changed `self.credits` to `self._credits` with a property. This encapsulation lets us add logic (like expiry checks) in Chapter 5 without changing the interface. Tests still pass because the public API (`member.credits`) remains the same.

Run the tests. Still green. But now the business rules live in the domain objects. `Member` enforces credit rules. `FitnessClass` enforces capacity rules. The booking function just orchestrates.

**What just happened?** We answered the question "what behavior goes where?" through TDD:
- First attempt: `book_class()` directly manipulated credits and bookings (worked, but fragile)
- Refactored: Domain objects (`Member`, `FitnessClass`) enforce their own rules
- Result: Better design emerged from the refactor step

This is TDD driving design. The tests forced us to think about the interface. The refactoring step let us improve the structure. The safety net let us move code around confidently.

**Notice the pattern:**
1. Business rule → Test scenario → Required objects and behavior
2. Write test → Discover what interface you need
3. Make it pass → Prove the behavior works
4. Refactor → Move logic where it belongs

This pattern repeats throughout the book. In Chapter 5, we'll see how these domain objects become entities and value objects. In Chapter 6, we'll see how `book_class()` becomes a use case. But it all starts here, with tests driving the design.

## Test-Driven Design Decisions

TDD influences design in specific, observable ways.

### Testable Code Is Decoupled Code

When you write tests first, you naturally create boundaries. A function that does one thing is easier to test than a function that does ten things. A class with clear dependencies is easier to test than a class with hidden global state.

If a test is hard to write, it's usually because the code is too coupled. The test is telling you something.

```python
# Hard to test - coupled to infrastructure
def book_class(member_id: str, class_id: str):
    conn = sqlite3.connect('gym.db')
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM members WHERE id = ?", (member_id,))
    credits = cursor.fetchone()[0]
    
    if credits <= 0:
        raise ValueError("Insufficient credits")
    
    cursor.execute("UPDATE members SET credits = credits - 1 WHERE id = ?", (member_id,))
    conn.commit()
    # More database code...
```

To test this, you need a real database. Every test requires setup and teardown. Changes to the database schema break tests. The test is screaming: "This function does too much!"

TDD pushes you toward this:

```python
# Easy to test - dependencies injected
def book_class(member: Member, fitness_class: FitnessClass) -> Booking:
    member.deduct_credit()
    fitness_class.add_booking(member.id)
    return Booking(...)
```

No database. No infrastructure. Just domain objects interacting. The test is simple because the design is simple.

### Tests Define Contracts

When you write a test first, you're defining a contract. "This function, given these inputs, produces this output." That contract becomes documentation. It becomes a specification. It becomes proof that the code works.

```python
def test_cancellation_refunds_credit():
    """When a booking is cancelled, the member gets their credit back."""
    member = Member("M001", "Alice", "alice@example.com", credits=5)
    booking = Booking("B001", "M001", "C001", "confirmed", datetime.now())
    
    cancel_booking(member, booking)
    
    assert member.credits == 6
    assert booking.status == "cancelled"
```

This test is a specification. It says exactly what cancellation means. Anyone reading this code knows what to expect. Six months from now, when you've forgotten the details, the test remembers.

### Red-Green-Refactor Prevents Over-Engineering

TDD's rhythm keeps you focused. Write the test. Make it pass. Clean it up. That's it.

You don't add features you don't need. You don't abstract before you understand the pattern. You don't optimize before you measure. The test defines what's needed. Nothing more.

This is how you avoid over-engineering. You only add complexity when the tests demand it. When two tests require the same setup code, you extract a helper. When three classes need the same validation, you create a value object. But not before.

TDD is incremental. It resists the urge to build everything up front.

## The Testing Pyramid

Not all tests are created equal. Some are fast, focused, and fragile. Some are slow, comprehensive, and stable. A well-tested system has the right balance.

The **testing pyramid** is a guide:

```
        /\
       /  \
      / E2E \      End-to-End: Few, slow, realistic
     /______\
    /        \
   /Integration\   Integration: Some, medium speed, focused
  /____________\
 /              \
/   Unit Tests   \  Unit: Many, fast, isolated
/__________________\
```

**Unit tests** are at the base. They test individual functions or classes in isolation—no databases, no network, no external dependencies. They're fast—milliseconds. They're focused—one behavior per test. They're many—hundreds or thousands. Unit tests verify that your business logic works correctly.

```python
def test_member_deduct_credit():
    """Unit test: tests a single method in isolation"""
    member = Member("M001", "Alice", "alice@example.com", credits=10)
    member.deduct_credit()
    assert member.credits == 9
```

**Integration tests** are in the middle. They test how components work together—your code interacting with databases, file systems, or other services. They're slower—seconds. They're broader—testing workflows across multiple classes. Integration tests verify that your code integrates correctly with external systems.

```python
def test_booking_persists_to_database():
    """Integration test: tests interaction with database"""
    repo = SqliteMemberRepository(test_db)
    member = Member("M001", "Alice", "alice@example.com", credits=10)
    repo.save(member)
    
    loaded = repo.get_by_id("M001")
    assert loaded.credits == 10
```

**End-to-end tests** (E2E) are at the top. They test the entire system from the user's perspective—HTTP requests, database, email sending, everything running together as it would in production. They're slowest—minutes. They're fewest—a handful of critical paths. E2E tests verify that the complete user workflow works as expected.

```python
def test_complete_booking_flow():
    """E2E test: tests complete user workflow through HTTP API"""
    response = client.post('/bookings', json={
        'member_id': 'M001',
        'class_id': 'C001'
    })
    
    assert response.status_code == 201
    assert response.json['status'] == 'confirmed'
```

The pyramid shape matters. Most tests should be unit tests. They run fast, so you run them constantly. Integration tests are slower, so you have fewer. End-to-end tests are slowest, so you have just enough to verify critical workflows.

If your pyramid is inverted—mostly end-to-end tests, few unit tests—your test suite is slow and brittle. Tests take minutes to run. Failures are hard to debug. You stop running tests before every commit.

TDD naturally builds the right pyramid. When you write tests first, you start with unit tests. Integration and end-to-end tests come later, as you verify that components work together.

## TDD in Practice: A Complete Example

Let's build a feature from scratch using TDD: premium members get priority when a class is full.

**Business rule:** When a class is full, premium members can join a waitlist. When someone cancels, the next premium member on the waitlist gets the spot.

Before we write any tests, let's think through what we're building. This is a critical step that many developers skip—they jump straight to writing tests without understanding what behavior they're trying to capture.

### Breaking Down the Feature

TDD doesn't mean "write random tests." It means "write tests that specify the behavior you need." To do that, you need to understand the behavior first.

#### What scenarios does this business rule create?

Let's analyze the business rule and identify the distinct paths through our system:

1. **Premium member encounters full class** - A premium member tries to book a full class and should be added to a waitlist instead of being rejected
2. **Basic member encounters full class** - A basic member tries to book a full class and should get an error (no waitlist access)
3. **Cancellation promotes waitlisted member** - When someone cancels their booking, the first premium member on the waitlist should automatically get the spot

Each scenario represents a different behavior we need to test.

#### What domain concepts emerge?

From these scenarios, we can see we need:

- **Member with membership type** - We need to distinguish premium from basic members
- **FitnessClass with waitlist** - Classes need to track both confirmed bookings and waitlisted members
- **Waitlist rules** - Logic for who can join and when they get promoted

#### How do tests reveal architecture?

Notice what happened: we started with a business rule, broke it into scenarios, and discovered the objects and behaviors we need. **The tests will make these discoveries explicit.**

When we write the test for "premium member encounters full class," we'll be forced to decide:
- How does a Member know if it's premium?
- How does a FitnessClass track waitlisted members?
- What does the `book_class` function return when someone is waitlisted?

**This is how TDD drives design.** The test forces you to answer these questions before you write implementation code. You design the interface (what the code does) before the implementation (how it does it).

### Step 1: Write the Test

Now that we understand what we're building, let's write a test for the first scenario: premium member encounters full class.

```python
def test_premium_member_joins_waitlist_when_class_full():
    premium_member = Member(
        member_id="M001",
        name="Alice",
        email="alice@example.com",
        membership_type="premium",
        credits=10
    )
    
    fitness_class = FitnessClass(
        class_id="C001",
        name="Yoga",
        capacity=1
    )
    
    # Fill the class
    basic_member = Member("M002", "Bob", "bob@example.com", "basic", 10)
    fitness_class.add_booking(basic_member.id)
    
    # Premium member tries to book
    result = book_class(premium_member, fitness_class)
    
    assert result.status == "waitlisted"
    assert premium_member in fitness_class.waitlist
```

**Red.** The code doesn't exist.

**What did this test reveal about our design?**

Look at what we had to decide just to write this test:
- `Member` needs a `membership_type` parameter
- `FitnessClass` needs to track a `waitlist` (separate from bookings)
- `book_class` needs to return a result with a `status` field
- There's a concept of "waitlisted" as a booking status

These are design decisions. We made them by thinking about how the code should be used, not how it will be implemented. This is the power of TDD—it forces you to design from the outside in.

### Step 2: Make It Pass

```python
class Member:
    def __init__(self, member_id: str, name: str, email: str, 
                 membership_type: str, credits: int):
        self.id = member_id
        self.name = name
        self.email = EmailAddress(email)
        self.membership_type = membership_type
        self._credits = credits
    
    def is_premium(self) -> bool:
        return self.membership_type == "premium"


class FitnessClass:
    def __init__(self, class_id: str, name: str, capacity: int):
        self.id = class_id
        self.name = name
        self._capacity = capacity
        self._bookings = []
        self._waitlist = []
    
    def add_to_waitlist(self, member_id: str):
        if member_id not in self._waitlist:
            self._waitlist.append(member_id)
    
    @property
    def waitlist(self):
        return self._waitlist.copy()


def book_class(member: Member, fitness_class: FitnessClass) -> Booking:
    if fitness_class.is_full():
        if member.is_premium():
            fitness_class.add_to_waitlist(member.id)
            return Booking(
                booking_id=generate_booking_id(),
                member_id=member.id,
                class_id=fitness_class.id,
                status="waitlisted",
                booked_at=datetime.now()
            )
        else:
            raise ValueError("Class is full")
    
    member.deduct_credit()
    fitness_class.add_booking(member.id)
    
    return Booking(
        booking_id=generate_booking_id(),
        member_id=member.id,
        class_id=fitness_class.id,
        status="confirmed",
        booked_at=datetime.now()
    )
```

**Green.** Test passes.

**What did making this test pass reveal?**

- We needed an `is_premium()` method on Member (encapsulation of the membership type check)
- FitnessClass needs both `_bookings` and `_waitlist` as separate collections
- The `book_class` function has branching logic based on class fullness and member type

This is simple code, but it works. We resisted the urge to over-engineer. We didn't create a "WaitlistStrategy" or "MembershipTypeFactory." We wrote the simplest code that makes the test pass.

Now we can refactor with confidence because the test proves the behavior works.

### Step 3: Refactor

The `book_class` function is getting complex. It has multiple responsibilities: checking capacity, handling waitlists, deducting credits. Let's split it.

```python
class BookingService:
    def book_class(self, member: Member, fitness_class: FitnessClass) -> Booking:
        if fitness_class.is_full():
            return self._handle_full_class(member, fitness_class)
        
        return self._confirm_booking(member, fitness_class)
    
    def _handle_full_class(self, member: Member, fitness_class: FitnessClass) -> Booking:
        if not member.is_premium():
            raise ValueError("Class is full")
        
        fitness_class.add_to_waitlist(member.id)
        return self._create_booking(member.id, fitness_class.id, "waitlisted")
    
    def _confirm_booking(self, member: Member, fitness_class: FitnessClass) -> Booking:
        member.deduct_credit()
        fitness_class.add_booking(member.id)
        return self._create_booking(member.id, fitness_class.id, "confirmed")
    
    def _create_booking(self, member_id: str, class_id: str, status: str) -> Booking:
        return Booking(
            booking_id=generate_booking_id(),
            member_id=member_id,
            class_id=class_id,
            status=status,
            booked_at=datetime.now()
        )
    ```

    **Why this refactoring?**

    The `book_class` function was doing too much: checking capacity, handling waitlists, deducting credits. It had multiple reasons to change (violates Single Responsibility Principle).

    By extracting a `BookingService` class, we've:
    - Separated concerns (each private method has one job)
    - Made the code easier to test (we can test `_handle_full_class` independently if needed)
    - Made the code easier to read (the public method reads like a story)

    **This is the TDD cycle in action:** Red (write test) → Green (make it pass) → Refactor (improve design). Tests enabled this refactoring. We moved logic into a service class without changing behavior. The test proves it still works.

    #### Adding the Second Scenario

    We've tested the happy path (premium member joins waitlist). Now let's test what happens when someone cancels:

    ```python
    def test_cancellation_promotes_waitlisted_member():
    premium_member = Member("M001", "Alice", "alice@example.com", "premium", 10)
    basic_member = Member("M002", "Bob", "bob@example.com", "basic", 10)
    
    fitness_class = FitnessClass("C001", "Yoga", capacity=1)
    
    # Basic member books
    booking = BookingService().book_class(basic_member, fitness_class)
    
    # Premium member gets waitlisted
    waitlist_booking = BookingService().book_class(premium_member, fitness_class)
    
    # Basic member cancels
    service = BookingService()
    service.cancel_booking(basic_member, booking)
    
    # Premium member should be promoted
    assert waitlist_booking.status == "confirmed"
    assert premium_member.id in fitness_class.bookings
    assert premium_member.id not in fitness_class.waitlist
```

**Red.** The promotion logic doesn't exist.

Write the code to make it pass. Refactor. Repeat.

This is TDD. Each test adds a new behavior. Each refactor improves the design. The tests guide you toward a clean, maintainable architecture.

## How TDD Influences Everything That Follows

The architectural patterns in the next chapters—layers, domain models, use cases, ports and adapters—all emerge naturally when you practice TDD.

This isn't theory. Look at what we just built:

**Tests revealed domain models.** We wrote tests for booking logic and discovered we needed:
- `Member` that enforces its own credit rules (not a passive data bag)
- `FitnessClass` that manages capacity and waitlists (not just properties)
- `MembershipType` that encodes business rules (not just a string)

The tests showed us these objects because we needed somewhere to put the business logic.

**Tests revealed the need for layers.** Right now, `book_class()` is simple. But what happens when we add:
- Database persistence (save the booking)
- Email notifications (confirm the booking)
- Payment processing (charge for the class)

Suddenly your test needs a database, an email server, and a payment API just to verify that "premium members can join waitlists." That's a signal. The business logic needs to be separated from infrastructure.

**Tests revealed use cases.** The `BookingService.book_class()` method we refactored? That's a use case waiting to happen. It orchestrates the workflow: check capacity, handle waitlist, deduct credits. Chapter 6 shows how to formalize this.

**Tests revealed the need for abstractions.** When we test `BookingService`, we don't want to depend on a real database. We want to test the logic. This pushes us toward ports (interfaces) and adapters (implementations). Chapter 7 shows the pattern.

**The key insight:** You don't need to know these patterns up front. TDD will lead you to them. When a test is hard to write, that's a signal. The code is asking for better structure. Listen to the tests—they're showing you the architecture you need.

## When NOT to Use TDD

TDD is powerful. But it's not always the right tool.

**Exploratory coding:** When you're learning a new library or API, you don't know what the interface should be yet. Write some experimental code. Figure out how things work. Then, when you understand it, write tests and refactor.

**Throwaway prototypes:** If you're building something to prove a concept and you know it'll be deleted, tests are overhead. Build it, learn from it, throw it away.

**UI design:** Pixel-perfect layouts, animations, visual styling—these are hard to test-drive. Build the UI, get it looking right, then add tests for the interactions and state management.

**Simple scripts:** A 20-line script that runs once to migrate data? Just write it. Tests would take longer than the script.

TDD is a tool. Use it when it helps. Skip it when it doesn't.

## From Tests to Structure

You've built a solid testing foundation. Your gym booking system has tests for member creation, class bookings, credit deduction, and waitlist management. The red-green-refactor rhythm guides your development. Each test passes. The code works.

But as the system grows, a new challenge emerges. Your tests are getting harder to write.

To test booking logic, you need a database. To test notifications, you need an email server. To test API endpoints, you need the full HTTP stack running. Each test requires more setup. More dependencies. More infrastructure that has nothing to do with the business rules you're trying to verify.

The tests are telling you something. They're saying: "This code is too tangled."

TDD revealed the need for better structure. The domain logic—member rules, class capacity, pricing strategies—is mixed with infrastructure concerns like database persistence and email sending. Your tests want to verify business rules, but they're forced to set up technical infrastructure.

**This is the signal.** When tests become difficult to write, when you can't test business logic in isolation, when infrastructure leaks into your domain—that's when you need architectural boundaries.

The next chapter introduces those boundaries. We'll separate business logic from technical details. We'll organise code into layers that let you test domain rules without databases, write use cases without HTTP, and swap infrastructure without touching business logic.

TDD got you here. It showed you what works and what doesn't. It built your confidence to refactor. Now it's telling you that the code needs structure—not because of architectural dogma, but because the tests are asking for it.

## Summary

TDD is the foundation of intentional architecture. It gives you:

1. **Design feedback** - Tests tell you when code is too coupled or too complex
2. **Safety** - Tests let you refactor confidently, knowing you won't break things
3. **Documentation** - Tests show how code is meant to be used
4. **Focus** - Red-Green-Refactor keeps you incremental, preventing over-engineering

The chapters that follow—layers, domain modeling, ports and adapters—build on this foundation. Without TDD, those patterns feel academic. With TDD, they emerge naturally from the tests.

Start simple. Write a failing test. Make it pass. Clean it up. Repeat.

We've built domain objects through TDD. `Member`, `FitnessClass`, `Booking`—each tested and focused. But as we add persistence, APIs, and infrastructure, we'll discover these objects need organization. That's where layers come in.

That's how architecture happens.
