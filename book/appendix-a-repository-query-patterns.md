# Appendix A: Repository Query Patterns

Remember the repository ports from Chapter 7? Clean interfaces that define what the application needs from persistence:

```python
class MemberRepository(ABC):
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def list_all(self) -> List[Member]:
        pass
```

This works. But as your application grows, so do the queries:

```python
class MemberRepository(ABC):
    @abstractmethod
    def get_by_id(self, member_id: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Member]:
        pass
    
    @abstractmethod
    def find_by_membership_type(self, membership_type: str) -> List[Member]:
        pass
    
    @abstractmethod
    def find_by_status(self, status: MemberStatus) -> List[Member]:
        pass
    
    @abstractmethod
    def find_active_premium_members(self) -> List[Member]:
        pass
    
    @abstractmethod
    def find_members_with_expiring_credits(self, days: int) -> List[Member]:
        pass
    
    @abstractmethod
    def find_by_signup_date_range(self, start: date, end: date) -> List[Member]:
        pass
    
    @abstractmethod
    def find_inactive_members(self, since: date) -> List[Member]:
        pass
    
    @abstractmethod
    def list_all(self) -> List[Member]:
        pass
```

Now you have eight query methods. Next sprint, the product team wants to filter members by location, by referral source, by credit balance range. The repository grows to fifteen methods. Twenty. Thirty.

**This is repository interface explosion.**

Every new query means:
1. Adding a method to the port (abstract interface)
2. Implementing it in every adapter (SQLite, PostgreSQL, in-memory for tests)
3. Testing each implementation
4. Maintaining all of them as the domain changes

And the queries keep coming. The more flexible your application needs to be, the more methods you add. The repository becomes a maintenance nightmare.

**There's another problem.** Complex queries start leaking implementation details:

```python
@abstractmethod
def find_by_custom_filter(self, 
                         membership_type: Optional[str] = None,
                         status: Optional[MemberStatus] = None,
                         min_credits: Optional[int] = None,
                         max_credits: Optional[int] = None,
                         signup_after: Optional[date] = None,
                         signup_before: Optional[date] = None,
                         is_premium: Optional[bool] = None) -> List[Member]:
    pass
```

This method tries to handle every possible combination. But it's brittle. Every new filter means adding another parameter. The signature grows. The implementation becomes a mess of conditional logic. And you still can't handle arbitrary combinations—what if someone wants "premium members with more than 5 credits who signed up in Q1 and live in California"?

You could expose the database query language in the domain:

```python
@abstractmethod
def find_by_sql(self, query: str, params: tuple) -> List[Member]:
    """Execute raw SQL and return members."""
    pass
```

But now the application layer contains SQL. Your domain is coupled to your database. Tests become harder. Switching from SQLite to PostgreSQL breaks queries. This defeats the purpose of the repository abstraction.

**We need flexible querying without coupling to the database.**

This appendix teaches three patterns that solve repository interface explosion:

1. **Specification Pattern** — Encapsulate query logic as objects
2. **Query Objects** — Build queries using composable criteria
3. **Generic `find(criteria)` methods** — A single flexible query method

And crucially: **when to use specific finder methods anyway.**

By the end, you'll understand how to keep repository interfaces manageable while supporting flexible queries.

## The Problem in Detail

Let's make this concrete. You're building the gym booking system from the book. The `BookingRepository` starts simple:

```python
class BookingRepository(ABC):
    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    def find_by_member(self, member_id: str) -> List[Booking]:
        pass
    
    @abstractmethod
    def find_by_class(self, class_id: str) -> List[Booking]:
        pass
```

Then new requirements arrive:

**Requirement 1:** Admin dashboard needs to show upcoming bookings for the next 7 days.

```python
@abstractmethod
def find_upcoming(self, days: int) -> List[Booking]:
    pass
```

**Requirement 2:** Email service needs active bookings for a specific member.

```python
@abstractmethod
def find_active_by_member(self, member_id: str) -> List[Booking]:
    pass
```

**Requirement 3:** Analytics needs bookings grouped by status.

```python
@abstractmethod
def find_by_status(self, status: BookingStatus) -> List[Booking]:
    pass
```

**Requirement 4:** Reporting needs bookings for a specific class within a date range.

```python
@abstractmethod
def find_by_class_and_date_range(self, 
                                 class_id: str,
                                 start: datetime,
                                 end: datetime) -> List[Booking]:
    pass
```

**Requirement 5:** Waitlist feature needs to find cancelled bookings for a class to notify waiting members.

```python
@abstractmethod
def find_cancelled_by_class(self, class_id: str) -> List[Booking]:
    pass
```

You're up to eight methods. But the queries keep coming. What about:
- Bookings made in the last 24 hours?
- Bookings for a member in a specific date range?
- Bookings for premium members?
- Bookings that are both active and upcoming?

Each combination is a new method. The repository grows. Every adapter implementation grows. Testing becomes tedious. The port becomes a catalog of every query the application has ever needed.

**This isn't sustainable.**

And look at what happens when you try to implement `find_by_class_and_date_range` in the in-memory adapter:

```python
class InMemoryBookingRepository(BookingRepository):
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}
    
    def find_by_class_and_date_range(self, 
                                     class_id: str,
                                     start: datetime,
                                     end: datetime) -> List[Booking]:
        results = []
        for booking in self._bookings.values():
            if (booking.class_id == class_id and 
                start <= booking.created_at <= end):
                results.append(booking)
        return results
```

Now implement it in SQLite:

```python
class SqliteBookingRepository(BookingRepository):
    def find_by_class_and_date_range(self, 
                                     class_id: str,
                                     start: datetime,
                                     end: datetime) -> List[Booking]:
        query = """
            SELECT * FROM bookings 
            WHERE class_id = ? 
            AND created_at BETWEEN ? AND ?
        """
        cursor = self._conn.execute(query, (class_id, start, end))
        return [self._row_to_booking(row) for row in cursor.fetchall()]
```

And PostgreSQL:

```python
class PostgresBookingRepository(BookingRepository):
    def find_by_class_and_date_range(self, 
                                     class_id: str,
                                     start: datetime,
                                     end: datetime) -> List[Booking]:
        query = """
            SELECT * FROM bookings 
            WHERE class_id = %s 
            AND created_at BETWEEN %s AND %s
        """
        cursor = self._conn.execute(query, (class_id, start, end))
        return [self._row_to_booking(row) for row in cursor.fetchall()]
```

Three implementations of the same filtering logic. The filtering logic—"bookings for this class in this date range"—is duplicated across every adapter. When the requirement changes (say, "exclude cancelled bookings"), you update it in three places.

You're violating DRY. The query logic should live in one place. But where?

## Pattern 1: The Specification Pattern

The Specification Pattern encapsulates query logic as objects. Instead of adding methods to the repository, you create specification objects that describe what you're looking for.

A specification is a predicate—a function that returns true or false for an entity. "Is this booking active?" "Is this member premium?" "Does this class have space?"

Here's the idea:

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')


class Specification(ABC, Generic[T]):
    """A specification that describes criteria for entities."""
    
    @abstractmethod
    def is_satisfied_by(self, entity: T) -> bool:
        """Returns True if entity satisfies this specification."""
        pass
    
    def and_(self, other: 'Specification[T]') -> 'Specification[T]':
        """Combines this specification with another using AND."""
        return AndSpecification(self, other)
    
    def or_(self, other: 'Specification[T]') -> 'Specification[T]':
        """Combines this specification with another using OR."""
        return OrSpecification(self, other)
    
    def not_(self) -> 'Specification[T]':
        """Negates this specification."""
        return NotSpecification(self)
```

The base class defines the contract. Concrete specifications implement `is_satisfied_by()`:

```python
from domain.entities import Booking, BookingStatus


class ActiveBookingSpecification(Specification[Booking]):
    """Specification for active bookings."""
    
    def is_satisfied_by(self, booking: Booking) -> bool:
        return booking.status == BookingStatus.ACTIVE


class BookingForClassSpecification(Specification[Booking]):
    """Specification for bookings of a specific class."""
    
    def __init__(self, class_id: str):
        self.class_id = class_id
    
    def is_satisfied_by(self, booking: Booking) -> bool:
        return booking.class_id == self.class_id


class BookingInDateRangeSpecification(Specification[Booking]):
    """Specification for bookings within a date range."""
    
    def __init__(self, start: datetime, end: datetime):
        self.start = start
        self.end = end
    
    def is_satisfied_by(self, booking: Booking) -> bool:
        return self.start <= booking.created_at <= self.end
```

Each specification encapsulates one piece of query logic. Now you can combine them:

```python
# Find active bookings for a specific class
spec = ActiveBookingSpecification().and_(
    BookingForClassSpecification("class-123")
)

# Find bookings for a class in a date range
spec = BookingForClassSpecification("class-123").and_(
    BookingInDateRangeSpecification(start_date, end_date)
)

# Find active bookings for a class that are NOT in the past week
spec = (ActiveBookingSpecification()
        .and_(BookingForClassSpecification("class-123"))
        .and_(BookingInDateRangeSpecification(last_week, today).not_()))
```

The specifications compose. You build complex queries from simple pieces.

Now the repository needs just one method:

```python
class BookingRepository(ABC):
    @abstractmethod
    def find(self, spec: Specification[Booking]) -> List[Booking]:
        """Find all bookings matching the specification."""
        pass
```

Instead of dozens of methods, you have one flexible query method. The repository interface stays small. The query logic lives in specifications, not scattered across repository methods.

Here's how the in-memory adapter implements it:

```python
class InMemoryBookingRepository(BookingRepository):
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}
    
    def find(self, spec: Specification[Booking]) -> List[Booking]:
        return [
            booking 
            for booking in self._bookings.values()
            if spec.is_satisfied_by(booking)
        ]
```

Simple. Filter the collection using the specification. The specification handles the complexity.

The composite specifications (`AndSpecification`, `OrSpecification`, `NotSpecification`) are straightforward:

```python
class AndSpecification(Specification[T]):
    """Combines two specifications with AND."""
    
    def __init__(self, left: Specification[T], right: Specification[T]):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, entity: T) -> bool:
        return (self.left.is_satisfied_by(entity) and 
                self.right.is_satisfied_by(entity))


class OrSpecification(Specification[T]):
    """Combines two specifications with OR."""
    
    def __init__(self, left: Specification[T], right: Specification[T]):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, entity: T) -> bool:
        return (self.left.is_satisfied_by(entity) or 
                self.right.is_satisfied_by(entity))


class NotSpecification(Specification[T]):
    """Negates a specification."""
    
    def __init__(self, spec: Specification[T]):
        self.spec = spec
    
    def is_satisfied_by(self, entity: T) -> bool:
        return not self.spec.is_satisfied_by(entity)
```

They delegate to the underlying specifications and combine results with boolean logic.

**Usage in the application layer:**

```python
class ListUpcomingBookingsUseCase:
    def __init__(self, booking_repo: BookingRepository):
        self.booking_repo = booking_repo
    
    def execute(self, class_id: str) -> List[Booking]:
        now = datetime.now()
        next_week = now + timedelta(days=7)
        
        spec = (ActiveBookingSpecification()
                .and_(BookingForClassSpecification(class_id))
                .and_(BookingInDateRangeSpecification(now, next_week)))
        
        return self.booking_repo.find(spec)
```

The use case builds the specification and passes it to the repository. The query logic is explicit, composable, and testable.

**Testing specifications:**

```python
def test_active_booking_specification():
    active_booking = Booking(
        id="b1",
        member_id="m1",
        class_id="c1",
        status=BookingStatus.ACTIVE
    )
    cancelled_booking = Booking(
        id="b2",
        member_id="m1",
        class_id="c1",
        status=BookingStatus.CANCELLED
    )
    
    spec = ActiveBookingSpecification()
    
    assert spec.is_satisfied_by(active_booking)
    assert not spec.is_satisfied_by(cancelled_booking)


def test_combining_specifications():
    booking = Booking(
        id="b1",
        member_id="m1",
        class_id="c1",
        status=BookingStatus.ACTIVE,
        created_at=datetime(2024, 1, 15)
    )
    
    spec = (ActiveBookingSpecification()
            .and_(BookingForClassSpecification("c1"))
            .and_(BookingInDateRangeSpecification(
                datetime(2024, 1, 1),
                datetime(2024, 1, 31)
            )))
    
    assert spec.is_satisfied_by(booking)
```

The specifications are plain objects. Easy to instantiate, easy to test.

### The Database Problem

The specification pattern works beautifully with in-memory collections. But there's a problem with database adapters.

Look at the SQLite implementation:

```python
class SqliteBookingRepository(BookingRepository):
    def find(self, spec: Specification[Booking]) -> List[Booking]:
        # Load ALL bookings from the database
        cursor = self._conn.execute("SELECT * FROM bookings")
        all_bookings = [self._row_to_booking(row) for row in cursor.fetchall()]
        
        # Filter in Python
        return [
            booking 
            for booking in all_bookings
            if spec.is_satisfied_by(booking)
        ]
```

This loads every booking from the database into memory, then filters them in Python. For 100 bookings, fine. For 100,000 bookings, disaster.

Databases are designed for filtering. SQL's WHERE clause is optimized for this. By filtering in Python, you're throwing away database performance.

**Solution: Translate specifications to SQL.**

Extend the `Specification` base class with a method that generates SQL:

```python
class Specification(ABC, Generic[T]):
    @abstractmethod
    def is_satisfied_by(self, entity: T) -> bool:
        pass
    
    @abstractmethod
    def to_sql(self) -> tuple[str, tuple]:
        """Returns (WHERE clause, parameters) for SQL queries."""
        pass
```

Now specifications can both filter in memory and generate SQL:

```python
class ActiveBookingSpecification(Specification[Booking]):
    def is_satisfied_by(self, booking: Booking) -> bool:
        return booking.status == BookingStatus.ACTIVE
    
    def to_sql(self) -> tuple[str, tuple]:
        return ("status = ?", (BookingStatus.ACTIVE.value,))


class BookingForClassSpecification(Specification[Booking]):
    def __init__(self, class_id: str):
        self.class_id = class_id
    
    def is_satisfied_by(self, booking: Booking) -> bool:
        return booking.class_id == self.class_id
    
    def to_sql(self) -> tuple[str, tuple]:
        return ("class_id = ?", (self.class_id,))


class AndSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, entity: T) -> bool:
        return (self.left.is_satisfied_by(entity) and 
                self.right.is_satisfied_by(entity))
    
    def to_sql(self) -> tuple[str, tuple]:
        left_clause, left_params = self.left.to_sql()
        right_clause, right_params = self.right.to_sql()
        clause = f"({left_clause} AND {right_clause})"
        params = left_params + right_params
        return (clause, params)
```

The SQLite adapter now uses `to_sql()`:

```python
class SqliteBookingRepository(BookingRepository):
    def find(self, spec: Specification[Booking]) -> List[Booking]:
        where_clause, params = spec.to_sql()
        query = f"SELECT * FROM bookings WHERE {where_clause}"
        
        cursor = self._conn.execute(query, params)
        return [self._row_to_booking(row) for row in cursor.fetchall()]
```

The database does the filtering. Efficient. Scalable.

**The tradeoff:**

Now each specification must know how to translate to SQL. That couples them to the database. If you switch from SQLite to MongoDB, specifications need to generate MongoDB queries instead of SQL.

You've reduced coupling at the repository interface (one `find()` method instead of many), but you've added coupling in the specifications (they must know SQL).

Whether this tradeoff is worth it depends on:
1. How often you add new queries
2. How often you change databases
3. How important performance is

For most applications, you add queries frequently but change databases rarely. The specification pattern is a win.

## Pattern 2: Query Objects

Query objects take a different approach. Instead of encapsulating query logic as predicates, they encapsulate query logic as data structures.

A query object is a plain data class that describes what you're looking for:

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class BookingQuery:
    """Criteria for querying bookings."""
    member_id: Optional[str] = None
    class_id: Optional[str] = None
    status: Optional[BookingStatus] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
```

It's declarative. "I want bookings with these attributes." Not "I have logic that filters bookings."

The repository accepts a query object:

```python
class BookingRepository(ABC):
    @abstractmethod
    def find(self, query: BookingQuery) -> List[Booking]:
        """Find bookings matching the query criteria."""
        pass
```

Usage in the application layer:

```python
class ListMemberBookingsUseCase:
    def __init__(self, booking_repo: BookingRepository):
        self.booking_repo = booking_repo
    
    def execute(self, member_id: str) -> List[Booking]:
        query = BookingQuery(
            member_id=member_id,
            status=BookingStatus.ACTIVE
        )
        return self.booking_repo.find(query)
```

Simple. Explicit. No boolean logic, no composing specifications. Just "here's what I want."

**Implementation in the in-memory adapter:**

```python
class InMemoryBookingRepository(BookingRepository):
    def find(self, query: BookingQuery) -> List[Booking]:
        results = list(self._bookings.values())
        
        if query.member_id is not None:
            results = [b for b in results if b.member_id == query.member_id]
        
        if query.class_id is not None:
            results = [b for b in results if b.class_id == query.class_id]
        
        if query.status is not None:
            results = [b for b in results if b.status == query.status]
        
        if query.created_after is not None:
            results = [b for b in results if b.created_at >= query.created_after]
        
        if query.created_before is not None:
            results = [b for b in results if b.created_at <= query.created_before]
        
        if query.limit is not None:
            results = results[:query.limit]
        
        return results
```

Each field in the query object is optional. If it's `None`, skip that filter. If it's set, apply it.

**Implementation in the SQLite adapter:**

```python
class SqliteBookingRepository(BookingRepository):
    def find(self, query: BookingQuery) -> List[Booking]:
        conditions = []
        params = []
        
        if query.member_id is not None:
            conditions.append("member_id = ?")
            params.append(query.member_id)
        
        if query.class_id is not None:
            conditions.append("class_id = ?")
            params.append(query.class_id)
        
        if query.status is not None:
            conditions.append("status = ?")
            params.append(query.status.value)
        
        if query.created_after is not None:
            conditions.append("created_at >= ?")
            params.append(query.created_after)
        
        if query.created_before is not None:
            conditions.append("created_at <= ?")
            params.append(query.created_before)
        
        sql = "SELECT * FROM bookings"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        if query.limit is not None:
            sql += f" LIMIT {query.limit}"
        
        cursor = self._conn.execute(sql, tuple(params))
        return [self._row_to_booking(row) for row in cursor.fetchall()]
```

The adapter builds the SQL dynamically based on which fields are set. Database filtering, not Python filtering.

### Comparison to Specifications

**Query objects are simpler.** They're data classes. No logic. No composition. Easy to understand, easy to serialize (useful for APIs or caching).

**Query objects are less flexible.** You can't express complex logic. "Find bookings that are either premium OR have more than 5 credits" requires adding a field to the query object. Specifications can compose arbitrary logic.

**Query objects put more work on adapters.** Each adapter must interpret the query object and build the appropriate query. With specifications, the logic is in the specification itself.

**When to use query objects:**

- Your queries follow predictable patterns (filter by these known fields)
- You need to serialize queries (send them over HTTP, cache them, log them)
- You want simple, declarative query definitions
- Your queries don't require complex boolean logic

**When to use specifications:**

- You need arbitrary combinations of conditions
- Query logic is complex and deserves its own tested abstractions
- You want the same specification to work in memory and in the database
- You're comfortable with the added abstraction

Both patterns solve repository interface explosion. Pick the one that fits your constraints.

## Pattern 3: Builder-Style Query API

Some repositories use a fluent builder API for queries:

```python
class BookingRepository(ABC):
    @abstractmethod
    def query(self) -> 'BookingQueryBuilder':
        """Start building a query."""
        pass


class BookingQueryBuilder(ABC):
    """Fluent interface for building booking queries."""
    
    @abstractmethod
    def for_member(self, member_id: str) -> 'BookingQueryBuilder':
        pass
    
    @abstractmethod
    def for_class(self, class_id: str) -> 'BookingQueryBuilder':
        pass
    
    @abstractmethod
    def with_status(self, status: BookingStatus) -> 'BookingQueryBuilder':
        pass
    
    @abstractmethod
    def created_after(self, date: datetime) -> 'BookingQueryBuilder':
        pass
    
    @abstractmethod
    def created_before(self, date: datetime) -> 'BookingQueryBuilder':
        pass
    
    @abstractmethod
    def limit(self, n: int) -> 'BookingQueryBuilder':
        pass
    
    @abstractmethod
    def execute(self) -> List[Booking]:
        """Execute the query and return results."""
        pass
```

Usage:

```python
bookings = (booking_repo.query()
            .for_member("member-123")
            .with_status(BookingStatus.ACTIVE)
            .created_after(last_week)
            .limit(10)
            .execute())
```

It's expressive. Reads like a sentence. But it requires more boilerplate—the abstract builder interface and concrete implementations for each adapter.

**This is popular in ORM libraries** (like Django's QuerySet or SQLAlchemy's Query). They've already implemented the builder. You just use it.

If you're building your own repository layer from scratch, builders add complexity. Query objects or specifications are usually simpler.

## When to Use Specific Finder Methods

After all this—specifications, query objects, builders—when should you still use specific `find_by_*` methods?

**Use specific methods when:**

1. **The query is a core domain operation.** If "find active bookings for a member" is a fundamental operation that appears everywhere in your use cases, make it explicit:

```python
class BookingRepository(ABC):
    @abstractmethod
    def find_active_for_member(self, member_id: str) -> List[Booking]:
        """Find active bookings for a member - core operation."""
        pass
```

This makes the repository easier to understand. Someone reading the code sees `find_active_for_member()` and immediately knows what it does. With a generic query API, they have to read the query construction to understand intent.

2. **The query requires complex database optimization.** Some queries need careful SQL tuning—joins, indexes, specific query plans. Hiding that complexity behind a well-named method is cleaner than exposing it in query objects or specifications:

```python
@abstractmethod
def find_members_with_expired_credits(self) -> List[Member]:
    """
    Find members with credits that expired in the last 7 days.
    Uses optimized query with credit_expiry index.
    """
    pass
```

The implementation can use database-specific optimizations. The caller doesn't need to know.

3. **The operation has side effects or complex semantics.** Finding waitlist members when a class has an opening might involve complex logic—checking priorities, sorting, limiting results. That deserves its own method:

```python
@abstractmethod
def find_next_waitlist_member(self, class_id: str) -> Optional[Member]:
    """
    Find the next member on the waitlist according to priority rules.
    Premium members have priority; ties are broken by signup time.
    """
    pass
```

This is more than a query—it's a business rule about waitlist priority.

4. **You're starting out.** Don't prematurely optimize. Add `find_by_email()`. Add `find_by_class()`. When you have ten methods and see patterns, refactor to specifications or query objects. Starting with a generic query API when you have two use cases is premature abstraction.

**Mix and match:**

Nothing says you must choose one approach. A repository can have both specific methods and a generic query API:

```python
class BookingRepository(ABC):
    # Core domain operations - explicit methods
    @abstractmethod
    def find_active_for_member(self, member_id: str) -> List[Booking]:
        pass
    
    @abstractmethod
    def find_upcoming_for_class(self, class_id: str) -> List[Booking]:
        pass
    
    # Flexible querying for admin/reporting features
    @abstractmethod
    def find(self, query: BookingQuery) -> List[Booking]:
        pass
```

Use specific methods for common operations. Use the generic query API for ad-hoc queries in reporting or admin features.

## Practical Example: Refactoring the Gym System

Let's refactor the `BookingRepository` from Chapter 7 using query objects.

**Original (from Chapter 7):**

```python
class BookingRepository(ABC):
    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    def save(self, booking: Booking) -> None:
        pass
    
    @abstractmethod
    def find_by_member(self, member_id: str) -> List[Booking]:
        pass
    
    @abstractmethod
    def find_by_class(self, class_id: str) -> List[Booking]:
        pass
    
    @abstractmethod
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        pass
    
    @abstractmethod
    def find_by_status(self, status: BookingStatus) -> List[Booking]:
        pass
```

This works for the current features. But the product team wants:
- List all active bookings for a member
- Show upcoming bookings (next 7 days) for a class
- Admin view: filter bookings by member, class, status, and date range

Adding specific methods:

```python
@abstractmethod
def find_active_by_member(self, member_id: str) -> List[Booking]:
    pass

@abstractmethod
def find_upcoming_by_class(self, class_id: str, days: int) -> List[Booking]:
    pass

@abstractmethod
def find_by_filters(self, 
                   member_id: Optional[str] = None,
                   class_id: Optional[str] = None,
                   status: Optional[BookingStatus] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None) -> List[Booking]:
    pass
```

We're up to nine methods. And `find_by_filters` is already awkward—lots of optional parameters, unclear semantics.

**Refactored with query objects:**

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class BookingQuery:
    """Flexible query criteria for bookings."""
    member_id: Optional[str] = None
    class_id: Optional[str] = None
    status: Optional[BookingStatus] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: Optional[int] = None


class BookingRepository(ABC):
    # Core operations - keep them explicit
    @abstractmethod
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        """Get a specific booking by ID."""
        pass
    
    @abstractmethod
    def save(self, booking: Booking) -> None:
        """Save a booking."""
        pass
    
    # Core domain query - worth keeping explicit
    @abstractmethod
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        """Find a member's booking for a specific class - prevents duplicates."""
        pass
    
    # Flexible querying
    @abstractmethod
    def find(self, query: BookingQuery) -> List[Booking]:
        """Find bookings matching flexible criteria."""
        pass
```

Down from nine methods (and growing) to four. `get_by_id`, `save`, and `find_by_member_and_class` stay because they're core operations. Everything else goes through `find()`.

**Usage in use cases:**

```python
class ListMemberBookingsUseCase:
    def __init__(self, booking_repo: BookingRepository):
        self.booking_repo = booking_repo
    
    def execute(self, member_id: str) -> List[Booking]:
        query = BookingQuery(
            member_id=member_id,
            status=BookingStatus.ACTIVE
        )
        return self.booking_repo.find(query)


class ListUpcomingClassBookingsUseCase:
    def __init__(self, booking_repo: BookingRepository):
        self.booking_repo = booking_repo
    
    def execute(self, class_id: str) -> List[Booking]:
        now = datetime.now()
        next_week = now + timedelta(days=7)
        
        query = BookingQuery(
            class_id=class_id,
            status=BookingStatus.ACTIVE,
            created_after=now,
            created_before=next_week
        )
        return self.booking_repo.find(query)


class AdminBookingSearchUseCase:
    def __init__(self, booking_repo: BookingRepository):
        self.booking_repo = booking_repo
    
    def execute(self,
                member_id: Optional[str] = None,
                class_id: Optional[str] = None,
                status: Optional[BookingStatus] = None,
                start_date: Optional[datetime] = None,
                end_date: Optional[datetime] = None) -> List[Booking]:
        query = BookingQuery(
            member_id=member_id,
            class_id=class_id,
            status=status,
            created_after=start_date,
            created_before=end_date
        )
        return self.booking_repo.find(query)
```

The intent is clear. Query construction is declarative. No complex method signatures.

**In-memory adapter:**

```python
class InMemoryBookingRepository(BookingRepository):
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}
    
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        return self._bookings.get(booking_id)
    
    def save(self, booking: Booking) -> None:
        self._bookings[booking.id] = booking
    
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        for booking in self._bookings.values():
            if (booking.member_id == member_id and 
                booking.class_id == class_id):
                return booking
        return None
    
    def find(self, query: BookingQuery) -> List[Booking]:
        results = list(self._bookings.values())
        
        if query.member_id is not None:
            results = [b for b in results if b.member_id == query.member_id]
        
        if query.class_id is not None:
            results = [b for b in results if b.class_id == query.class_id]
        
        if query.status is not None:
            results = [b for b in results if b.status == query.status]
        
        if query.created_after is not None:
            results = [b for b in results 
                      if b.created_at >= query.created_after]
        
        if query.created_before is not None:
            results = [b for b in results 
                      if b.created_at <= query.created_before]
        
        if query.limit is not None:
            results = results[:query.limit]
        
        return results
```

**SQLite adapter:**

```python
class SqliteBookingRepository(BookingRepository):
    def __init__(self, connection):
        self._conn = connection
    
    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        cursor = self._conn.execute(
            "SELECT * FROM bookings WHERE id = ?",
            (booking_id,)
        )
        row = cursor.fetchone()
        return self._row_to_booking(row) if row else None
    
    def save(self, booking: Booking) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO bookings 
            (id, member_id, class_id, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (booking.id, booking.member_id, booking.class_id,
             booking.status.value, booking.created_at)
        )
        self._conn.commit()
    
    def find_by_member_and_class(self, member_id: str, 
                                  class_id: str) -> Optional[Booking]:
        cursor = self._conn.execute(
            """
            SELECT * FROM bookings 
            WHERE member_id = ? AND class_id = ?
            """,
            (member_id, class_id)
        )
        row = cursor.fetchone()
        return self._row_to_booking(row) if row else None
    
    def find(self, query: BookingQuery) -> List[Booking]:
        conditions = []
        params = []
        
        if query.member_id is not None:
            conditions.append("member_id = ?")
            params.append(query.member_id)
        
        if query.class_id is not None:
            conditions.append("class_id = ?")
            params.append(query.class_id)
        
        if query.status is not None:
            conditions.append("status = ?")
            params.append(query.status.value)
        
        if query.created_after is not None:
            conditions.append("created_at >= ?")
            params.append(query.created_after)
        
        if query.created_before is not None:
            conditions.append("created_at <= ?")
            params.append(query.created_before)
        
        sql = "SELECT * FROM bookings"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        if query.limit is not None:
            sql += f" LIMIT {query.limit}"
        
        cursor = self._conn.execute(sql, tuple(params))
        return [self._row_to_booking(row) for row in cursor.fetchall()]
    
    def _row_to_booking(self, row) -> Booking:
        return Booking(
            id=row[0],
            member_id=row[1],
            class_id=row[2],
            status=BookingStatus(row[3]),
            created_at=row[4]
        )
```

The adapter builds SQL dynamically based on the query. Database does the filtering.

New query needs? Don't add repository methods. Just use the existing `find()` with different criteria:

```python
# Find cancelled bookings for a class
query = BookingQuery(
    class_id=class_id,
    status=BookingStatus.CANCELLED
)
bookings = booking_repo.find(query)

# Find recent bookings (last 24 hours)
query = BookingQuery(
    created_after=datetime.now() - timedelta(days=1)
)
bookings = booking_repo.find(query)
```

The repository stays small. The application stays flexible.

## Testing with Query Patterns

Query objects and specifications make testing easier because they're explicit data.

**Testing a use case with query objects:**

```python
def test_list_member_bookings():
    # Arrange
    member_id = "member-123"
    repo = InMemoryBookingRepository()
    
    active_booking = Booking(
        id="b1",
        member_id=member_id,
        class_id="c1",
        status=BookingStatus.ACTIVE
    )
    cancelled_booking = Booking(
        id="b2",
        member_id=member_id,
        class_id="c2",
        status=BookingStatus.CANCELLED
    )
    
    repo.save(active_booking)
    repo.save(cancelled_booking)
    
    use_case = ListMemberBookingsUseCase(repo)
    
    # Act
    result = use_case.execute(member_id)
    
    # Assert
    assert len(result) == 1
    assert result[0].id == "b1"
```

You know exactly what query the use case builds. If the test fails, you know whether the issue is query construction or repository implementation.

**Testing specifications:**

```python
def test_active_booking_specification():
    active = Booking(id="b1", status=BookingStatus.ACTIVE)
    cancelled = Booking(id="b2", status=BookingStatus.CANCELLED)
    
    spec = ActiveBookingSpecification()
    
    assert spec.is_satisfied_by(active)
    assert not spec.is_satisfied_by(cancelled)


def test_combined_specification():
    booking = Booking(
        id="b1",
        member_id="m1",
        class_id="c1",
        status=BookingStatus.ACTIVE
    )
    
    spec = (ActiveBookingSpecification()
            .and_(BookingForClassSpecification("c1")))
    
    assert spec.is_satisfied_by(booking)
    
    wrong_class_spec = (ActiveBookingSpecification()
                       .and_(BookingForClassSpecification("c2")))
    
    assert not wrong_class_spec.is_satisfied_by(booking)
```

Specifications are testable in isolation. You don't need a repository or database. Just create entities and check if they satisfy the spec.

**Testing query object construction:**

```python
def test_booking_query_construction():
    query = BookingQuery(
        member_id="m1",
        status=BookingStatus.ACTIVE
    )
    
    assert query.member_id == "m1"
    assert query.status == BookingStatus.ACTIVE
    assert query.class_id is None  # Optional fields default to None
```

Trivial, but documents the query object structure.

## Tradeoffs and Guidelines

Here's how to choose between approaches:

**Use specific `find_by_*` methods when:**
- You have < 5 query methods
- Queries are core domain operations
- Queries require complex optimization
- You're starting out and don't know patterns yet

**Use the Specification Pattern when:**
- You need complex boolean logic (AND, OR, NOT combinations)
- Queries are reusable across contexts
- You want the same query to work in-memory and in the database
- You're comfortable with additional abstraction

**Use Query Objects when:**
- Queries follow predictable patterns (filter by known fields)
- You need to serialize queries (APIs, logging, caching)
- You want simple, declarative queries
- You don't need complex boolean composition

**Use Builder APIs when:**
- You're using an ORM that provides one
- You want a fluent, expressive query syntax
- You're willing to implement the builder interface

**Mix approaches:**
- Keep core domain operations as specific methods
- Use a generic query API for flexible/ad-hoc queries
- Start simple, refactor when interface explosion happens

## Key Takeaways

1. **Repository interface explosion is real.** Every new query shouldn't mean a new repository method.

2. **The Specification Pattern encapsulates query logic as objects.** Compose them with AND, OR, NOT. Works great in memory; requires SQL translation for databases.

3. **Query objects are declarative data structures.** Simple, serializable, less flexible than specifications.

4. **Builder APIs are fluent but require more boilerplate.** Use them if your ORM provides one.

5. **Specific finder methods still have a place.** Use them for core operations, complex optimizations, or when starting out.

6. **Mix approaches.** Specific methods for common operations, generic APIs for flexibility.

7. **Refactor when it hurts.** Don't prematurely optimize. Add patterns when you have the problem they solve.

The goal isn't to eliminate all specific methods. It's to keep your repository interface manageable while supporting the queries your application needs. Choose the approach that fits your context, and refactor when you outgrow it.
