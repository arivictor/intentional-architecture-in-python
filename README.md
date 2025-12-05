# Intentional Architecture in Python

> DRAFT NOTE: A layered approch toa rchitecture where we learn and apply the minimal required architecture to build something viable. The appendix chapters then build upon the main book with advanced topics.

TODO:

Part I: Foundations (Build the Mindset)**

**Chapter 0: Introduction** ✅ (Keep as-is)
- Sets expectations perfectly

**Chapter 1: Philosophy** ✅ (Keep as-is)  
- Essential vs accidental complexity
- Architecture as communication

**Chapter 2: SOLID Principles** ✅ (Keep as-is)
- Foundation for all architectural decisions

---

### **Part II: Test-Driven Mindset** 

**Chapter 3: Test-Driven Development** ⚠️ **MISSING - ADD THIS**
- *Why TDD before architecture*
- Red-Green-Refactor cycle
- Start with the gym booking system's simplest feature
- Show how TDD drives design decisions
- Testing pyramid: unit, integration, end-to-end
- **This is critical** - TDD influences everything that follows


Part III: Architectural Patterns (Build the Structure)**

**Chapter 4: Layers & Clean Architecture** ← *Rename current Chapter 3*
- Four layers: Domain, Application, Infrastructure, Interface
- Dependency rule
- Why layers matter
- **Expand**: Show how TDD from Chapter 3 naturally leads to layered design

**Chapter 5: Domain Modeling (DDD)** ← *Keep current Chapter 4*
- Entities, Value Objects, Aggregates
- Rich domain models
- Keep all the excellent DDD content you have

**Chapter 6: Use Cases & Application Layer** ← *Keep current Chapter 5*
- Orchestration without business logic
- Cross-aggregate coordination
- Perfect as-is

**Chapter 7: Ports & Adapters (Hexagonal Architecture)** ← *Keep current Chapter 6*
- Dependency inversion in practice
- Repository patterns
- Swappable adapters
- This chapter is comprehensive - keep it!

Part IV: Integration (Bring It All Together)**

**Chapter 8: Putting It All Together** ⚠️ **MISSING - ADD THIS**

This is where you show the complete picture:

```/dev/null/example.md#L1-25
# Chapter 8: Putting It All Together

## The Complete Gym Booking System

Take readers through building a complete feature end-to-end:

1. **Start with a user story**: "Premium members get waitlist priority"
2. **TDD**: Write tests first for the new requirement
3. **Domain**: Model Waitlist as an aggregate
4. **SOLID**: Apply OCP for priority strategies
5. **Layers**: Keep business logic in domain
6. **Use Cases**: Orchestrate waitlist processing
7. **Ports/Adapters**: Add notification adapter for waitlist
8. **Testing**: Show full test coverage

## Evolution of the Codebase
- Show before/after comparisons
- Discuss refactoring decisions
- Demonstrate how architecture made the change easy
- Cost-benefit analysis

## Running the Complete Application
- Full directory structure
- Dependency injection container
- Configuration management
- Deployment considerations

📊 Recommended Chapter Flow Logic

```/dev/null/flow.md#L1-20
Introduction → Philosophy → SOLID
         ↓
     Learn TDD (drives everything else)
         ↓
     Layers (where does code live?)
         ↓
     Domain (the heart of the system)
         ↓
     Use Cases (orchestrating domain)
         ↓
     Ports & Adapters (decoupling infrastructure)
         ↓
     Integration (seeing the complete picture)
         ↓
     Appendices (reference material)

💡 Additional Recommendations

1. **Add "Project Evolution" boxes** throughout to show:
   - "In Chapter 3, we had X"
   - "Now in Chapter 5, we've evolved to Y"
   - "This change was easy because we followed principle Z"

2. **Include refactoring examples** showing:
   - Code smell → Recognition → Solution
   - Before/after with tests proving behavior didn't change

3. **Add a "When NOT to use this" section** in each pattern chapter
   - You do this sometimes - make it consistent
   - Helps readers apply judgment, not just follow rules

4. **Consider adding**: 
   - Chapter on handling errors/exceptions architecturally
   - Section on performance considerations
   - Async/concurrent patterns if relevant
---

Learn architecture by understanding how, when, and why to apply various architectural patterns and philosophies. Understand how they work together to create a minimal yet viable architecural pattern you can easily apply to small and large projects.

<p align="center">
  <img src="cover.png" alt="book cover - intentional architecture in python" width="300">
</p>

<p align="center">
  <a href="">Buy on Amazon</a> | <a href="">Buy on Lulu</a> | <a href="#contents">Read free online</a>
</p>

## Contents

* [Introduction](book/0-introduction.md)

Chapters:

* Chapter 1 [Philosophy](book/1-philosophy.md)
* Chapter 2 [SOLID](book/2-solid.md)
* Chapter 3 [Layers](book/3-layers.md)
* Chapter 4 [Entities](book/4-entities.md)
* Chapter 5 [Aggregates](book/5-aggregates.md)
* Chapter 6 [Use Cases](book/6-use-cases.md)
* Chapter 7 [Ports](book/7-ports.md)
* Chapter 8 [Adapters](book/8-adapters.md)

## License

This book is licensed under [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/).

**Copyright © 2025 Ari Laverty**

You are free to share this work for non-commercial purposes with attribution. You may not create derivative works or use this material commercially without permission.

See [LICENSE](LICENSE) for full terms.
