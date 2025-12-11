# Chapter 12: Layered Architecture

## Introduction

**Layered Architecture** organizes code into horizontal layers, where each layer has a specific responsibility and depends only on layers below it. The most common pattern has four layers: **Presentation** (UI/API), **Application** (use cases), **Domain** (business logic), and **Infrastructure** (databases, external services).

This separation of concerns makes code easier to understand, test, and maintain. Business logic stays pure and independent of frameworks, while infrastructure details are isolated in specific layers.

## The Problem

Mixing concerns across your codebase makes it hard to change and test.

**Symptoms:**
- SQL queries mixed with business logic
- Business rules scattered across UI code
- Can't test without database or web framework
- Changing database requires touching business logic
- Duplicate logic across different entry points (API, CLI, UI)
- Unclear where new code should go

**Example of the problem:**

```python
from flask import Flask, request, jsonify
import sqlite3
import hashlib

app = Flask(__name__)

@app.route('/posts', methods=['POST'])
def create_post():
    """Everything mixed together - UI, logic, database."""
    # Parse request (presentation concern)
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    author_id = data.get('author_id')
    
    # Validation (business rule) mixed with framework code
    if not title or len(title) < 3:
        return jsonify({'error': 'Title too short'}), 400
    if not content or len(content) < 10:
        return jsonify({'error': 'Content too short'}), 400
    
    # Business logic mixed with database code
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Check author exists (business rule + database)
    cursor.execute('SELECT id FROM users WHERE id = ?', (author_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Author not found'}), 404
    
    # Generate slug (business logic)
    slug = title.lower().replace(' ', '-')
    post_id = hashlib.md5(slug.encode()).hexdigest()[:8]
    
    # Insert post (database)
    cursor.execute(
        'INSERT INTO posts (id, title, content, author_id, slug) VALUES (?, ?, ?, ?, ?)',
        (post_id, title, content, author_id, slug)
    )
    conn.commit()
    conn.close()
    
    # Return response (presentation)
    return jsonify({'id': post_id, 'title': title, 'slug': slug}), 201

@app.route('/posts/<post_id>/publish', methods=['POST'])
def publish_post(post_id):
    """Duplicate logic - validation and database access repeated."""
    conn = sqlite3.connect('blog.db')
    cursor = conn.cursor()
    
    # Same database pattern repeated
    cursor.execute('SELECT id, title FROM posts WHERE id = ?', (post_id,))
    post = cursor.fetchone()
    
    if not post:
        conn.close()
        return jsonify({'error': 'Post not found'}), 404
    
    # Business rule hardcoded in endpoint
    cursor.execute('UPDATE posts SET status = ? WHERE id = ?', ('published', post_id))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'published'}), 200
```

**Problems:**
- Can't test business logic without Flask and SQLite
- Business rules (validation, slug generation) mixed with infrastructure
- Duplicate database connection code
- Changing from SQLite to PostgreSQL requires modifying every endpoint
- No way to reuse logic in CLI tool or background job
- Business rules scattered - unclear what makes a valid post

## The Pattern

**Layered Architecture:** Organize code into distinct layers with clear responsibilities.

### The Four Layers

**1. Presentation Layer (Interface/API)**
- Handles HTTP requests/responses
- Input parsing and output formatting
- Routes to appropriate use cases
- No business logic

**2. Application Layer (Use Cases)**
- Orchestrates domain objects
- Implements application-specific workflows
- Transaction boundaries
- Delegates to domain for business rules

**3. Domain Layer (Business Logic)**
- Core business entities and value objects
- Business rules and invariants
- Framework-independent
- Pure business logic

**4. Infrastructure Layer (Persistence/External Services)**
- Database access
- External API calls
- File system operations
- Framework-specific code

### Dependency Rule

```
Presentation → Application → Domain
                ↓
        Infrastructure
```

Upper layers depend on lower layers. Domain has no dependencies. Infrastructure implements interfaces defined by domain/application.

## Implementation

```python
# =============================================================================
# DOMAIN LAYER - Pure business logic, no dependencies
# =============================================================================

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import re


@dataclass
class Post:
    """
    Domain entity representing a blog post.
    
    Contains business logic and invariants.
    """
    id: str
    title: str
    content: str
    author_id: str
    slug: str
    status: str = 'draft'
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            object.__setattr__(self, 'created_at', datetime.now())
        
        # Invariants - business rules
        self.validate()
    
    def validate(self) -> None:
        """Enforce business rules."""
        if not self.title or len(self.title) < 3:
            raise ValueError("Title must be at least 3 characters")
        if not self.content or len(self.content) < 10:
            raise ValueError("Content must be at least 10 characters")
        if not self.slug:
            raise ValueError("Slug is required")
    
    def publish(self) -> None:
        """Business rule: publish post."""
        if self.status == 'published':
            raise ValueError("Post already published")
        object.__setattr__(self, 'status', 'published')
    
    def unpublish(self) -> None:
        """Business rule: unpublish post."""
        if self.status != 'published':
            raise ValueError("Post not published")
        object.__setattr__(self, 'status', 'draft')
    
    @staticmethod
    def generate_slug(title: str) -> str:
        """Business logic: create URL-friendly slug from title."""
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        return slug


from abc import ABC, abstractmethod
from typing import List


class PostRepository(ABC):
    """
    Domain interface for post persistence.
    
    Domain defines what it needs, infrastructure implements it.
    """
    
    @abstractmethod
    def save(self, post: Post) -> None:
        """Save a post."""
        pass
    
    @abstractmethod
    def find_by_id(self, post_id: str) -> Optional[Post]:
        """Find post by ID."""
        pass
    
    @abstractmethod
    def find_by_slug(self, slug: str) -> Optional[Post]:
        """Find post by slug."""
        pass
    
    @abstractmethod
    def list_all(self, status: Optional[str] = None) -> List[Post]:
        """List all posts, optionally filtered by status."""
        pass


# =============================================================================
# APPLICATION LAYER - Use cases and workflows
# =============================================================================

import uuid


class CreatePostUseCase:
    """
    Application service for creating posts.
    
    Orchestrates domain objects and infrastructure.
    """
    
    def __init__(self, post_repository: PostRepository):
        self.post_repository = post_repository
    
    def execute(self, title: str, content: str, author_id: str) -> Post:
        """
        Create a new blog post.
        
        Args:
            title: Post title
            content: Post content
            author_id: Author user ID
            
        Returns:
            Created post
            
        Raises:
            ValueError: If validation fails
        """
        # Generate ID and slug (application logic)
        post_id = str(uuid.uuid4())[:8]
        slug = Post.generate_slug(title)
        
        # Create domain entity (validates automatically)
        post = Post(
            id=post_id,
            title=title,
            content=content,
            author_id=author_id,
            slug=slug
        )
        
        # Persist using repository
        self.post_repository.save(post)
        
        return post


class PublishPostUseCase:
    """Use case for publishing a post."""
    
    def __init__(self, post_repository: PostRepository):
        self.post_repository = post_repository
    
    def execute(self, post_id: str) -> Post:
        """
        Publish a post.
        
        Args:
            post_id: ID of post to publish
            
        Returns:
            Published post
            
        Raises:
            ValueError: If post not found or already published
        """
        # Load from repository
        post = self.post_repository.find_by_id(post_id)
        if not post:
            raise ValueError(f"Post {post_id} not found")
        
        # Execute business logic
        post.publish()
        
        # Persist changes
        self.post_repository.save(post)
        
        return post


class ListPostsUseCase:
    """Use case for listing posts."""
    
    def __init__(self, post_repository: PostRepository):
        self.post_repository = post_repository
    
    def execute(self, status: Optional[str] = None) -> List[Post]:
        """List posts, optionally filtered by status."""
        return self.post_repository.list_all(status)


# =============================================================================
# INFRASTRUCTURE LAYER - Database implementation
# =============================================================================


class InMemoryPostRepository(PostRepository):
    """
    In-memory implementation of PostRepository.
    
    Infrastructure detail - can be swapped for SQLite, PostgreSQL, etc.
    """
    
    def __init__(self):
        self._posts: dict[str, Post] = {}
    
    def save(self, post: Post) -> None:
        """Save post to memory."""
        self._posts[post.id] = post
    
    def find_by_id(self, post_id: str) -> Optional[Post]:
        """Find post by ID."""
        return self._posts.get(post_id)
    
    def find_by_slug(self, slug: str) -> Optional[Post]:
        """Find post by slug."""
        for post in self._posts.values():
            if post.slug == slug:
                return post
        return None
    
    def list_all(self, status: Optional[str] = None) -> List[Post]:
        """List all posts."""
        posts = list(self._posts.values())
        if status:
            posts = [p for p in posts if p.status == status]
        return posts


# =============================================================================
# PRESENTATION LAYER - API endpoints
# =============================================================================


class BlogAPI:
    """
    Presentation layer for blog API.
    
    Handles HTTP concerns, delegates to use cases.
    """
    
    def __init__(
        self,
        create_post_use_case: CreatePostUseCase,
        publish_post_use_case: PublishPostUseCase,
        list_posts_use_case: ListPostsUseCase
    ):
        self.create_post = create_post_use_case
        self.publish_post = publish_post_use_case
        self.list_posts = list_posts_use_case
    
    def handle_create_post(self, request_data: dict) -> tuple[dict, int]:
        """
        Handle POST /posts request.
        
        Returns: (response_body, status_code)
        """
        try:
            # Parse input
            title = request_data.get('title')
            content = request_data.get('content')
            author_id = request_data.get('author_id')
            
            # Delegate to use case
            post = self.create_post.execute(title, content, author_id)
            
            # Format response
            return {
                'id': post.id,
                'title': post.title,
                'slug': post.slug,
                'status': post.status,
                'created_at': post.created_at.isoformat()
            }, 201
            
        except ValueError as e:
            return {'error': str(e)}, 400
    
    def handle_publish_post(self, post_id: str) -> tuple[dict, int]:
        """
        Handle POST /posts/{id}/publish request.
        
        Returns: (response_body, status_code)
        """
        try:
            post = self.publish_post.execute(post_id)
            return {
                'id': post.id,
                'status': post.status
            }, 200
            
        except ValueError as e:
            return {'error': str(e)}, 404
    
    def handle_list_posts(self, status: Optional[str] = None) -> tuple[dict, int]:
        """
        Handle GET /posts request.
        
        Returns: (response_body, status_code)
        """
        posts = self.list_posts.execute(status)
        
        return {
            'posts': [
                {
                    'id': p.id,
                    'title': p.title,
                    'slug': p.slug,
                    'status': p.status,
                    'created_at': p.created_at.isoformat()
                }
                for p in posts
            ]
        }, 200


# =============================================================================
# COMPOSITION ROOT - Wire everything together
# =============================================================================

if __name__ == "__main__":
    # Infrastructure
    repository = InMemoryPostRepository()
    
    # Application
    create_post_uc = CreatePostUseCase(repository)
    publish_post_uc = PublishPostUseCase(repository)
    list_posts_uc = ListPostsUseCase(repository)
    
    # Presentation
    api = BlogAPI(create_post_uc, publish_post_uc, list_posts_uc)
    
    # Use the API
    print("=== Create Post ===")
    response, status = api.handle_create_post({
        'title': 'My First Blog Post',
        'content': 'This is the content of my first blog post. It has enough characters.',
        'author_id': 'user-123'
    })
    print(f"Status: {status}")
    print(f"Response: {response}")
    print()
    
    post_id = response['id']
    
    print("=== Publish Post ===")
    response, status = api.handle_publish_post(post_id)
    print(f"Status: {status}")
    print(f"Response: {response}")
    print()
    
    print("=== List Published Posts ===")
    response, status = api.handle_list_posts(status='published')
    print(f"Status: {status}")
    print(f"Response: {response}")
```

## Explanation

### Layer Separation

Each layer has a clear responsibility:

- **Domain (Post, PostRepository interface):** Business logic, no dependencies
- **Application (Use cases):** Workflows, orchestration
- **Infrastructure (InMemoryPostRepository):** Database implementation
- **Presentation (BlogAPI):** HTTP handling

### Dependency Inversion

The domain defines `PostRepository` interface. Infrastructure implements it:

```python
# Domain defines what it needs
class PostRepository(ABC):
    @abstractmethod
    def save(self, post: Post): pass

# Infrastructure implements it
class InMemoryPostRepository(PostRepository):
    def save(self, post: Post):
        self._posts[post.id] = post
```

### Testability

Each layer can be tested independently:

```python
# Test domain without database or HTTP
post = Post("id", "Title Here", "Content here...", "author-1", "title-here")
post.publish()

# Test application with fake repository
fake_repo = FakePostRepository()
use_case = CreatePostUseCase(fake_repo)
use_case.execute("Title", "Content", "author-1")

# Test presentation with fake use cases
fake_uc = FakeCreatePostUseCase()
api = BlogAPI(fake_uc, ...)
api.handle_create_post({...})
```

### Business Logic in Domain

Business rules live in the domain layer:

```python
class Post:
    def publish(self):
        if self.status == 'published':
            raise ValueError("Already published")
        self.status = 'published'
```

Not scattered across endpoints or database code.

## Benefits

**1. Separation of Concerns**

Each layer has one responsibility. Database logic isn't mixed with business rules or HTTP handling.

**2. Testability**

Test each layer independently. Test business logic without database. Test use cases with fake repository.

**3. Flexibility**

Swap implementations without affecting other layers:

```python
# Development
dev_repo = InMemoryPostRepository()

# Production
prod_repo = PostgreSQLPostRepository()
```

**4. Reusability**

Use cases can be called from different interfaces (REST API, CLI, background job):

```python
# Same use case, different interfaces
# REST API
api.handle_create_post({...})

# CLI tool
cli.create_post_command(title, content, author)

# Background job
job.process_scheduled_post(title, content, author)
```

**5. Maintainability**

Clear structure makes it obvious where code belongs. Need to add validation? Domain layer. Change response format? Presentation layer.

## Trade-offs

**When NOT to use layered architecture:**

**1. Simple CRUD Applications**

For basic data entry with minimal logic, layers add unnecessary complexity:

```python
# Overkill for simple CRUD
# Just write: app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    db.save(data)
```

**2. Prototypes**

When exploring a domain, start simple. Add layers when structure emerges.

**3. Overhead**

Layers add:
- More files and classes
- Indirection (harder to trace code flow)
- Need to understand layer boundaries
- More boilerplate

**4. Small Scripts**

For one-off scripts or simple tools, direct approach is fine:

```python
# Simple script - no layers needed
import requests
data = requests.get('api.example.com').json()
for item in data:
    process(item)
```

## Testing

```python
import pytest


def test_post_creation_validates_title():
    """Test that post validates title length."""
    with pytest.raises(ValueError, match="Title must be at least 3 characters"):
        Post("id", "ab", "Content here", "author", "slug")


def test_post_publish_changes_status():
    """Test publishing a post."""
    post = Post("id", "Title", "Content here", "author", "slug")
    
    post.publish()
    
    assert post.status == 'published'


def test_cannot_publish_already_published_post():
    """Test that publishing twice raises error."""
    post = Post("id", "Title", "Content here", "author", "slug")
    post.publish()
    
    with pytest.raises(ValueError, match="already published"):
        post.publish()


def test_create_post_use_case():
    """Test creating a post through use case."""
    repository = InMemoryPostRepository()
    use_case = CreatePostUseCase(repository)
    
    post = use_case.execute("My Title", "Content goes here", "author-123")
    
    assert post.title == "My Title"
    assert post.slug == "my-title"
    assert post.status == "draft"
    
    # Verify saved to repository
    saved_post = repository.find_by_id(post.id)
    assert saved_post is not None
    assert saved_post.title == "My Title"


def test_publish_post_use_case():
    """Test publishing post through use case."""
    repository = InMemoryPostRepository()
    
    # Create post first
    post = Post("post-1", "Title", "Content here", "author", "slug")
    repository.save(post)
    
    # Publish it
    use_case = PublishPostUseCase(repository)
    published_post = use_case.execute("post-1")
    
    assert published_post.status == "published"


def test_publish_nonexistent_post_raises_error():
    """Test that publishing nonexistent post raises error."""
    repository = InMemoryPostRepository()
    use_case = PublishPostUseCase(repository)
    
    with pytest.raises(ValueError, match="not found"):
        use_case.execute("nonexistent")


def test_list_posts_use_case():
    """Test listing posts."""
    repository = InMemoryPostRepository()
    
    # Add some posts
    post1 = Post("1", "Title 1", "Content 1", "author", "slug-1", status="published")
    post2 = Post("2", "Title 2", "Content 2", "author", "slug-2", status="draft")
    repository.save(post1)
    repository.save(post2)
    
    use_case = ListPostsUseCase(repository)
    
    # List all
    all_posts = use_case.execute()
    assert len(all_posts) == 2
    
    # Filter by status
    published = use_case.execute(status="published")
    assert len(published) == 1
    assert published[0].id == "1"


def test_api_create_post():
    """Test API endpoint for creating post."""
    repository = InMemoryPostRepository()
    create_uc = CreatePostUseCase(repository)
    publish_uc = PublishPostUseCase(repository)
    list_uc = ListPostsUseCase(repository)
    api = BlogAPI(create_uc, publish_uc, list_uc)
    
    response, status = api.handle_create_post({
        'title': 'Test Post',
        'content': 'Test content here',
        'author_id': 'author-1'
    })
    
    assert status == 201
    assert response['title'] == 'Test Post'
    assert response['slug'] == 'test-post'
    assert response['status'] == 'draft'


def test_api_create_post_invalid_data():
    """Test API handles invalid data."""
    repository = InMemoryPostRepository()
    create_uc = CreatePostUseCase(repository)
    publish_uc = PublishPostUseCase(repository)
    list_uc = ListPostsUseCase(repository)
    api = BlogAPI(create_uc, publish_uc, list_uc)
    
    response, status = api.handle_create_post({
        'title': 'ab',  # Too short
        'content': 'Test content',
        'author_id': 'author-1'
    })
    
    assert status == 400
    assert 'error' in response
```

## Common Mistakes

**1. Skipping the Domain Layer**

Don't put business logic in application or presentation:

```python
# Bad - business logic in use case
class CreatePostUseCase:
    def execute(self, title, content, author_id):
        if len(title) < 3:  # Business rule in application layer
            raise ValueError("Title too short")

# Good - business logic in domain
class Post:
    def validate(self):
        if len(self.title) < 3:  # Business rule in domain
            raise ValueError("Title too short")
```

**2. Leaky Layers**

Don't let infrastructure details leak into domain:

```python
# Bad - SQLAlchemy in domain
from sqlalchemy import Column, String

class Post(Base):  # Coupled to SQLAlchemy
    __tablename__ = 'posts'
    id = Column(String, primary_key=True)

# Good - pure domain
@dataclass
class Post:
    id: str
    title: str
```

**3. Fat Application Layer**

Application layer should orchestrate, not implement business logic:

```python
# Bad - business logic in application
class CreatePostUseCase:
    def execute(self, title, content):
        # Complex validation and transformation
        # This should be in Post class

# Good - thin application layer
class CreatePostUseCase:
    def execute(self, title, content):
        post = Post(...)  # Domain validates itself
        self.repository.save(post)
```

**4. Direct Cross-Layer Access**

Don't bypass layers:

```python
# Bad - presentation directly accessing infrastructure
@app.route('/posts')
def list_posts():
    posts = database.query("SELECT * FROM posts")  # Skip application layer

# Good - go through layers
@app.route('/posts')
def list_posts():
    use_case = ListPostsUseCase(repository)
    posts = use_case.execute()
```

## Related Patterns

- **Chapter 8 (Dependency Inversion):** Enables testable layers
- **Chapter 13 (Hexagonal Architecture):** Alternative architectural pattern
- **Chapter 14 (Repository):** Infrastructure layer implementation
- **Chapter 17 (CQRS):** Can be implemented within layered architecture

## Summary

Layered Architecture organizes code into horizontal layers with clear responsibilities: Presentation handles I/O, Application orchestrates workflows, Domain contains business logic, and Infrastructure manages external concerns. Each layer depends only on layers below it, with the domain being dependency-free.

Use layered architecture for applications with significant business logic that need to be testable, maintainable, and flexible. Skip it for simple CRUD apps, prototypes, or scripts where the overhead outweighs the benefits. Layered architecture provides a proven structure that scales from small applications to large enterprise systems.

## Further Reading

- Fowler, Martin. *Patterns of Enterprise Application Architecture*. Addison-Wesley, 2002. (Chapter 1: Layering)
- Evans, Eric. *Domain-Driven Design*. Addison-Wesley, 2003. (Chapter 4: Isolating the Domain)
- Martin, Robert C. *Clean Architecture*. Prentice Hall, 2017.
- Nilsson, Jimmy. *Applying Domain-Driven Design and Patterns*. Addison-Wesley, 2006.
- Microsoft. "Common web application architectures." docs.microsoft.com.
