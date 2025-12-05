# Chapter 3: Test-Driven Development

The SOLID principles from Chapter 2 gave you tools to write flexible code. But they don't tell you when to apply them. They don't guide the design process itself. They're reactive—you use them when code starts to hurt.

Test-Driven Development (TDD) is proactive. It shapes your design from the first line of code.

TDD isn't just about testing. It's a design discipline. When you write tests first, you're forced to think about how your code will be used before you write it. You define the interface before the implementation. You discover design problems early, when they're cheap to fix.

This chapter introduces TDD as the foundation for everything that follows. The layers, the domain modeling, the ports and adapters—all of these patterns emerge more naturally when you start with tests.

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

Then repeat. Each cycle is small—a few minutes at most. Each cycle adds a new behavior or improves the design. Over time, a well-tested, well-designed system emerges.

Let's see this in practice with our gym booking system.

## Starting Simple: Our First Feature

We'll build the simplest possible feature: creating a member.

From a user's perspective: "I want to register a new gym member with a name and email address."

We start with a test. Not with the implementation. The test describes what we want:

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
    with pytest.raises(ValueError, match="Invalid email"):
        Member(
            member_id="M001",
            name="Alice Johnson",
            email="not-an-email"
        )

def test_member_requires_non_empty_name():
    with pytest.raises(ValueError, match="Name cannot be empty"):
        Member(
            member_id="M001",
            name="",
            email="alice@example.com"
        )
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

## Building a Complete Feature: Booking a Class

Let's build something more complex: booking a member into a fitness class.

Business rules:
- The class must have available capacity
- The member must have sufficient credits
- A booking creates a record

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

Run the tests. Still green. But now the business rules live in the domain objects. `Member` enforces credit rules. `FitnessClass` enforces capacity rules. The booking function just orchestrates.

This is TDD driving design. The tests forced us to think about the interface. The refactoring step let us improve the structure. The safety net let us move code around confidently.

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

**Unit tests** are at the base. They test individual functions or classes in isolation. They're fast—milliseconds. They're focused—one behavior per test. They're many—hundreds or thousands.

```python
def test_member_deduct_credit():
    member = Member("M001", "Alice", "alice@example.com", credits=10)
    member.deduct_credit()
    assert member.credits == 9
```

**Integration tests** are in the middle. They test how components work together. They might touch a database or call an external service. They're slower—seconds. They're broader—testing workflows across multiple classes.

```python
def test_booking_persists_to_database():
    repo = SqliteMemberRepository(test_db)
    member = Member("M001", "Alice", "alice@example.com", credits=10)
    repo.save(member)
    
    loaded = repo.get_by_id("M001")
    assert loaded.credits == 10
```

**End-to-end tests** are at the top. They test the entire system from the user's perspective. HTTP requests, database, email sending—everything. They're slowest—minutes. They're fewest—a handful of critical paths.

```python
def test_complete_booking_flow():
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

Business rule: When a class is full, premium members can join a waitlist. When someone cancels, the next premium member on the waitlist gets the spot.

### Step 1: Write the Test

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

Run the tests. Still green. The code is cleaner. Each method has one purpose.

Now add the next feature: when someone cancels, promote the first waitlisted member.

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

**Layers** happen because you can't test business logic mixed with infrastructure. TDD forces separation.

**Domain models** happen because tests prefer objects that enforce their own rules. TDD pushes logic into entities and value objects.

**Use cases** happen because tests need clear entry points. TDD encourages focused, orchestrating functions.

**Ports and adapters** happen because tests can't depend on real databases and APIs. TDD demands abstractions.

You don't need to know these patterns up front. TDD will lead you to them. When a test is hard to write, that's a signal. The code is asking for better structure.

## When NOT to Use TDD

TDD is powerful. But it's not always the right tool.

**Exploratory coding:** When you're learning a new library or API, you don't know what the interface should be yet. Write some experimental code. Figure out how things work. Then, when you understand it, write tests and refactor.

**Throwaway prototypes:** If you're building something to prove a concept and you know it'll be deleted, tests are overhead. Build it, learn from it, throw it away.

**UI design:** Pixel-perfect layouts, animations, visual styling—these are hard to test-drive. Build the UI, get it looking right, then add tests for the interactions and state management.

**Simple scripts:** A 20-line script that runs once to migrate data? Just write it. Tests would take longer than the script.

TDD is a tool. Use it when it helps. Skip it when it doesn't.

## Summary

TDD is the foundation of intentional architecture. It gives you:

1. **Design feedback** - Tests tell you when code is too coupled or too complex
2. **Safety** - Tests let you refactor confidently, knowing you won't break things
3. **Documentation** - Tests show how code is meant to be used
4. **Focus** - Red-Green-Refactor keeps you incremental, preventing over-engineering

The chapters that follow—layers, domain modeling, ports and adapters—build on this foundation. Without TDD, those patterns feel academic. With TDD, they emerge naturally from the tests.

Start simple. Write a failing test. Make it pass. Clean it up. Repeat.

That's how architecture happens.
