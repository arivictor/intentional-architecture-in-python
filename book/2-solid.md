# Chapter 2: SOLID Principles

Philosophy only takes you so far. Architecture isn't built on principles alone, it's built on decisions made when code demands them. Chapter 1 gave you the mindset. Now we're going to apply it.

## Where We Left Off

In Chapter 1, we inherited a simple but functional gym booking system. Here's what we had:

```python
# gym_booking.py - The complete working script
from datetime import datetime
import uuid

# Our "database" - just dictionaries in memory
members = {}
classes = {}
bookings = {}

def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    members[member_id] = {
        'id': member_id,
        'name': name,
        'email': email,
        'membership_type': membership_type,
        'credits': 20 if membership_type == 'premium' else 10
    }
    print(f"✓ Created member: {name} ({membership_type})")

def create_class(class_id, name, capacity, day, start_time):
    """Create a new fitness class."""
    classes[class_id] = {
        'id': class_id,
        'name': name,
        'capacity': capacity,
        'day': day,
        'start_time': start_time,
        'bookings': []
    }
    print(f"✓ Created class: {name} on {day} at {start_time}")

def book_class(member_id, class_id):
    """Book a member into a class."""
    if member_id not in members:
        print("✗ Member not found")
        return
    if class_id not in classes:
        print("✗ Class not found")
        return
    
    member = members[member_id]
    fitness_class = classes[class_id]
    
    # Business rules
    if len(fitness_class['bookings']) >= fitness_class['capacity']:
        print("✗ Class is full")
        return
    if member['credits'] <= 0:
        print("✗ Insufficient credits")
        return
    
    # Create the booking
    booking_id = uuid.uuid4().hex
    bookings[booking_id] = {
        'id': booking_id,
        'member_id': member_id,
        'class_id': class_id,
        'status': 'confirmed',
        'booked_at': datetime.now()
    }
    
    # Update state
    member['credits'] -= 1
    fitness_class['bookings'].append(member_id)
    
    print(f"✓ Booked {member['name']} into {fitness_class['name']}")
    print(f"  Booking ID: {booking_id}")
    print(f"  Credits remaining: {member['credits']}")

def cancel_booking(booking_id):
    """Cancel a booking and refund the credit."""
    if booking_id not in bookings:
        print("✗ Booking not found")
        return
    
    booking = bookings[booking_id]
    member = members[booking['member_id']]
    fitness_class = classes[booking['class_id']]
    
    # Refund and update
    member['credits'] += 1
    fitness_class['bookings'].remove(booking['member_id'])
    booking['status'] = 'cancelled'
    
    print(f"✓ Cancelled booking {booking_id}")
    print(f"  Refunded 1 credit to {member['name']}")

# ... list_members(), list_classes(), list_bookings(), show_help(), main() ...
```

This script worked. It was simple, understandable, and got the job done. Members could book classes. Classes tracked capacity. Bookings got confirmed and cancelled. For a proof of concept, it was exactly what was needed.

## The New Challenge

A few weeks pass. The system is being used daily. Then new requirements arrive:

1. **Email validation:** We need to prevent members from registering with invalid email addresses. We've had several typos already.
2. **Prevent duplicates:** Members are accidentally registered twice with the same email. We need to check for duplicates.
3. **Premium member features:** Premium members should get priority booking and special pricing. The business logic for different membership types is growing.

Simple enough, right? Let's add these features to our existing code.

## Why Our Current Approach Struggles

### Problem 1: The `create_member()` Function Is Getting Bloated

Let's add email validation to `create_member()`:

```python
def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    # NEW: Email validation
    if '@' not in email or '.' not in email:
        print("✗ Invalid email address")
        return
    
    # NEW: Check for duplicates
    for existing_member in members.values():
        if existing_member['email'] == email:
            print("✗ Email already registered")
            return
    
    # NEW: More validation
    if membership_type not in ['basic', 'premium']:
        print("✗ Invalid membership type")
        return
    
    members[member_id] = {
        'id': member_id,
        'name': name,
        'email': email,
        'membership_type': membership_type,
        'credits': 20 if membership_type == 'premium' else 10
    }
    print(f"✓ Created member: {name} ({membership_type})")
```

The function is growing. Validation logic is mixing with data creation. What happens when we need to:
- Add phone number validation?
- Check password strength?
- Integrate with an external verification service?

The function keeps getting longer. It's doing too many things.

### Problem 2: Membership Type Logic Is Scattered Everywhere

Now premium members want priority booking when classes are near full. Let's update `book_class()`:

```python
def book_class(member_id, class_id):
    """Book a member into a class."""
    if member_id not in members:
        print("✗ Member not found")
        return
    if class_id not in classes:
        print("✗ Class not found")
        return
    
    member = members[member_id]
    fitness_class = classes[class_id]
    
    spots_left = fitness_class['capacity'] - len(fitness_class['bookings'])
    
    # NEW: Premium members can book when only 2 spots left
    # Basic members can only book when 3+ spots left
    if member['membership_type'] == 'premium':
        if spots_left < 1:
            print("✗ Class is full")
            return
    else:  # basic member
        if spots_left < 3:
            print("✗ Class is full (priority booking for premium members)")
            return
    
    if member['credits'] <= 0:
        print("✗ Insufficient credits")
        return
    
    # Create booking...
    # (rest of the function)
```

Now we have `if member['membership_type'] == 'premium'` checks appearing throughout the code. What happens when we add:
- Student memberships?
- Corporate memberships?
- Discount programs?

We'll have membership type checks scattered across every function. Every new membership type means modifying multiple functions.

### The Pain Is Real

Our simple script is straining. The code is:
- **Hard to change:** Adding a new membership type touches multiple functions
- **Hard to test:** How do you test email validation without running the whole program?
- **Hard to understand:** Business rules are buried in if-statements
- **Fragile:** Changing one function can break others

This is the signal. The code is asking for better structure. It's asking for SOLID.

## What Is SOLID?

**SOLID is an acronym** for five principles that guide how you write classes and structure code:

- **S**ingle Responsibility Principle
- **O**pen/Closed Principle
- **L**iskov Substitution Principle
- **I**nterface Segregation Principle
- **D**ependency Inversion Principle

These aren't theoretical rules. They're patterns that emerged from watching what makes code rigid and what makes it flexible. They give you a vocabulary for recognizing problems and reasoning about solutions.

Let's work through each one, using our actual pain points as motivation.

## Single Responsibility Principle

**A class should have one reason to change.**

The confusion comes from the word "responsibility." It doesn't mean "do one thing." It means "have one reason to change."

A responsibility is a stakeholder or concern that might request a change. If two different people, for two different reasons, might ask you to modify the same class, that class has multiple responsibilities.

### Refactoring Step 1: Extract `Member` Class

Our `create_member()` function mixes validation with data creation. Let's separate these concerns.

First, let's create a `Member` class that validates itself:

```python
class Member:
    """Represents a gym member with validation."""
    
    def __init__(self, member_id, name, email, membership_type):
        # Validation happens in the constructor
        if '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        if membership_type not in ['basic', 'premium']:
            raise ValueError(f"Invalid membership type: {membership_type}")
        
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.credits = 20 if membership_type == 'premium' else 10
    
    def __repr__(self):
        return f"Member({self.name}, {self.email}, {self.membership_type})"
```

Now our `create_member()` function becomes simpler:

```python
def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    # Check for duplicates
    for existing_member in members.values():
        if existing_member.email == email:
            print("✗ Email already registered")
            return
    
    try:
        member = Member(member_id, name, email, membership_type)
        members[member_id] = member  # Store Member object, not dict
        print(f"✓ Created member: {name} ({membership_type})")
    except ValueError as e:
        print(f"✗ {e}")
```

**What changed?**
- `Member` class handles member data and validation
- `create_member()` function handles duplicate checking and storage
- If email validation rules change, we only modify `Member`
- If storage logic changes, we only modify `create_member()`

One responsibility per component. This is SRP in action.

### Refactoring Step 2: Extract `FitnessClass` Class

Let's do the same for fitness classes:

```python
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
        self.bookings = []  # List of member IDs
    
    def spots_available(self):
        """Calculate available spots."""
        return self.capacity - len(self.bookings)
    
    def is_full(self):
        """Check if class is full."""
        return self.spots_available() <= 0
    
    def __repr__(self):
        return f"FitnessClass({self.name}, {self.day} {self.start_time})"
```

Now `create_class()` becomes:

```python
def create_class(class_id, name, capacity, day, start_time):
    """Create a new fitness class."""
    try:
        fitness_class = FitnessClass(class_id, name, capacity, day, start_time)
        classes[class_id] = fitness_class  # Store FitnessClass object
        print(f"✓ Created class: {name} on {day} at {start_time}")
    except ValueError as e:
        print(f"✗ {e}")
```

### Refactoring Step 3: Extract `Booking` Class

Finally, let's create a proper `Booking` class:

```python
class Booking:
    """Represents a class booking."""
    
    def __init__(self, booking_id, member_id, class_id):
        self.id = booking_id
        self.member_id = member_id
        self.class_id = class_id
        self.status = 'confirmed'
        self.booked_at = datetime.now()
    
    def cancel(self):
        """Mark booking as cancelled."""
        self.status = 'cancelled'
    
    def __repr__(self):
        return f"Booking({self.id}, status={self.status})"
```

Now `book_class()` uses our classes:

```python
def book_class(member_id, class_id):
    """Book a member into a class."""
    if member_id not in members:
        print("✗ Member not found")
        return
    if class_id not in classes:
        print("✗ Class not found")
        return
    
    member = members[member_id]  # Now a Member object
    fitness_class = classes[class_id]  # Now a FitnessClass object
    
    # Business rules
    if fitness_class.is_full():
        print("✗ Class is full")
        return
    if member.credits <= 0:
        print("✗ Insufficient credits")
        return
    
    # Create booking
    booking_id = uuid.uuid4().hex
    booking = Booking(booking_id, member_id, class_id)
    bookings[booking_id] = booking
    
    # Update state
    member.credits -= 1
    fitness_class.bookings.append(member_id)
    
    print(f"✓ Booked {member.name} into {fitness_class.name}")
    print(f"  Booking ID: {booking_id}")
    print(f"  Credits remaining: {member.credits}")
```

**Progress check:**
- We still have dictionaries (`members`, `classes`, `bookings`)
- We still have functions (`create_member`, `book_class`, etc.)
- We still have the command loop in `main()`
- But now we have **classes with behavior** instead of raw dictionaries
- Validation is encapsulated
- Business logic is clearer

This is incremental refactoring. We haven't changed everything. We've made it better, step by step.

## Open/Closed Principle

**Software entities should be open for extension, closed for modification.**

This principle feels paradoxical. How can something be both open and closed? The key is understanding what "extension" means in practice.

The goal is to add new behavior without changing existing code. When new requirements arrive, you extend the system by adding new classes, not by modifying working code.

### The Problem: Adding Student Pricing

The gym wants to add student memberships with special pricing:
- Premium: Free classes
- Basic: $10 per class
- **Student: $5 per class (NEW)**

With our current approach, we'd add if-statements everywhere:

```python
def book_class(member_id, class_id):
    # ... validation code ...
    
    # Calculate pricing
    if member.membership_type == 'premium':
        price = 0
    elif member.membership_type == 'basic':
        price = 10
    elif member.membership_type == 'student':  # NEW
        price = 5
    else:
        price = 15
    
    # ... rest of booking ...
```

Every time a new membership type appears, we modify existing functions. This violates Open/Closed.

### Refactoring: Pricing Strategies

Instead of if-statements, let's use the **Strategy Pattern**:

```python
from abc import ABC, abstractmethod

class PricingStrategy(ABC):
    """Abstract base class for pricing strategies."""
    
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
```

Now update `Member` to use a pricing strategy:

```python
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
    
    def get_class_price(self):
        """Calculate the price for this member."""
        return self.pricing_strategy.calculate_price()
```

Update `create_member()` to select the right strategy:

```python
def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    # Check for duplicates
    for existing_member in members.values():
        if existing_member.email == email:
            print("✗ Email already registered")
            return
    
    # Select pricing strategy
    if membership_type == 'premium':
        pricing = PremiumPricing()
    elif membership_type == 'basic':
        pricing = BasicPricing()
    elif membership_type == 'student':
        pricing = StudentPricing()
    else:
        print(f"✗ Invalid membership type: {membership_type}")
        return
    
    try:
        member = Member(member_id, name, email, membership_type, pricing)
        members[member_id] = member
        print(f"✓ Created member: {name} ({membership_type})")
    except ValueError as e:
        print(f"✗ {e}")
```

**What did we gain?**

Now when we add a new membership type, we:
1. Create a new `PricingStrategy` class (extension, not modification)
2. Update the strategy selection in `create_member()` (one place)

We **don't** modify:
- `Member` class
- `book_class()` function
- Any pricing calculation logic

The system is **open for extension** (new pricing strategies) but **closed for modification** (existing strategies don't change).

## Liskov Substitution Principle

**Objects of a subclass should be replaceable with objects of the superclass without breaking the program.**

This principle is about maintaining consistent behavior. If you have a base class and derived classes, using any derived class should work wherever the base is expected.

### The Problem: Inconsistent Membership Behavior

Let's say we want to add a `GuestPass` membership type. Guests can book classes, but they have limited uses:

```python
class Member:
    # ... existing Member code ...
    
    def can_book(self):
        """Check if member can book classes."""
        return self.credits > 0


class GuestPass(Member):
    def __init__(self, member_id, name, email):
        super().__init__(member_id, name, email, 'guest', PremiumPricing())
        self.classes_remaining = 3  # Only 3 classes allowed
    
    def can_book(self):
        """Guests check remaining classes, not credits."""
        return self.classes_remaining > 0  # Different behavior!
```

This violates LSP. Code that expects `Member.can_book()` to check credits will break with `GuestPass`.

### Refactoring: Unified Interface

Make the behavior consistent:

```python
class Member:
    def __init__(self, member_id, name, email, membership_type, pricing_strategy):
        # ... validation ...
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.pricing_strategy = pricing_strategy
        self.credits = 20 if membership_type == 'premium' else 10
    
    def can_book(self):
        """Check if member can book classes."""
        return self.credits > 0
    
    def deduct_credit(self):
        """Deduct one credit."""
        if self.credits > 0:
            self.credits -= 1


class GuestPass(Member):
    def __init__(self, member_id, name, email):
        super().__init__(member_id, name, email, 'guest', PremiumPricing())
        self.credits = 3  # Use credits, not a separate field
    
    # No need to override can_book() - it works the same way!
```

Now `GuestPass` is a true substitute for `Member`. The interface is consistent. Code that works with `Member` works with `GuestPass` without special cases.

## Interface Segregation Principle

**Clients should not be forced to depend on interfaces they don't use.**

This principle is about keeping interfaces focused. Don't create massive interfaces that do everything. Split them into smaller, specific ones.

For our gym system, this principle is less critical right now because our classes are still simple. But let's see a quick example.

### Bad: Fat Interface

```python
class MemberOperations(ABC):
    @abstractmethod
    def book_class(self, fitness_class): pass
    
    @abstractmethod
    def cancel_booking(self, booking): pass
    
    @abstractmethod
    def make_payment(self, amount): pass
    
    @abstractmethod
    def update_payment_method(self, method): pass
    
    @abstractmethod
    def get_payment_history(self): pass
```

If you only need booking functionality, you're forced to implement all payment methods too.

### Good: Focused Interfaces

```python
class Bookable(ABC):
    @abstractmethod
    def book_class(self, fitness_class): pass
    
    @abstractmethod
    def cancel_booking(self, booking): pass


class Payable(ABC):
    @abstractmethod
    def make_payment(self, amount): pass
    
    @abstractmethod
    def update_payment_method(self, method): pass
    
    @abstractmethod
    def get_payment_history(self): pass
```

Now classes implement only what they need. We'll see this principle matter more as we build out the system in later chapters.

## Dependency Inversion Principle

**High-level modules should not depend on low-level modules. Both should depend on abstractions.**

This is the principle that enables testability and flexibility. Instead of concrete dependencies, depend on abstractions (interfaces).

### The Problem: Adding Email Notifications

The gym wants to send email confirmations when bookings are made. Let's add it directly:

```python
import smtplib

def book_class(member_id, class_id):
    # ... validation and booking logic ...
    
    # Send email notification
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login("gym@example.com", "password")
    message = f"Hi {member.name}, your booking for {fitness_class.name} is confirmed."
    server.sendmail("gym@example.com", member.email, message)
    server.quit()
    
    print(f"✓ Booked {member.name} into {fitness_class.name}")
```

**Problems:**
- Can't test booking logic without sending emails
- Can't change email provider without modifying `book_class()`
- Function is slow (network calls)
- Violates SRP (booking + notifications)

### Refactoring: Depend on Abstractions

First, define an abstraction:

```python
class NotificationService(ABC):
    @abstractmethod
    def send_booking_confirmation(self, member, fitness_class):
        pass
```

Then create implementations:

```python
class EmailNotificationService(NotificationService):
    def send_booking_confirmation(self, member, fitness_class):
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("gym@example.com", "password")
        message = f"Hi {member.name}, your booking for {fitness_class.name} is confirmed."
        server.sendmail("gym@example.com", member.email, message)
        server.quit()


class FakeNotificationService(NotificationService):
    """For testing - doesn't actually send emails."""
    def __init__(self):
        self.sent = []
    
    def send_booking_confirmation(self, member, fitness_class):
        self.sent.append((member, fitness_class))
```

Now `book_class()` depends on the abstraction:

```python
# Create a global notification service (we'll improve this in later chapters)
notification_service = EmailNotificationService()

def book_class(member_id, class_id):
    """Book a member into a class."""
    if member_id not in members:
        print("✗ Member not found")
        return
    if class_id not in classes:
        print("✗ Class not found")
        return
    
    member = members[member_id]
    fitness_class = classes[class_id]
    
    # Business rules
    if fitness_class.is_full():
        print("✗ Class is full")
        return
    if not member.can_book():
        print("✗ Insufficient credits")
        return
    
    # Create booking
    booking_id = uuid.uuid4().hex
    booking = Booking(booking_id, member_id, class_id)
    bookings[booking_id] = booking
    
    # Update state
    member.deduct_credit()
    fitness_class.bookings.append(member_id)
    
    # Send notification (abstraction!)
    notification_service.send_booking_confirmation(member, fitness_class)
    
    print(f"✓ Booked {member.name} into {fitness_class.name}")
    print(f"  Booking ID: {booking_id}")
    print(f"  Credits remaining: {member.credits}")
```

**What did we gain?**
- Can swap `EmailNotificationService` for `FakeNotificationService` in tests
- Can add SMS notifications without changing `book_class()`
- Business logic is separate from infrastructure
- Testable without network calls

## What We Have Now

Let's take stock of our progress. We've refactored our procedural script using SOLID principles:

**Our code now has:**
1. **Classes with behavior:** `Member`, `FitnessClass`, `Booking`
2. **Validation encapsulated:** Email validation lives in `Member.__init__()`
3. **Pricing strategies:** Easy to add new membership types
4. **Notification abstraction:** Ready for different notification methods

**But we still have:**
- Dictionaries for storage (`members = {}`, `classes = {}`, `bookings = {}`)
- Procedural functions (`create_member()`, `book_class()`, etc.)
- Interactive command loop in `main()`
- Everything in one file (it's getting long!)
- In-memory storage only (data lost on exit)

**Current file structure:**
```
gym_booking.py (single file, ~300 lines)
  ├── Classes: Member, FitnessClass, Booking
  ├── Strategies: PricingStrategy, PremiumPricing, BasicPricing, StudentPricing
  ├── Services: NotificationService, EmailNotificationService
  ├── Data: members={}, classes={}, bookings={}
  └── Functions: create_member(), book_class(), main(), etc.
```

This is good progress, but we're not done. Our classes follow SOLID principles, but the overall structure is still procedural. The code is easier to understand and modify, but it's all tangled together in one file.

## Transition to Chapter 3

We now have well-designed classes. But how do we know they work correctly? How do we ensure that when we refactor (and we will), we don't break existing behavior?

We need tests.

In Chapter 3, we'll learn Test-Driven Development. We'll write tests for our `Member`, `FitnessClass`, and `Booking` classes. We'll discover that having followed SOLID principles makes our code much easier to test. We'll test-drive a new feature (premium waitlist) from scratch. And we'll build the safety net that lets us refactor with confidence.

**The challenge:** "We need to be confident our business rules work before deploying to production. How do we test this code without running the entire CLI?"

That's next.
