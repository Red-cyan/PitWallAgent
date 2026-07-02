# RFC-001: Technology Stack Selection

**Project:** PitWall Agent

**RFC ID:** RFC-001

**Author:** Red Cyan

**Status:** Accepted

**Created:** 2026-07-01

**Last Updated:** 2026-07-01

---

# 1. Abstract

This RFC defines the complete technology stack for the PitWall Agent project.

The objective is to establish a modern, production-ready architecture capable of supporting:

- AI Agent orchestration
- Retrieval-Augmented Generation (RAG)
- External Tool Calling
- Long-term maintainability
- Containerized deployment
- Continuous Integration
- Future scalability

Technology choices are evaluated not only by functionality, but also by ecosystem maturity, community adoption, production readiness, and long-term maintenance cost.

---

# 2. Design Goals

The selected technology stack must satisfy the following goals.

## G1 Production Ready

Every selected framework must already be widely used in production.

Experimental frameworks should be avoided unless they provide overwhelming advantages.

---

## G2 AI Native

The stack should prioritize AI application development rather than traditional CRUD systems.

The architecture should naturally support:

- LLM
- Agent
- RAG
- Tool Calling
- Streaming
- Memory

---

## G3 Modular

Every component should be independently replaceable.

Example:

PostgreSQL + pgvector

↓

PGVector

should require minimal code modifications.

---

## G4 Open Source Friendly

The project should avoid excessive vendor lock-in.

Developers should be able to deploy the entire project locally.

---

## G5 Interview Friendly

The technology stack should represent current industry best practices.

Each component should have clear architectural justification.

---

# 3. Project Constraints

The following constraints influence technology selection.

## C1

Single developer.

---

## C2

Cross-platform development.

Windows

Linux

macOS

must all be supported.

---

## C3

Deployment target:

Linux Server

Docker Compose

---

## C4

Python ecosystem.

The backend should remain entirely Python-based.

---

## C5

Support future microservice evolution.

---

# 4. Overall Stack

| Layer | Technology |
|---------|------------|
| Frontend | Next.js |
| Backend | FastAPI |
| Agent | LangGraph |
| LLM | OpenAI Compatible API |
| Embedding | BAAI BGE-M3 |
| Vector DB | PostgreSQL + pgvector |
| Database | PostgreSQL |
| Cache | Redis |
| Package Manager | uv |
| Deployment | Docker Compose |
| Reverse Proxy | Nginx |
| Monitoring | LangSmith |
| CI/CD | GitHub Actions |

---

# 5. Python Version Selection

## Candidates

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13

---

## Evaluation

### Python 3.10

Pros

- Stable
- Wide compatibility

Cons

- Becoming outdated

---

### Python 3.11

Pros

- Faster execution
- Excellent compatibility

Cons

- Will gradually become legacy during the project lifecycle.

---

### Python 3.12

Pros

- Excellent ecosystem support
- Mature AI library compatibility
- Long maintenance window
- Better performance than 3.11

Cons

- A few older libraries still require updates.

---

### Python 3.13

Pros

Latest language improvements.

Cons

Many AI libraries still lag behind.

Risk of dependency incompatibility.

---

## Decision

Python **3.12** is selected.

---

## Rationale

Python 3.12 provides the best balance between

- stability
- performance
- compatibility
- future support

---

# 6. Dependency Management

## Candidates

- pip
- Poetry
- uv
- Conda

---

## pip

Advantages

- Universal

Disadvantages

- Slow
- No lock file
- Weak dependency resolution

---

## Poetry

Advantages

- Mature
- Lock file

Disadvantages

- Slow dependency solving
- Larger learning curve

---

## Conda

Advantages

Scientific computing

GPU

Disadvantages

Not ideal for backend services.

Heavyweight.

Poor Docker experience.

---

## uv

Advantages

- Extremely fast
- Native pyproject.toml support
- Lock file
- Excellent Docker support
- Excellent developer experience

Disadvantages

Smaller ecosystem than pip (rapidly growing).

---

## Decision

**uv**

---

## Rationale

uv represents the current direction of Python dependency management.

Its performance and developer experience significantly outperform traditional solutions while remaining fully compatible with the Python ecosystem.

---

# 7. Backend Framework

## Candidates

- FastAPI
- Flask
- Django

---

## Flask

Advantages

Simple.

Flexible.

Disadvantages

Requires significant manual integration.

Not ideal for AI service development.

---

## Django

Advantages

Powerful ORM

Admin

Authentication

Disadvantages

Heavyweight.

Designed for CRUD applications.

---

## FastAPI

Advantages

Native async

Excellent OpenAPI support

High performance

Modern dependency injection

Strong AI ecosystem adoption

Streaming support

---

## Decision

FastAPI

---

## Rationale

FastAPI has become the de facto standard for modern AI backends due to its asynchronous architecture and excellent developer experience.

---

# 8. Agent Framework

## Problem Statement

PitWall Agent is fundamentally an AI Agent system rather than a traditional chatbot.

The framework must support:

- Complex workflows
- Tool Calling
- Conditional routing
- Multi-step reasoning
- Memory
- Human-in-the-loop (future)
- Streaming
- Interrupt/Resume
- State persistence

The framework should also remain maintainable as the project evolves into a multi-agent architecture.

---

## Candidates

- LangChain AgentExecutor
- LangGraph
- CrewAI
- AutoGen
- PydanticAI
- Semantic Kernel

---

## Option 1 — LangChain AgentExecutor

### Advantages

- Simple to learn
- Rich ecosystem
- Large community
- Good for quick prototypes

### Disadvantages

- Limited workflow customization
- Difficult to visualize execution
- Poor support for complex state transitions
- Not designed for production-grade agent orchestration

### Conclusion

Suitable for demos and simple assistants.

Not suitable for this project.

---

## Option 2 — LangGraph

### Advantages

- Explicit graph-based workflow
- Stateful execution
- Conditional routing
- Retry support
- Checkpoint support
- Streaming support
- Human-in-the-loop ready
- Excellent LangSmith integration

### Disadvantages

- Steeper learning curve
- More boilerplate than AgentExecutor

### Conclusion

Designed specifically for production AI Agents.

---

## Option 3 — CrewAI

### Advantages

- Very easy multi-agent setup
- Role-based collaboration
- Good readability

### Disadvantages

- Limited workflow flexibility
- Less mature ecosystem
- Difficult to customize deeply

### Conclusion

Excellent for demonstrations.

Less suitable for highly customized production systems.

---

## Option 4 — AutoGen

### Advantages

- Strong multi-agent conversation model
- Microsoft-backed
- Flexible communication

### Disadvantages

- Conversation-centric architecture
- Less suitable for deterministic workflows
- More difficult to debug

### Conclusion

Better suited for research scenarios.

---

## Option 5 — PydanticAI

### Advantages

- Excellent type safety
- Modern API design
- Strong Pydantic integration

### Disadvantages

- Ecosystem still developing
- Limited workflow capabilities compared with LangGraph

### Conclusion

Very promising, but not mature enough for this project.

---

## Option 6 — Semantic Kernel

### Advantages

- Enterprise-oriented
- Microsoft ecosystem
- Planner support

### Disadvantages

- Smaller Python community
- Better fit for .NET environments

---

## Decision

LangGraph

---

## Rationale

LangGraph provides the strongest balance between flexibility, observability, ecosystem maturity, and production readiness.

Its graph-based execution model naturally represents complex workflows such as:

User

↓

Intent Recognition

↓

Planner

↓

Tool Selection

↓

Tool Execution

↓

Reasoning

↓

Response

without hiding execution logic inside opaque agent loops.

---

## Trade-offs

Choosing LangGraph increases implementation complexity.

However, the explicit workflow significantly improves:

- maintainability
- debugging
- testing
- observability

These benefits outweigh the additional development effort.

---

## Future Evolution

Future versions may introduce:

- Multi-Agent Supervisor
- Distributed Agents
- Human Approval Nodes
- Parallel Tool Execution

without redesigning the architecture.

---

# 9. LLM Provider

## Problem Statement

PitWall Agent should not be tightly coupled to a single LLM provider.

Developers should be free to switch models according to:

- performance
- cost
- latency
- deployment environment

---

## Candidates

- OpenAI
- Anthropic
- Google Gemini
- DeepSeek
- Qwen
- Local Models

---

## Evaluation Criteria

The provider must support:

- Tool Calling
- Streaming
- Long Context
- Stable API
- OpenAI-Compatible Interface (preferred)

---

## Decision

OpenAI-Compatible API

---

## Rationale

Instead of binding the system to a specific vendor, PitWall Agent adopts an abstraction layer based on the OpenAI API specification.

This enables seamless switching between providers with minimal code changes.

Supported providers include:

- OpenAI
- Azure OpenAI
- DeepSeek
- Qwen
- SiliconFlow
- OpenRouter
- Ollama (via compatibility layer)

---

## Benefits

- Vendor independence
- Lower migration cost
- Easier experimentation
- Better cost optimization

---

# 10. Embedding Model

## Problem Statement

The RAG subsystem requires a multilingual embedding model capable of accurately retrieving:

- FIA regulations
- Technical documents
- News articles
- Mixed English terminology

---

## Candidates

- OpenAI text-embedding-3-large
- BAAI BGE-M3
- Jina Embeddings
- GTE
- E5

---

## Evaluation Criteria

The embedding model should provide:

- High retrieval accuracy
- English terminology support
- Multilingual capability
- Local deployment
- Active maintenance

---

## Option Comparison

### OpenAI Embeddings

Advantages

- Excellent quality
- Fully managed

Disadvantages

- API cost
- Vendor lock-in
- No offline deployment

---

### Jina

Advantages

- High quality
- Modern architecture

Disadvantages

- Smaller community

---

### GTE

Advantages

- Lightweight

Disadvantages

- Slightly weaker multilingual performance

---

### BGE-M3

Advantages

- State-of-the-art retrieval quality
- Dense + Sparse + Multi-vector capability
- Strong multilingual support
- Local deployment
- Excellent benchmark results
- Active open-source maintenance

Disadvantages

- Larger model size

---

## Decision

BAAI BGE-M3

---

## Rationale

BGE-M3 provides one of the strongest open-source retrieval performances currently available while supporting multiple retrieval paradigms.

It aligns well with the project's hybrid retrieval strategy.

---

# 11. Vector Database

## Problem Statement

The project requires a scalable vector database capable of storing hundreds of thousands of document chunks while supporting efficient similarity search.

---

## Candidates

- Chroma
- PostgreSQL + pgvector
- PGVector
- Pinecone
- Weaviate

---

## Chroma

Advantages

- Very easy setup
- Lightweight

Disadvantages

- Limited scalability
- Better suited for prototypes

---

## Pinecone

Advantages

- Managed service
- High availability

Disadvantages

- Paid
- Vendor lock-in
- Internet dependency

---

## Weaviate

Advantages

- Rich feature set

Disadvantages

- Higher operational complexity

---

## PGVector

Advantages

- PostgreSQL integration
- Simple deployment

Disadvantages

- Lower retrieval performance for very large datasets

---

## PostgreSQL + pgvector

Advantages

- Designed specifically for vector search
- High performance
- Mature indexing strategies
- Active open-source community
- Strong enterprise adoption

Disadvantages

- Slightly higher deployment complexity

---

## Decision

PostgreSQL + pgvector

---

## Rationale

PostgreSQL + pgvector offers the best balance between scalability, performance, and production readiness.

It also allows future migration toward distributed deployment if document volume increases significantly.

---

## Future Evolution

If document volume remains relatively small (<100K chunks), a future lightweight deployment profile may optionally support PGVector for simplified infrastructure.

