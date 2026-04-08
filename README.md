# Robust Software Architecture Design Review System

This project is a Retrieval-Augmented Generation (RAG) system built to serve as an expert architectural assistant. It allows users to upload architecture documents (PDFs), evaluates the architecture automatically across several key enterprise categories, and provides an interactive copilot to refine and continuously update a live Architecture Document.

## Prerequisites

Before running the application, ensure you have the following installed:
- **Node.js**: version 18+ (for running the React frontend)
- **Python**: version 3.10+ (for the FastAPI backend)
- **PostgreSQL**: Running locally on port `5432` with the `pgvector` extension installed.
    - Default credentials expected: User `postgres`, Password `password`, DB name `postgres`.

## Step 1: Environment Variables Setup

Ensure you have a `.env` file located in the root or `backend/` directory containing your Groq API Key:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Step 2: Running the Backend

The backend is built with FastAPI, Langchain, and SQLAlchemy. It runs within a Python virtual environment.

1. Open a terminal and navigate to the `backend` directory.
   ```bash
   cd backend
   ```
2. Activate your virtual environment:
   - **Windows PowerShell**: `.\.venv\Scripts\Activate.ps1`
   - **Windows CMD**: `.\.venv\Scripts\activate.bat`
   - **Mac/Linux**: `source .venv/bin/activate`
3. If dependencies are missing, install them:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI server using Uvicorn:
   ```bash
   uvicorn main:app --reload
   ```
   *The backend will now be running at `http://localhost:8000` and automatically configure database tables on startup.*

## Step 3: Running the Frontend

The front end is built with React, Vite, and tailors a robust Enterprise-class, triple-pane interface.

1. Open a new terminal and navigate to the `frontend` directory.
   ```bash
   cd frontend
   ```
2. Install dependencies (Make sure to run in an administrative shell or bypass Windows execution policies if `npm` acts up):
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *The frontend will now be running at `http://localhost:3000` (or the port specified by Vite, usually `http://localhost:5173`).*

## Usage

1. Open the UI in your browser.
2. Select an active Groq Model from the dropdown on the left.
3. Click the Upload Zone on the left pane to submit an Architecture PDF.
4. Wait for the automated "Diagnostic Review" to populate on the right panel.
5. Use the Copilot chat window to ask to update the architecture or mandate new system constraints! Toggle the "Live Document" tab to watch your markdown continuously refine.
