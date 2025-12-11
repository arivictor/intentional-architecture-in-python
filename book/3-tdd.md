# Chapter 3: Test-Driven Development

SOLID principles from Chapter 2 gave us well-designed rich domain classes. `Member`, `FitnessClass`, and `Booking` now encapsulate their own validation and behavior. They're no longer anemic data containers—they have methods like `can_book()`, `deduct_credit()`, and `add_booking()` that express business logic. We have pricing strategies. We have notification abstractions. The code is more maintainable.

But how do we know it works? How do we verify that our business rules are correct? How do we ensure that when we refactor—and we will—we don't break existing behavior?

We need tests. And more importantly, we need a way to design with tests.

## Where We Left Off

In Chapter 2, we refactored our gym booking system from dictionaries to anemic classes to rich classes following SOLID principles. Here's what we ended up with:

```python
# gym_booking.py (still one file, ~400 lines)
from datetime import datetime
from abc import ABC, abstractmethod
import uuid

# Domain Classes
class Member:
    """Represents a gym member with validation."""
    
    def __init__(self, member_id, name, email, membership_type, pricing_strategy):
        if '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.pricing_strategy = pricing_strategy
        self.credits = 20 if membership_type == 'premium' else 10
    
    def can_book(self):
        return self.credits > 0
    
    def deduct_credit(self):
        if self.credits > 0:
            self.credits -= 1
    
    def get_class_price(self):
        return self.pricing_strategy.calculate_price()


class FitnessClass:
    """Represents a fitness class."""
    
    def __init__(self, class_id, name, capacity, day, start_time):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.id = class_id
        self.name = name
        self.capacity = capacity
        self.day = day
        self.start_time = start_time
        self.bookings = []
    
    def spots_available(self):
        return self.capacity - len(self.bookings)
    
    def is_full(self):
        return self.spots_available() <= 0


class Booking:
    """Represents a class booking."""
    
    def __init__(self, booking_id, member_id, class_id):
        self.id = booking_id
        self.member_id = member_id
        self.class_id = class_id
        self.status = 'confirmed'
        self.booked_at = datetime.now()
    
    def cancel(self):
        self.status = 'cancelled'


# Pricing Strategies
class PricingStrategy(ABC):
    @abstractmethod
    def calculate_price(self) -> float:
        pass

class PremiumPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 0.0

class BasicPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 10.0

class StudentPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 5.0


# Notification Service
class NotificationService(ABC):
    @abstractmethod
    def send_booking_confirmation(self, member, fitness_class):
        pass

class EmailNotificationService(NotificationService):
    def send_booking_confirmation(self, member, fitness_class):
        # Email implementation...
        pass


# Global storage and services
members = {}
classes = {}
bookings = {}
notification_service = EmailNotificationService()

# Functions for CLI
def create_member(member_id, name, email, membership_type):
    # ... validation and creation ...
    pass

def book_class(member_id, class_id):
    # ... booking logic ...
    pass

# ... more functions ...
# ... main() CLI loop ...
```

**The problem:** This code works, but we have no automated way to verify it. To test if a member can book a class, we have to:
1. Run the entire program
2. Type commands manually
3. Check the output with our eyes
4. Repeat for every scenario

What if we could automatically verify that:
- Members can't book without credits?
- Classes can't exceed capacity?
- Email validation works correctly?
- Premium members get free classes?

We need automated tests.

## The New Challenge

The gym's CEO calls a meeting: "We're rolling out to three new locations next month. We can't afford bugs in production. Before we deploy any new feature, I need proof it works."

Fair request. But our current approach to testing is manual. To verify booking logic:
1. Run `python gym_booking.py`
2. Type `add-member M001 Alice alice@example.com premium`
3. Type `add-class C001 Yoga 20 Monday 09:00`
4. Type `book M001 C001`
5. Type `members` to verify credits were deducted
6. Repeat for every edge case

This is:
- **Slow:** Each test takes minutes of manual work
- **Error-prone:** Easy to miss edge cases
- **Unrepeatable:** Can't run the same tests quickly
- **Unmaintainable:** As features grow, manual testing becomes impossible

## Why Our Current Approach Struggles

### Problem 1: Business Logic Is Tangled With the CLI

Try to test the `Member` class:

```python
# How do you test this without running the whole program?
member = Member("M001", "Alice", "alice@example.com", "premium", PremiumPricing())
```

You can't. The `Member` class is defined inside `gym_booking.py`, which runs the CLI loop when imported. You can't import it without starting the interactive program.

### Problem 2: No Way to Verify Edge Cases

Let's say you want to verify: "Members with zero credits can't book classes."

How do you test this? You'd need to:
1. Create a member
2. Book classes until they run out of credits
3. Try to book one more
4. Verify it fails

Then do it again for the next edge case. And again. And again.

### Problem 3: Can't Test Without Side Effects

The `book_class()` function:
- Modifies global dictionaries
- Sends email notifications
- Prints to console

How do you test that booking logic works without actually sending emails? Without modifying production data? Without cluttering your terminal?

You can't. The code isn't designed for testing.

## What Is Test-Driven Development?

**Test-Driven Development (TDD)** is a discipline where you write tests before you write code.

The rhythm is simple: **Red, Green, Refactor.**

1. **Red:** Write a failing test. The test describes what you want the code to do. It fails because the code doesn't exist yet.
2. **Green:** Write the simplest code that makes the test pass. Don't worry about elegance. Just make it work.
3. **Refactor:** Improve the code while keeping tests green. Remove duplication. Apply SOLID principles.

Then repeat. Each cycle is small—a few minutes at most. Each cycle adds a behavior. Over time, a well-tested, well-designed system emerges.

**Why does this matter?**

TDD isn't just about testing. It's a design discipline. When you write tests first, you're forced to think about how code will be used before you write it. You discover design problems early, when they're cheap to fix.

More importantly, TDD builds a safety net. Every test is executable proof that your code works. This safety net lets you refactor confidently. You can change implementation details knowing that if you break something, the tests will tell you.

This is why TDD comes before architectural patterns. The patterns we'll learn in later chapters—layers, domain models, ports and adapters—all require refactoring. You can't refactor safely without tests.

**TDD enables architecture.**

## Refactoring Step 1: Separate Code From CLI

Before we can write tests, we need to separate our business logic from the CLI. Let's extract our classes into a separate module.

Create a new file structure:

```
gym_booking/
  ├── domain.py          # New: Domain classes
  ├── pricing.py         # New: Pricing strategies
  ├── notifications.py   # New: Notification service
  ├── cli.py            # New: CLI interface (renamed from gym_booking.py)
  └── tests/
      └── test_member.py # New: Our first test!
```

**domain.py:**
```python
from datetime import datetime

class Member:
    """Represents a gym member with validation."""
    
    def __init__(self, member_id, name, email, membership_type, pricing_strategy):
        if '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.pricing_strategy = pricing_strategy
        self.credits = 20 if membership_type == 'premium' else 10
    
    def can_book(self):
        return self.credits > 0
    
    def deduct_credit(self):
        if self.credits > 0:
            self.credits -= 1
    
    def get_class_price(self):
        return self.pricing_strategy.calculate_price()


class FitnessClass:
    """Represents a fitness class."""
    
    def __init__(self, class_id, name, capacity, day, start_time):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.id = class_id
        self.name = name
        self.capacity = capacity
        self.day = day
        self.start_time = start_time
        self.bookings = []
    
    def spots_available(self):
        return self.capacity - len(self.bookings)
    
    def is_full(self):
        return self.spots_available() <= 0


class Booking:
    """Represents a class booking."""
    
    def __init__(self, booking_id, member_id, class_id):
        self.id = booking_id
        self.member_id = member_id
        self.class_id = class_id
        self.status = 'confirmed'
        self.booked_at = datetime.now()
    
    def cancel(self):
        self.status = 'cancelled'
```

Now we can import these classes in tests without running the CLI!

## Writing Our First Test

Let's test the `Member` class. We'll use Python's built-in `pytest` framework (install with `pip install pytest`).

**tests/test_member.py:**
```python
import pytest
from domain import Member
from pricing import PremiumPricing, BasicPricing

def test_create_member_with_valid_email():
    """Test that a member can be created with valid data."""
    # Given: Valid member data
    member = Member(
        member_id="M001",
        name="Alice Johnson",
        email="alice@example.com",
        membership_type="premium",
        pricing_strategy=PremiumPricing()
    )
    
    # Then: Member is created with correct attributes
    assert member.id == "M001"
    assert member.name == "Alice Johnson"
    assert member.email == "alice@example.com"
    assert member.membership_type == "premium"
    assert member.credits == 20  # Premium members get 20 credits


def test_create_member_with_invalid_email():
    """Test that invalid email raises an error."""
    # When: Creating a member with invalid email
    # Then: ValueError is raised
    with pytest.raises(ValueError, match="Invalid email address"):
        Member(
            member_id="M001",
            name="Alice",
            email="not-an-email",  # No @ or .
            membership_type="premium",
            pricing_strategy=PremiumPricing()
        )


def test_premium_member_gets_20_credits():
    """Test that premium members start with 20 credits."""
    member = Member("M001", "Alice", "alice@example.com", "premium", PremiumPricing())
    assert member.credits == 20


def test_basic_member_gets_10_credits():
    """Test that basic members start with 10 credits."""
    member = Member("M001", "Bob", "bob@example.com", "basic", BasicPricing())
    assert member.credits == 10


def test_member_can_book_with_credits():
    """Test that members with credits can book."""
    member = Member("M001", "Alice", "alice@example.com", "premium", PremiumPricing())
    assert member.can_book() is True


def test_member_cannot_book_without_credits():
    """Test that members without credits cannot book."""
    member = Member("M001", "Alice", "alice@example.com", "basic", BasicPricing())
    member.credits = 0
    assert member.can_book() is False


def test_deduct_credit_reduces_credits():
    """Test that deducting a credit reduces the count."""
    member = Member("M001", "Alice", "alice@example.com", "premium", PremiumPricing())
    initial_credits = member.credits
    
    member.deduct_credit()
    
    assert member.credits == initial_credits - 1
```

Run the tests:

```bash
$ pytest tests/test_member.py -v
========================= test session starts =========================
tests/test_member.py::test_create_member_with_valid_email PASSED
tests/test_member.py::test_create_member_with_invalid_email PASSED
tests/test_member.py::test_premium_member_gets_20_credits PASSED
tests/test_member.py::test_basic_member_gets_10_credits PASSED
tests/test_member.py::test_member_can_book_with_credits PASSED
tests/test_member.py::test_member_cannot_book_without_credits PASSED
tests/test_member.py::test_deduct_credit_reduces_credits PASSED
======================== 7 passed in 0.03s ========================
```

**What just happened?**

We verified seven different scenarios in 0.03 seconds. No manual typing. No visual inspection. Automated proof that our `Member` class works correctly.

## Testing FitnessClass

Let's add tests for `FitnessClass`:

**tests/test_fitness_class.py:**
```python
import pytest
from domain import FitnessClass

def test_create_fitness_class():
    """Test creating a fitness class with valid data."""
    fitness_class = FitnessClass(
        class_id="C001",
        name="Yoga Flow",
        capacity=20,
        day="Monday",
        start_time="09:00"
    )
    
    assert fitness_class.id == "C001"
    assert fitness_class.name == "Yoga Flow"
    assert fitness_class.capacity == 20
    assert fitness_class.day == "Monday"
    assert fitness_class.start_time == "09:00"
    assert len(fitness_class.bookings) == 0


def test_cannot_create_class_with_zero_capacity():
    """Test that capacity must be positive."""
    with pytest.raises(ValueError, match="Capacity must be positive"):
        FitnessClass("C001", "Yoga", 0, "Monday", "09:00")


def test_cannot_create_class_with_negative_capacity():
    """Test that capacity cannot be negative."""
    with pytest.raises(ValueError, match="Capacity must be positive"):
        FitnessClass("C001", "Yoga", -5, "Monday", "09:00")


def test_spots_available_when_empty():
    """Test spots available equals capacity when no bookings."""
    fitness_class = FitnessClass("C001", "Yoga", 20, "Monday", "09:00")
    assert fitness_class.spots_available() == 20


def test_spots_available_decreases_with_bookings():
    """Test spots available decreases as bookings are added."""
    fitness_class = FitnessClass("C001", "Yoga", 20, "Monday", "09:00")
    fitness_class.bookings.append("M001")
    fitness_class.bookings.append("M002")
    
    assert fitness_class.spots_available() == 18


def test_class_not_full_initially():
    """Test that a new class is not full."""
    fitness_class = FitnessClass("C001", "Yoga", 20, "Monday", "09:00")
    assert fitness_class.is_full() is False


def test_class_is_full_at_capacity():
    """Test that a class is full when bookings equal capacity."""
    fitness_class = FitnessClass("C001", "Yoga", 2, "Monday", "09:00")
    fitness_class.bookings.append("M001")
    fitness_class.bookings.append("M002")
    
    assert fitness_class.is_full() is True
```

Run all tests:

```bash
$ pytest tests/ -v
========================= test session starts =========================
tests/test_member.py::test_create_member_with_valid_email PASSED
tests/test_member.py::test_create_member_with_invalid_email PASSED
tests/test_member.py::test_premium_member_gets_20_credits PASSED
tests/test_member.py::test_basic_member_gets_10_credits PASSED
tests/test_member.py::test_member_can_book_with_credits PASSED
tests/test_member.py::test_member_cannot_book_without_credits PASSED
tests/test_member.py::test_deduct_credit_reduces_credits PASSED
tests/test_fitness_class.py::test_create_fitness_class PASSED
tests/test_fitness_class.py::test_cannot_create_class_with_zero_capacity PASSED
tests/test_fitness_class.py::test_cannot_create_class_with_negative_capacity PASSED
tests/test_fitness_class.py::test_spots_available_when_empty PASSED
tests/test_fitness_class.py::test_spots_available_decreases_with_bookings PASSED
tests/test_fitness_class.py::test_class_not_full_initially PASSED
tests/test_fitness_class.py::test_class_is_full_at_capacity PASSED
======================== 14 passed in 0.04s ========================
```

We now have 14 automated tests. They run in milliseconds. They verify business rules. They give us confidence.

## Test-Driving a New Feature: Waitlist

Now let's use TDD to add a new feature from scratch. The gym wants a waitlist for full classes.

**Business requirement:** "When a class is full, members should be able to join a waitlist. If someone cancels, the first person on the waitlist gets their spot."

Let's break this into testable scenarios:

1. Members can join waitlist when class is full
2. Waitlist is processed in order (FIFO)
3. Cancelling a booking offers spot to first waitlist member
4. Can't join waitlist if already booked in the class

### Red: Write Failing Tests

Let's start with the first scenario:

**tests/test_waitlist.py:**
```python
import pytest
from domain import FitnessClass

def test_can_join_waitlist_when_class_full():
    """Test that members can join waitlist when class is full."""
    # Given: A full class
    fitness_class = FitnessClass("C001", "Yoga", 2, "Monday", "09:00")
    fitness_class.bookings.append("M001")
    fitness_class.bookings.append("M002")
    
    # When: A member tries to join the waitlist
    fitness_class.add_to_waitlist("M003")
    
    # Then: They are added to the waitlist
    assert "M003" in fitness_class.waitlist
```

Run the test:

```bash
$ pytest tests/test_waitlist.py -v
========================= test session starts =========================
tests/test_waitlist.py::test_can_join_waitlist_when_class_full FAILED
======================== FAILURES ========================
E   AttributeError: 'FitnessClass' object has no attribute 'waitlist'
```

**Red!** The test fails because `FitnessClass` doesn't have a waitlist yet.

### Green: Make It Pass

Add the simplest code to make the test pass:

**domain.py:**
```python
class FitnessClass:
    def __init__(self, class_id, name, capacity, day, start_time):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.id = class_id
        self.name = name
        self.capacity = capacity
        self.day = day
        self.start_time = start_time
        self.bookings = []
        self.waitlist = []  # NEW
    
    def spots_available(self):
        return self.capacity - len(self.bookings)
    
    def is_full(self):
        return self.spots_available() <= 0
    
    def add_to_waitlist(self, member_id):  # NEW
        self.waitlist.append(member_id)
```

Run the test again:

```bash
$ pytest tests/test_waitlist.py -v
========================= test session starts =========================
tests/test_waitlist.py::test_can_join_waitlist_when_class_full PASSED
======================== 1 passed in 0.01s ========================
```

**Green!** The test passes.

### Red: Add More Scenarios

Now let's test that we can't join the waitlist if already booked:

**tests/test_waitlist.py:**
```python
def test_cannot_join_waitlist_if_already_booked():
    """Test that you can't join waitlist if you're already booked."""
    # Given: A member is already booked in a class
    fitness_class = FitnessClass("C001", "Yoga", 20, "Monday", "09:00")
    fitness_class.bookings.append("M001")
    
    # When/Then: They try to join waitlist and it fails
    with pytest.raises(ValueError, match="Already booked in this class"):
        fitness_class.add_to_waitlist("M001")
```

Run it:

```bash
$ pytest tests/test_waitlist.py::test_cannot_join_waitlist_if_already_booked -v
FAILED
E   Failed: DID NOT RAISE <class 'ValueError'>
```

**Red!** Now make it pass.

### Green: Implement the Check

**domain.py:**
```python
def add_to_waitlist(self, member_id):
    if member_id in self.bookings:
        raise ValueError("Already booked in this class")
    self.waitlist.append(member_id)
```

Run the tests:

```bash
$ pytest tests/test_waitlist.py -v
========================= test session starts =========================
tests/test_waitlist.py::test_can_join_waitlist_when_class_full PASSED
tests/test_waitlist.py::test_cannot_join_waitlist_if_already_booked PASSED
======================== 2 passed in 0.01s ========================
```

**Green!**

### Refactor: Improve the Design

Now that we have tests, we can refactor safely. Let's add a method to process the waitlist when a booking is cancelled:

**tests/test_waitlist.py:**
```python
def test_waitlist_member_gets_spot_when_booking_cancelled():
    """Test that first waitlist member gets spot when booking cancelled."""
    # Given: A full class with one person on waitlist
    fitness_class = FitnessClass("C001", "Yoga", 2, "Monday", "09:00")
    fitness_class.bookings.append("M001")
    fitness_class.bookings.append("M002")
    fitness_class.add_to_waitlist("M003")
    
    # When: A booking is removed
    fitness_class.bookings.remove("M002")
    promoted = fitness_class.process_waitlist()
    
    # Then: First waitlist member is promoted
    assert promoted == "M003"
    assert "M003" in fitness_class.bookings
    assert "M003" not in fitness_class.waitlist
```

**Red** → Implement `process_waitlist()` → **Green**:

**domain.py:**
```python
def process_waitlist(self):
    """Move first waitlist member to bookings if space available."""
    if self.waitlist and not self.is_full():
        member_id = self.waitlist.pop(0)  # FIFO
        self.bookings.append(member_id)
        return member_id
    return None
```

Run all tests:

```bash
$ pytest tests/ -v
========================= test session starts =========================
tests/test_member.py::test_create_member_with_valid_email PASSED
tests/test_member.py::test_create_member_with_invalid_email PASSED
... (14 member and fitness class tests)
tests/test_waitlist.py::test_can_join_waitlist_when_class_full PASSED
tests/test_waitlist.py::test_cannot_join_waitlist_if_already_booked PASSED
tests/test_waitlist.py::test_waitlist_member_gets_spot_when_booking_cancelled PASSED
======================== 17 passed in 0.05s ========================
```

**We just built a complete feature using TDD.** Each test drove a piece of behavior. Each piece builds on the last. The tests prove it works.

## What We Have Now

Let's take stock of our progress. We've added testing to our gym booking system:

**Our code now has:**
1. **Separated concerns:** Classes in `domain.py`, not tangled with CLI
2. **Automated tests:** 17 tests verifying business logic
3. **Test suite:** Can run all tests in milliseconds
4. **Confidence:** Tests prove business rules work
5. **New feature:** Waitlist functionality, built with TDD

**But we still have:**
- Classes in simple .py files (no package structure yet)
- In-memory storage (dictionaries in CLI)
- No database persistence
- Everything still runs from the CLI
- Business logic and storage mixed together

**Current file structure:**
```
gym_booking/
  ├── domain.py              # Domain classes
  ├── pricing.py             # Pricing strategies
  ├── notifications.py       # Notification service
  ├── cli.py                # CLI interface
  └── tests/
      ├── test_member.py
      ├── test_fitness_class.py
      └── test_waitlist.py
```

This is progress! We can now:
- Verify business logic automatically
- Refactor with confidence
- Add features using TDD
- Catch bugs before production

But our tests reveal a problem: **business logic is still tangled with data storage.** Look at our tests—they directly manipulate `fitness_class.bookings` lists and `member.credits` integers. When we want to persist data to a database, these tests will break.

## Transition to Chapter 4

We have tests. We have confidence. But the tests exposed a deeper issue: **where does data persistence belong?**

Right now, business logic and storage are intertwined:
- `FitnessClass` stores bookings in a list
- `Member` tracks credits as an integer
- The CLI manages global dictionaries

When we add database persistence (and we will), where does that code go? If we put it in `Member` or `FitnessClass`, our tests will require a database. If we put it in the CLI, we're mixing concerns again.

We need layers. We need to separate:
- **Business rules** (domain logic that never changes)
- **Application logic** (orchestrating use cases)
- **Infrastructure** (databases, email, external services)
- **Interface** (CLI, APIs, anything that talks to users)

In Chapter 4, we'll learn **Layered Architecture**. We'll reorganize our code into layers. We'll create use cases that orchestrate domain objects. We'll add database persistence without breaking our tests. And we'll discover that good architecture makes testing even easier.

**The challenge:** "We need to save data to a database so bookings persist between sessions. Where does that code go? How do we keep our tests fast?"

That's next.
