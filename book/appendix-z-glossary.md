# Appendix Z: Glossary

This glossary defines the architectural terms and concepts used throughout this book. Terms are organized alphabetically for easy reference.

## A

### Adapter
A concrete implementation that connects a port (abstraction) to real infrastructure. Adapters implement the interfaces defined by ports, allowing the application to interact with databases, email services, external APIs, and other technical details without depending on them directly. Examples: `PostgresMemberRepository`, `SMTPNotificationService`.

### Aggregate
A cluster of entities and value objects treated as a single unit for data changes. An aggregate defines a consistency boundary—everything inside must remain consistent at the end of each transaction. One entity serves as the aggregate root, which is the entry point for all access to objects inside the aggregate. Aggregates reference each other by ID rather than holding direct object references. Example: A `Booking` aggregate containing booking details as a single transactional unit.

### Anemic Domain Model
A domain model where objects hold data but contain no business logic or behavior. All logic lives in services outside the domain objects, making them little more than property bags or data containers. This pattern can lead to scattered business rules, duplicated validation logic, and difficulty maintaining invariants. The opposite of a rich domain model.

### Application Layer
The layer that orchestrates use cases by coordinating domain objects to accomplish specific user goals. It defines transaction boundaries, handles workflow coordination, and translates between the domain and external systems. The application layer contains no business rules—those belong in the domain. Also called the use case layer.

## C

### Clean Architecture
An architectural approach that organizes code into layers with strict dependency rules: dependencies point inward toward the domain, never outward toward infrastructure. High-level policy (business rules) doesn't depend on low-level details (databases, frameworks). This enables testability, flexibility, and maintainability by isolating business logic from technical concerns.

### Consistency Boundary
The scope within which business invariants must be maintained transactionally. Everything inside the boundary must be consistent at the end of each transaction. Everything outside can be eventually consistent. Aggregates define consistency boundaries in domain-driven design.

## D

### Dependency Injection
A technique where dependencies are provided to an object from outside rather than created internally. This allows high-level code to depend on abstractions (ports) while concrete implementations (adapters) are injected at runtime. Enables testing with mock implementations and swapping infrastructure without changing business logic.

### Dependency Inversion Principle (DIP)
One of the SOLID principles stating that high-level modules should not depend on low-level modules—both should depend on abstractions. Abstractions should not depend on details; details should depend on abstractions. This principle enables clean architecture by ensuring business logic doesn't depend on infrastructure.

### Domain
This term has three distinct meanings in this book:
- **Domain (business problem)**: The real-world problem being solved with code (e.g., the gym booking system)
- **Domain layer (architecture)**: The specific layer of code that contains business logic, isolated from infrastructure and interfaces
- **Domain model (code representation)**: The entities, value objects, and services that model the business concepts

### Domain-Driven Design (DDD)
An approach to software development that focuses on modeling complex business logic by creating a rich domain model. Emphasizes collaboration with domain experts, using ubiquitous language, and employing patterns like entities, value objects, aggregates, and domain services to capture business rules in code.

### Domain Service
A service that contains business logic that doesn't naturally belong to any single entity or value object. Domain services coordinate between entities, implement complex business rules that span multiple objects, or perform operations that don't fit into a single aggregate. Unlike application services, domain services contain business logic and belong in the domain layer.

## E

### Entity
A domain object that is defined by its identity rather than its attributes. Two entities are different if they have different identities, even if all their attributes are identical. Entities typically have lifecycles—they are created, modified, and sometimes deleted. They protect their invariants and enforce business rules. Examples: `Member`, `FitnessClass`, `Booking`.

## H

### Hexagonal Architecture
An architectural pattern (also called Ports and Adapters) where the application core is surrounded by ports (abstractions) and adapters (implementations). The core contains business logic and defines what it needs from infrastructure through ports. Adapters implement those ports using specific technologies. This allows swapping implementations without changing the core, and testing the core without requiring real infrastructure.

## I

### Infrastructure Layer
The layer that handles technical details: databases, external APIs, email services, file systems, frameworks. This layer implements the ports defined by the application layer using concrete technologies. Business logic has no dependencies on this layer—dependencies point inward, from infrastructure toward the domain.

### Interface Layer
The layer that handles interaction with external actors: REST APIs, command-line interfaces, message queues, batch jobs. This layer translates external requests into use case invocations and translates domain results back into appropriate formats. Also called the presentation layer or delivery mechanism.

### Interface Segregation Principle (ISP)
One of the SOLID principles stating that clients should not be forced to depend on interfaces they don't use. Better to have multiple specific interfaces than one general-purpose interface. This keeps dependencies focused and prevents unnecessary coupling.

### Invariant
A business rule or condition that must always be true. Invariants define what makes an object or system valid. Domain objects enforce their invariants—they never allow themselves to enter an invalid state. Examples: "A class cannot exceed its capacity," "An email address must be valid," "Credits cannot be negative."

## L

### Layer
A logical grouping of code with a specific responsibility in the architecture. Common layers include domain (business logic), application (use case orchestration), infrastructure (technical details), and interface (external interactions). Layers have dependency rules—typically, dependencies point inward toward the domain.

### Liskov Substitution Principle (LSP)
One of the SOLID principles stating that objects of a derived class should be substitutable for objects of the base class without breaking the program. If you have a base class and derived classes, you should be able to use any derived class wherever the base class is expected, and the behavior should remain sensible.

## O

### Open/Closed Principle (OCP)
One of the SOLID principles stating that software entities should be open for extension but closed for modification. You should be able to add new functionality without changing existing, working code. Achieved through abstraction, inheritance, and polymorphism.

## P

### Port
An abstract interface that defines what the application needs from infrastructure without specifying how it's provided. Ports live at the boundary between the application core and infrastructure. The application depends on ports, and infrastructure implements ports. This inverts dependencies and enables swapping implementations. Examples: `MemberRepository` (interface), `NotificationService` (interface).

### Ports and Adapters
See Hexagonal Architecture.

## R

### Repository
A port that abstracts data persistence and retrieval. Repositories provide collection-like interfaces for accessing aggregates, hiding the details of how data is stored. The domain depends on repository abstractions (ports), and infrastructure provides concrete implementations (adapters). Examples: `MemberRepository` (port), `PostgresMemberRepository` (adapter).

### Rich Domain Model
A domain model where business logic lives within domain objects themselves. Entities and value objects enforce their own rules, validate their own state, and protect their invariants. This contrasts with anemic domain models where objects are just data containers and logic lives elsewhere.

## S

### Single Responsibility Principle (SRP)
One of the SOLID principles stating that a class should have only one reason to change. Each class should have one responsibility, one job, one focus. This makes code easier to understand, test, and modify because changes to one responsibility don't affect other concerns.

### SOLID
An acronym for five object-oriented design principles: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion. These principles guide how to write classes and structure code to be maintainable, testable, and flexible.

## T

### Test-Driven Development (TDD)
A development approach where you write tests before writing implementation code. The cycle is: write a failing test (red), write minimal code to make it pass (green), refactor to improve design (refactor). TDD drives design decisions by forcing you to think about interfaces and behavior before implementation.

### Transaction Boundary
The scope of operations that must succeed together or fail together—all or nothing. In domain-driven design, aggregates typically define transaction boundaries. Use cases in the application layer define where transactions begin and end.

## U

### Ubiquitous Language
A shared vocabulary between developers and domain experts. The code uses the same terms and concepts that business people use. Classes, methods, and variables reflect real business concepts rather than technical implementations. This reduces translation overhead and makes the codebase accessible to domain experts.

### Unit of Work
A pattern that maintains a list of objects affected by a business transaction and coordinates the writing of changes. It ensures that multiple repository operations succeed together or fail together, providing transactional consistency across multiple aggregates.

### Use Case
A single action that accomplishes a specific goal from a user's perspective. Use cases live in the application layer and orchestrate domain objects to complete workflows. They define transaction boundaries but contain no business logic. Examples: "Book a class," "Cancel a booking," "Process waitlist."

## V

### Value Object
A domain object that is defined by its attributes rather than identity. Two value objects are equal if all their attributes are equal. Value objects are immutable—once created, they cannot change. They enforce rules and make invalid states impossible. Value objects have no lifecycle beyond their attributes. Examples: `EmailAddress`, `TimeSlot`, `ClassCapacity`.

---

**Note on Usage:** These terms appear throughout the book with specific meanings in the context of software architecture. Understanding these concepts and their relationships is key to applying the patterns and principles presented in this book.
