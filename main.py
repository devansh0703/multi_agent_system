# File: /multi_agent_system/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
import uuid
import time
from typing import Optional, Dict, Any, Union

# Load environment variables FIRST so they are available for SharedMemory initialization
load_dotenv()

# Check for GOOGLE_API_KEY before initializing LLM agents
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it in a .env file or your system environment.")

# Import SharedMemory CLASS and ActionRouter CLASS
from core.memory import SharedMemory
from core.action_router import ActionRouter

# Initialize SharedMemory instance (will connect to Redis or fallback)
memory = SharedMemory(host=os.getenv("REDIS_HOST", "localhost"))

# Initialize ActionRouter instance, passing the memory instance to it
action_router = ActionRouter(memory_instance=memory)

# Import Agent Classes
from agents.classifier_agent import ClassifierAgent
from agents.email_agent import EmailAgent
from agents.json_agent import JsonAgent
from agents.pdf_agent import PdfAgent

# Initialize agents, passing the shared memory and action router instances
# This is crucial for proper dependency injection and avoiding circular imports.
classifier_agent = ClassifierAgent(memory_instance=memory)
email_agent = EmailAgent(memory_instance=memory, action_router_instance=action_router)
json_agent = JsonAgent(memory_instance=memory, action_router_instance=action_router)
pdf_agent = PdfAgent(memory_instance=memory, action_router_instance=action_router)

app = FastAPI(
    title="Multi-Agent Document Processing System",
    description="Processes various document formats, classifies intent, routes to specialized agents, and triggers dynamic actions.",
    version="1.0.0"
)

templates = Jinja2Templates(directory="templates")

def with_retry(func, *args, retries=3, delay=1, **kwargs):
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Attempt {i+1} failed for {func.__name__}: {e}")
            if i < retries - 1:
                time.sleep(delay * (2**i))
            else:
                raise

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Serves the simple UI for uploading inputs.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process_input")
async def process_input(
    file: Optional[UploadFile] = File(None),
    raw_content: Optional[str] = Form(None),
    input_type_hint: Optional[str] = Form(None, description="Optional hint for content type (e.g., 'email', 'json', 'pdf'). Will be auto-detected if not provided.")
):
    """
    Processes an input, classifying its format and intent, then routing to specialized agents.
    Accepts either a file upload or raw text content.
    """
    process_id = str(uuid.uuid4())
    start_time = time.time()
    
    input_metadata = {
        "process_id": process_id,
        "timestamp": time.time(),
        "source_type": "file" if file else "raw_content",
        "original_filename": file.filename if file else None,
        "input_type_hint": input_type_hint
    }
    memory.add_entry(process_id, "input_metadata", input_metadata)

    content_bytes: Optional[bytes] = None
    content_str: Optional[str] = None

    if file:
        content_bytes = await file.read()
        try:
            content_str = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass
    elif raw_content:
        content_str = raw_content
        content_bytes = raw_content.encode('utf-8')
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'raw_content' must be provided.")

    print(f"\n--- Processing ID: {process_id} ---")
    print("Classifying format and intent...")
    try:
        classifier_input = content_bytes if content_bytes and classifier_agent.classify_format_heuristic(content_bytes) == "PDF" else (content_str or content_bytes.decode('utf-8', errors='ignore'))
        
        classification_result = with_retry(classifier_agent.process, process_id, classifier_input)
    except Exception as e:
        memory.add_entry(process_id, "classification_error", {"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")

    print(f"Routing to agent based on classification: Format={classification_result.format}, Intent={classification_result.intent}")
    processing_status = "Processing in progress"
    agent_output: Optional[Dict[str, Any]] = None

    try:
        if classification_result.format == "Email":
            if not content_str:
                raise HTTPException(status_code=400, detail="Email content must be decodeable to string.")
            agent_output = with_retry(email_agent.process, process_id, content_str).model_dump()
            processing_status = "Email processed"
        elif classification_result.format == "JSON":
            if not content_str:
                raise HTTPException(status_code=400, detail="JSON content must be decodeable to string.")
            agent_output = with_retry(json_agent.process, process_id, content_str).model_dump()
            processing_status = "JSON processed"
        elif classification_result.format == "PDF":
            if not content_bytes:
                raise HTTPException(status_code=400, detail="PDF content must be provided as bytes.")
            agent_output = with_retry(pdf_agent.process, process_id, content_bytes).model_dump()
            processing_status = "PDF processed"
        else:
            processing_status = "Unknown format, no specialized agent action"
            memory.add_entry(process_id, "routing_decision", {"agent": "None", "reason": "Unknown format"})

    except Exception as e:
        processing_status = f"Agent processing failed: {e}"
        memory.add_entry(process_id, "agent_processing_error", {"error": str(e)})
        print(f"Error during specialized agent processing: {e}")


    end_time = time.time()
    memory.add_entry(process_id, "processing_summary", {
        "status": processing_status,
        "duration_seconds": end_time - start_time
    })

    full_trace = memory.get_all_entries_for_process(process_id)
    print(f"--- Processing complete for ID: {process_id} ---")
    return JSONResponse(content={"process_id": process_id, "status": processing_status, "trace": full_trace})


@app.get("/trace/{process_id}")
async def get_trace(process_id: str):
    """
    Retrieves the full processing trace for a given process_id from shared memory.
    """
    trace = memory.get_all_entries_for_process(process_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Process ID not found.")
    return JSONResponse(content={"process_id": process_id, "trace": trace})

@app.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {"status": "ok", "message": "Multi-Agent System is running"}