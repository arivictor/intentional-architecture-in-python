# Chapter 8: Interface Layer - Building an API

We have a complete hexagonal architecture from Chapter 7. Domain entities enforce business rules. Use cases orchestrate workflows. Ports define abstractions. Adapters implement infrastructure. Dependencies point inward. The core is clean and testable.

But there's one piece missing: **how do users actually access this system?**

## Where We Left Off

In Chapter 7, we built complete hexagonal architecture:

**The Core:**
```python
# application/use_cases/book_class_use_case.py
class BookClassUseCase:
    def __init__(self, member_repository: MemberRepository,  # Port!
                 class_repository: FitnessClassRepository,    # Port!
                 booking_repository: BookingRepository,        # Port!
                 notification_service: NotificationService):   # Port!
        self.member_repository = member_repository
        # ...
    
    def execute(self, command: BookClassCommand) -> BookingResult:
        # Orchestration using ports
        # ...
```

**The Adapters:**
```python
# infrastructure/adapters/sqlite_member_repository.py
class SqliteMemberRepository(MemberRepository):  # Implements port
    def get_by_id(self, member_id: str) -> Member:
        # SQLite implementation
        # ...
```

**The Container:**
```python
# infrastructure/container.py
def create_production_container() -> ApplicationContainer:
    # Wire up adapters
    member_repo = SqliteMemberRepository(db)
    # ...
    book_class_use_case = BookClassUseCase(member_repo, ...)
    return container
```

**What works:**
- Complete hexagonal architecture
- Testable with InMemory adapters
- Swappable infrastructure
- Clean dependency flow

**The problem:**
We can run use cases directly in tests:
```python
def test_booking():
    use_case = BookClassUseCase(...)
    result = use_case.execute(command)
    # Works great in tests!
```

But there's **no way for real users to access the system.** No REST API. No command-line interface. No web interface. The application is functionally complete but externally invisible.

We need an **interface layer**.

## The New Challenge

The gym manager says: "Our mobile app needs to access the booking system via REST API. Also, gym staff still want the command-line interface for administrative tasks."

Requirements:
1. **REST API** for mobile app integration
2. **CLI** for staff administrative access
3. **Both use the same use cases** (no duplicate logic)
4. **HTTP concerns stay out of the core** (status codes, JSON serialization belong in interface)
5. **Easy to add more interfaces later** (GraphQL, WebSockets, etc.)

This is what hexagonal architecture enables: multiple interfaces, one core.

## Where the Interface Layer Fits

Recall the four layers from Chapter 4:

```
┌─────────────────────────────────────┐
│      Interface Layer                │  ← We're building this
│   (HTTP API, CLI, GraphQL)          │
├─────────────────────────────────────┤
│      Application Layer              │
│   (Use Cases, Orchestration)        │
├─────────────────────────────────────┤
│      Domain Layer                   │
│   (Business Logic, Entities)        │
├─────────────────────────────────────┤
│      Infrastructure Layer           │
│   (Database, Email, External APIs)  │
└─────────────────────────────────────┘
```

The interface layer sits at the top. It depends on the application layer (use cases) but nothing depends on it. This is intentional:

- **Domain doesn't know about HTTP** - `Member` doesn't care if the request came from REST, GraphQL, or a CLI
- **Application doesn't know about JSON** - `BookClassUseCase` works the same whether called from an API or a test
- **Infrastructure doesn't know about routing** - Repositories don't care about HTTP status codes

The interface layer is the **adapter between the outside world and your application**. It's the entry point, not the core.

## Why We're Not Using a Framework

You might be wondering: "Why aren't we using FastAPI or Flask?"

This is a fair question. In production, you absolutely should use a framework. But for learning, we need to understand what frameworks do before we use them.

**Frameworks change.** 

Twenty years ago, Python web development meant CGI scripts. Then came Django. Then Flask became popular for APIs. Now FastAPI dominates with async/await and Pydantic validation. In five years, something new will emerge.

**Principles don't change.**

HTTP request/response has been the same since 1991. The idea of routing URLs to handlers is universal. Serializing domain objects to JSON is a constant need. Status codes (200, 404, 500) are stable. These fundamentals transcend any framework.

When you learn a framework first, you learn *how that framework does things*. You learn FastAPI's decorators, Flask's request context, Django's middleware. But you don't learn *what they're actually doing underneath*.

Then the framework changes. Or you switch jobs and the new company uses something different. Suddenly you're lost, because you learned the abstraction without understanding the foundation.

**Understanding the foundation makes learning any framework trivial.**

Once you see how HTTP works—reading request bodies, parsing JSON, setting response headers, routing based on paths—picking up FastAPI becomes a weekend project. You'll recognize what it's abstracting. You'll appreciate what it's doing for you. You'll make better decisions about when to use it and when not to.

**Your architecture shouldn't depend on the framework.**

This is the key architectural insight. If your domain logic knows about Flask, you can't switch frameworks without rewriting your business rules. If your use cases depend on FastAPI's dependency injection, you're coupled to that framework forever.

Clean architecture means your core application works the same whether the interface is HTTP, CLI, GraphQL, or anything else. The framework is a detail. An implementation choice. Not a foundation.

**What we're doing in this chapter:**

- Building an HTTP API using Python's standard library `http.server`
- Seeing exactly what frameworks do behind the scenes
- Understanding request parsing, routing, serialization, and error handling
- Applying the same architectural principles that work in any framework

**What we're NOT saying:**

- "Don't use frameworks in production" (please do!)
- "Frameworks are bad" (they're excellent tools)
- "You should always build from scratch" (you shouldn't)

We're saying: **understand the fundamentals so you can use frameworks intentionally, not dependently.**

At the end of this chapter, we'll show the FastAPI equivalent. You'll see it's the same architecture, just less boilerplate. The use cases don't change. The domain doesn't change. Only the interface layer changes—which is exactly the point.

## The Interface Layer's Responsibilities

What does the interface layer actually do?

**It translates.**

External format → Internal format → Use case execution → Internal format → External format

Specifically:

1. **Accept requests from the outside world**
   - HTTP requests with JSON bodies
   - CLI commands with arguments
   - GraphQL queries
   - Message queue events

2. **Parse and validate input**
   - Extract data from request (JSON, query params, headers)
   - Validate required fields are present
   - Convert external types to internal types (strings to domain objects)

3. **Call the appropriate use case**
   - Map URL path to use case (`/api/bookings` → `BookClassUseCase`)
   - Pass extracted data to use case
   - Handle any exceptions the use case raises

4. **Translate results back to external format**
   - Convert domain objects to JSON
   - Format datetime objects
   - Serialize enums and value objects

5. **Handle protocol-specific concerns**
   - HTTP status codes (200, 201, 400, 404, 500)
   - HTTP headers (Content-Type, Location)
   - Error responses with appropriate formats

**What the interface layer does NOT do:**

- **Business logic** - That's in the domain layer
- **Workflow orchestration** - That's in the application layer
- **Data persistence** - That's in the infrastructure layer

The interface layer should be *thin*. Almost mechanical. If you find yourself writing business logic in an HTTP handler, you've violated layer boundaries.

Here's a concrete example:

```python
# ❌ BAD - Business logic in interface layer
def handle_booking(self):
    data = self._parse_json_body()
    
    # This is business logic! Doesn't belong here.
    if member.credits < 1:
        self._send_error(400, "Insufficient credits")
        return
    
    if class.current_bookings >= class.capacity:
        self._send_error(400, "Class is full")
        return
    
    # More business logic...
    member.credits -= 1
    class.current_bookings += 1
```

```python
# ✓ GOOD - Interface layer just translates
def handle_booking(self):
    data = self._parse_json_body()
    
    try:
        # Use case handles all business logic
        booking = self.book_class_use_case.execute(
            data['member_id'], 
            data['class_id']
        )
        
        # Interface layer just formats the response
        response = {
            'id': booking.id,
            'member_id': booking.member_id,
            'class_id': booking.class_id
        }
        self._send_json_response(201, response)
        
    except InsufficientCreditsException:
        self._send_error(400, "Insufficient credits")
    except ClassFullException:
        self._send_error(400, "Class is full")
```

The difference: the interface layer translates and routes. The use case enforces rules and orchestrates. Clear separation.

## Building a Simple HTTP API

Let's build an HTTP API for our gym booking system using Python's standard library. We'll start simple and add complexity progressively.

Why this approach? Because understanding HTTP fundamentals makes learning any framework trivial. Once you see how routing, parsing, and serialization work at the bare-metal level, frameworks become obvious. You'll recognize what they're abstracting and appreciate what they do for you.

### Basic Server Setup

Python's `http.server` module provides everything we need to handle HTTP requests:

```python
# interface/api.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class GymBookingHandler(BaseHTTPRequestHandler):
    """HTTP request handler for gym booking API."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._send_json_response(200, {
                'message': 'Gym Booking API',
                'version': '1.0',
                'endpoints': [
                    'GET /api/classes',
                    'POST /api/bookings',
                    'DELETE /api/bookings/{id}'
                ]
            })
        else:
            self._send_error(404, "Not Found")
    
    def _send_json_response(self, status_code: int, data: dict):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """Send an error response."""
        self._send_json_response(status_code, {'error': message})


if __name__ == '__main__':
    server = HTTPServer(('localhost', 8000), GymBookingHandler)
    print("Server running on http://localhost:8000")
    server.serve_forever()
```

Let's understand what's happening:

**`HTTPServer`** - Python's built-in HTTP server. It listens on a port and handles the HTTP protocol details (parsing headers, managing connections, etc.).

**`BaseHTTPRequestHandler`** - Base class that parses HTTP requests. We subclass it and implement methods like `do_GET()`, `do_POST()` to handle different HTTP verbs.

**`do_GET(self)`** - Called automatically when a GET request arrives. `self.path` contains the URL path (`/api/classes`).

**`send_response(200)`** - Sets the HTTP status code (200 = OK, 404 = Not Found, etc.).

**`send_header()`** - Sets HTTP response headers. `Content-Type: application/json` tells the client we're sending JSON.

**`end_headers()`** - Signals the end of headers. After this, we write the response body.

**`wfile.write()`** - Writes the response body. Must be bytes, not strings.

This is what frameworks do for you. Flask's `@app.route()` decorator? It's setting up handlers like this. FastAPI's automatic JSON serialization? It's doing `json.dumps()` for you.

But now you see it. It's not magic. It's just HTTP.

### Routing

Real APIs have multiple endpoints. We need routing—mapping URL paths to handlers.

Why manually? Because when you see the pattern matching (`if self.path == '/api/classes'`), you understand what Flask's decorators and FastAPI's path operations are actually doing. They're just nicer syntax for the same concept.

```python
class GymBookingHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        """Route GET requests."""
        if self.path == '/':
            self._handle_root()
        elif self.path == '/api/classes':
            self._handle_list_classes()
        elif self.path.startswith('/api/members/'):
            self._handle_get_member()
        else:
            self._send_error(404, "Not Found")
    
    def do_POST(self):
        """Route POST requests."""
        if self.path == '/api/bookings':
            self._handle_create_booking()
        elif self.path == '/api/bookings/cancel':
            self._handle_cancel_booking()
        else:
            self._send_error(404, "Not Found")
    
    def do_DELETE(self):
        """Route DELETE requests."""
        if self.path.startswith('/api/bookings/'):
            self._handle_delete_booking()
        else:
            self._send_error(404, "Not Found")
```

This is manual routing. Check the path, call the appropriate handler method.

Frameworks provide nicer syntax:

```python
# Flask
@app.get('/api/classes')
def list_classes():
    ...

# FastAPI
@app.post('/api/bookings')
def create_booking():
    ...
```

But underneath, they're doing exactly this: mapping paths to functions. The decorator is syntactic sugar. The concept is identical.

### Parsing Request Data

POST and PUT requests include data in the request body. We need to parse it.

Why does this matter? Because understanding Content-Length headers, reading from socket streams, and parsing JSON teaches you what frameworks hide. When you debug a request parsing issue in production, you'll know what's actually happening.

```python
class GymBookingHandler(BaseHTTPRequestHandler):
    
    def _parse_json_body(self) -> dict:
        """Parse JSON from request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        
        if content_length == 0:
            return {}
        
        body_bytes = self.rfile.read(content_length)
        body_str = body_bytes.decode('utf-8')
        
        try:
            return json.loads(body_str)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body")
    
    def _handle_create_booking(self):
        """Handle POST /api/bookings."""
        try:
            data = self._parse_json_body()
            
            # Validate required fields
            member_id = data.get('member_id')
            class_id = data.get('class_id')
            
            if not member_id or not class_id:
                self._send_error(400, "Missing required fields: member_id, class_id")
                return
            
            # TODO: Call use case
            self._send_json_response(201, {
                'message': 'Booking created',
                'member_id': member_id,
                'class_id': class_id
            })
            
        except ValueError as e:
            self._send_error(400, str(e))
        except Exception as e:
            print(f"Unexpected error: {e}")
            self._send_error(500, "Internal server error")
```

**`Content-Length` header** - Tells us how many bytes to read from the request body.

**`self.rfile.read(content_length)`** - Reads that many bytes from the request stream.

**`decode('utf-8')`** - Converts bytes to a string.

**`json.loads()`** - Parses JSON string into a Python dict.

In Flask, this is just `request.json`. In FastAPI, it's automatic if you use Pydantic models. But the work is the same—they're reading Content-Length, reading from the socket, and parsing JSON.

We're doing it manually to see what's happening. Once you've seen it, you'll appreciate frameworks more. And you'll understand why they sometimes fail—network issues, encoding problems, malformed JSON.

### Calling Use Cases

This is where the interface layer connects to the application layer. This is the architectural boundary.

Why is this important? Because this is where framework code meets your business logic. If you understand this boundary, you can switch frameworks without touching your domain or application layers. The interface is the only thing that changes.

```python
from domain.exceptions import (
    ClassFullException,
    InsufficientCreditsException,
    BookingNotFoundException
)


class GymBookingHandler(BaseHTTPRequestHandler):
    # Class attributes for dependencies (injected before server starts)
    book_class_use_case = None
    cancel_booking_use_case = None
    get_classes_use_case = None
    
    def _handle_create_booking(self):
        """Handle POST /api/bookings - Book a member into a class."""
        try:
            # 1. Parse request (interface layer responsibility)
            data = self._parse_json_body()
            
            # 2. Extract and validate input
            member_id = data.get('member_id')
            class_id = data.get('class_id')
            
            if not member_id or not class_id:
                self._send_error(400, "Missing required fields")
                return
            
            # 3. Call use case (application layer)
            # This is where interface meets application
            booking = self.book_class_use_case.execute(member_id, class_id)
            
            # 4. Translate domain object to JSON (interface layer responsibility)
            response = {
                'id': booking.id,
                'member_id': booking.member_id,
                'class_id': booking.class_id,
                'status': booking.status.value,
                'booked_at': booking.booked_at.isoformat()
            }
            
            # 5. Send response with appropriate status code
            self._send_json_response(201, response)
            
        except ValueError as e:
            # Domain validation errors → 400 Bad Request
            self._send_error(400, str(e))
        except InsufficientCreditsException as e:
            # Business rule violation → 400 Bad Request
            self._send_error(400, str(e))
        except ClassFullException as e:
            # Business rule violation → 400 Bad Request
            self._send_error(400, str(e))
        except Exception as e:
            # Unexpected errors → 500 Internal Server Error
            print(f"Unexpected error: {e}")
            self._send_error(500, "Internal server error")
```

Notice the clear responsibilities:

**Interface layer (HTTP handler):**
- Parses JSON from request
- Validates required fields are present
- Calls the use case
- Translates domain objects to JSON
- Maps exceptions to HTTP status codes

**Application layer (use case):**
- Validates business rules
- Orchestrates domain objects
- Handles persistence
- Sends notifications

**Domain layer (entities):**
- Enforces invariants
- Implements business logic

The interface layer is thin. It's almost mechanical:
1. Parse input
2. Call use case
3. Format output
4. Map errors to status codes

No business logic. No decisions about capacity or credits. Just translation and routing.

This pattern applies to every interface—CLI, GraphQL, message queues. Parse input. Call use case. Format output. Map errors. That's it.

### Dependency Injection

How do we give the handler access to use cases?

We can't instantiate use cases inside the handler—they need repositories, which need database connections. We need to inject dependencies from the outside.

Why this matters: Dependency injection is what makes our architecture work. The interface doesn't create its dependencies. It receives them. This keeps the interface layer thin and testable.

For `BaseHTTPRequestHandler`, we use class attributes:

```python
# interface/api.py
class GymBookingHandler(BaseHTTPRequestHandler):
    """HTTP handler with injected dependencies."""
    
    # Class attributes set before server starts
    book_class_use_case = None
    cancel_booking_use_case = None
    get_classes_use_case = None
    get_member_use_case = None
    
    def _handle_create_booking(self):
        if self.book_class_use_case is None:
            self._send_error(500, "Server not properly configured")
            return
        
        # Use the injected use case
        booking = self.book_class_use_case.execute(member_id, class_id)
        # ...


def create_handler(book_class_uc, cancel_booking_uc, get_classes_uc, get_member_uc):
    """Factory function to create handler class with dependencies injected."""
    handler = GymBookingHandler
    handler.book_class_use_case = book_class_uc
    handler.cancel_booking_use_case = cancel_booking_uc
    handler.get_classes_use_case = get_classes_uc
    handler.get_member_use_case = get_member_uc
    return handler
```

Then in the main script, we wire everything together:

```python
# main.py
from http.server import HTTPServer
from infrastructure.database import create_database, get_connection
from infrastructure.repositories import (
    SqliteMemberRepository,
    SqliteFitnessClassRepository,
    SqliteBookingRepository
)
from infrastructure.services import EmailNotificationService
from application.use_cases import (
    BookClassUseCase,
    CancelBookingUseCase,
    GetClassesUseCase,
    GetMemberUseCase
)
from interface.api import create_handler


def main():
    # 1. Set up infrastructure
    create_database()  # Create tables if they don't exist
    db_connection = get_connection()
    
    # 2. Create repositories
    member_repo = SqliteMemberRepository(db_connection)
    class_repo = SqliteFitnessClassRepository(db_connection)
    booking_repo = SqliteBookingRepository(db_connection)
    
    # 3. Create services
    notification_service = EmailNotificationService(
        smtp_host='localhost',
        smtp_port=1025  # Development SMTP server
    )
    
    # 4. Create use cases (application layer)
    book_class_uc = BookClassUseCase(
        member_repo,
        class_repo,
        booking_repo,
        notification_service
    )
    
    cancel_booking_uc = CancelBookingUseCase(
        booking_repo,
        member_repo,
        notification_service
    )
    
    get_classes_uc = GetClassesUseCase(class_repo)
    get_member_uc = GetMemberUseCase(member_repo)
    
    # 5. Create HTTP handler with dependencies (interface layer)
    handler_class = create_handler(
        book_class_uc,
        cancel_booking_uc,
        get_classes_uc,
        get_member_uc
    )
    
    # 6. Start HTTP server
    server = HTTPServer(('localhost', 8000), handler_class)
    print("🚀 Gym Booking API running on http://localhost:8000")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server")
        server.shutdown()


if __name__ == '__main__':
    main()
```

This is dependency injection at the composition root. We build the object graph from the outside in:

```
Infrastructure (SQLite repos, SMTP service)
    ↓
Application (Use cases)
    ↓
Interface (HTTP handlers)
    ↓
HTTP Server
```

Dependencies flow inward. The domain knows nothing about databases or HTTP. The application knows nothing about JSON or routing. The interface layer depends on application, but application doesn't depend on interface.

This is the Dependency Inversion Principle in action. High-level policy (use cases) doesn't depend on low-level details (HTTP). Both depend on abstractions (ports).

## Complete API Implementation

Let's build out the complete handlers for our gym booking API. We'll implement four key endpoints:

1. **POST /api/bookings** - Book a class
2. **DELETE /api/bookings/{id}** - Cancel a booking
3. **GET /api/classes** - List available classes
4. **GET /api/members/{id}** - Get member details

Here's the full implementation:

```python
# interface/api.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import re
from datetime import datetime
from typing import Optional

from domain.exceptions import (
    ClassFullException,
    InsufficientCreditsException,
    BookingNotFoundException,
    MemberNotFoundException,
    ClassNotFoundException
)


class GymBookingHandler(BaseHTTPRequestHandler):
    """HTTP request handler for gym booking API."""
    
    # Dependencies injected via class attributes
    book_class_use_case = None
    cancel_booking_use_case = None
    get_classes_use_case = None
    get_member_use_case = None
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._handle_root()
        elif self.path == '/api/classes':
            self._handle_list_classes()
        elif self.path.startswith('/api/members/'):
            self._handle_get_member()
        else:
            self._send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/bookings':
            self._handle_create_booking()
        else:
            self._send_error(404, "Not Found")
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        if self.path.startswith('/api/bookings/'):
            self._handle_delete_booking()
        else:
            self._send_error(404, "Not Found")
    
    # ===== Request Handlers =====
    
    def _handle_root(self):
        """Handle GET / - API information."""
        response = {
            'name': 'Gym Booking API',
            'version': '1.0.0',
            'endpoints': {
                'bookings': {
                    'create': 'POST /api/bookings',
                    'cancel': 'DELETE /api/bookings/{id}'
                },
                'classes': {
                    'list': 'GET /api/classes'
                },
                'members': {
                    'get': 'GET /api/members/{id}'
                }
            }
        }
        self._send_json_response(200, response)
    
    def _handle_list_classes(self):
        """Handle GET /api/classes - List all fitness classes."""
        try:
            classes = self.get_classes_use_case.execute()
            
            # Translate domain objects to JSON
            response = [
                {
                    'id': cls.id,
                    'name': cls.name,
                    'day': cls.day,
                    'start_time': cls.start_time,
                    'capacity': cls.capacity,
                    'current_bookings': len(cls.bookings),
                    'available_spots': cls.capacity - len(cls.bookings)
                }
                for cls in classes
            ]
            
            self._send_json_response(200, response)
            
        except Exception as e:
            print(f"Error listing classes: {e}")
            self._send_error(500, "Internal server error")
    
    def _handle_get_member(self):
        """Handle GET /api/members/{id} - Get member details."""
        # Extract member ID from path
        match = re.match(r'/api/members/([^/]+)$', self.path)
        if not match:
            self._send_error(400, "Invalid member ID format")
            return
        
        member_id = match.group(1)
        
        try:
            member = self.get_member_use_case.execute(member_id)
            
            # Translate domain object to JSON
            response = {
                'id': member.id,
                'name': member.name,
                'email': member.email.value,
                'membership_type': member.membership_type.value,
                'credits_remaining': member.credits
            }
            
            self._send_json_response(200, response)
            
        except MemberNotFoundException as e:
            self._send_error(404, str(e))
        except Exception as e:
            print(f"Error getting member: {e}")
            self._send_error(500, "Internal server error")
    
    def _handle_create_booking(self):
        """Handle POST /api/bookings - Book a member into a class."""
        try:
            data = self._parse_json_body()
            
            # Extract and validate required fields
            member_id = data.get('member_id')
            class_id = data.get('class_id')
            
            if not member_id or not class_id:
                self._send_error(400, "Missing required fields: member_id, class_id")
                return
            
            # Execute use case (application layer handles all business logic)
            booking = self.book_class_use_case.execute(member_id, class_id)
            
            # Translate domain object to JSON
            response = {
                'id': booking.id,
                'member_id': booking.member_id,
                'class_id': booking.class_id,
                'status': booking.status.value,
                'booked_at': booking.booked_at.isoformat()
            }
            
            # 201 Created with Location header
            self.send_response(201)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Location', f'/api/bookings/{booking.id}')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except ValueError as e:
            self._send_error(400, str(e))
        except InsufficientCreditsException as e:
            self._send_error(400, f"Insufficient credits: {e}")
        except ClassFullException as e:
            self._send_error(400, f"Class is full: {e}")
        except MemberNotFoundException as e:
            self._send_error(404, str(e))
        except ClassNotFoundException as e:
            self._send_error(404, str(e))
        except Exception as e:
            print(f"Unexpected error creating booking: {e}")
            self._send_error(500, "Internal server error")
    
    def _handle_delete_booking(self):
        """Handle DELETE /api/bookings/{id} - Cancel a booking."""
        # Extract booking ID from path
        match = re.match(r'/api/bookings/([^/]+)$', self.path)
        if not match:
            self._send_error(400, "Invalid booking ID format")
            return
        
        booking_id = match.group(1)
        
        try:
            # Execute use case
            self.cancel_booking_use_case.execute(booking_id)
            
            # 204 No Content - successful deletion
            self.send_response(204)
            self.end_headers()
            
        except BookingNotFoundException as e:
            self._send_error(404, str(e))
        except ValueError as e:
            self._send_error(400, str(e))
        except Exception as e:
            print(f"Unexpected error canceling booking: {e}")
            self._send_error(500, "Internal server error")
    
    # ===== Helper Methods =====
    
    def _parse_json_body(self) -> dict:
        """Parse JSON from request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        
        if content_length == 0:
            return {}
        
        body_bytes = self.rfile.read(content_length)
        body_str = body_bytes.decode('utf-8')
        
        try:
            return json.loads(body_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    def _send_json_response(self, status_code: int, data: dict):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response_body = json.dumps(data, indent=2)
        self.wfile.write(response_body.encode('utf-8'))
    
    def _send_error(self, status_code: int, message: str):
        """Send an error response."""
        error_response = {
            'error': message,
            'status': status_code
        }
        self._send_json_response(status_code, error_response)
    
    def log_message(self, format, *args):
        """Override to customize logging format."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def create_handler(book_class_uc, cancel_booking_uc, get_classes_uc, get_member_uc):
    """
    Factory function to create handler class with dependencies injected.
    
    Args:
        book_class_uc: BookClassUseCase instance
        cancel_booking_uc: CancelBookingUseCase instance
        get_classes_uc: GetClassesUseCase instance
        get_member_uc: GetMemberUseCase instance
    
    Returns:
        Handler class with dependencies set
    """
    handler = GymBookingHandler
    handler.book_class_use_case = book_class_uc
    handler.cancel_booking_use_case = cancel_booking_uc
    handler.get_classes_use_case = get_classes_uc
    handler.get_member_use_case = get_member_uc
    return handler
```

Let's examine what makes this a good interface layer implementation:

**1. Thin handlers** - Each handler method is 10-30 lines. Most of it is translation. The actual work happens in use cases.

**2. Clear separation** - Interface handles HTTP. Application handles business logic. No mixing.

**3. Consistent error mapping:**
- Domain exceptions (`InsufficientCreditsException`) → 400 Bad Request
- Not found exceptions → 404 Not Found
- Unexpected errors → 500 Internal Server Error

**4. Proper HTTP semantics:**
- POST returns 201 Created with Location header
- DELETE returns 204 No Content on success
- GET returns 200 OK with data

**5. Type translation:**
- Domain enums → strings (`status.value`)
- Datetime objects → ISO 8601 strings (`booked_at.isoformat()`)
- Value objects → primitives (`email.value`)

This is what frameworks do for you automatically. But because we've built it manually, we understand what's happening. When you use FastAPI later, you'll recognize all of this.

## What Frameworks Give You

Now that you've seen the manual approach, let's look at what frameworks provide. Here's the same API in FastAPI:

```python
# interface/fastapi_app.py
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Gym Booking API", version="1.0.0")


# Request/Response models
class BookingRequest(BaseModel):
    member_id: str
    class_id: str


class BookingResponse(BaseModel):
    id: str
    member_id: str
    class_id: str
    status: str
    booked_at: str


class ClassResponse(BaseModel):
    id: str
    name: str
    day: str
    start_time: str
    capacity: int
    current_bookings: int
    available_spots: int


# Dependency injection for use cases
# (In real FastAPI, you'd use Depends() for this)
book_class_use_case = None
cancel_booking_use_case = None
get_classes_use_case = None


@app.get("/")
def root():
    return {
        "name": "Gym Booking API",
        "version": "1.0.0"
    }


@app.get("/api/classes", response_model=List[ClassResponse])
def list_classes():
    try:
        classes = get_classes_use_case.execute()
        
        return [
            ClassResponse(
                id=cls.id,
                name=cls.name,
                day=cls.day,
                start_time=cls.start_time,
                capacity=cls.capacity,
                current_bookings=len(cls.bookings),
                available_spots=cls.capacity - len(cls.bookings)
            )
            for cls in classes
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(request: BookingRequest):
    try:
        booking = book_class_use_case.execute(
            request.member_id,
            request.class_id
        )
        
        return BookingResponse(
            id=booking.id,
            member_id=booking.member_id,
            class_id=booking.class_id,
            status=booking.status.value,
            booked_at=booking.booked_at.isoformat()
        )
        
    except InsufficientCreditsException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ClassFullException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MemberNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(booking_id: str):
    try:
        cancel_booking_use_case.execute(booking_id)
    except BookingNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**What FastAPI handles for you:**

1. **Routing** - `@app.post()` decorator instead of manual path matching
2. **Request parsing** - `request: BookingRequest` automatically parses JSON
3. **Validation** - Pydantic validates required fields, types, formats
4. **Serialization** - `response_model=BookingResponse` auto-converts to JSON
5. **Status codes** - `status_code=201` instead of `send_response(201)`
6. **Documentation** - Automatic OpenAPI/Swagger docs at `/docs`
7. **Type safety** - Type hints provide IDE autocomplete and validation
8. **Async support** - Can use `async def` for concurrent request handling

**What stays the same:**

- The use case is still called the same way
- Domain logic is unchanged
- Error handling is similar (exceptions → HTTP errors)
- The architecture is identical

The interface layer is still just translation. FastAPI just automates the boilerplate.

This is why understanding the fundamentals matters. When you switch to FastAPI, you're not learning something completely different. You're learning a more convenient way to express the same concepts.

## Testing the Interface Layer

We test the interface layer at two levels:

**1. Unit tests** - Test handler logic without HTTP

**2. Integration tests** - Test actual HTTP requests

### Unit Testing Handlers

We can test the handler methods directly by mocking the use case:

```python
# tests/unit/interface/test_api_handlers.py
from unittest.mock import Mock, MagicMock
import json
from io import BytesIO

from interface.api import GymBookingHandler
from domain.entities import Booking, BookingStatus
from domain.exceptions import ClassFullException
from datetime import datetime


def test_create_booking_success():
    """Test successful booking creation returns 201 with booking data."""
    # Mock use case
    mock_use_case = Mock()
    mock_booking = Booking(
        booking_id='B001',
        member_id='M001',
        class_id='C001',
        status=BookingStatus.CONFIRMED,
        booked_at=datetime(2024, 1, 15, 10, 0)
    )
    mock_use_case.execute.return_value = mock_booking
    
    # Create handler with mocked use case
    handler = GymBookingHandler()
    handler.book_class_use_case = mock_use_case
    
    # Mock the request
    handler.path = '/api/bookings'
    handler.headers = {'Content-Length': '45'}
    handler.rfile = BytesIO(b'{"member_id": "M001", "class_id": "C001"}')
    
    # Mock the response writer
    response_data = BytesIO()
    handler.wfile = response_data
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    
    # Execute
    handler._handle_create_booking()
    
    # Verify use case was called correctly
    mock_use_case.execute.assert_called_once_with('M001', 'C001')
    
    # Verify HTTP response
    handler.send_response.assert_called_with(201)
    
    # Verify JSON response
    response_json = json.loads(response_data.getvalue().decode())
    assert response_json['id'] == 'B001'
    assert response_json['member_id'] == 'M001'
    assert response_json['status'] == 'CONFIRMED'


def test_create_booking_class_full():
    """Test booking when class is full returns 400 error."""
    # Mock use case that raises exception
    mock_use_case = Mock()
    mock_use_case.execute.side_effect = ClassFullException("Yoga is at capacity")
    
    handler = GymBookingHandler()
    handler.book_class_use_case = mock_use_case
    
    # Mock request
    handler.path = '/api/bookings'
    handler.headers = {'Content-Length': '45'}
    handler.rfile = BytesIO(b'{"member_id": "M001", "class_id": "C001"}')
    
    # Mock response
    response_data = BytesIO()
    handler.wfile = response_data
    handler.send_response = Mock()
    handler.send_header = Mock()
    handler.end_headers = Mock()
    
    # Execute
    handler._handle_create_booking()
    
    # Verify 400 response
    handler.send_response.assert_called_with(400)
    
    # Verify error message
    response_json = json.loads(response_data.getvalue().decode())
    assert 'error' in response_json
    assert 'full' in response_json['error'].lower()
```

These tests verify the handler logic without running an actual HTTP server. Fast, focused, isolated.

### Integration Testing with HTTP

For integration tests, we start the server and make real HTTP requests:

```python
# tests/integration/test_api_integration.py
import requests
import pytest
import threading
import time
from http.server import HTTPServer

from interface.api import create_handler
from application.use_cases import BookClassUseCase
from infrastructure.repositories import InMemoryMemberRepository
# ... other imports


@pytest.fixture
def api_server():
    """Start API server in background thread for testing."""
    # Create in-memory repositories for testing
    member_repo = InMemoryMemberRepository()
    class_repo = InMemoryFitnessClassRepository()
    booking_repo = InMemoryBookingRepository()
    notification_service = MockNotificationService()
    
    # Seed test data
    member_repo.save(Member('M001', 'Alice', 'alice@gym.com', credits=10))
    class_repo.save(FitnessClass('C001', 'Yoga', capacity=5))
    
    # Create use cases
    book_class_uc = BookClassUseCase(
        member_repo, class_repo, booking_repo, notification_service
    )
    # ... other use cases
    
    # Create handler
    handler_class = create_handler(book_class_uc, ...)
    
    # Start server in background
    server = HTTPServer(('localhost', 8888), handler_class)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    # Wait for server to start
    time.sleep(0.1)
    
    yield 'http://localhost:8888'
    
    # Cleanup
    server.shutdown()


def test_create_booking_integration(api_server):
    """Test full booking workflow via HTTP."""
    response = requests.post(
        f'{api_server}/api/bookings',
        json={'member_id': 'M001', 'class_id': 'C001'}
    )
    
    assert response.status_code == 201
    
    data = response.json()
    assert data['member_id'] == 'M001'
    assert data['class_id'] == 'C001'
    assert data['status'] == 'CONFIRMED'
    assert 'id' in data


def test_list_classes_integration(api_server):
    """Test listing classes via HTTP."""
    response = requests.get(f'{api_server}/api/classes')
    
    assert response.status_code == 200
    
    classes = response.json()
    assert isinstance(classes, list)
    assert len(classes) > 0
    assert classes[0]['name'] == 'Yoga'


def test_booking_error_handling(api_server):
    """Test error responses are properly formatted."""
    response = requests.post(
        f'{api_server}/api/bookings',
        json={'member_id': 'INVALID'}  # Missing class_id
    )
    
    assert response.status_code == 400
    
    error = response.json()
    assert 'error' in error
    assert 'required' in error['error'].lower()
```

Integration tests verify the full stack: HTTP parsing, routing, use case execution, JSON serialization, error handling. They're slower but catch issues unit tests miss.

## The Dependency Rule Still Applies

Remember the dependency rule from Chapter 4:

**Dependencies point inward. Outer layers depend on inner layers, never the reverse.**

```
┌─────────────────────────────────────┐
│      Interface Layer                │
│         ↓ depends on                │
├─────────────────────────────────────┤
│      Application Layer              │
│         ↓ depends on                │
├─────────────────────────────────────┤
│      Domain Layer                   │
│         ↑ implemented by            │
├─────────────────────────────────────┤
│      Infrastructure Layer           │
└─────────────────────────────────────┘
```

**Interface layer depends on application:**
```python
# Interface knows about use cases
from application.use_cases import BookClassUseCase

booking = self.book_class_use_case.execute(member_id, class_id)
```

**Application does NOT depend on interface:**
```python
# Use case knows nothing about HTTP
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str) -> Booking:
        # No mention of requests, responses, JSON, or status codes
        member = self.member_repository.get_by_id(member_id)
        # ...
```

**Domain knows nothing about any outer layer:**
```python
# Member doesn't know about databases, HTTP, or JSON
class Member:
    def deduct_credit(self):
        if self.credits <= 0:
            raise InsufficientCreditsException()
        self.credits -= 1
```

This separation is what makes the architecture flexible:

- **Change the interface** (HTTP → CLI) without touching use cases
- **Change the infrastructure** (SQLite → PostgreSQL) without touching domain
- **Test use cases** without HTTP servers or databases
- **Deploy differently** (monolith → microservices) without rewriting business logic

The dependency rule isn't academic theory. It's practical design that makes change easier.

## Other Interface Types

HTTP APIs aren't the only way users interact with systems. The same use cases can be exposed through different interfaces:

### Command-Line Interface

```python
# interface/cli.py
import argparse

from application.use_cases import BookClassUseCase
# ... other imports


def main():
    parser = argparse.ArgumentParser(description='Gym Booking System')
    subparsers = parser.add_subparsers(dest='command')
    
    # Book command
    book_parser = subparsers.add_parser('book', help='Book a class')
    book_parser.add_argument('--member-id', required=True)
    book_parser.add_argument('--class-id', required=True)
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a booking')
    cancel_parser.add_argument('--booking-id', required=True)
    
    args = parser.parse_args()
    
    # Set up dependencies (same as HTTP)
    book_class_uc = setup_book_class_use_case()
    
    # Route to appropriate handler
    if args.command == 'book':
        try:
            booking = book_class_uc.execute(args.member_id, args.class_id)
            print(f"✓ Booking created: {booking.id}")
        except ClassFullException:
            print("✗ Error: Class is full")
            exit(1)
    
    elif args.command == 'cancel':
        # ...
```

Same use cases. Different interface. No HTTP. No JSON. Just command-line arguments and print statements.

### GraphQL Interface

```python
# interface/graphql_schema.py
import graphene

from application.use_cases import BookClassUseCase
# ... other imports


class BookingType(graphene.ObjectType):
    id = graphene.String()
    member_id = graphene.String()
    class_id = graphene.String()
    status = graphene.String()


class BookClass(graphene.Mutation):
    class Arguments:
        member_id = graphene.String(required=True)
        class_id = graphene.String(required=True)
    
    booking = graphene.Field(BookingType)
    
    def mutate(self, info, member_id, class_id):
        # Same use case!
        booking = book_class_use_case.execute(member_id, class_id)
        
        return BookClass(booking=BookingType(
            id=booking.id,
            member_id=booking.member_id,
            class_id=booking.class_id,
            status=booking.status.value
        ))


class Mutation(graphene.ObjectType):
    book_class = BookClass.Field()


schema = graphene.Schema(mutation=Mutation)
```

Different query language. Same architecture. Same use cases. Just different translation.

**The pattern is consistent:**

1. Parse input (HTTP JSON, CLI args, GraphQL query)
2. Call use case
3. Translate output (JSON, terminal text, GraphQL response)

The interface layer is always just an adapter between the outside world and your application.

## When to Use a Framework

Now that you understand what frameworks do, when should you use them?

**Use a framework when:**

✅ **Building production APIs** - Frameworks are battle-tested and handle edge cases you haven't thought of

✅ **You need performance** - FastAPI with async/await handles thousands of concurrent requests

✅ **You want auto-documentation** - OpenAPI/Swagger docs are incredibly valuable for API consumers

✅ **Your team knows it** - Shared knowledge means faster development and easier onboarding

✅ **Rapid prototyping matters** - Less boilerplate means shipping features faster

✅ **You need middleware** - CORS, authentication, rate limiting, logging—frameworks provide these

**Use native/minimal approach when:**

✅ **Learning fundamentals** - Understanding what frameworks abstract is educational

✅ **Very simple needs** - A three-endpoint internal service doesn't need FastAPI

✅ **Maximum control required** - Custom protocols or unusual requirements

✅ **Unusual format** - Not HTTP? Not JSON? You might need manual handling

**The pragmatic answer:** In production, use FastAPI or Flask. But understand what they're doing for you. Then you'll use them intentionally, not blindly.

## Transitioning to a Framework

When you're ready to switch from our manual HTTP handling to FastAPI, the change is minimal:

**What stays the same:**
- Use cases (unchanged)
- Domain logic (unchanged)
- Repositories (unchanged)
- Application layer architecture (unchanged)

**What changes:**
- Interface layer implementation (HTTP handlers → FastAPI routes)
- Dependency injection mechanism (class attributes → FastAPI Depends)
- Configuration setup (manual → FastAPI startup events)

Here's the migration:

```python
# Before (manual)
class GymBookingHandler(BaseHTTPRequestHandler):
    book_class_use_case = None
    
    def _handle_create_booking(self):
        data = self._parse_json_body()
        booking = self.book_class_use_case.execute(...)
        self._send_json_response(201, {...})

# After (FastAPI)
@app.post("/api/bookings", status_code=201)
def create_booking(
    request: BookingRequest,
    use_case: BookClassUseCase = Depends(get_book_class_use_case)
):
    booking = use_case.execute(request.member_id, request.class_id)
    return BookingResponse(...)
```

The architecture is identical. Only the interface layer changed. This is exactly why we separated concerns.

You can have both interfaces running simultaneously:

```python
# Run both HTTP and FastAPI side-by-side
if __name__ == '__main__':
    # Same use cases for both interfaces
    book_class_uc = setup_use_cases()
    
    # Manual HTTP on port 8000
    manual_handler = create_handler(book_class_uc, ...)
    threading.Thread(
        target=HTTPServer(('localhost', 8000), manual_handler).serve_forever
    ).start()
    
    # FastAPI on port 8001
    import uvicorn
    uvicorn.run(app, host='localhost', port=8001)
```

Two interfaces. One application. This is the power of separation.

## What We Have Now

Let's take stock. We've completed the interface layer:

**Our system now has:**
1. **Multiple interfaces using same core:**
   - REST API (HTTP endpoints for mobile app)
   - CLI (command-line for staff)
   - Both call the same use cases

2. **Clean separation:**
   - Domain: Business rules (no HTTP knowledge)
   - Application: Use case orchestration (no JSON knowledge)
   - Infrastructure: Database/email adapters
   - Interface: HTTP/CLI translation layer

3. **Framework-independent architecture:**
   - Understand what frameworks do (routing, validation, serialization)
   - Can use vanilla Python HTTP or migrate to FastAPI
   - Core unchanged regardless of framework choice

4. **Complete stack:**
```
┌──────────────────────────────────────────┐
│      Interface Layer                     │
│   ┌────────────┐    ┌────────────┐      │
│   │ REST API   │    │    CLI     │      │
│   └─────┬──────┘    └─────┬──────┘      │
├─────────┼─────────────────┼──────────────┤
│         ▼                 ▼              │
│      Application Layer                   │
│   (Use Cases with Ports)                 │
├──────────────────────────────────────────┤
│      Domain Layer                        │
│   (Entities + Value Objects)             │
├──────────────────────────────────────────┤
│      Infrastructure Layer                │
│   (Adapters: SQLite, SMTP, InMemory)    │
└──────────────────────────────────────────┘
```

**What we gained:**
- Users can actually access the system!
- Mobile app uses REST API
- Staff use CLI for admin tasks
- Same business logic powers both
- Easy to add GraphQL, WebSockets, etc.
- Framework changes don't affect core

**The complete journey:**
1. Ch 1: Simple procedural CLI
2. Ch 2: SOLID classes
3. Ch 3: TDD with tests
4. Ch 4: Layered architecture
5. Ch 5: Rich domain model
6. Ch 6: Formalized use cases
7. Ch 7: Hexagonal architecture (ports & adapters)
8. Ch 8: Multiple interfaces (REST API + CLI)

We now have a **complete, well-architected system** from the ground up!

## Transition to Chapter 9

We've learned all the pieces individually:
- SOLID principles (Chapter 2)
- Test-Driven Development (Chapter 3)
- Layered architecture (Chapter 4)
- Rich domain modeling (Chapter 5)
- Use cases and orchestration (Chapter 6)
- Ports and adapters (Chapter 7)
- Interface layer (Chapter 8)

But how do they all work together? How do you apply everything when building a real feature from scratch?

In Chapter 9, we'll walk through **building a complete feature** using all these patterns:

**New requirement:** "Premium members should get priority on waitlists. When a class opens up, promote premium members before basic members."

We'll:
- Use TDD to drive the feature
- Model it in the domain (value objects, business rules)
- Create the use case (orchestration)
- Update repositories (ports & adapters)
- Expose via both API and CLI (interface layer)
- Show how everything fits together

This is **Putting It All Together**—the complete workflow from requirement to deployment.

## Key Takeaways

**1. The interface layer is translation, not logic**
- Parse external format → internal format
- Call use cases
- Translate results → external format
- Map exceptions → status codes/error formats

**2. Keep it thin**
- No business logic in handlers
- No orchestration in routes
- Just translation and routing

**3. Understand what frameworks do**
- Request parsing
- Routing
- Validation
- Serialization
- Error handling
- Documentation

**4. Architecture is framework-agnostic**
- Domain doesn't know about HTTP
- Application doesn't know about JSON
- Infrastructure doesn't know about routing
- Only interface knows about external protocols

**5. Dependencies point inward**
- Interface → Application → Domain
- Never the reverse
- This enables flexibility

**6. Use frameworks in production**
- But understand what they're doing
- Then you use them intentionally
- And you can switch when needed

You now have a complete system: domain, application, infrastructure, and interface. Every layer has a clear responsibility. Dependencies flow inward. Business logic is isolated from technical details.

In the next chapter, we'll see how all these pieces work together by building a complete feature from requirements to deployment.

---

**Exercises:**

1. Add a `GET /api/bookings/{id}` endpoint to retrieve booking details
2. Implement request logging middleware manually (before trying framework middleware)
3. Add basic authentication using HTTP headers
4. Build a simple CLI interface for the same use cases
5. Migrate one endpoint to FastAPI and compare the code
6. Write integration tests that verify HTTP status codes match business exceptions
7. Add pagination to `GET /api/classes` (query params: `?page=1&limit=10`)
8. Implement content negotiation (support both JSON and XML responses based on Accept header)

**Further Reading:**

- [PEP 333 - Python Web Server Gateway Interface](https://peps.python.org/pep-0333/) - The WSGI standard
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Modern Python web framework
- [RESTful API Design Best Practices](https://restfulapi.net/) - HTTP API conventions
- [Fielding's REST Dissertation](https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm) - The original REST architecture
