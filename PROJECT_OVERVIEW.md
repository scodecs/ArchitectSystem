# ArchReview AI
*Your Enterprise Architecture Co-Pilot*

![ArchReview AI Working Demo](file:///C:/Users/scodee/.gemini/antigravity/brain/c1b86f15-1905-460d-a164-31517e18c5a4/archreview_ai_final_demo_1775659077712.webp)

## What this tool is about?
**ArchReview AI** is a professional-grade intelligent workspace designed to bridge the gap between high-level architectural brainstorming and production-ready technical specifications. It serves as a digital "Principal Architect" that audits your designs in real-time, enforcing enterprise standards across security, scalability, and structural integrity.

## How it works?
The core experience is built around a **Knowledge-First Architecture**:
1. **RAG Ingestion**: Ingests project PDFs to establish a baseline system context.
2. **Specialized Personas**: Uses `@mentions` to toggle between discrete AI behaviors:
   - `@ReviewDocumentation`: Executes a "red-team" audit of your design, flagging scalability bottlenecks and single points of failure.
   - `@LiveDocumentation`: Automates the "Technical Writing" phase, weaving conversation decisions directly into a formal `arc42/C4` markdown specification.
3. **Automated Auditing**: Continuously calculates "Architectural Health Scores" across five critical pillars (DDD, Microservices, Clean Architecture, Zero Trust, and Well-Architected).

## Tech Stack
- **AI/LLM**: Groq (Llama-3.3-70b-versatile) for low-latency, high-reasoning output.
- **Backend**: Python (FastAPI), SQLAlchemy (SQLite/PostgreSQL), and Langchain for RAG orchestration.
- **Frontend**: React 19, Vite, and Lucide React.
- **Features**: Custom "Mirror Overlay" for real-time tag highlighting, bubble-based persona chat, and Mermaid.js for automated diagramming.

## ROI & Business Value
1. **Reduce Architectural Debt**: Catching one scalability gap during the design phase is **100x cheaper** than refactoring after a production performance incident.
2. **Documentation Velocity**: Eliminates the "SAD Overhead." Architecture documents are updated as a side-effect of the discussion, not a manual chore.
3. **Audit Compliance**: Automates the alignment with enterprise-mandated frameworks (TOGAF, C4, etc.), ensuring every project follows the same rigour.
