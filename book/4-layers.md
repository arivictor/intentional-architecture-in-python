# Chapter 4: Layers & Clean Architecture

We've made significant progress. In Chapter 2, we applied SOLID principles to create well-designed classes. In Chapter 3, we added Test-Driven Development to build confidence through automated testing.

Our code is better. We have tests that let us refactor safely. Our domain classes are separated from the CLI. But there's still room for improvement.

## Where We Left Off

In Chapter 3, we reorganized our code to enable testing. Here's what we ended up with:

**File structure:**
```
gym_booking/
  ├── domain.py              # Member, FitnessClass, Booking classes
  ├── pricing.py             # PricingStrategy implementations
  ├── notifications.py       # NotificationService
  ├── cli.py                # CLI interface with global dictionaries
  └── tests/
      ├── test_member.py
      ├── test_fitness_class.py
      └── test_waitlist.py   # 17 passing tests
```

**What we have:**
- Domain classes with business logic and validation
- Pricing strategies following Open/Closed Principle
- Notification abstractions following Dependency Inversion
- Comprehensive test suite (17 tests, runs in milliseconds)
- CLI still manages global dictionaries for storage

**What works:**
- We can test business logic without running the CLI
- Tests are fast (no database, no network calls)
- Business rules are verified automatically
- Adding new features is safer with test coverage

**What's still a problem:**
- Data stored in-memory dictionaries (lost when program ends)
- All storage logic in CLI (mixed with interface code)
- No clear separation between "booking logic" and "where bookings are stored"
- Tests manipulate object attributes directly (`fitness_class.bookings.append(...)`)

## The New Challenge

Then new requirements arrive:

**The gym needs to persist data.** When the script ends, everything is lost. They want to store members, classes, and bookings in a SQLite database.

**The gym wants a REST API.** Other systems need to integrate with the booking system. They want endpoints: `POST /bookings`, `GET /classes`, etc.

You could add database code to your classes. You could add Flask routes next to your domain logic. It would work. But let's see what happens.

Here's our `Member` class with database persistence added:

```python
import sqlite3

class Member:
    def __init__(self, member_id: str, name: str, email: str, pricing_strategy):
        self.id = member_id
        self.name = name
        self.email = email
        self.pricing_strategy = pricing_strategy
        self.bookings = []
    
    def save(self):
        """Save member to database."""
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO members (id, name, email, pricing_type) VALUES (?, ?, ?, ?)",
            (self.id, self.name, self.email, self.pricing_strategy.__class__.__name__)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def load(member_id: str):
        """Load member from database."""
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, email, pricing_type FROM members WHERE id = ?", (member_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # Reconstruct pricing strategy from database
            if row[2] == 'PremiumPricing':
                pricing = PremiumPricing()
            elif row[2] == 'BasicPricing':
                pricing = BasicPricing()
            else:
                pricing = PayPerClassPricing()
            
            return Member(member_id, row[0], row[1], pricing)
        return None
    
    def get_class_price(self) -> float:
        return self.pricing_strategy.calculate_price()
```

And here's the API endpoint mixed in:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/bookings', methods=['POST'])
def create_booking():
    data = request.json
    member = Member.load(data['member_id'])
    fitness_class = FitnessClass.load(data['class_id'])
    
    if not member or not fitness_class:
        return jsonify({'error': 'Not found'}), 404
    
    if fitness_class.is_full():
        return jsonify({'error': 'Class is full'}), 400
    
    booking = Booking(generate_id(), member, fitness_class)
    booking.save()
    
    return jsonify({'booking_id': booking.id}), 201
```

This works. But look at what we've lost:

1. **Can't test business logic without a database.** Every test needs SQLite running.
2. **Can't change storage mechanism.** Want PostgreSQL? Rewrite every domain class.
3. **Can't test domain rules without Flask.** Testing capacity checks requires HTTP mocking.
4. **Domain classes know about infrastructure.** `Member` understands SQL and database connections.
5. **Business logic is tangled with technical details.** Where does the member concept end and the database concern begin?

We've violated the very principles we just learned. `Member` now has multiple reasons to change:
- Business rules change → modify `Member`
- Database schema changes → modify `Member`
- Storage mechanism changes → modify `Member`

The Single Responsibility Principle is broken. And we can't apply Dependency Inversion because the domain directly depends on concrete infrastructure.

**The code is asking for structure.** Not because layers are "correct," but because mixing these concerns makes everything harder.

This is the signal. We need layers.

## What Are Layers?

Layers organize code by the type of concern it addresses. Business logic in one place. Database code in another. API handling somewhere else. Each layer has a specific job, and the boundaries between them are enforced.

This isn't theoretical organization. It's solving the problem we just experienced:

**Without layers:** Database code lives in `Member`. Can't test business rules without SQLite. Can't swap databases without rewriting domain classes.

**With layers:** Database code lives in `infrastructure/`. Domain is pure business logic. Swap SQLite for PostgreSQL by changing one module, not twenty classes.

The separation makes change possible. Business rules can evolve without touching database code. Database implementation can change without touching business rules. This is what we lost when we mixed everything together.

## The Four Layers

We'll separate our code into four layers:

**Domain** - Pure business logic. The `Member`, `FitnessClass`, and `Booking` classes without any database code. Rules like "a class can't exceed capacity" or "premium members pay nothing." This layer knows nothing about SQLite, Flask, or email servers. It only knows the business.

**Application** - Use case orchestration. "Book a class" coordinates a member, a class, a booking, and notifications. It's not business logic (that's in domain), it's the workflow. It combines domain objects to achieve specific goals.

**Infrastructure** - Technical details. The SQLite code. The email sending. The file system. Everything that touches the outside world. This is where `Member.save()` and `Member.load()` should live, not in the domain class itself.

**Interface** - How the outside world talks to us. The Flask API endpoints. CLI commands. GraphQL resolvers. This layer translates HTTP requests into application use cases and domain results back into JSON.

**The dependency rule:** Dependencies flow inward toward the domain.
- Domain depends on nothing (no imports from other layers)
- Application depends on domain only
- Infrastructure implements abstractions defined by domain (imports interfaces, not business logic)
- Interface depends on application and infrastructure (to execute use cases and wire up adapters)

**Important nuance about infrastructure:** Infrastructure implements abstractions defined by the domain. The domain defines what it needs (like a repository interface), and infrastructure provides concrete implementations. Infrastructure imports domain entities for persistence operations, but never contains business logic. This is Dependency Inversion from Chapter 2. We'll see this pattern fully in Chapter 7 when we introduce ports and adapters.

> **Forward Reference:** We introduce the repository concept here, but the full implementation using ports and adapters comes in Chapter 7. For now, understand that repositories mediate between domain and data storage.

This rule is what makes layers work. Domain never imports from infrastructure. Application calls domain methods and uses infrastructure through abstractions. When we violated this by putting database code in `Member`, we broke the rule and created coupling.

## Refactoring Into Layers

Let's take our SOLID classes and organize them into layers. We'll extract the database code from `Member`, separate the API endpoints from business logic, and create clear boundaries.

Here's how our gym booking system looks when structured into layers:

```
gym_booking/
├── domain/
│   ├── __init__.py
│   ├── member.py
│   ├── fitness_class.py
│   └── pricing.py
├── application/
│   ├── __init__.py
│   └── booking_service.py
├── infrastructure/
│   ├── __init__.py
│   └── notifications.py
└── interface/
    ├── __init__.py
    └── api.py
```

This is the skeleton. The boundaries are clear before a single line of code is written. When you create a new file, you immediately know where it belongs. Business logic? Domain. Use case coordination? Application. Database access? Infrastructure. API endpoint? Interface.

The structure guides you.

## Domain Layer

The domain layer contains the core business concepts. Entities. Value objects. Business rules. Everything that makes your gym booking system a gym booking system, not a generic CRUD application.

**Note:** "Domain" refers to the business problem (gym booking). "Domain layer" refers to the architectural layer (the `domain/` directory). "Domain model" refers to the code that represents the business (entities, value objects, services).

From Chapter 2, we had a `Member` class. That's a domain concept. Members exist whether we have a database or not. They're part of the business.

Here's `domain/member.py`:

```python
class Member:
    def __init__(self, name: str, email: str, pricing_strategy):
        self.name = name
        self.email = email
        self.pricing_strategy = pricing_strategy
        self.bookings = []
    
    def get_class_price(self) -> float:
        return self.pricing_strategy.calculate_price()
```

Notice what's missing: no database code, no HTTP, no external services. Just the concept of a member and their pricing.

The `FitnessClass` entity lives here too. Here's `domain/fitness_class.py`:

```python
class FitnessClass:
    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        self.bookings = []
    
    def is_full(self) -> bool:
        return len(self.bookings) >= self.capacity
    
    def can_accept_booking(self) -> bool:
        return not self.is_full()
```

Simple. Clear. Focused on the concept of a fitness class and its rules.

The pricing strategies from Chapter 2 also belong in the domain. They're business logic. Here's `domain/pricing.py`:

```python
from abc import ABC, abstractmethod

class PricingStrategy(ABC):
    @abstractmethod
    def calculate_price(self) -> float:
        pass


class PremiumPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 0


class BasicPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 10


class PayPerClassPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 15
```

This is your domain layer. Pure business logic. No technical dependencies. If you wanted to test these classes, you could do it with nothing but Python itself. No database required. No web framework. Just the rules.

## Application Layer

The application layer orchestrates domain objects to fulfil use cases. It's the conductor. The domain provides the instruments, and the application plays the music.

From Chapter 2, we had a `BookingService`. It coordinated bookings. That's application-level concern—not business logic, but executing a use case.

Here's `application/booking_service.py`:

```python
# application/booking_service.py
from domain.member import Member
from domain.fitness_class import FitnessClass

class BookingService:
    def __init__(self, notification_service):
        self.notification_service = notification_service
    
    def book_class(self, member: Member, fitness_class: FitnessClass):
        if not fitness_class.can_accept_booking():
            raise ValueError("Class is full")
        
        price = member.get_class_price()
        
        member.bookings.append(fitness_class)
        fitness_class.bookings.append(member)
        
        self.notification_service.send_booking_confirmation(member, fitness_class)
        
        return price
```

Notice the imports at the top. The application layer imports from the domain layer. This is the dependency flowing inward—application depends on domain, never the reverse. The domain has no idea the application layer exists.

The `BookingService` doesn't contain business rules. "Is the class full?" That's answered by `FitnessClass.can_accept_booking()`. "What's the price?" That's answered by `Member.get_class_price()`. The application just coordinates.

This is the key distinction. Domain answers business questions. Application executes use cases by asking the domain those questions.

## Infrastructure Layer

Infrastructure handles technical details. The domain said it needs a notification service. The application uses that service. But neither of them know how notifications actually work. That's infrastructure's job.

Here's `infrastructure/notifications.py`:

```python
# infrastructure/notifications.py
from abc import ABC, abstractmethod
import smtplib

class NotificationService(ABC):
    @abstractmethod
    def send_booking_confirmation(self, member, fitness_class):
        pass


class EmailNotificationService(NotificationService):
    def send_booking_confirmation(self, member, fitness_class):
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("gym@example.com", "password")
        message = f"Confirmed: {fitness_class.name}"
        server.sendmail("gym@example.com", member.email, message)
        server.quit()


class FakeNotificationService(NotificationService):
    def __init__(self):
        self.sent = []
    
    def send_booking_confirmation(self, member, fitness_class):
        self.sent.append((member, fitness_class))
```

This infrastructure code doesn't import from domain or application in this simple example. When infrastructure implements domain-defined interfaces (like repositories), it imports only those abstractions—never concrete domain entities or use cases. It provides implementations that other layers can use.

Notice the abstraction. `NotificationService` is defined here, but it could also be defined in the domain if the domain needs to express notification requirements. The key is that the concrete implementation—the SMTP details—lives in infrastructure.

If you swap email providers, you change this file. Nothing else. The domain doesn't care. The application doesn't care. They depend on the abstraction, not the implementation.

## Interface Layer

The interface layer presents your system to the outside world. In this example, we'll show a simple API, but it could just as easily be a CLI, a web UI, or a GraphQL endpoint.

Here's `interface/api.py`:

```python
# interface/api.py
from application.booking_service import BookingService
from infrastructure.notifications import EmailNotificationService
from domain.member import Member
from domain.fitness_class import FitnessClass
from domain.pricing import PremiumPricing, BasicPricing

# This would typically use a web framework like Flask or FastAPI
class BookingAPI:
    def __init__(self):
        notification_service = EmailNotificationService()
        self.booking_service = BookingService(notification_service)
    
    def handle_booking_request(self, member_data: dict, class_data: dict):
        # Convert external data into domain objects
        pricing = PremiumPricing() if member_data['type'] == 'premium' else BasicPricing()
        member = Member(
            name=member_data['name'],
            email=member_data['email'],
            pricing_strategy=pricing
        )
        
        fitness_class = FitnessClass(
            name=class_data['name'],
            capacity=class_data['capacity']
        )
        
        # Execute the use case
        try:
            price = self.booking_service.book_class(member, fitness_class)
            return {'status': 'success', 'price': price}
        except ValueError as e:
            return {'status': 'error', 'message': str(e)}
```

The interface layer imports from every other layer. It's the outermost layer, the orchestrator of everything. See how the imports show the dependency flow: interface depends on application, infrastructure, and domain. But domain imports nothing from the other layers. Application only imports domain. The dependencies flow inward.

The interface layer translates between the external world and your domain. HTTP requests come in. The interface converts them to domain objects. The use case does the work. The domain enforces the rules. The result goes back out as an HTTP response.

This layer knows about both the external world (HTTP, JSON, request formats) and the internal world (domain objects, use cases). It's the translator.

## What We Gained: Before and After

Let's compare what we had at the start of this chapter with what we have now.

**Before layers (mixed concerns):**

```python
# Everything tangled together
class Member:
    def save(self):
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO members ...", ...)
        conn.commit()
        conn.close()
```

**Problem:** Can't test `Member` without SQLite. Can't change database without rewriting domain class.

**After layers (separated):**

```python
# Domain: domain/member.py
class Member:
    def __init__(self, member_id: str, name: str, email: str, pricing_strategy):
        self.id = member_id
        self.name = name
        # Just business logic, no database

# Domain: domain/member_repository.py (interface/protocol)
from abc import ABC, abstractmethod
from typing import Optional
from domain.member import Member

class MemberRepository(ABC):
    """
    Repository interface: Defines what the domain needs for persistence.
    The domain defines the interface, infrastructure provides the implementation.
    """
    @abstractmethod
    def save(self, member: Member):
        pass
    
    @abstractmethod
    def find_by_id(self, member_id: str) -> Optional[Member]:
        pass

# Infrastructure: infrastructure/sqlite_member_repository.py
import sqlite3
from typing import Optional
from domain.member import Member
from domain.member_repository import MemberRepository

class SqliteMemberRepository(MemberRepository):
    """
    Concrete implementation: SQLite-specific persistence logic.
    Implements the interface defined by the domain.
    """
    def save(self, member: Member):
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO members (id, name, email) VALUES (?, ?, ?)",
            (member.id, member.name, member.email)
        )
        conn.commit()
        conn.close()
    
    def find_by_id(self, member_id: str) -> Optional[Member]:
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM members WHERE id = ?", (member_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # Note: In a real implementation, you'd also load the pricing strategy
            # from the database. We'll cover this in Chapter 7.
            return Member(member_id=row[0], name=row[1], email=row[2], pricing_strategy=None)
        return None
```

**Benefit:** Test `Member` with nothing but Python. Swap SQLite for PostgreSQL by changing one file.

**The Repository Pattern:** Instead of domain entities knowing how to save themselves (`member.save()`), we use a repository object that knows how to persist entities. The domain defines the repository interface (what operations are needed), and infrastructure provides concrete implementations (how those operations work). This separation is key to the dependency rule—domain doesn't depend on infrastructure. We'll explore repository interfaces (ports) fully in Chapter 7.

> **Note:** We introduce the repository concept here to show the separation of concerns, but the full implementation using ports and adapters comes in Chapter 7. For now, understand that repositories mediate between domain and data storage, with the interface defined in the domain and implementation in infrastructure.

---

**Before layers (testing nightmare):**

To test if premium members get free classes:
1. Set up SQLite database
2. Insert test member into database
3. Load member from database
4. Check pricing
5. Clean up database

**After layers (simple test):**

```python
def test_premium_pricing():
    member = Member("M001", "Alice", "alice@example.com", PremiumPricing())
    assert member.get_class_price() == 0
```

No database. No setup. No cleanup. Just business logic.

---

**Before layers (change is expensive):**

Switching from SQLite to PostgreSQL requires:
- Modifying `Member.save()`
- Modifying `Member.load()`
- Modifying `FitnessClass.save()`
- Modifying `FitnessClass.load()`
- Modifying `Booking.save()`
- Modifying `Booking.load()`
- Hope you didn't break business logic

**After layers (change is contained):**

Switching from SQLite to PostgreSQL requires:
- Replace `infrastructure/member_repository.py`
- Replace `infrastructure/class_repository.py`
- Replace `infrastructure/booking_repository.py`
- Domain layer untouched
- Application layer untouched
- Tests still pass

---

This is what separation buys you. Not theoretical purity. Practical flexibility. The ability to change infrastructure without touching business logic. The ability to test business rules without infrastructure. The ability to understand what the code does without drowning in how it does it.

## The Dependency Rule Visualised

The imports tell the story. Here's how dependencies flow through our layers:

```
┌─────────────────────────────────────────────┐
│ Interface Layer                             │
│ (interface/api.py)                          │
│                                             │
│ Imports: application, infrastructure,      │
│          domain                             │
└──────────────┬──────────────────────────────┘
               │
               ├─────────────────┐
               │                 │
               ▼                 ▼
┌──────────────────────┐  ┌─────────────────────┐
│ Application Layer    │  │ Infrastructure Layer│
│ (application/)       │  │ (infrastructure/)   │
│                      │  │                     │
│ Imports: domain      │  │ Imports: domain     │
│                      │  │ (abstractions only) │
└──────────┬───────────┘  └─────────────────────┘
           │
           │
           ▼
┌──────────────────────┐
│ Domain Layer         │
│ (domain/)            │
│                      │
│ Imports: (none)      │
└──────────────────────┘
```

Dependencies flow from outer layers (Interface, Infrastructure) toward inner layers (Application, Domain). Think of it like gravity—everything depends on the core, but the core depends on nothing external. The domain is the centre, completely isolated. Application depends on domain. Infrastructure may import domain abstractions (interfaces, protocols) to implement them, but never imports concrete domain entities or use cases. Interface depends on everything—it ties the system together.

When you look at a Python file, check the imports. If you see `domain/member.py` importing from `infrastructure/`, you've spotted a violation. Domain should never import from outer layers. Application should never import from interface. These boundaries are not suggestions—they're architectural constraints that keep your system flexible.

How do you enforce this? How do you stop a developer from accidentally adding the wrong import? We'll cover that in later chapters when we introduce tools and techniques for maintaining these boundaries. For now, the key is to understand why the boundaries exist and what they protect.

## Layer Violations and How to Spot Them

Understanding layers is one thing. Enforcing them is another. Violations creep in. You're in a hurry. You need to ship a feature. You take a shortcut. Before you know it, domain logic is calling database code directly.

Here's what a violation looks like:

```python
# DON'T DO THIS
# In domain/member.py

import sqlite3

class Member:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email
    
    def save_to_database(self):
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO members (name, email) VALUES (?, ?)',
            (self.name, self.email)
        )
        conn.commit()
        conn.close()
```

This violates the dependency rule. The domain layer is importing a database library. It's reaching up into infrastructure concerns. Now if you want to change databases, you have to modify your domain entities. The core business logic is coupled to technical detail.

The fix is to keep persistence out of the domain:

```python
# Domain layer - domain/member.py
class Member:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email


# Infrastructure layer - infrastructure/member_repository.py
import sqlite3

# Note: We introduce the repository concept here, but the full implementation 
# using ports and adapters comes in Chapter 7. For now, understand that 
# repositories mediate between domain and data storage.
class MemberRepository:
    def save(self, member):
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO members (name, email) VALUES (?, ?)',
            (member.name, member.email)
        )
        conn.commit()
        conn.close()
    
    def find_by_email(self, email: str):
        conn = sqlite3.connect('gym.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name, email FROM members WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Member(name=row[0], email=row[1])
        return None
```

Now the domain is pure. The infrastructure handles persistence. If you change databases, you modify `MemberRepository`. The `Member` class remains untouched.

Another common violation is mixing use case orchestration with domain logic:

```python
# DON'T DO THIS
# In domain/fitness_class.py

class FitnessClass:
    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        self.bookings = []
    
    def book_member(self, member, notification_service):
        if self.is_full():
            raise ValueError("Class is full")
        
        self.bookings.append(member)
        notification_service.send_booking_confirmation(member, self)
```

The `FitnessClass` is coordinating a use case. It's calling a notification service. That's application-layer responsibility. The domain should focus on rules, not orchestration.

The fix:

```python
# Domain layer - domain/fitness_class.py
class FitnessClass:
    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        self.bookings = []
    
    def is_full(self) -> bool:
        return len(self.bookings) >= self.capacity
    
    def add_booking(self, member):
        if self.is_full():
            raise ValueError("Class is full")
        self.bookings.append(member)


# Application layer - application/booking_service.py
class BookingService:
    def __init__(self, notification_service):
        self.notification_service = notification_service
    
    def book_class(self, member, fitness_class):
        fitness_class.add_booking(member)
        self.notification_service.send_booking_confirmation(member, fitness_class)
```

Now `FitnessClass` handles the business rule (capacity check) and the state change (adding the booking). `BookingService` handles the coordination (notifications). Each layer does its job.

## How TDD from Chapter 3 Led Us Here

Remember the TDD cycle from Chapter 3? Red-Green-Refactor. Write a failing test, make it pass, clean it up.

That process naturally pushes you toward layers. Here's how:

**Tests demand testable code.** When you write a test for booking logic, you don't want to set up a database. You don't want to mock an SMTP server. You want to test the business rule: "A class at capacity cannot accept more bookings."

```python
# What TDD makes you want to write
def test_full_class_rejects_booking():
    fitness_class = FitnessClass(capacity=1)
    fitness_class.add_booking(member_1)
    
    with pytest.raises(ClassFullException):
        fitness_class.add_booking(member_2)
```

To write this test, `FitnessClass` can't know about databases. It can't depend on external services. **The test demands separation.** Domain logic in one layer, infrastructure in another.

**Refactoring reveals boundaries.** In the Green phase, you make the test pass. Maybe you write this:

```python
def book_class(member_id, class_id):
    conn = sqlite3.connect('gym.db')
    cursor = conn.cursor()
    cursor.execute("SELECT capacity, bookings FROM classes WHERE id = ?", (class_id,))
    row = cursor.fetchone()
    
    if row[1] >= row[0]:
        raise ValueError("Class is full")
    
    cursor.execute("INSERT INTO bookings ...", (member_id, class_id))
    conn.commit()
```

The test passes. **Green.** But now you're in the Refactor phase. You look at this code and see:
- Business logic (capacity check) tangled with database code
- Can't test the capacity rule without a database
- Can't change databases without changing the business logic

TDD's refactor step is where you extract layers:

```python
# Domain layer - pure business logic
class FitnessClass:
    def add_booking(self, member):
        if self.is_full():
            raise ClassFullException("Class at capacity")
        self._bookings.append(member)

# Infrastructure layer - database details
class FitnessClassRepository:
    def save(self, fitness_class):
        # Database code here
```

The test stays green. The design improves. **This is TDD driving architecture.**

**Project Evolution:**
- In Chapter 1, we had a simple script with everything in one file
- In Chapter 2, we applied SOLID to create focused classes
- In Chapter 3, we learned TDD and wrote tests first
- Now in Chapter 4, those tests naturally pushed us toward layers
- The change was easy because tests gave us a safety net

This is the power of combining TDD with architectural thinking. TDD tells you when code needs structure. Layers give you that structure. Together, they create maintainable systems.

## What We Have Now

Let's take stock of our progress. We've refactored our gym booking system into layers:

**Our code now has:**
1. **Four distinct layers:**
   - Domain: `Member`, `FitnessClass`, `Booking` with business logic only
   - Application: `BookingService` coordinating use cases
   - Infrastructure: `MemberRepository`, `FitnessClassRepository`, `SqliteDatabase`
   - Interface: `cli.py` handling user interaction

2. **Clear separation of concerns:**
   - Business rules don't know about databases
   - Database code doesn't contain business logic
   - CLI doesn't implement booking logic

3. **Tests still work (and are better):**
   - Domain tests don't need databases
   - Can test business logic in isolation
   - Infrastructure can be swapped without breaking domain tests

4. **File structure:**
   ```
   gym_booking/
     ├── domain/
     │   ├── member.py
     │   ├── fitness_class.py
     │   └── booking.py
     ├── application/
     │   └── booking_service.py
     ├── infrastructure/
     │   ├── database.py
     │   └── repositories.py
     ├── interface/
     │   └── cli.py
     └── tests/
         ├── test_member.py
         ├── test_fitness_class.py
         ├── test_waitlist.py
         └── test_booking_service.py  # New
   ```

**What we gained:**
- Can change from SQLite to PostgreSQL by modifying only `infrastructure/`
- Can add REST API alongside CLI without touching domain
- Domain layer is testable without infrastructure
- Clear boundaries make finding code easier
- Each layer can evolve independently

**But we still have:**
- Simple domain objects (classes are still data + basic methods)
- Business logic spread between domain classes and application services
- No rich domain concepts like Value Objects or Aggregates
- Credits are just integers (no expiry, no validation)
- Booking rules are procedural (not object-oriented)

**Current state summary:**
We have structure (layers) but our domain is still somewhat "anemic"—classes hold data with simple methods, while services do most of the work. This works, but there's room for improvement.

## Transition to Chapter 5

We have layers. Our code is organized. Tests prove it works. But look closely at our domain classes:

```python
class Member:
    def __init__(self, member_id, name, email, membership_type, pricing_strategy):
        self.id = member_id
        self.name = name
        self.email = email
        self.credits = 20  # Just an integer
    
    def can_book(self):
        return self.credits > 0  # Simple check
    
    def deduct_credit(self):
        self.credits -= 1  # Just arithmetic
```

This `Member` class is mostly a data container. The interesting behavior—pricing, booking rules, validation—lives in services outside the domain.

But what if credits could expire? What if members have join dates that affect loyalty status? What if email addresses need special validation rules? Do all these rules belong in services, or could the domain objects themselves be richer?

In Chapter 5, we'll learn **Domain Modeling**. We'll discover Value Objects (like `Credits` that can expire), Entities (objects with identity and lifecycle), and Aggregates (clusters of objects treated as a unit). We'll move from an "anemic domain model" to a "rich domain model" where business rules live in the objects themselves, not in services.

**The challenge:** "Credits should expire after 30 days. We need to track member join dates and calculate loyalty status. Where does this logic belong?"

That's next.

## When to Relax the Rules

Layers are guides, not laws. There are times when strict adherence creates more problems than it solves.

**You don't need layers if:**

- You're building a proof-of-concept that might be thrown away
- Your entire application is < 500 lines and unlikely to grow
- You're creating a one-time data migration script
- The project has one developer and no plans to scale
- You're prototyping to learn the domain
- Requirements are completely uncertain

In these cases, a single file or simple script is perfectly fine. Adding layers creates overhead without benefit.

**You DO need layers when you see these signals:**

- Testing business logic requires setting up infrastructure (database, API, email server)
- Changing one technical detail (database, email provider) requires touching business logic
- You can't understand what the code does without understanding how it does it
- New developers struggle to find where to add features
- Changes break unrelated parts of the system
- The codebase has grown past ~500-1000 lines
- Multiple developers work on the code
- The system will be maintained long-term

These are pain signals. The code is asking for structure.

**Start simple. Add layers when pain appears.**

If you're building a prototype, don't start with four layers. Use two: domain and everything else. When the prototype becomes production code, refactor. When you feel the pain of mixed concerns, separate them. When testing becomes hard, introduce boundaries.

The key is intention. If you violate a layer boundary, do it knowingly. Understand the tradeoff. Document why. Don't drift into violations by accident.

We started this chapter with database code in `Member` because new requirements appeared. That was the signal. If those requirements never came, the simple script from Chapter 1 would have been fine. Architecture responds to reality, not theory.

## Summary

Layers create boundaries that protect your core logic from technical detail.

Domain holds business rules. Application coordinates use cases. Infrastructure handles technical concerns. Interface translates between the outside world and your system. Dependencies flow in one direction: outward layers depend on inward layers, never the reverse.

We took the scattered examples from Chapter 2—`Member`, `FitnessClass`, `PricingStrategy`, `NotificationService`—and organised them into a structure. Now you can see where each piece belongs. The code didn't change. The organisation did.

This structure scales. When you add a new feature, you immediately know where it goes. When you swap a database, you know which files to touch. When you test business logic, you don't need to spin up infrastructure.

The gym booking system now has a skeleton. The domain layer contains our core entities. The application layer is ready for use cases. Infrastructure and interface are placeholders waiting to be filled.

In the next chapter, we'll dive deeper into the domain layer. You'll learn how to model complex business logic using entities, value objects, and aggregates. How to capture rules that don't fit neatly into a single class. How to make your domain rich and expressive, not just a collection of data containers.

The layers give you structure. The domain gives you meaning. Let's build that next.
