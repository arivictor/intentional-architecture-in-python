# Pattern Reference Guide - Writing Guidelines

This document provides guidelines for writing the remaining chapters in the pattern reference guide format.

## Chapter Template

Every chapter should follow this structure:

### 1. Introduction (2-3 sentences)
- What is this pattern?
- Why does it matter?

### 2. The Problem
- Describe the pain point this pattern solves
- Show a "bad" example (what happens WITHOUT this pattern)
- Keep it generic, not tied to a specific domain
- 50-100 lines of "bad" code showing the problem

### 3. The Pattern
- Explain the concept clearly
- Use diagrams where helpful (ASCII art is fine)
- Define key terms
- Theory and principles
- 1-2 paragraphs

### 4. Implementation
- Show a clean, isolated example (50-150 lines total)
- Use a simple, relatable domain - NOT part of larger system
- Complete and runnable
- All imports shown
- Clear, focused implementation

**Example Domain Selection:**
- Payment processing
- User management
- Order system
- Product catalog
- Blog/posts
- Inventory
- Notifications
- Email/messaging
- File processing
- Report generation

**DO NOT use:** Gym booking system (old approach)

### 5. Explanation
- Walk through key parts of the code
- Explain design decisions
- Highlight important patterns
- 3-5 paragraphs

### 6. Benefits
Why use this pattern?
- Benefit 1 with brief explanation
- Benefit 2 with brief explanation
- Benefit 3 with brief explanation

### 7. Trade-offs
When NOT to use this pattern:
- **Overhead:** What complexity does this add?
- **Overkill:** When is this too much?
- **Alternatives:** What simpler approaches might work?

### 8. Variations (optional)
- Common alternative implementations
- When to use each variation

### 9. Testing
- How to test code using this pattern
- Show example tests (3-5 test cases)
- Use pytest format

### 10. Common Mistakes
Anti-patterns and pitfalls to avoid:
- Mistake 1: Description and why it's wrong
- Mistake 2: Description and why it's wrong
- Mistake 3: Description and why it's wrong

### 11. Related Patterns
Cross-reference other chapters:
- See Chapter X for [related pattern]
- Often combined with [other pattern]

### 12. Summary
- 2-3 sentence recap of key takeaway
- Reinforce when to use and when not to use

### 13. Further Reading
- Citations to original sources
- 3-5 authoritative references

## Code Style Guidelines

```python
# Always show imports at the top
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

# Use type hints consistently
def get_product(product_id: str) -> Optional[Product]:
    pass

# Clear docstrings for public APIs
class Repository(ABC):
    """
    Abstract repository for data access.
    
    Implementations provide specific storage mechanisms
    while maintaining the same interface.
    """
    pass

# Complete implementations - no "..." or "# TODO" or "# implementation here"
def calculate_total(items):
    """Calculate total from items."""
    return sum(item.price * item.quantity for item in items)

# Use realistic but simple examples
class Order:
    def __init__(self, order_id: str):
        if not order_id:
            raise ValueError("Order ID required")
        self.id = order_id
        self._items = []
```

## Domain Selection by Chapter

### Completed Chapters
- **Ch 2 (TDD):** Task Manager - simple todo list
- **Ch 3 (Domain Modeling):** E-commerce Orders - Order, Product, OrderItem
- **Ch 4 (SRP):** User Management - registration, validation, persistence

### Recommended Domains for Remaining Chapters

**Chapter 5: Open/Closed Principle**
- Domain: Payment Processing
- Example: Different payment methods (credit card, PayPal, crypto)
- Show: Strategy pattern for extending without modifying

**Chapter 6: Liskov Substitution Principle**
- Domain: Shape Hierarchy or Vehicle Types
- Example: Rectangle/Square problem or Bird hierarchy
- Show: Violations and fixes

**Chapter 7: Interface Segregation Principle**
- Domain: Multi-function Printer
- Example: Printer, Scanner, Fax capabilities
- Show: Fat interface vs segregated interfaces

**Chapter 8: Dependency Inversion Principle**
- Domain: Notification System
- Example: Email, SMS, Push notifications
- Show: Depending on abstractions, not concretions

**Chapter 9: Entities vs Value Objects**
- Domain: Customer and Address/Money
- Example: Customer (entity with identity), Address (value object)
- Show: Identity-based vs value-based equality

**Chapter 10: Aggregates & Boundaries**
- Domain: Shopping Cart
- Example: Cart (aggregate root) with CartItems
- Show: Consistency boundaries, invariants

**Chapter 11: Domain Events**
- Domain: Order Processing
- Example: OrderPlaced, OrderPaid, OrderShipped events
- Show: Event publishing, handlers

**Chapter 12: Layered Architecture**
- Domain: Blog API
- Example: Post, Comment with layers (domain, application, infrastructure, interface)
- Show: Complete mini-app with ~200 lines

**Chapter 13: Hexagonal Architecture**
- Domain: Email Sending System
- Example: Message, MessageSender port, EmailAdapter, SMSAdapter
- Show: Ports and adapters clearly separated

**Chapter 14: Repository Pattern**
- Domain: Product Catalog
- Example: Product, ProductRepository interface, InMemory and SQLite implementations
- Show: Abstraction over data access

**Chapter 15: Unit of Work Pattern**
- Domain: Order with Line Items
- Example: Transaction boundaries across multiple repositories
- Show: Commit/rollback

**Chapter 16: Factory Pattern**
- Domain: User Creation
- Example: Different user types (Admin, Customer, Guest)
- Show: Encapsulating complex creation logic

**Chapter 17: CQRS**
- Domain: Product Inventory
- Example: Separate read/write models
- Show: Commands vs Queries

**Chapter 18: Event Sourcing**
- Domain: Bank Account
- Example: Account events (deposited, withdrawn)
- Show: Rebuilding state from events

**Chapter 19: Specification Pattern**
- Domain: Product Filtering
- Example: Filter products by price, category, availability
- Show: Composable business rules

## Quality Checklist

Before considering a chapter complete, verify:

- [ ] Introduction clearly states what and why
- [ ] Problem section shows "bad" code example
- [ ] Pattern section explains theory clearly
- [ ] Implementation is complete and runnable (50-150 lines)
- [ ] Example uses a simple, focused domain (not gym booking)
- [ ] All imports are shown
- [ ] Type hints are used
- [ ] Explanation walks through key decisions
- [ ] Benefits section has 3+ items
- [ ] Trade-offs section explains when NOT to use
- [ ] Testing section shows 3-5 test examples
- [ ] Common Mistakes section has 2-3 anti-patterns
- [ ] Related Patterns cross-references other chapters
- [ ] Summary is 2-3 sentences
- [ ] Further Reading has 3-5 authoritative sources
- [ ] Code is properly formatted and indented
- [ ] No "TODO" or incomplete sections
- [ ] Chapter is self-contained (can read without previous chapters)

## Length Guidelines

- Introduction: 2-3 sentences
- The Problem: 100-200 words + 50-100 line code example
- The Pattern: 100-150 words
- Implementation: 50-150 line complete example
- Explanation: 200-300 words
- Benefits: 3-5 bullet points
- Trade-offs: 3-5 bullet points
- Testing: 30-50 line test example
- Common Mistakes: 2-3 anti-patterns with examples
- Related Patterns: 2-3 cross-references
- Summary: 2-3 sentences
- Further Reading: 3-5 references

**Total chapter length:** Approximately 10-15 pages (2500-4000 words)

## Consistency Notes

- Use "we" sparingly, prefer direct statements
- Use "you" when addressing the reader
- Keep tone professional but accessible
- Avoid framework-specific code (Flask, Django, etc.)
- Use Python 3.9+ features (type hints, etc.)
- Follow PEP 8 style guide
- Use pytest for test examples
- Include docstrings on classes and public methods
- Use meaningful variable names, not abbreviations

## Examples of Good Domain Choices

✅ **Good:** Simple, focused, relatable
- Calculator for math operations
- Todo list for tasks
- Shopping cart for e-commerce
- Blog posts and comments
- Product catalog
- User registration
- Payment processing
- Notification sending

❌ **Bad:** Complex, requires too much context
- Trading platform with multiple instruments
- Healthcare system with insurance claims
- Multi-tenant SaaS with complex permissions
- Distributed system with microservices
- Real-time chat with websockets

The domain should be simple enough to understand in 30 seconds, but rich enough to demonstrate the pattern effectively.
