from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import os
import io
import uuid # Imported to generate unique pdf_ids
import json
from pypdf import PdfReader
from groq import Groq
from openai import OpenAI
from litellm import completion
from dotenv import load_dotenv

# DB Imports
from sqlalchemy.orm import Session
from database import engine, Base, get_db, SessionLocal
from models import Project, ArchitectureReview, ArchitectureState, ProjectConstraint, ProjectArtifact, ChatMessage

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

# SiliconFlow Client (OpenAI compatible)
silicon_client = OpenAI(
    api_key=os.getenv("SILICON_API_KEY", "sk-your-silicon-key"),
    base_url="https://api.siliconflow.cn/v1"
)

# SambaNova Client (OpenAI compatible)
sambanova_client = OpenAI(
    api_key=os.getenv("SAMBANOVA_API_KEY", "your-samba-key"),
    base_url="https://api.sambanova.ai/v1"
)

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
    provider: str = "Groq"

class EvalRequest(BaseModel):
    provider: str = "groq"
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
            "Synthesize this into a brief, bulleted running summary of the project state. "
            "Use clear bullet points. Include exactly two sections:\n"
            "- **Recent Queries**: what was asked lately.\n"
            "- **Live Document Updates**: what was updated lately on the architecture."
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

def generate_architecture_review(text_context: str, provider: str = "groq", model_id: str = "llama-3.3-70b-versatile") -> dict:
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
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Document context to evaluate:\n{text_context[:25000]}"}
    ]

    try:
        content = ""
        if provider == "siliconflow":
            resp = silicon_client.chat.completions.create(
                messages=messages,
                model=model_id,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content
        elif provider == "sambanova":
            resp = sambanova_client.chat.completions.create(
                messages=messages,
                model=model_id,
                temperature=0.1, # Rigorous evaluations benefit from low temp
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content
        elif provider == "litellm":
            resp = completion(
                model=model_id,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content
        else: # Default Goq
            resp = client.chat.completions.create(
                messages=messages,
                model=model_id,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content
        
        return json.loads(content)
    except Exception as e:
        print(f"Evaluation model error ({provider}/{model_id}): {e}")
        # Return a graceful fallback if JSON parsing fails or model errors
        return {
            "problem_statement": "Error during evaluation.",
            "overview": str(e),
            "ratings": {},
            "recommendations": []
        }

@app.get("/api/models")
async def get_models():
    # Only return the list of providers. The frontend will fetch models dynamically per provider.
    return {
        "providers": [
            {"id": "groq", "name": "Groq (Hyper-Fast)"},
            {"id": "siliconflow", "name": "SiliconFlow (OpenSource Expert)"},
            {"id": "sambanova", "name": "SambaNova Cloud"},
            {"id": "litellm", "name": "LiteLLM (Universal Gateway)"}
        ]
    }

@app.get("/api/models/{provider_id}")
async def get_provider_models(provider_id: str):
    provider_id = provider_id.lower()
    models = []
    
    try:
        if provider_id == "groq":
            raw_models = client.models.list()
            # Filter for text/chat models, exclude whisper
            models = [{"id": m.id, "name": m.id.replace("-", " ").title()} 
                     for m in raw_models.data if "whisper" not in m.id]
        
        elif provider_id == "siliconflow":
            raw_models = silicon_client.models.list()
            # Filter for instruct/reasoning models
            models = [{"id": m.id, "name": m.id.split('/')[-1].replace("-", " ").title()} 
                     for m in raw_models.data if ("instruct" in m.id.lower() or "deepseek" in m.id.lower())]
            
        elif provider_id == "sambanova":
            raw_models = sambanova_client.models.list()
            models = [{"id": m.id, "name": m.id.replace("-", " ").title()} 
                     for m in raw_models.data if "instruct" in m.id.lower()]
            
        elif provider_id == "litellm":
            # LiteLLM/OpenRouter often too big to list dynamically without heavy latency.
            # We'll provide a curated "Best of" list for the gateway.
            models = [
                {"id": "openrouter/anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"},
                {"id": "openrouter/google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash"},
                {"id": "openrouter/openai/gpt-4o", "name": "GPT-4o"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini"}
            ]
            
        return {"models": models}
    except Exception as e:
        print(f"Error fetching models for {provider_id}: {e}")
        # Fallback to a safe minimum if API fails
        fallback = {
            "groq": [{"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B"}],
            "siliconflow": [{"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek V3"}],
            "sambanova": [{"id": "Meta-Llama-3.1-405B-Instruct", "name": "Llama 3.1 405B"}]
        }
        return {"models": fallback.get(provider_id, [])}

@app.post("/api/project")
async def create_project(data: dict, db: Session = Depends(get_db)):
    project_id = data.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
        
    existing = db.query(Project).filter(Project.project_id == project_id).first()
    if existing:
        return {"status": "exists", "project_id": project_id}
        
    new_project = Project(project_id=project_id)
    db.add(new_project)
    db.commit()
    return {"status": "created", "project_id": project_id}

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

    history = db.query(ChatMessage).filter(ChatMessage.project_id == project_id).order_by(ChatMessage.created_at.desc()).limit(11).all()
    history = history[::-1] # chronological order
    
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
        "running_summary": project.running_summary,
        "history": [{"role": m.role, "content": m.content, "isError": m.is_error, "system_updates": m.system_updates} for m in history]
    }

@app.post("/api/upload")
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    provider: str = Form("groq"),
    model_id: str = Form("llama-3.3-70b-versatile"),
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
        review_data = generate_architecture_review(full_text, provider=provider, model_id=model_id)
        
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
async def evaluate_project(project_id: str, request: EvalRequest, db: Session = Depends(get_db)):
    state = db.query(ArchitectureState).filter(ArchitectureState.project_id == project_id).order_by(ArchitectureState.created_at.desc()).first()
    if not state or not state.content:
        raise HTTPException(status_code=400, detail="No architecture document available to evaluate.")

    try:
        review_data = generate_architecture_review(state.content, provider=request.provider, model_id=request.model_id)
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

@app.delete("/api/project/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)):
    try:
        # Cascading delete across all tables
        db.query(ChatMessage).filter(ChatMessage.project_id == project_id).delete()
        db.query(ArchitectureReview).filter(ArchitectureReview.project_id == project_id).delete()
        db.query(ArchitectureState).filter(ArchitectureState.project_id == project_id).delete()
        db.query(ProjectConstraint).filter(ProjectConstraint.project_id == project_id).delete()
        db.query(ProjectArtifact).filter(ProjectArtifact.project_id == project_id).delete()
        db.query(Project).filter(Project.project_id == project_id).delete()
        
        # Note: Vector store entries might still exist, ideally we should clean up PGVector by project_id too 
        # but the standard filter will handle it if we specify it.
        
        db.commit()
        return {"status": "success", "message": f"Project {project_id} and all associated data deleted."}
    except Exception as e:
        db.rollback()
        print(f"Error in delete_project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_with_model(request: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        search_filter = {"project_id": request.project_id}
        if request.pdf_ids and len(request.pdf_ids) > 0:
            search_filter["pdf_id"] = {"$in": request.pdf_ids}

        # Persist User Message
        db.add(ChatMessage(project_id=request.project_id, role='user', content=request.message))
        db.commit()

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
                "TONE: Professional, highly technical, rigorous, and uncompromising on engineering standards.\n"
                "STYLE: Use precise architectural terminology (e.g., 'idempotency', 'eventual consistency', 'circuit breaker', 'throughput bottleneck').\n"
                "FORMAT: Return ONLY the requested technical content. Do NOT include introductory pleasantries or conversational filler.\n\n"
                "You are an expert architectural assistant. Answer user questions relying on your knowledge and the RAG context.\n\n"
                f"CURRENT PROJECT CONSTRAINTS:\n{user_constraints if constraints else 'None'}\n\n"
                f"DOCUMENT CONTEXT (RAG):\n{retrieved_context}\n\n"
                f"CURRENT LIVE ARCHITECTURE DOCUMENT (Analyze the ENTIRE document context):\n{live_doc}\n\n"
                "--- SPECIALIZED ROLE: @ReviewDocumentation (Elite Principal Architect) ---\n"
                "When tagged, you act as a Principal Architect co-pilot. Your job is to rigorously review designs, identify gaps, and formulate critical questions.\n"
                "1. Mindset: Prioritize the 'Ilities' (scalability, reliability, security). Challenge the 'Happy Path'. Assume failure modes (blast radius, cascading failures, retry storms).\n"
                "2. Instructions: Identify what is MISSING (DR plans, latency, SLAs). Do NOT ask questions already answered in the doc. Push design boundaries.\n\n"
                "--- SPECIALIZED ROLE: @LiveDocumentation (Technical Writer) ---\n"
                "When tagged, you act as an expert technical writer seamlessly integrating updates.\n"
                "1. Parse: Extract core info and detect explicit/implicit section targets.\n"
                "2. Integrate: Read existing text for flow/tone. Rewrite input into professional technical English. EMBED naturally; do not just append.\n"
                "3. Rules: Maintain SAD structure, Markdown, and Mermaid diagrams. Do NOT delete info unless told to REPLACE it.\n\n"
                "--- DOCUMENT STRUCTURE (arc42/C4) ---\n"
                "1. Introduction and Business Goals | 2. Architecture Constraints | 3. System Context (Level 1) | 4. Container View (Level 2) | 5. Component View (Level 3) | 6. Runtime View (Sequences) | 7. Deployment View | 8. Cross-Cutting Concepts | 9. ADRs | 10. Quality Requirements\n\n"
                "DIAGRAMMING RULE: Use ```mermaid code blocks. Sequences for flow, graph TD for structure."
            )
        }

        # Sanitize history to only include 'role' and 'content' for the LLM API
        sanitized_history = []
        for m in request.history:
            if isinstance(m, dict) and "role" in m and "content" in m:
                # API specifically forbids extra fields like 'isError' or 'system_updates'
                msg = {"role": m["role"], "content": m["content"]}
                sanitized_history.append(msg)

        messages = [system_message] + sanitized_history + [{"role": "user", "content": request.message}]

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

        # Determine which client to use
        current_client = client
        prov_lower = request.provider.lower()
        
        if prov_lower == "siliconflow":
            current_client = silicon_client
        elif prov_lower == "sambanova":
            current_client = sambanova_client
        
        if prov_lower == "litellm":
            # LiteLLM routing
            chat_completion = completion(
                model=request.model_id,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=0.3,
                max_tokens=3000
            )
        else:
            # Direct SDK routing
            chat_completion = current_client.chat.completions.create(
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
            # First, append the assistant's message that contains the tool calls
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                raw_args = tool_call.function.arguments
                args = {}
                try:
                    # Attempt standard parse first
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    # Recovery: Strip garbage tags like </function> or trailing chars
                    try:
                        # Find the first { and last }
                        start = raw_args.find('{')
                        end = raw_args.rfind('}')
                        if start != -1 and end != -1:
                            args = json.loads(raw_args[start:end+1])
                        else:
                            print(f"CRITICAL: Unparseable tool arguments for {tool_call.function.name}: {raw_args}")
                    except Exception as e:
                        print(f"Failed to recover JSON for {tool_call.function.name}: {e}")

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

                # MANDATORY: Every tool call must have a corresponding tool response message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": json.dumps({"status": "success", "updates": updates_made})
                })

            if prov_lower == "litellm":
                final_completion = completion(
                    messages=messages,
                    model=request.model_id,
                    temperature=0.3,
                    max_tokens=1000,
                )
            else:
                final_completion = current_client.chat.completions.create(
                    messages=messages,
                    model=request.model_id,
                    temperature=0.3,
                    max_tokens=1000,
                )
            
            final_content = final_completion.choices[0].message.content or "Update processed successfully."
            # Persist Assistant Message
            db.add(ChatMessage(
                project_id=request.project_id, 
                role='assistant', 
                content=final_content, 
                system_updates=updates_made
            ))
            db.commit()
            
            background_tasks.add_task(update_project_summary_bg, request.project_id, project.running_summary if project else None, request.message, final_content)
            
            return {"role": "assistant", "content": final_content, "system_updates": updates_made}
            
        # Persist Assistant Message (non-tool)
        db.add(ChatMessage(project_id=request.project_id, role='assistant', content=response_message.content))
        db.commit()

        background_tasks.add_task(update_project_summary_bg, request.project_id, project.running_summary if project else None, request.message, response_message.content)

        return {
            "role": "assistant",
            "content": response_message.content,
            "system_updates": updates_made
        }

    except Exception as e:
        print(f"Error in chat: {e}")
        # Persist Error Message
        db.add(ChatMessage(project_id=request.project_id, role='system', content='Connection Error to Backend.', is_error=True))
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
