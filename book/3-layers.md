# Chapter 3: Layers

SOLID principles help you write better classes. But classes don't exist in isolation. They need structure. Organisation. A place to live. 

This is where most developers hit a wall. You understand Single Responsibility. You know how to invert dependencies. But when you open your codebase, everything still feels chaotic. Files are scattered. Logic bleeds between concerns. You can't tell at a glance where business rules end and database code begins.

The problem isn't the classes. It's the lack of architecture around them.

Architecture isn't about making the code harder to navigate. It's about making it impossible to navigate wrong. When you structure your system in layers, you create boundaries that protect your core logic from the chaos of technical detail.

This chapter introduces a practical layered architecture. Four layers. Each with a clear purpose. Each solving a specific problem. Together, they give your SOLID principles room to breathe.

## Why Layers?

Software has different kinds of concerns. Business logic. Data persistence. User interfaces. External integrations. These concerns change for different reasons, at different rates, driven by different people.

Business rules change when the business changes. Database code changes when you migrate to a new database. UI code changes when design trends evolve or users request new features. Each of these should be isolated so that changing one doesn't force you to change the others.

Layers create that isolation.

A layered architecture organises code by the type of concern it addresses. Business logic lives in one layer. Technical infrastructure lives in another. The interface users interact with lives somewhere else. Each layer has a specific job, and the boundaries between them are enforced.

This isn't academic purity. It's practical necessity. When your business logic is tangled with database queries and API calls, you can't change any of them independently. Everything becomes one massive, interconnected mess. Layers break that coupling.

## The Four Layers

We'll work with four layers. Not three, not five. Four is enough to separate concerns without creating unnecessary complexity.

**Domain** contains your business logic. The rules. The entities. The concepts that make your system valuable. This is the heart of your application. It doesn't know about databases. It doesn't know about HTTP. It just knows the business.

**Application** coordinates domain objects to fulfil use cases. It orchestrates. It doesn't contain business rules—those belong in the domain—but it knows how to combine domain objects to achieve specific goals. "Book a class." "Cancel a booking." "Process a payment." These are use cases, and they live here.

**Infrastructure** handles technical details. Databases. File systems. Email servers. External APIs. Everything that touches the outside world. The domain defines what it needs, and infrastructure provides it. This layer is replaceable. If you swap MySQL for PostgreSQL, or SendGrid for Mailgun, only this layer changes.

**Interface** presents the system to the outside world. REST APIs. GraphQL endpoints. Command-line tools. Web interfaces. This is how users interact with your application. It translates external requests into application use cases and translates domain results back into responses.

Each layer depends only on the layers below it. Domain depends on nothing. Application depends on domain. Infrastructure depends on domain and application. Interface depends on everything. This is the dependency rule, and it's non-negotiable.

When you violate this rule, you create coupling that makes change expensive. When you honour it, you get flexibility.

## From Examples to Structure

In the previous chapter, we built isolated examples. A `Member` class here. A `BookingService` there. Pricing strategies scattered across the page. They demonstrated SOLID principles, but they weren't organised into a system.

Let's fix that.

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

From Chapter 2, we had a `BookingService`. It coordinated bookings. That's application-level concern—not business logic, but use case execution.

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

This infrastructure code doesn't import from domain or application in this simple example. When infrastructure implements domain-defined interfaces (like repositories), it imports only those abstractions—never concrete domain entities or application services. It provides implementations that other layers can use.

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
        
        # Use application service
        try:
            price = self.booking_service.book_class(member, fitness_class)
            return {'status': 'success', 'price': price}
        except ValueError as e:
            return {'status': 'error', 'message': str(e)}
```

The interface layer imports from every other layer. It's the outermost layer, the orchestrator of everything. See how the imports show the dependency flow: interface depends on application, infrastructure, and domain. But domain imports nothing from the other layers. Application only imports domain. The dependencies flow inward.

The interface layer translates between the external world and your domain. HTTP requests come in. The interface converts them to domain objects. The application service does the work. The domain enforces the rules. The result goes back out as an HTTP response.

This layer knows about both the external world (HTTP, JSON, request formats) and the internal world (domain objects, application services). It's the translator.

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

Dependencies flow in one direction: inward. The domain is the centre, completely isolated. Application depends on domain. Infrastructure may import domain abstractions (interfaces, protocols) to implement them, but never imports concrete domain entities or application services. Interface depends on everything—it ties the system together.

When you look at a Python file, check the imports. If you see `domain/member.py` importing from `infrastructure/`, you've spotted a violation. Domain should never import from outer layers. Application should never import from interface. These boundaries are not suggestions—they're architectural constraints that keep your system flexible.

You might wonder: how do we enforce this? How do we stop a developer from accidentally adding the wrong import? We'll cover that in later chapters when we introduce tools and techniques for maintaining these boundaries. For now, the key is to understand why the boundaries exist and what they protect.

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

Another common violation is mixing use case logic with domain logic:

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

## When to Relax the Rules

Layers are guides, not laws. There are times when strict adherence creates more problems than it solves.

If you're building a prototype, you don't need four layers. Two might be enough: domain and everything else. Get it working. Prove the concept. Refactor into layers when the complexity justifies it.

If you're working on a small, stable feature that's unlikely to change, you can skip the abstraction. Directly accessing a database from an application service isn't always wrong. It depends on whether you expect that access to change.

The key is intention. If you violate a layer boundary, do it knowingly. Understand the tradeoff. Document why. Don't drift into violations by accident.

Layers exist to manage complexity. If the complexity isn't there yet, you don't need the layers. Start simple. Add structure when pain appears.

## Summary

Layers create boundaries that protect your core logic from technical detail.

Domain holds business rules. Application coordinates use cases. Infrastructure handles technical concerns. Interface translates between the outside world and your system. Dependencies flow in one direction: outward layers depend on inward layers, never the reverse.

We took the scattered examples from Chapter 2—`Member`, `FitnessClass`, `PricingStrategy`, `NotificationService`—and organised them into a structure. Now you can see where each piece belongs. The code didn't change. The organisation did.

This structure scales. When you add a new feature, you immediately know where it goes. When you swap a database, you know which files to touch. When you test business logic, you don't need to spin up infrastructure.

The gym booking system now has a skeleton. The domain layer contains our core entities. The application layer is ready for use cases. Infrastructure and interface are placeholders waiting to be filled.

In the next chapters (4 and 5), we'll dive deeper into the domain layer. You'll learn how to model complex business logic using entities, value objects, and aggregates. How to capture rules that don't fit neatly into a single class. How to make your domain rich and expressive, not just a collection of data containers.

The layers give you structure. The domain gives you meaning. Let's build that next.
