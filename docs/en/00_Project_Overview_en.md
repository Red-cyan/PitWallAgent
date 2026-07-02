# PitWall Agent

> A production-grade AI Agent for Formula One, integrating real-time race intelligence, FIA regulation retrieval, Retrieval-Augmented Generation (RAG), and intelligent tool orchestration.

---

# Document Information

| Item | Value |
|------|-------|
| Project Name | PitWall Agent |
| Version | 1.0 |
| Status | Architecture Freeze V1 |
| Type | Project Overview |
| Target Audience | Developers, Architects, Interviewers |
| Repository | PitWall-Agent |

---

# 1. Vision

Formula One generates an enormous amount of information every race weekend.

Fans continuously switch between official websites, news outlets, technical regulations, timing pages, social media, and community discussions to understand what is happening.

While Large Language Models can answer general Formula One questions, they suffer from three major limitations:

- Lack of real-time knowledge
- Inability to reliably reference official FIA regulations
- Hallucinations when discussing race incidents or technical rules

PitWall Agent aims to solve these problems by combining LLM reasoning with authoritative external knowledge sources.

Instead of relying solely on the language model, PitWall Agent dynamically retrieves information from multiple trusted systems, allowing the model to reason over verified data before generating a response.

The result is an AI-native Formula One assistant capable of delivering accurate, explainable, and up-to-date answers.

---

# 2. Project Objectives

PitWall Agent is designed around the following objectives.

## O1 Accurate Information Retrieval

The system should retrieve factual information from trusted external sources whenever possible instead of relying solely on the LLM's internal knowledge.

Examples include:

- FIA Sporting Regulations
- FIA Technical Regulations
- Official race schedules
- Driver standings
- Constructor standings
- Official news
- Team announcements

---

## O2 Explainable Responses

Every regulation-related answer should include clear citations.

Whenever the system answers questions based on official FIA documents, it must provide:

- Document name
- Article number
- Page number
- Supporting excerpts when appropriate

This allows users to verify every answer independently.

---

## O3 Intelligent Tool Orchestration

Rather than building multiple independent AI agents, PitWall Agent adopts a single-agent architecture.

The Agent dynamically selects and orchestrates specialized tools according to the user's intent.

Examples include:

- News Retrieval Tool
- Race Information Tool
- Regulation Retrieval Tool (RAG)
- Strategy Analysis Tool

This architecture simplifies maintenance while providing excellent extensibility.

---

## O4 Production Readiness

The project is not intended as a proof-of-concept demonstration.

Instead, it follows production-oriented engineering practices, including:

- Layered architecture
- Modular design
- Structured logging
- Containerized deployment
- Continuous integration
- Automated testing
- Configuration management
- Observability

---

## O5 Extensibility

The architecture should allow future capabilities to be added without modifying existing business logic.

Examples include:

- Telemetry analysis
- Voice interaction
- Image understanding
- Multi-modal inputs
- Push notifications
- Multi-language support

The core architecture should remain stable as new tools are introduced.

---

# 3. Project Scope

PitWall Agent focuses on assisting Formula One users through intelligent reasoning over multiple knowledge sources.

The project currently includes the following capability domains:

## Real-Time News

Retrieve and summarize current Formula One news from trusted sources.

Typical questions include:

- What happened in the paddock today?
- What is Ferrari working on this weekend?
- Has the FIA announced any new directives?

---

## Race Intelligence

Provide official race information including:

- Calendar
- Weekend schedule
- Session times
- Driver standings
- Constructor standings
- Race classifications
- Sprint results

---

## FIA Regulation Question Answering

Allow users to query official FIA documents using natural language.

Examples include:

- What is Parc Fermé?
- Why was the driver penalized?
- What are the plank wear limits?
- What defines an unsafe release?

The system retrieves relevant document sections using Retrieval-Augmented Generation (RAG) before generating an answer.

---

## Strategy Analysis

Combine regulation knowledge with race information to analyze strategic decisions.

Example questions include:

- Should Ferrari pit during a Safety Car?
- Why did McLaren choose the undercut?
- Was the Virtual Safety Car advantageous?

These answers rely on both retrieved knowledge and LLM reasoning.

---

# 4. Core Principles

The architecture of PitWall Agent is guided by the following principles.

## AI-Native

Artificial Intelligence is the core of the system rather than an additional feature.

The application is designed around an Agent Runtime capable of reasoning, planning, and orchestrating external tools instead of simply generating text.

---

## Retrieval Before Generation

Whenever factual information is required, the system retrieves external knowledge before invoking the language model.

The LLM should reason over verified context instead of relying on its internal memory.

This principle significantly reduces hallucinations and improves answer reliability.

---

## Tool-Oriented Reasoning

Large Language Models should not directly access external resources.

Instead, every external capability is encapsulated as a Tool.

Examples include:

- News Tool
- Race Tool
- Regulation Tool
- Strategy Tool

The Agent Runtime determines which tools are required to answer each request.

---

## Explainability

Answers should always be traceable.

Whenever knowledge is retrieved from official documents, responses should include citations whenever possible.

Users should understand not only the answer itself, but also where the answer comes from.

---

## Separation of Responsibilities

Each subsystem has a clearly defined responsibility.

The frontend focuses on user interaction.

The backend exposes application services.

The Agent Runtime performs reasoning.

Tools communicate with external systems.

Infrastructure manages storage and deployment.

No component should perform responsibilities outside its designated boundary.

---

## Extensibility

New capabilities should be introduced by adding new Tools or Services instead of modifying existing components.

The architecture favors composition over modification.

---

# 5. Target Users

PitWall Agent is designed for users with different levels of Formula One knowledge.

## Formula One Fans

Users who follow Formula One throughout the season and want quick, reliable answers about races, drivers, and teams.

Typical needs include:

- Daily news
- Race schedules
- Standings
- Incident explanations

---

## Technical Enthusiasts

Users interested in the engineering side of Formula One.

Typical needs include:

- Technical regulations
- Aerodynamics
- Vehicle design
- FIA interpretations
- Technical directives

---

## Students

Students studying software engineering, AI, motorsport engineering, or related disciplines.

The project also serves as a reference implementation for modern AI Agent systems.

---

## Content Creators

Writers, bloggers, and video creators who need rapid access to accurate Formula One information supported by authoritative references.

---

# 6. System Capabilities

PitWall Agent currently provides the following core capabilities.

## News Retrieval

Retrieve the latest Formula One news from trusted external sources.

The Agent summarizes and organizes information into concise responses.

---

## Race Information

Provide official race schedules, standings, classifications, and weekend information.

---

## Regulation Retrieval

Retrieve relevant sections from FIA Sporting Regulations and Technical Regulations using Retrieval-Augmented Generation.

---

## Intelligent Question Answering

Answer natural language questions by combining:

- Tool outputs
- Retrieved documents
- Language model reasoning

---

## Multi-Turn Conversation

Maintain conversational context during a session.

The Agent should understand follow-up questions without requiring users to repeat previous information.

---

## Citation Support

Whenever information originates from official documentation, the response should include supporting references.

---

# 7. High-Level Architecture

PitWall Agent adopts a layered architecture.

```

Presentation Layer

↓

Application Layer

↓

Agent Runtime

↓

Tool Layer

↓

Knowledge & Infrastructure

```

The responsibilities of each layer are summarized below.

## Presentation Layer

Responsible for all user-facing interfaces.

Examples include:

- Web UI
- Chat interface
- Streaming output
- Markdown rendering

---

## Application Layer

Coordinates business workflows.

Responsibilities include:

- API endpoints
- Session management
- Authentication
- Request validation
- Service orchestration

The Application Layer is intentionally independent of Agent logic.

---

## Agent Runtime

The Agent Runtime is the reasoning engine of the system.

Implemented using LangGraph, it is responsible for:

- Intent analysis
- Planning
- Tool selection
- Tool orchestration
- Context construction
- Response generation

The Agent Runtime never communicates directly with databases or external APIs.

All external interactions occur through the Tool Layer.

---

## Tool Layer

The Tool Layer encapsulates every external capability.

Examples include:

- News Tool
- Race Tool
- Regulation Tool
- Strategy Tool

Each Tool provides a stable interface regardless of the underlying implementation.

---

## Knowledge & Infrastructure Layer

Responsible for persistent storage and knowledge retrieval.

Components include:

- PostgreSQL
- Redis
- PostgreSQL + pgvector
- Object Storage
- External APIs

This layer is completely isolated from business logic.

---

# 8. Engineering Goals

PitWall Agent is intended to demonstrate modern software engineering practices.

The project emphasizes:

- Clean architecture
- Layered design
- Strong typing
- Dependency injection
- Modular components
- Comprehensive logging
- Automated testing
- Continuous Integration
- Containerized deployment
- Observability

The codebase should remain maintainable as the project evolves.

---

# 9. Technology Overview

The project is built upon a modern AI-native technology stack.

| Layer | Technology |
|--------|------------|
| Frontend | Next.js |
| Backend | FastAPI |
| Agent Runtime | LangGraph |
| LLM | OpenAI Compatible API |
| Embedding | BAAI BGE-M3 |
| Vector Database | PostgreSQL + pgvector |
| Relational Database | PostgreSQL |
| Cache | Redis |
| Package Management | uv |
| Reverse Proxy | Nginx |
| Containerization | Docker Compose |
| Observability | LangSmith |
| CI/CD | GitHub Actions |

Each technology has been selected through an Architecture Decision Record (ADR/RFC) process to ensure long-term maintainability and production readiness.

---

# 10. Engineering Principles

The project follows several engineering principles throughout development.

## Modular Design

Every module should have a single, clearly defined responsibility.

Business logic should never be tightly coupled to infrastructure components.

---

## Low Coupling

Components communicate through stable interfaces.

Replacing one implementation should not require modifications to unrelated modules.

For example:

- replacing one embedding model with another
- switching vector databases
- changing LLM providers

should require minimal changes.

---

## High Cohesion

Related responsibilities should remain within the same module.

For example:

- all retrieval logic belongs to the Knowledge module
- all orchestration logic belongs to the Agent Runtime
- all HTTP endpoints belong to the API module

---

## Configuration over Hard Coding

Environment-specific values must be externalized.

Examples include:

- API Keys
- Database URLs
- Model Names
- Service Endpoints

No sensitive information should be committed to the repository.

---

## Observability

The system should expose sufficient information for debugging and monitoring.

Logging, tracing, and runtime metrics should be considered first-class engineering concerns rather than afterthoughts.

---

## Testability

Every major component should be independently testable.

The project should support:

- Unit Testing
- Integration Testing
- End-to-End Testing

without requiring extensive modifications.

---

# 11. Project Deliverables

The initial release of PitWall Agent is expected to include the following deliverables.

## Core Features

- Conversational AI interface
- Tool orchestration
- Real-time race information retrieval
- Formula One news retrieval
- FIA regulation question answering
- Strategy analysis
- Citation support

---

## Engineering Deliverables

- Dockerized deployment
- Automated testing
- CI/CD pipeline
- Logging system
- Configuration management
- API documentation

---

## Documentation

The repository includes comprehensive project documentation covering:

- Product Requirements
- System Architecture
- Technology Decisions
- Backend Design
- Agent Design
- RAG Design
- Database Design
- Deployment
- API Specifications

---

# 12. Future Roadmap

The architecture has been designed with long-term evolution in mind.

Potential future enhancements include:

## Knowledge Expansion

- Historical race archives
- Technical directives
- Steward decisions
- FIA press releases

---

## Additional Tools

- Weather analysis
- Telemetry visualization
- Tire strategy simulation
- Driver comparison
- Historical statistics

---

## Multi-Modal Capabilities

- Image understanding
- PDF annotation
- Voice interaction
- Audio summaries

---

## User Features

- Personalized watchlists
- Favorite teams and drivers
- Daily briefing subscriptions
- Push notifications

---

## Platform Evolution

Future versions may introduce:

- Distributed services
- Horizontal scaling
- Multi-agent collaboration
- Enterprise authentication
- Public API platform

The current architecture intentionally leaves room for these future enhancements without requiring significant redesign.

---

# 13. Success Criteria

The project will be considered successful if it satisfies the following goals.

## Functional

- Accurate retrieval of race information
- Reliable regulation question answering
- Effective multi-tool orchestration
- Explainable responses with citations

---

## Engineering

- Clean project structure
- Comprehensive documentation
- Production-ready deployment
- Stable automated testing
- Maintainable codebase

---

## Educational

The project should demonstrate practical understanding of:

- Modern AI Agent architecture
- Retrieval-Augmented Generation (RAG)
- Tool Calling
- Software architecture
- Backend engineering
- Containerized deployment

It should serve as a strong portfolio project for software engineering and AI-related positions.

---

# 14. Non-Goals

The initial release intentionally excludes several features.

These include:

- Live telemetry processing
- Autonomous race strategy optimization
- Team radio transcription
- Full simulation engines
- Mobile applications
- Enterprise multi-tenancy

These capabilities may be considered in future releases but are outside the scope of Version 1.0.

---

# 15. Conclusion

PitWall Agent is designed as a production-oriented AI Agent that combines modern software engineering with practical AI technologies.

Rather than functioning as a simple chatbot, the system integrates external knowledge retrieval, intelligent tool orchestration, Retrieval-Augmented Generation, and structured engineering practices into a unified architecture.

The project emphasizes:

- Reliability
- Explainability
- Maintainability
- Extensibility
- Production readiness

These principles guide every architectural decision throughout the project lifecycle.

The following documents describe the system in greater detail, including product requirements, architecture, implementation decisions, and engineering specifications.

---

**End of Document**
