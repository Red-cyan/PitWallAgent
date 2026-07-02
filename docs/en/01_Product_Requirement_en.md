# Product Requirement Document

# PitWall Agent

---

## Document Information

| Item | Value |
|------|-------|
| Document | Product Requirement Document |
| Version | 1.0 |
| Status | Architecture Freeze V1 |
| Project | PitWall Agent |
| Target Release | MVP v1.0 |

---

# 1. Introduction

## 1.1 Background

Formula One fans consume information from a wide variety of sources, including official FIA documents, Formula One websites, team announcements, technical analyses, timing services, and motorsport media.

Although Large Language Models are capable of answering general Formula One questions, they cannot reliably provide:

- Real-time news
- Official race information
- Accurate regulation interpretation
- Traceable references to FIA documents

PitWall Agent addresses these problems by integrating Large Language Models with external tools and Retrieval-Augmented Generation (RAG).

Instead of generating answers solely from model knowledge, the system retrieves authoritative information before reasoning.

---

## 1.2 Product Positioning

PitWall Agent is a production-grade AI assistant designed specifically for Formula One.

It combines:

- Natural language interaction
- Intelligent tool orchestration
- Real-time information retrieval
- FIA regulation retrieval
- Context-aware reasoning

The product is intended for both casual fans and technically-oriented users.

---

## 1.3 Product Goals

The primary objectives of the project are:

- Provide reliable Formula One information
- Reduce misinformation and hallucinations
- Improve accessibility of FIA regulations
- Simplify access to race information
- Demonstrate production-grade AI engineering

---

# 2. Target Users

## User Group A

### Formula One Fans

Characteristics

- Follow most races
- Read Formula One news
- Watch race weekends
- Want fast answers

Typical Questions

- What happened today?
- Who won qualifying?
- Why was a driver penalized?
- What is the next race?

---

## User Group B

### Technical Enthusiasts

Characteristics

- Interested in regulations
- Follow technical updates
- Understand engineering concepts

Typical Questions

- Why is this design legal?
- Which article defines this rule?
- Why did the FIA reject this component?
- What does the regulation actually say?

---

## User Group C

### Students

Characteristics

- Learning AI
- Learning motorsport
- Learning software engineering

Typical Needs

- Reliable references
- Technical explanations
- Regulation understanding

---

# 3. User Scenarios

## Scenario 1

### Daily News

User asks:

> What happened in Formula One today?

Expected Result

The Agent retrieves the latest news from trusted sources, summarizes the most important events, and provides links or citations where applicable.

---

## Scenario 2

### Regulation Question

User asks:

> What is Parc Fermé?

Expected Result

The Agent retrieves relevant FIA regulation sections through the RAG pipeline and generates an answer with supporting citations.

---

## Scenario 3

### Race Schedule

User asks:

> When is the Belgian Grand Prix?

Expected Result

The Agent retrieves the official race calendar and returns accurate scheduling information.

---

## Scenario 4

### Driver Standings

User asks:

> Who leads the championship?

Expected Result

The Agent retrieves the latest standings from official race data.

---

## Scenario 5

### Technical Question

User asks:

> Why was this car considered illegal?

Expected Result

The Agent combines regulation retrieval and contextual reasoning to explain the decision.

---

# 4. Functional Scope

PitWall Agent Version 1.0 consists of five core capability domains.

- News Retrieval
- Race Information
- Regulation Question Answering
- Strategy Analysis
- Conversational Interaction

Each capability is described in detail below.

---

# 5. Functional Requirements

## FR-001

### Conversational Interaction

Priority

P0

Description

The system shall support natural language conversations.

Acceptance Criteria

- Multi-turn dialogue
- Context awareness
- Streaming responses
- Markdown rendering

---

## FR-002

### News Retrieval

Priority

P0

Description

The system shall retrieve recent Formula One news from trusted external sources.

Input

Natural language.

Example

"What happened today?"

Output

- Summary
- Source
- Publication time
- Related team or driver

Acceptance Criteria

- Response generated within ten seconds
- Multiple news items summarized
- Information sourced from external providers

---

## FR-003

### Race Information

Priority

P0

Description

The system shall retrieve official race information.

Supported Data

- Calendar
- Weekend schedule
- Qualifying results
- Sprint results
- Race classification
- Driver standings
- Constructor standings

Example

"When is the next Grand Prix?"

Acceptance Criteria

Information must reflect the latest available official data.

---

---

## FR-004

### FIA Regulation Question Answering

**Priority**

P0

**Description**

The system shall answer questions related to Formula One Sporting Regulations and Technical Regulations using Retrieval-Augmented Generation (RAG).

Instead of relying solely on the language model, the system retrieves relevant regulation sections before generating an answer.

**Example Questions**

- What is Parc Fermé?
- What is an unsafe release?
- What is the minimum plank thickness?
- When can a team replace a power unit?

**Input**

Natural language.

**Output**

The response shall include:

- Answer
- Supporting regulation
- Regulation article number
- Document title
- Confidence level (internal use)

**Acceptance Criteria**

- Relevant document chunks are retrieved.
- Retrieved context is incorporated into the final response.
- Hallucinations are minimized through grounded generation.

---

## FR-005

### Strategy Analysis

**Priority**

P1

**Description**

The system shall provide race strategy analysis by combining retrieved race information with LLM reasoning.

This feature focuses on explanation rather than prediction.

**Example Questions**

- Why did McLaren pit earlier?
- Why did Ferrari lose track position?
- Was the Safety Car beneficial?

**Output**

The system explains strategic decisions using available race information and regulation knowledge.

**Acceptance Criteria**

- Analysis is logically structured.
- Reasoning references available race context.
- The system clearly distinguishes facts from analysis.

---

## FR-006

### Conversation Memory

**Priority**

P1

**Description**

The system shall maintain conversation context during a user session.

Users should not need to repeat previous questions when asking follow-up questions.

**Example**

User:

> Why was Verstappen penalized?

Follow-up:

> Was that consistent with previous races?

The system shall understand that the follow-up question refers to the previously discussed incident.

**Acceptance Criteria**

- Conversation context is preserved.
- Follow-up questions are resolved correctly.
- Session state is isolated between users.

---

## FR-007

### Citation Support

**Priority**

P1

**Description**

Whenever an answer is generated from retrieved documents, the response should provide supporting references.

Possible citation elements include:

- Document title
- Article number
- Section title
- Page number

**Acceptance Criteria**

- Citations are displayed whenever available.
- References correspond to the retrieved document.
- Citation formatting remains consistent.

---

## FR-008

### Error Handling

**Priority**

P1

**Description**

The system shall gracefully handle failures during retrieval, tool execution, or language model invocation.

Possible failure scenarios include:

- External API unavailable
- Vector database timeout
- Missing document
- LLM request failure

**Acceptance Criteria**

- User receives a meaningful error message.
- Internal errors are logged.
- The application remains responsive.

---

# 6. Non-Functional Requirements

## NFR-001

### Performance

**Priority**

P0

The average response time should remain acceptable for interactive use.

Target response times:

| Operation | Target |
|----------|--------|
| Chat response | < 10 s |
| News retrieval | < 8 s |
| Race information | < 5 s |
| Regulation retrieval | < 10 s |

---

## NFR-002

### Availability

**Priority**

P1

The application should remain available under normal operating conditions.

Unexpected failures should not terminate the entire service.

---

## NFR-003

### Scalability

**Priority**

P2

The architecture should support future horizontal expansion.

Examples include:

- Multiple API instances
- Independent vector database deployment
- Separate model servers

---

## NFR-004

### Maintainability

**Priority**

P0

The project shall adopt a modular architecture.

Each module should have a clearly defined responsibility.

Business logic should not depend directly on infrastructure components.

---

## NFR-005

### Security

**Priority**

P1

The system shall protect sensitive configuration information.

Requirements include:

- Environment variables
- Secure API key management
- Input validation
- Request sanitization

---

## NFR-006

### Observability

**Priority**

P1

The application shall provide sufficient operational information for debugging.

This includes:

- Structured logging
- Request tracing
- Agent execution records
- Tool invocation logs

---

## NFR-007

### Extensibility

**Priority**

P0

The architecture shall allow new tools to be added with minimal changes to existing modules.

Examples include:

- Weather Tool
- Telemetry Tool
- Historical Statistics Tool
- FIA Document Update Tool

---

---

# 7. User Stories

The following user stories describe the expected interactions between users and PitWall Agent.

---

## US-001

### Read Today's Formula One News

**As a**

Formula One fan

**I want**

to ask what happened today in Formula One

**So that**

I can quickly understand the latest events without reading multiple news websites.

**Acceptance Criteria**

- The system retrieves recent news.
- The response summarizes the most important events.
- Major news sources are referenced when available.

---

## US-002

### View Race Weekend Schedule

**As a**

Formula One fan

**I want**

to know the schedule of the current or upcoming race weekend

**So that**

I know when each session takes place.

**Acceptance Criteria**

The system returns:

- Practice schedule
- Sprint schedule (if applicable)
- Qualifying schedule
- Race schedule

---

## US-003

### Check Championship Standings

**As a**

Formula One fan

**I want**

to view the latest driver and constructor standings

**So that**

I can follow the championship battle.

**Acceptance Criteria**

The standings should reflect the latest available official results.

---

## US-004

### Understand FIA Regulations

**As a**

Technical enthusiast

**I want**

to ask questions about FIA regulations using natural language

**So that**

I do not need to manually search hundreds of pages of official documents.

**Acceptance Criteria**

The response includes:

- Explanation
- Relevant regulation
- Article number
- Supporting citation

---

## US-005

### Explain Race Incidents

**As a**

Formula One fan

**I want**

to understand why a driver received a penalty

**So that**

I can better understand steward decisions.

**Acceptance Criteria**

The answer combines:

- Regulation retrieval
- Race context
- Natural language explanation

---

## US-006

### Multi-turn Conversation

**As a**

User

**I want**

to ask follow-up questions naturally

**So that**

I do not need to repeat previous context.

**Acceptance Criteria**

Conversation context is maintained throughout the current session.

---

## US-007

### Strategy Discussion

**As a**

Formula One fan

**I want**

to discuss race strategy

**So that**

I can better understand tactical decisions made by teams.

**Acceptance Criteria**

The response clearly separates:

- Known facts
- Analytical reasoning
- Assumptions

---

# 8. System Constraints

The initial release includes several intentional limitations.

## Data Scope

Only Formula One is supported.

Other FIA championships such as Formula 2, Formula 3, Formula E, WEC, or WRC are outside the scope of Version 1.0.

---

## Language

Version 1.0 provides responses in English.

Support for additional languages may be introduced in future releases.

---

## Knowledge Source

Regulation-based answers rely only on documents that have been ingested into the knowledge base.

Documents outside the indexed corpus cannot be referenced.

---

## External Dependencies

The system depends on several external services.

Examples include:

- Large Language Model provider
- News providers
- Race information APIs
- Vector database

Temporary failures of these services may affect certain capabilities.

---

## Real-Time Information

The accuracy of race information and news depends on the update frequency of external data providers.

The system does not guarantee second-level real-time synchronization.

---

# 9. Assumptions

The following assumptions are made during development.

- Users have internet connectivity.
- External APIs are operational.
- FIA documents are periodically updated.
- Embedding models remain compatible with indexed data.
- Supported LLMs provide tool-calling capabilities.

If any assumption changes, corresponding implementation adjustments may be required.

---

# 10. Acceptance Criteria

The Minimum Viable Product (MVP) shall satisfy the following conditions before release.

## Functional Acceptance

The system shall:

- Support conversational interaction.
- Retrieve Formula One news.
- Retrieve race schedules and standings.
- Answer FIA regulation questions using RAG.
- Maintain conversation context.
- Generate structured responses.

---

## Engineering Acceptance

The project shall include:

- Modular project structure
- Environment configuration
- Logging
- Error handling
- Unit tests
- Docker deployment

---

## Documentation Acceptance

The repository shall contain:

- Project Overview
- Product Requirement Document
- System Architecture
- Technology RFC
- Agent RFC
- Backend RFC
- RAG RFC
- Deployment Documentation

All documents shall remain synchronized with the implementation.

---

---

# 11. Release Plan

Development of PitWall Agent follows an incremental delivery strategy.

Each milestone introduces independently testable functionality while maintaining a deployable application.

---

## Phase 1 — Project Initialization

Objectives

- Initialize repository
- Configure development environment
- Establish project structure
- Configure dependency management
- Configure code quality tools

Deliverables

- Project skeleton
- Dependency management
- Configuration system
- Logging framework

---

## Phase 2 — Backend Foundation

Objectives

- Implement FastAPI backend
- Build application services
- Configure database connections
- Configure Redis
- Implement API routing

Deliverables

- Backend framework
- REST API
- Configuration management
- Basic health check endpoints

---

## Phase 3 — Agent Runtime

Objectives

- Implement LangGraph workflow
- Build Agent Runtime
- Implement tool orchestration
- Implement conversation state

Deliverables

- Agent Runtime
- Planning workflow
- Tool execution pipeline
- Session memory

---

## Phase 4 — RAG Pipeline

Objectives

- Parse FIA regulations
- Chunk documents
- Generate embeddings
- Build vector index
- Implement retrieval pipeline

Deliverables

- Knowledge ingestion pipeline
- PostgreSQL + pgvector vector database
- Regulation retrieval capability

---

## Phase 5 — Tool Integration

Objectives

Integrate external tools.

Initial tools include:

- News Tool
- Race Information Tool
- Regulation Retrieval Tool
- Strategy Analysis Tool

Deliverables

- Tool framework
- External API integration
- Unified tool interface

---

## Phase 6 — Frontend

Objectives

Develop the web interface.

Deliverables

- Chat interface
- Streaming responses
- Markdown rendering
- Citation display
- Responsive layout

---

## Phase 7 — Deployment

Objectives

Prepare the application for production deployment.

Deliverables

- Docker Compose
- Reverse proxy
- Environment configuration
- Deployment documentation
- CI/CD pipeline

---

# 12. Risks

The following risks have been identified during project planning.

---

## R-001

### External API Availability

Some capabilities depend on third-party services.

Potential Impact

- Missing news
- Missing race data
- Partial functionality

Mitigation

- Timeout handling
- Retry mechanism
- Graceful degradation

---

## R-002

### LLM Hallucination

Language models may generate incorrect information.

Mitigation

- Retrieval-Augmented Generation
- Tool-based reasoning
- Citation support
- Grounded prompts

---

## R-003

### Regulation Updates

FIA regulations change over time.

Mitigation

- Scheduled document updates
- Re-indexing pipeline
- Version management

---

## R-004

### Performance

Retrieval and LLM inference may increase response latency.

Mitigation

- Redis caching
- Optimized retrieval
- Parallel tool execution where applicable

---

# 13. Out of Scope

The following items are intentionally excluded from Version 1.0.

- Live telemetry analysis
- Race simulation
- Automated race prediction
- Fantasy Formula One integration
- Mobile applications
- User account system
- Team collaboration features
- Enterprise administration
- Payment systems

These features may be considered in future releases.

---

# 14. Success Metrics

The success of PitWall Agent will be evaluated using both functional and engineering metrics.

## Functional Metrics

- Accurate answers to regulation-related questions
- Reliable retrieval of race information
- Successful execution of external tools
- Stable multi-turn conversations

---

## Performance Metrics

- Average response latency within target limits
- Stable retrieval performance
- Successful completion of tool execution workflows

---

## Engineering Metrics

- Modular architecture
- Comprehensive documentation
- Automated testing
- Containerized deployment
- Maintainable codebase

---

## Portfolio Metrics

The project should demonstrate practical experience in:

- AI Agent development
- LangGraph workflows
- Retrieval-Augmented Generation (RAG)
- Tool Calling
- FastAPI backend development
- Vector databases
- Modern software architecture
- Docker deployment
- Engineering documentation

The project is intended to serve as a portfolio-quality implementation suitable for technical interviews and software engineering recruitment.

---

# 15. Conclusion

PitWall Agent aims to provide an accurate, explainable, and production-oriented AI assistant for Formula One.

The product combines conversational AI with intelligent tool orchestration and Retrieval-Augmented Generation to deliver trustworthy answers grounded in authoritative sources.

Version 1.0 focuses on establishing a solid engineering foundation while delivering practical capabilities including:

- Formula One news retrieval
- Race information retrieval
- FIA regulation question answering
- Strategy analysis
- Multi-turn conversational interaction

The requirements defined in this document serve as the baseline for system architecture, implementation, testing, and future iterations.

---

**End of Document**
