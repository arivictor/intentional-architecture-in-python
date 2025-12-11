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

This is the signal. The code is asking for better structure. But before we jump into design principles, we need to understand the journey from where we are to where we're going.

## From Dictionaries to Classes: Understanding the Progression

In Chapter 1, we used dictionaries to represent our domain concepts. Now we're about to introduce classes. But this isn't a single leap—it's a progression. Understanding each step helps you recognize where you are and what comes next.

### The Three Stages of Domain Model Evolution

**Stage 1: Dictionaries (Procedural)**
- Data in dictionaries: `{'id': 'M001', 'name': 'Alice', 'credits': 20}`
- Functions manipulate the data: `book_class(member_id, class_id)`
- No type safety, no IDE autocomplete
- Easy to make typos: `member['creditz']` silently creates a new key

**Stage 2: Anemic Classes (Data Containers)**
- Data in classes with just `__init__`: Simple data holders
- Still functions to manipulate them
- Type safety and IDE support improve
- But behavior is still external to the data

**Stage 3: Rich Classes (Object-Oriented)**
- Data AND behavior together in classes
- Methods encapsulate business logic
- Objects protect their own invariants
- True object-oriented design

Let's walk through this progression with our `Member` example.

### Stage 1: Where We Started (Dictionaries)

From Chapter 1, we had this:

```python
members = {}

def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    members[member_id] = {
        'id': member_id,
        'name': name,
        'email': email,
        'membership_type': membership_type,
        'credits': 20 if membership_type == 'premium' else 10
    }

def book_class(member_id, class_id):
    """Book a member into a class."""
    member = members[member_id]
    
    # Business rule: check credits
    if member['credits'] <= 0:
        print("✗ Insufficient credits")
        return
    
    # Deduct credit
    member['credits'] -= 1
```

**Problems with this approach:**
- **No type safety:** `member['creditz']` creates a new key instead of erroring
- **No IDE support:** Your editor doesn't know what fields exist
- **No validation:** Can create `{'credits': -100}` without complaint
- **Scattered behavior:** Credit deduction logic is in `book_class()`, not with the member data
- **Easy to bypass rules:** Code elsewhere can set `member['credits'] = 999` directly

This works for prototypes, but breaks down as complexity grows.

### Stage 2: Anemic Classes (Data Containers)

The first step is to replace dictionaries with classes that hold data:

```python
class Member:
    """A gym member - just data for now."""
    
    def __init__(self, member_id: str, name: str, email: str, membership_type: str):
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.credits = 20 if membership_type == 'premium' else 10
```

Now instead of dictionaries, we create `Member` objects:

```python
# Create members using the class
def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    member = Member(member_id, name, email, membership_type)
    members[member_id] = member  # Store Member object, not dict
    print(f"✓ Created member: {name} ({membership_type})")

# Access member data through attributes
def book_class(member_id, class_id):
    """Book a member into a class."""
    member = members[member_id]  # Now a Member object
    
    if member.credits <= 0:  # Attribute access, not dict lookup
        print("✗ Insufficient credits")
        return
    
    member.credits -= 1  # Still manipulating from outside
```

**What improved:**
- ✅ **Type safety:** `member.creditz` is an error, not a silent bug
- ✅ **IDE support:** Your editor autocompletes `.name`, `.email`, `.credits`
- ✅ **Clear structure:** Every member has the same fields
- ✅ **Easier to read:** `member.credits` is clearer than `member['credits']`

**What's still a problem:**
- ❌ **No validation:** Can still create invalid members
- ❌ **Behavior is external:** Credit deduction logic lives in functions, not in `Member`
- ❌ **No encapsulation:** Can directly set `member.credits = -100` from anywhere
- ❌ **Still procedural:** We're just using classes as fancy dictionaries

This is called an **anemic domain model**. The class has data but no behavior. It's anemic because it's weak—it can't protect itself or do anything useful. All the logic lives in functions outside the class.

**Anemic models aren't wrong—they're an improvement over dictionaries.** They give you type safety and better tooling. For simple CRUD applications, they might be enough. But when business logic grows, you need more.

### Stage 3: Rich Classes (Object-Oriented)

Now we add behavior to the class. Instead of functions manipulating member data from outside, the member manages itself:

```python
class Member:
    """A gym member with validation and behavior."""
    
    def __init__(self, member_id: str, name: str, email: str, membership_type: str):
        # Validation in the constructor
        if '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        if membership_type not in ['basic', 'premium']:
            raise ValueError(f"Invalid membership type: {membership_type}")
        
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.credits = 20 if membership_type == 'premium' else 10
    
    def can_book(self) -> bool:
        """Check if member has enough credits to book a class."""
        return self.credits > 0
    
    def deduct_credit(self):
        """Deduct one credit, with validation."""
        if self.credits <= 0:
            raise ValueError("No credits remaining")
        self.credits -= 1
    
    def add_credit(self):
        """Add one credit (e.g., for cancellations)."""
        self.credits += 1
```

Now the business logic lives IN the class:

```python
def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    try:
        member = Member(member_id, name, email, membership_type)
        members[member_id] = member
        print(f"✓ Created member: {name} ({membership_type})")
    except ValueError as e:
        print(f"✗ {e}")

def book_class(member_id, class_id):
    """Book a member into a class."""
    member = members[member_id]
    
    # Ask the member if it can book (behavior in the class)
    if not member.can_book():
        print("✗ Insufficient credits")
        return
    
    # Tell the member to deduct a credit (behavior in the class)
    member.deduct_credit()
    
    # Rest of booking logic...
```

**What improved:**
- ✅ **Validation on creation:** Can't create invalid members
- ✅ **Behavior with data:** `deduct_credit()` lives where it belongs
- ✅ **Self-protection:** Member enforces its own rules
- ✅ **Encapsulation:** Credit logic is in one place, not scattered
- ✅ **Expressive code:** `member.can_book()` reads like English

This is a **rich domain model**. The class understands what a member is and what a member can do. It has both data and behavior. It enforces its own rules. It's a true object.

### Anemic vs Rich: A Quick Comparison

| Aspect | Dictionaries | Anemic Classes | Rich Classes |
|--------|-------------|----------------|--------------|
| **Type safety** | ❌ No | ✅ Yes | ✅ Yes |
| **IDE support** | ❌ No | ✅ Yes | ✅ Yes |
| **Validation** | ❌ No | ❌ No | ✅ Yes |
| **Behavior location** | In functions | In functions | In class methods |
| **Encapsulation** | ❌ None | ❌ Weak | ✅ Strong |
| **Business logic** | Scattered | Scattered | Centralized |
| **When to use** | Quick prototypes | Simple CRUD | Complex business rules |

### Why This Progression Matters

You don't always need to go all the way to rich classes. The right choice depends on your needs:

**Stay with dictionaries when:**
- You're prototyping and want maximum flexibility
- The data structure is temporary or ad-hoc
- You're parsing JSON/YAML and just passing it along
- The "object" is really just a data bag with no behavior

**Use anemic classes when:**
- You want type safety and IDE support
- You're building a simple CRUD application
- Business rules are minimal (just basic validation)
- The class is truly just a data transfer object

**Use rich classes when:**
- Business logic is complex and growing
- Rules need to be enforced consistently
- You want the code to read like the business domain
- You need encapsulation to prevent invalid states
- You're building a system that will live for years

For our gym booking system, we're moving to rich classes because we have real business rules: credit management, capacity checks, booking validation. These rules deserve to live in the domain objects themselves.

### The Member Class: Progressive Enrichment

Let's see the complete progression of our `Member` class through all three stages:

**Stage 1: Dictionary (from Chapter 1)**
```python
member = {
    'id': 'M001',
    'name': 'Alice',
    'email': 'alice@example.com',
    'membership_type': 'premium',
    'credits': 20
}

# Functions operate on the data
def deduct_credit(member):
    if member['credits'] > 0:
        member['credits'] -= 1
```

**Stage 2: Anemic Class (data container)**
```python
class Member:
    def __init__(self, member_id: str, name: str, email: str, membership_type: str):
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.credits = 20 if membership_type == 'premium' else 10

# Functions still operate on the data
def deduct_credit(member: Member):
    if member.credits > 0:
        member.credits -= 1
```

**Stage 3: Rich Class (data + behavior)**
```python
class Member:
    def __init__(self, member_id: str, name: str, email: str, membership_type: str):
        # Validation on construction
        if '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        if membership_type not in ['basic', 'premium']:
            raise ValueError(f"Invalid membership type: {membership_type}")
        
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.credits = 20 if membership_type == 'premium' else 10
    
    def can_book(self) -> bool:
        """Business rule: members need credits to book."""
        return self.credits > 0
    
    def deduct_credit(self):
        """Business logic: controlled credit deduction."""
        if not self.can_book():
            raise ValueError("No credits remaining")
        self.credits -= 1

# No external function needed - the class does it
member = Member("M001", "Alice", "alice@example.com", "premium")
member.deduct_credit()  # The object manages itself
```

Each stage builds on the previous. Dictionaries → anemic classes adds type safety. Anemic → rich adds business logic and protection.

### Moving Forward

Now that we understand this progression, the rest of this chapter will show you how SOLID principles guide you toward rich, well-designed classes. But remember:

- **SOLID applies to classes**, not dictionaries
- **Rich models benefit most** from SOLID
- **Anemic models are a stepping stone**, not a destination

The principles we're about to learn (Single Responsibility, Open/Closed, etc.) make the most sense in the context of rich domain models. They help you organize behavior, not just data.

Let's dive into SOLID.

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

Now that we understand the progression from dictionaries to anemic to rich models, we can apply SOLID principles to build our classes properly. SRP helps us decide what belongs in each class.

### Building a Rich `Member` Class with SRP

We've already seen three versions of `Member`:
1. Dictionary (Chapter 1)
2. Anemic class (earlier in this chapter)  
3. Rich class with validation and behavior (earlier in this chapter)

Now let's build it properly with Single Responsibility Principle in mind. The `Member` class should have ONE responsibility: **represent what a gym member is and what they can do**.

This means `Member` handles:
- Member data (name, email, credits, membership type)
- Member validation (email format, membership type validity)
- Member behavior (booking, credit management)

This means `Member` does NOT handle:
- Duplicate checking (that's a storage concern)
- Creating new member IDs (that's ID generation)
- Saving to database (that's persistence)
- Sending welcome emails (that's notifications)

Let's create a proper rich `Member` class:

```python
class Member:
    """Represents a gym member with validation and behavior (rich model)."""
    
    def __init__(self, member_id, name, email, membership_type):
        # Validation happens in the constructor
        if '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email address: {email}")
        
        if membership_type not in ['basic', 'premium']:
            raise ValueError(f"Invalid membership type: {membership_type}")
        
        # Member data
        self.id = member_id
        self.name = name
        self.email = email
        self.membership_type = membership_type
        self.credits = 20 if membership_type == 'premium' else 10
    
    def can_book(self) -> bool:
        """Check if member has enough credits to book a class."""
        return self.credits > 0
    
    def deduct_credit(self):
        """Deduct one credit when booking a class."""
        if not self.can_book():
            raise ValueError(f"Member {self.name} has no credits remaining")
        self.credits -= 1
    
    def add_credit(self):
        """Add one credit (e.g., when cancelling a booking)."""
        self.credits += 1
    
    def __repr__(self):
        return f"Member({self.name}, {self.email}, {self.membership_type}, {self.credits} credits)"
```

**This is a rich model because:**
- ✅ Validates data on construction (`__init__` checks email and membership type)
- ✅ Encapsulates behavior (`can_book()`, `deduct_credit()`, `add_credit()`)
- ✅ Protects invariants (can't deduct credits if none available)
- ✅ Expresses business concepts (members have credits, can book classes)

Now our `create_member()` function becomes simpler:

```python
def create_member(member_id, name, email, membership_type):
    """Register a new member."""
    # Check for duplicates (storage concern, not Member's job)
    for existing_member in members.values():
        if existing_member.email == email:
            print("✗ Email already registered")
            return
    
    try:
        # Member validates itself on construction
        member = Member(member_id, name, email, membership_type)
        members[member_id] = member  # Store Member object, not dict
        print(f"✓ Created member: {name} ({membership_type})")
    except ValueError as e:
        print(f"✗ {e}")
```

**What changed from the anemic version?**
- `Member` now has **behavior** (`can_book()`, `deduct_credit()`, `add_credit()`)
- The class is **self-protecting** (can't deduct when credits are zero)
- Business logic **lives in the class**, not scattered in functions
- `create_member()` is **simpler**—it just handles duplicate checks and storage

**Single Responsibility achieved:**
- `Member` class: Represents member data and behavior
- `create_member()` function: Handles duplicate checking and storage
- If member business rules change → modify `Member`
- If storage logic changes → modify `create_member()`

This is SRP in action: one class, one responsibility.

### Building a Rich `FitnessClass` with SRP

Let's do the same for fitness classes—create a rich model with behavior:

```python
class FitnessClass:
    """Represents a fitness class with validation and behavior (rich model)."""
    
    def __init__(self, class_id, name, capacity, day, start_time):
        # Validation
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        if not name or not name.strip():
            raise ValueError("Class name cannot be empty")
        
        # Class data
        self.id = class_id
        self.name = name
        self.capacity = capacity
        self.day = day
        self.start_time = start_time
        self.bookings = []  # List of member IDs
    
    def spots_available(self) -> int:
        """Calculate available spots."""
        return self.capacity - len(self.bookings)
    
    def is_full(self) -> bool:
        """Check if class is full."""
        return self.spots_available() <= 0
    
    def can_accept_booking(self) -> bool:
        """Check if class can accept new bookings."""
        return not self.is_full()
    
    def add_booking(self, member_id: str):
        """Add a member to this class."""
        if self.is_full():
            raise ValueError(f"Class {self.name} is at capacity")
        
        if member_id in self.bookings:
            raise ValueError(f"Member already booked in this class")
        
        self.bookings.append(member_id)
    
    def remove_booking(self, member_id: str):
        """Remove a member from this class."""
        if member_id not in self.bookings:
            raise ValueError(f"Member not found in class {self.name}")
        
        self.bookings.remove(member_id)
    
    def __repr__(self):
        return f"FitnessClass({self.name}, {self.day} {self.start_time}, {len(self.bookings)}/{self.capacity})"
```

**This is a rich model because:**
- ✅ Validates data on construction (capacity, name)
- ✅ Encapsulates behavior (`add_booking()`, `remove_booking()`, `can_accept_booking()`)
- ✅ Protects invariants (can't exceed capacity, can't double-book)
- ✅ Expresses business concepts (classes have capacity, accept bookings)

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

Now `book_class()` uses our **rich models**:

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
    
    # Ask the objects about their state (using their methods)
    if not member.can_book():
        print("✗ Insufficient credits")
        return
    
    # Business rules checked by the domain objects
    try:
        # Let the class validate and add the booking
        fitness_class.add_booking(member_id)
        
        # Let the member handle credit deduction
        member.deduct_credit()
        
        # Create the booking record
        booking_id = uuid.uuid4().hex
        booking = Booking(booking_id, member_id, class_id)
        bookings[booking_id] = booking
        
        print(f"✓ Booked {member.name} into {fitness_class.name}")
        print(f"  Booking ID: {booking_id}")
        print(f"  Credits remaining: {member.credits}")
        
    except ValueError as e:
        print(f"✗ {e}")
```

**Notice the difference from the anemic version:**
- **Anemic**: `if member.credits <= 0:` (checking primitive values)
- **Rich**: `if not member.can_book():` (asking the object about its capability)

- **Anemic**: `member.credits -= 1` (directly manipulating data)
- **Rich**: `member.deduct_credit()` (telling the object to perform behavior)

- **Anemic**: `if len(fitness_class.bookings) >= fitness_class.capacity:` (manual checking)
- **Rich**: `fitness_class.add_booking(member_id)` (object enforces its own rules)

**Progress check:**
- We still have dictionaries (`members`, `classes`, `bookings`) for storage
- We still have functions (`create_member`, `book_class`, etc.) for workflow
- We still have the command loop in `main()`
- But now we have **rich domain models** with behavior, not just data containers
- Validation is encapsulated in the classes
- Business logic lives where it belongs (in domain objects)
- The objects protect themselves from invalid states

This is incremental refactoring. We haven't changed everything. We've made it better, step by step. The progression from dictionaries → anemic classes → rich classes is complete for our core domain objects.

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
