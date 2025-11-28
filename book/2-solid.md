# Chapter 2: SOLID

Let's build something.

Throughout this book we'll work with a gym class booking system. A gym offers fitness classes: yoga, spin, HIIT. Members book spots in these classes. Some members have premium subscriptions, others pay per class. Classes have capacity limits. Bookings can be made, cancelled, confirmed.

It's a domain most of us understand intuitively. Simple enough to grasp quickly, complex enough to reveal real architectural challenges.

We'll start here, in this chapter, with isolated examples that demonstrate how to think about writing maintainable code. The full system comes later. For now, we're establishing a mindset.

SOLID is an acronym. Five principles that guide how you write classes and structure code. Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. They've been around for decades, and they matter because they help you write code that's easier to change.

These aren't rules. They're ideas that emerged from watching what makes code rigid and what makes it flexible. Understanding them gives you a vocabulary for recognising problems and reasoning about solutions.

Let's work through each one. Not as abstract theory, but as practical decisions you'll face every time you write a class.

## Single Responsibility Principle

**A class should have one reason to change.**

Simple to state, harder to recognise in practice. The confusion comes from the word "responsibility." It sounds like "a class should do one thing," which leads people to over-fragment their code into tiny classes that do almost nothing. That's not what this means.

A responsibility is a reason for change. More specifically, it's a stakeholder or concern that might request a change. If two different people, for two different reasons, might ask you to modify the same class, that class has multiple responsibilities.

Here's what violation looks like:

```python
class Member:
    def __init__(self, name: str, email: str, membership_type: str):
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.bookings = []
    
    def book_class(self, fitness_class):
        if len(fitness_class.bookings) >= fitness_class.capacity:
            raise ValueError("Class is full")
        
        if self.membership_type == "premium":
            price = 0
        elif self.membership_type == "basic":
            price = 10
        else:
            price = 15
        
        self.bookings.append(fitness_class)
        fitness_class.bookings.append(self)
        
        # Send confirmation email
        import smtplib
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("gym@example.com", "password")
        message = f"Confirmed: {fitness_class.name}"
        server.sendmail("gym@example.com", self.email, message)
        server.quit()
        
        return price
```

This class is doing too much. It's handling member data, booking logic, pricing rules, and email notifications. Four different concerns, four different reasons to change.

If the pricing model changes, you modify this class. If the email provider changes, you modify this class. If the booking rules change, you modify this class. If you need to store member data differently, you modify this class.

Each change risks breaking something unrelated. Testing becomes a nightmare because you can't test booking logic without also dealing with email infrastructure.

Here's the same functionality, separated:

```python
class Member:
    def __init__(self, name: str, email: str, membership_type: str):
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.bookings = []


class PricingService:
    def calculate_price(self, member: Member) -> float:
        if member.membership_type == "premium":
            return 0
        elif member.membership_type == "basic":
            return 10
        else:
            return 15


class BookingService:
    def __init__(self, pricing: PricingService, notifications):
        self.pricing = pricing
        self.notifications = notifications
    
    def book_class(self, member: Member, fitness_class):
        if len(fitness_class.bookings) >= fitness_class.capacity:
            raise ValueError("Class is full")
        
        price = self.pricing.calculate_price(member)
        
        member.bookings.append(fitness_class)
        fitness_class.bookings.append(member)
        
        self.notifications.send_confirmation(member, fitness_class)
        
        return price
```

Now `Member` represents member data. That's it. One responsibility. If you need to add a phone number or track membership duration, you change `Member`. Nothing else.

Pricing lives in `PricingService`. If pricing rules change, that's the only place you look. Booking coordination lives in `BookingService`. Notifications live elsewhere.

Each class has one axis of change. One reason to open the file. Testing becomes simpler because you can test pricing logic without spinning up email servers.

This is what maintainability looks like. Not perfection, not academic purity. Just clear boundaries that make change safer.

## Open/Closed Principle

**Software entities should be open for extension, closed for modification.**

This principle feels paradoxical at first. How can something be both open and closed? The key is in understanding what "extension" means in practice.

The goal is to add new behaviour without changing existing code. When new requirements arrive, you want to extend the system by adding new classes or modules, not by modifying working code. Modifying working code risks breaking it. Adding new code keeps the old code stable.

Let's revisit pricing. The example above hardcodes membership types in an if-else chain. Every time a new membership type appears, you modify `PricingService`. That's fine for three types. But what happens when you have ten? Twenty? What if different gyms have different pricing models?

Here's the violation:

```python
class PricingService:
    def calculate_price(self, member: Member) -> float:
        if member.membership_type == "premium":
            return 0
        elif member.membership_type == "basic":
            return 10
        elif member.membership_type == "pay_per_class":
            return 15
        elif member.membership_type == "off_peak":
            return 7
        elif member.membership_type == "student":
            return 5
        # This keeps growing...
```

Every new membership type means modifying this method. The method grows. The complexity increases. You're changing working code to add new features.

Here's the same system, designed for extension:

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


class Member:
    def __init__(self, name: str, email: str, pricing: PricingStrategy):
        self.name = name
        self.email = email
        self.pricing = pricing
    
    def get_class_price(self) -> float:
        return self.pricing.calculate_price()
```

Now when a new membership type appears, you don't modify anything. You add a new class:

```python
class StudentPricing(PricingStrategy):
    def calculate_price(self) -> float:
        return 5
```

The existing code remains untouched. `PremiumPricing` still works. `BasicPricing` still works. You extended the system without modifying it.

This is the Open/Closed Principle in action. The abstraction (`PricingStrategy`) is closed to modification. The implementations are the extension points.

Does this mean you should abstract everything? No. Premature abstraction is just as harmful as premature optimisation. Start with the if-else chain. When you see the pattern emerging, when a third or fourth case appears, that's when you refactor toward extension points.

The principle guides you toward flexibility where it matters.

## Liskov Substitution Principle

**Objects of a subclass should be replaceable with objects of the superclass without breaking the program.**

This is the most technically worded of the SOLID principles, but the idea is straightforward: if you have a base class and derived classes, you should be able to use any derived class wherever the base class is expected. The program shouldn't break. The behaviour should remain sensible.

Violations happen when subclasses change the fundamental contract of their parent class. When they require special handling. When using them in place of the parent causes errors or unexpected behaviour.

Here's a violation using membership types:

```python
class Membership:
    def __init__(self, member_name: str):
        self.member_name = member_name
        self.active = True
    
    def book_class(self, fitness_class):
        if not self.active:
            raise ValueError("Membership is inactive")
        # Book the class
        fitness_class.bookings.append(self.member_name)


class GuestPass(Membership):
    def __init__(self, member_name: str, classes_remaining: int):
        super().__init__(member_name)
        self.classes_remaining = classes_remaining
    
    def book_class(self, fitness_class):
        if self.classes_remaining <= 0:
            raise ValueError("No classes remaining on guest pass")
        
        if not self.active:
            raise ValueError("Membership is inactive")
        
        fitness_class.bookings.append(self.member_name)
        self.classes_remaining -= 1
```

At first glance this looks reasonable. `GuestPass` is a kind of `Membership`. It extends the booking behaviour to track remaining classes.

But there's a problem. If you write code that expects a `Membership`, and someone passes in a `GuestPass`, you get different errors. A regular membership fails with "Membership is inactive." A guest pass can fail with "No classes remaining on guest pass."

Code that handles errors from `Membership` doesn't know about the guest pass error. The substitution isn't clean. You can't reliably use `GuestPass` wherever you use `Membership` without special case handling.

You might be thinking: why does this matter? Can't we just catch different exceptions? We could. But now imagine you have ten membership types, each with its own failure conditions. Your error handling sprawls across the codebase. Every place that books classes needs to know about every membership type. That's coupling. That's fragility.

Here's a better approach that unifies the contract:

```python
class Membership:
    def __init__(self, member_name: str):
        self.member_name = member_name
    
    def can_book(self) -> bool:
        return True
    
    def book_class(self, fitness_class):
        if not self.can_book():
            raise ValueError("Cannot book class")
        fitness_class.bookings.append(self.member_name)


class RegularMembership(Membership):
    def __init__(self, member_name: str, active: bool):
        super().__init__(member_name)
        self.active = active
    
    def can_book(self) -> bool:
        return self.active


class GuestPass(Membership):
    def __init__(self, member_name: str, classes_remaining: int):
        super().__init__(member_name)
        self.classes_remaining = classes_remaining
    
    def can_book(self) -> bool:
        return self.classes_remaining > 0
    
    def book_class(self, fitness_class):
        if not self.can_book():
            raise ValueError("Cannot book class")
        fitness_class.bookings.append(self.member_name)
        self.classes_remaining -= 1
```

Now both subclasses follow the same contract. They both implement `can_book()`. They both raise the same error message when booking isn't possible. The error handling is consistent.

You can write code like this:

```python
def process_booking(membership: Membership, fitness_class):
    try:
        membership.book_class(fitness_class)
        print("Booking successful")
    except ValueError as e:
        print(f"Booking failed: {e}")
```

It works the same whether you pass `RegularMembership` or `GuestPass`. No special cases. No surprises. That's Liskov Substitution.

Yes, we added a `can_book()` method. Yes, that's more code. But look at what we gained: you can now add ten different membership types without changing any code that processes bookings. Each type encapsulates its own booking rules. The complexity is contained, not scattered.

The principle pushes you toward consistent contracts. When your subclasses honour the same interface and expectations as their parent, your code becomes more reliable. Polymorphism works the way it's supposed to.

⸻

## Interface Segregation Principle

**Clients should not be forced to depend on interfaces they don't use.**

This principle is about keeping interfaces focused. When you define an interface or base class, don't make it a dumping ground for every possible operation. Split it into smaller, more specific interfaces so that classes only depend on what they actually need.

Large, monolithic interfaces force implementing classes to provide implementations for methods they don't care about. They create false dependencies and make the code harder to understand and change.

Here's a violation:

```python
from abc import ABC, abstractmethod

class MemberOperations(ABC):
    @abstractmethod
    def book_class(self, fitness_class):
        pass
    
    @abstractmethod
    def cancel_booking(self, fitness_class):
        pass
    
    @abstractmethod
    def make_payment(self, amount: float):
        pass
    
    @abstractmethod
    def update_payment_method(self, payment_method: str):
        pass
    
    @abstractmethod
    def get_payment_history(self):
        pass
```

This interface defines everything a member might do. Booking, payments, payment history. If you want to implement a class that only handles bookings, you still have to implement all five methods. Even the payment methods you don't care about.

```python
class BookingHandler(MemberOperations):
    def book_class(self, fitness_class):
        # Actual implementation
        pass
    
    def cancel_booking(self, fitness_class):
        # Actual implementation
        pass
    
    def make_payment(self, amount: float):
        raise NotImplementedError("This class doesn't handle payments")
    
    def update_payment_method(self, payment_method: str):
        raise NotImplementedError("This class doesn't handle payments")
    
    def get_payment_history(self):
        raise NotImplementedError("This class doesn't handle payments")
```

You end up with methods that exist only to throw errors. That's a sign the interface is too broad.

Here's the corrected version:

```python
from abc import ABC, abstractmethod

class Bookable(ABC):
    @abstractmethod
    def book_class(self, fitness_class):
        pass
    
    @abstractmethod
    def cancel_booking(self, fitness_class):
        pass


class Payable(ABC):
    @abstractmethod
    def make_payment(self, amount: float):
        pass
    
    @abstractmethod
    def update_payment_method(self, payment_method: str):
        pass
    
    @abstractmethod
    def get_payment_history(self):
        pass
```

Now you have two focused interfaces. A class that only handles bookings can implement `Bookable`. A class that handles payments can implement `Payable`. A class that does both can implement both.

```python
class BookingService(Bookable):
    def book_class(self, fitness_class):
        # Implementation
        pass
    
    def cancel_booking(self, fitness_class):
        # Implementation
        pass


class PaymentService(Payable):
    def make_payment(self, amount: float):
        # Implementation
        pass
    
    def update_payment_method(self, payment_method: str):
        # Implementation
        pass
    
    def get_payment_history(self):
        # Implementation
        pass
```

Each class depends only on the interface it needs. No forced methods. No fake implementations. The dependencies are honest.

Small interfaces are easier to implement, easier to test, and easier to understand. They keep your code focused on what actually matters.

## Dependency Inversion Principle

**High-level modules should not depend on low-level modules. Both should depend on abstractions.**

This is the principle that shifts how you think about dependencies. Most code naturally flows from high-level business logic down to low-level technical details. A booking service calls a database. A notification system calls an email API. The high-level code depends directly on the low-level implementation.

The problem is that your business logic becomes coupled to technical detail. If you swap databases, you rewrite the business logic. If you change email providers, you modify the notification system. The core logic, which should be stable, becomes tangled with infrastructure, which changes frequently.

Dependency Inversion flips this. Instead of high-level code depending on low-level code, both depend on abstractions. The business logic defines what it needs, and the infrastructure implements it.

Here's the violation:

```python
import smtplib

class BookingService:
    def book_class(self, member, fitness_class):
        # Booking logic
        fitness_class.bookings.append(member)
        
        # Send email notification
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("gym@example.com", "password")
        message = f"Confirmed: {fitness_class.name}"
        server.sendmail("gym@example.com", member.email, message)
        server.quit()
```

The booking service knows about SMTP. It knows about Gmail. It knows about email infrastructure. If you want to switch to SendGrid, or add SMS notifications, you modify `BookingService`. The core business logic is coupled to the email implementation.

Testing is painful. You can't test booking logic without also testing email sending, which means you need a real SMTP server or elaborate mocks.

Here's the corrected version:

```python
from abc import ABC, abstractmethod

class NotificationService(ABC):
    @abstractmethod
    def send_booking_confirmation(self, member, fitness_class):
        pass


class BookingService:
    def __init__(self, notifications: NotificationService):
        self.notifications = notifications
    
    def book_class(self, member, fitness_class):
        # Booking logic
        fitness_class.bookings.append(member)
        
        # Notify member
        self.notifications.send_booking_confirmation(member, fitness_class)
```

Now `BookingService` depends on an abstraction: `NotificationService`. It doesn't know about email. It doesn't know about SMTP. It just knows that notifications can be sent.

The implementation details live in a separate class:

```python
import smtplib

class EmailNotificationService(NotificationService):
    def send_booking_confirmation(self, member, fitness_class):
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login("gym@example.com", "password")
        message = f"Confirmed: {fitness_class.name}"
        server.sendmail("gym@example.com", member.email, message)
        server.quit()
```

If you want SMS notifications, you add a new implementation:

```python
class SMSNotificationService(NotificationService):
    def send_booking_confirmation(self, member, fitness_class):
        # Send SMS via Twilio or similar
        pass
```

The booking service remains unchanged. The business logic is isolated from the infrastructure.

Testing becomes trivial. You can test booking logic with a fake notification service:

```python
class FakeNotificationService(NotificationService):
    def __init__(self):
        self.sent = []
    
    def send_booking_confirmation(self, member, fitness_class):
        self.sent.append((member, fitness_class))


# In tests
notifications = FakeNotificationService()
booking_service = BookingService(notifications)
booking_service.book_class(member, fitness_class)

assert len(notifications.sent) == 1
```

No SMTP servers. No network calls. Just pure logic.

This is Dependency Inversion. The high-level policy (booking) defines what it needs (notifications). The low-level detail (email) implements it. Both depend on the abstraction.

## When SOLID Doesn't Matter

Let's be honest about something important: you don't need SOLID everywhere.

These principles exist to manage complexity and enable change. But not all code is complex. Not all code needs to change. Sometimes you're writing a script that runs once and gets deleted. Sometimes you're prototyping an idea to see if it's worth building. Sometimes you know with certainty that a piece of code will never grow beyond its current form.

In those moments, SOLID is overhead. Pure overhead.

A script that scrapes a website and dumps CSV data? One file. One class if you're feeling formal. Maybe just functions. No abstractions. No interfaces. No dependency injection. You're not building a system. You're solving a problem and moving on.

A prototype to test if an API integration works? Hardcode the credentials. Put everything in `main()`. Get it working. If the prototype succeeds and becomes a real feature, *then* you refactor toward SOLID. Not before.

The key is recognising the difference between code that's disposable and code that's foundational. Code that'll be read, modified, extended, and maintained over months or years—that's when SOLID thinking pays off. Code that exists to answer a quick question or automate a one-time task—that's when SOLID is waste.

This isn't permission to write sloppy code everywhere. It's permission to match your effort to the problem's scope. A throwaway script doesn't need the architecture of a banking system. Don't pretend it does.

Start simple. Add structure when complexity forces you to. That's not laziness. That's pragmatism.

## Summary

These five principles work together. They're not separate rules you apply in isolation. They're different angles on the same idea: write code that's easy to change.

Single Responsibility gives you clear boundaries. Open/Closed lets you extend without breaking. Liskov Substitution keeps your polymorphism reliable. Interface Segregation keeps your dependencies focused. Dependency Inversion protects your core logic from technical detail.

You won't apply all of them all the time. Sometimes a simple if-else chain is exactly what you need. Sometimes a single class that does multiple things is the pragmatic choice for a feature that's unlikely to change. These principles are tools, not laws.

Use them when complexity appears. When change becomes painful. When you find yourself modifying the same class for different reasons. That's when SOLID thinking helps.

We've worked with isolated examples here. Simple classes. Focused demonstrations. The gym booking system exists in fragments: a `Member` class here, a `BookingService` there, pricing strategies scattered across examples.

In the next chapter, we'll bring structure to this. We'll talk about layers. How to organise a codebase so that these principles have room to breathe. How to separate concerns at a system level, not just a class level.

For now, you've learned to think about responsibilities, extension points, substitution, focused interfaces, and inverted dependencies. That's the foundation. Everything else builds on this.
