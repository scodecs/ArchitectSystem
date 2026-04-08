from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import io
import uuid # Imported to generate unique pdf_ids
import json
from pypdf import PdfReader
from groq import Groq
from dotenv import load_dotenv

# DB Imports
from sqlalchemy.orm import Session
from database import engine, Base, get_db, SessionLocal
from models import Project, ArchitectureReview, ArchitectureState, ProjectConstraint, ProjectArtifact

# LangChain & PGVector imports
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from langchain_core.documents import Document

load_dotenv()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()
client = Groq()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database & Embedding Configuration ---
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:password@localhost:5432/postgres")

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

vector_store = PGVector(
    embeddings=embeddings,
    collection_name="architecture_pdfs",
    connection=POSTGRES_URL,
    use_jsonb=True,
)
# ------------------------------------------

class ChatRequest(BaseModel):
    project_id: str
    pdf_ids: list[str] = []
    message: str
    history: list = []
    model_id: str = "llama-3.3-70b-versatile"

def update_project_summary_bg(project_id: str, old_summary: str, user_msg: str, asst_msg: str):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            return
            
        summary_prompt = (
            "You are summarizing an architectural discussion.\n"
            f"Previous Summary:\n{old_summary or 'No summary yet.'}\n\n"
            f"Latest User Msg:\n{user_msg}\n\n"
            f"Latest Assistant Msg:\n{asst_msg}\n\n"
            "Synthesize these into a brief, ongoing 3-5 sentence running summary of the project state."
        )
        
        comp = client.chat.completions.create(
            messages=[{"role": "user", "content": summary_prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1
        )
        project.running_summary = comp.choices[0].message.content
        db.commit()
    except Exception as e:
        print(f"Error updating summary: {e}")
    finally:
        db.close()

def generate_architecture_review(text_context: str) -> dict:
    system_prompt = (
        "You are an expert software architect. Read the provided architecture text and evaluate it strictly against these Industry Standard Enterprise Frameworks:\n"
        "1. Macro Frameworks: TOGAF, Zachman Framework, and Cloud Well-Architected Frameworks (Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization).\n"
        "2. Software Design Patterns: Microservices Architecture (loose coupling), Event-Driven Architecture (EDA via brokers), Domain-Driven Design (DDD), Clean/Hexagonal Architecture (dependency inversion), The Twelve-Factor App methodology, and Zero Trust Security (authenticate everywhere).\n\n"
        "Output MUST be pure JSON matching this schema: \n"
        "{\n"
        "  \"problem_statement\": \"string\",\n"
        "  \"overview\": \"string\",\n"
        "  \"ratings\": { \"Cloud Well-Architected\": {\"score\": 0, \"rationale\": \"string\"}, \"Microservices/EDA\": {\"score\": 0, \"rationale\": \"string\"}, \"Domain-Driven Design\": {\"score\": 0, \"rationale\": \"string\"}, \"Clean Architecture\": {\"score\": 0, \"rationale\": \"string\"}, \"Zero Trust Security\": {\"score\": 0, \"rationale\": \"string\"} },\n"
        "  \"recommendations\": [\n"
        "    { \"category\": \"string\", \"title\": \"string\", \"detail\": \"string\", \"why_it_fits\": \"string\" }\n"
        "  ]\n"
        "}\n"
        "Ratings map to the keys provided and the 'score' is from 1 to 10. For 'rationale', strictly explain why the design received that score. For recommendations, 'detail' explains the action to take in technical depth, and 'why_it_fits' explicitly justifies why it fits the current requirement/use-case perfectly."
    )
    
    review_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Document context to evaluate:\n{text_context[:25000]}"}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return json.loads(review_completion.choices[0].message.content)

@app.get("/api/models")
async def get_models():
    try:
        models = client.models.list()
        # Filter for models that make sense for this use-case
        valid_models = [m.id for m in models.data if any(x in m.id for x in ["llama", "gemma", "mixtral"])]
        return {"models": valid_models}
    except Exception as e:
        return {"models": ["llama-3.3-70b-versatile", "gemma2-9b-it", "mixtral-8x7b-32768"]}

@app.get("/api/projects")
async def get_all_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return {"projects": [p.project_id for p in projects]}

@app.get("/api/project/{project_id}")
async def get_project_state(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    review = db.query(ArchitectureReview).filter(ArchitectureReview.project_id == project_id).order_by(ArchitectureReview.created_at.desc()).first()
    state = db.query(ArchitectureState).filter(ArchitectureState.project_id == project_id).order_by(ArchitectureState.created_at.desc()).first()
    constraints = db.query(ProjectConstraint).filter(ProjectConstraint.project_id == project_id).all()
    artifacts = db.query(ProjectArtifact).filter(ProjectArtifact.project_id == project_id).all()

    return {
        "project_id": project.project_id,
        "review": {
            "ratings": review.ratings.get("scores", review.ratings) if review and isinstance(review.ratings, dict) else {},
            "problem_statement": review.ratings.get("problem_statement", "") if review and isinstance(review.ratings, dict) else "",
            "overview": review.ratings.get("overview", "") if review and isinstance(review.ratings, dict) else "",
            "recommendations": review.recommendations if review else []
        },
        "live_document": state.content if state else "# No Architecture Document Found",
        "constraints": [{"description": c.description, "reason": c.reason} for c in constraints],
        "artifacts": [{"pdf_id": a.pdf_id, "filename": a.filename} for a in artifacts],
        "running_summary": project.running_summary
    }

@app.post("/api/upload")
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        pdf_id = str(uuid.uuid4())
        pdf_bytes = await file.read()
        pdf_stream = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_stream)
        
        full_text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                full_text += extracted + "\n"

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(full_text)

        documents = [
            Document(page_content=chunk, metadata={"source": file.filename, "project_id": project_id, "pdf_id": pdf_id})
            for chunk in chunks
        ]
        vector_store.add_documents(documents)

        # Store project
        project = db.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            project = Project(project_id=project_id)
            db.add(project)
            db.commit()

        # Step: Initial Review Generation
        review_data = generate_architecture_review(full_text)
        
        # Save Review
        new_review = ArchitectureReview(
            project_id=project_id,
            ratings={
                "scores": review_data.get("ratings", {}),
                "problem_statement": review_data.get("problem_statement", "N/A"),
                "overview": review_data.get("overview", "N/A")
            },
            recommendations=review_data.get("recommendations", [])
        )
        db.add(new_review)

        # Generate Initial Markdown Structure
        prob_statement = review_data.get('problem_statement', 'N/A')
        overview = review_data.get('overview', 'N/A')
        
        markdown_state = f"# Architecture Draft: {file.filename}\n\n## Problem Statement\n{prob_statement}\n\n## Overview\n{overview}\n\n## Original Document Source\n\n```text\n{full_text}\n```"
        new_state = ArchitectureState(project_id=project_id, content=markdown_state)
        db.add(new_state)
        
        # Save Artifact Reference
        new_artifact = ProjectArtifact(project_id=project_id, pdf_id=pdf_id, filename=file.filename)
        db.add(new_artifact)

        db.commit()

        return {
            "message": f"Successfully processed {file.filename}",
            "project_id": project_id,
            "pdf_id": pdf_id
        }

    except Exception as e:
        print(f"Error in upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/project/{project_id}/evaluate")
async def evaluate_project(project_id: str, db: Session = Depends(get_db)):
    state = db.query(ArchitectureState).filter(ArchitectureState.project_id == project_id).order_by(ArchitectureState.created_at.desc()).first()
    if not state or not state.content:
        raise HTTPException(status_code=400, detail="No architecture document available to evaluate.")

    try:
        review_data = generate_architecture_review(state.content)
        new_review = ArchitectureReview(
            project_id=project_id,
            ratings={
                "scores": review_data.get("ratings", {}),
                "problem_statement": review_data.get("problem_statement", "N/A"),
                "overview": review_data.get("overview", "N/A")
            },
            recommendations=review_data.get("recommendations", [])
        )
        db.add(new_review)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        print(f"Error in evaluate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_with_model(request: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        search_filter = {"project_id": request.project_id}
        if request.pdf_ids and len(request.pdf_ids) > 0:
            search_filter["pdf_id"] = {"$in": request.pdf_ids}

        # Check if project has artifacts before querying PGVector
        artifacts_exist = db.query(ProjectArtifact).filter(ProjectArtifact.project_id == request.project_id).first()
        
        retrieved_context = "No RAG context available for this project."
        if artifacts_exist:
            results = vector_store.similarity_search(request.message, k=4, filter=search_filter)
            if results:
                retrieved_context = "\n\n".join([doc.page_content for doc in results])

        # Fetch current project state to inform the LLM
        project = db.query(Project).filter(Project.project_id == request.project_id).first()
        state = db.query(ArchitectureState).filter(ArchitectureState.project_id == request.project_id).order_by(ArchitectureState.created_at.desc()).first()
        constraints = db.query(ProjectConstraint).filter(ProjectConstraint.project_id == request.project_id).all()
        
        live_doc = state.content if state else "No current document."
        user_constraints = "\n".join([f"- {c.description} (Reason: {c.reason})" for c in constraints])

        system_message = {
            "role": "system",
            "content": (
                "You are an expert architectural assistant. Answer user questions relying on your vast internal knowledge and utilizing the RAG context where available.\n\n"
                f"CURRENT PROJECT CONSTRAINTS (You MUST respect these):\n{user_constraints if constraints else 'None'}\n\n"
                f"DOCUMENT CONTEXT (RAG):\n{retrieved_context}\n\n"
                f"CURRENT LIVE ARCHITECTURE DOCUMENT:\n{live_doc}\n\n"
                "CRITICAL INSTRUCTION: You MUST NOT update the live documentation UNLESS the user explicitly included the tag @LiveDocumentation in their message.\n"
                "When you DO use the update_architecture_document tool, you MUST ingest the ENTIRE existing text, merge the user's requested fragment/section seamlessly without losing old information, and output the fully rewritten and comprehensive architecture document.\n\n"
                "CRITICAL DOCUMENT FORMATTING REQUIREMENT:\n"
                "Whenever you generate or update the document using the tool, you MUST use the following Software Architecture Document (SAD) Template (arc42/C4). "
                "Do NOT use arbitrary headers. Map the design exclusively into these exact sections with extreme depth:\n"
                "1. Introduction and Business Goals\n"
                "2. Architecture Constraints\n"
                "3. System Context (Level 1) - Include Mermaid graph TD\n"
                "4. Container View (Level 2) - Include Mermaid graph TD\n"
                "5. Component View (Level 3)\n"
                "6. Runtime View (Data Flow & Request Sequences) - MANDATORY: Include at least one 'mermaid' sequenceDiagram or flow diagram here showing how components interact.\n"
                "7. Deployment View\n"
                "8. Cross-Cutting Concepts (auth, logging, etc.)\n"
                "9. Architecture Decision Records (ADRs)\n"
                "10. Quality Requirements\n\n"
                "DIAGRAMMING RULE: Use ```mermaid code blocks for all diagrams. For flow/request logic, use 'sequenceDiagram' or 'graph LR'. For static structure, use 'graph TD'."
            )
        }

        messages = [system_message] + request.history + [{"role": "user", "content": request.message}]

        update_tool = {
            "type": "function",
            "function": {
                "name": "update_architecture_document",
                "description": "Rewrite the complete live architecture markdown document to include new components, changes, or fixes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "markdown_content": {
                            "type": "string",
                            "description": "The entirely rewritten markdown content reflecting all architectural changes."
                        }
                    },
                    "required": ["markdown_content"]
                }
            }
        }
        
        constraint_tool = {
            "type": "function",
            "function": {
                "name": "add_constraint",
                "description": "Record a new user constraint or rigid design decision.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Crisp description of the constraint (e.g., 'Must use an on-premise PostgresDB')."
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why the user chose this constraint."
                        }
                    },
                    "required": ["description", "reason"]
                }
            }
        }

        tools = [constraint_tool]
        # Only grant the LLM the update_architecture tool if the tag is explicitly requested by the user
        tool_choice = "auto"
        if "@LiveDocumentation" in request.message:
            tools.append(update_tool)
            tool_choice = {"type": "function", "function": {"name": "update_architecture_document"}}

        chat_completion = client.chat.completions.create(
            messages=messages,
            model=request.model_id,
            temperature=0.3,
            max_tokens=3000,
            tools=tools,
            tool_choice=tool_choice
        )

        response_message = chat_completion.choices[0].message
        
        # Check if the model decided to use a tool
        updates_made = []
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                if tool_call.function.name == "update_architecture_document":
                    new_doc = args.get("markdown_content")
                    if new_doc:
                        db.add(ArchitectureState(project_id=request.project_id, content=new_doc))
                        db.commit()
                        updates_made.append("Updated Live Architecture Document.")
                
                elif tool_call.function.name == "add_constraint":
                    desc, reason = args.get("description"), args.get("reason", "")
                    if desc:
                        db.add(ProjectConstraint(project_id=request.project_id, description=desc, reason=reason))
                        db.commit()
                        updates_made.append(f"Recorded new constraint: {desc}")

            # Optionally, ask the LLM to generate a textual reply based on the tool execution
            messages.append(response_message)
            messages.append({
                "role": "tool",
                "tool_call_id": response_message.tool_calls[0].id,
                "name": response_message.tool_calls[0].function.name,
                "content": json.dumps({"status": "success", "updates": updates_made})
            })
            
            final_completion = client.chat.completions.create(
                messages=messages,
                model=request.model_id,
                temperature=0.3,
                max_tokens=1000,
            )
            final_content = final_completion.choices[0].message.content
            
            background_tasks.add_task(update_project_summary_bg, request.project_id, project.running_summary if project else None, request.message, final_content)
            
            return {"role": "assistant", "content": final_content, "system_updates": updates_made}
            
        background_tasks.add_task(update_project_summary_bg, request.project_id, project.running_summary if project else None, request.message, response_message.content)

        return {
            "role": "assistant",
            "content": response_message.content,
            "system_updates": updates_made
        }

    except Exception as e:
        print(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
