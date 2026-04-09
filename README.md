# ArchReview AI - Enterprise Architecture Copilot

ArchReview AI is a Retrieval-Augmented Generation (RAG) system designed to serve as an expert architectural assistant. It automates the evaluation of design documents (PDFs) and provides an interactive copilot to continuously refine a "Live Architecture Document."

## Key Features
- **Multi-Provider Discovery**: Dynamically switch between Groq, SiliconFlow, SambaNova Cloud, and LiteLLM/OpenRouter.
- **Dynamic Model Discovery**: Real-time fetching of active AI models directly from provider APIs.
- **Expert Audit**: Automated diagnostic reviews covering Scalability, Security, Performance, and Operational Excellence.
- **Live Document Refinement**: Use `@LiveDocumentation` in chat to update your system design on the fly.
- **Persistent Workspace**: Full state recovery powered by PostgreSQL and PGVector.

## Prerequisites
- **Node.js**: version 18+
- **Python**: version 3.10+
- **PostgreSQL**: Running on port `5432` with the `pgvector` extension.

## Setup Instructions

### 1. Environment Configuration
Create a `.env` file in the root or `backend/` directory based on the `.env.example` provided:
```env
GROQ_API_KEY=your_key
SILICON_API_KEY=your_key
SAMBANOVA_API_KEY=your_key
OPENROUTER_API_KEY=your_key
DATABASE_URL=postgresql://user:password@localhost:5432/postgres
```

### 2. Run the Backend (FastAPI)
```bash
cd backend
python -m venv .venv
# Activate venv: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. Run the Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

## Usage Workflow
1. **Initialize**: Select or Create a Project from the sidebar.
2. **Configure Engine**: Choose your preferred AI Provider and Model.
3. **Analyze**: Upload an Architecture PDF to trigger the **Diagnostic Review**.
4. **Refine**: Switch to the **Live Document** tab and use the **Architecture Copilot** to evolve the design!

---
*For a deeper dive into the architectural journey of this project, see [blog.md](./blog.md).*
