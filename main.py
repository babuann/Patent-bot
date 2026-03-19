import os
import json
import logging
from typing import List, Dict, Any, TypedDict
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# LangGraph and Langchain imports
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

app = FastAPI(title="IP Research Lab API - Multi-Agent LangGraph (Gemini Edition)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResearchRequest(BaseModel):
    topic: str
    api_key: str = None  # We will ignore this and use the hardcoded requested one

# --- LangGraph State ---
class AgentState(TypedDict):
    topic: str
    sub_domains: List[str]
    patents: List[Dict[str, Any]]
    keywords: List[Dict[str, Any]]
    wipo_links: List[str]
    final_report: Dict[str, Any]
    error: str

# Load Gemini API Key from environment (Set locally in .env, or in Render Dashboard)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logging.warning("No GEMINI_API_KEY found in environment variables!")

# --- Agent Nodes ---
def scope_topic_node(state: AgentState) -> AgentState:
    topic = state.get("topic", "")
    
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            google_api_key=GEMINI_API_KEY, 
            temperature=0.4
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an IP research scoping agent. Break the down user's topic into 3 specific technical sub-domains. Return ONLY a valid JSON array of strings."),
            ("user", "Topic: {topic}")
        ])
        
        response = llm.invoke(prompt.format_messages(topic=topic))
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
            
        state["sub_domains"] = json.loads(content.strip())
    except Exception as e:
        logging.error(f"Scope Node Error: {e}")
        state["sub_domains"] = ["Compilation Methods", "Architecture", "ML Deployment"]
        
    return state

def generate_patents_node(state: AgentState) -> AgentState:
    topic = state.get("topic", "")
    sub_domains = state.get("sub_domains", [])
    
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            google_api_key=GEMINI_API_KEY, 
            temperature=0.7
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Generate 5 mock patents for the given topic and sub-domains. Return ONLY a valid JSON array of objects with keys: publication_number (String), title (String), abstract (String), cpc_codes (Array of Strings), assignee (String), date (String YYYY-MM-DD)."),
            ("user", "Topic: {topic}\nSub-domains: {sub_domains}")
        ])
        
        response = llm.invoke(prompt.format_messages(topic=topic, sub_domains=", ".join(sub_domains)))
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
            
        state["patents"] = json.loads(content.strip())
    except Exception as e:
        logging.error(f"Patent Node Error: {e}")
        state["patents"] = _mock_patents(topic)
        
    return state

def extract_keywords_node(state: AgentState) -> AgentState:
    topic = state.get("topic", "")
    patents = state.get("patents", [])
    
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            google_api_key=GEMINI_API_KEY, 
            temperature=0.2
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract 8-10 keywords from these patents. Cluster them. Return ONLY a valid JSON array of objects with keys: keyword (String), cluster (String, e.g. 'Methods', 'Materials'), score (Float 0.0-1.0)."),
            ("user", "Patents: {patents}")
        ])
        
        response = llm.invoke(prompt.format_messages(patents=json.dumps(patents[:3]))) 
        content = response.content
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
            
        state["keywords"] = json.loads(content.strip())
    except Exception as e:
        logging.error(f"Keyword Node Error: {e}")
        state["keywords"] = _mock_keywords(topic)
        
    return state

def format_report_node(state: AgentState) -> AgentState:
    state["final_report"] = {
        "sub_domains": state.get("sub_domains", []),
        "patents": state.get("patents", []),
        "keywords": state.get("keywords", [])
    }
    return state

# --- Build LangGraph ---
workflow = StateGraph(AgentState)
workflow.add_node("scope_agent", scope_topic_node)
workflow.add_node("search_agent", generate_patents_node)
workflow.add_node("extract_agent", extract_keywords_node)
workflow.add_node("formatter_node", format_report_node)

workflow.add_edge("scope_agent", "search_agent")
workflow.add_edge("search_agent", "extract_agent")
workflow.add_edge("extract_agent", "formatter_node")
workflow.add_edge("formatter_node", END)

workflow.set_entry_point("scope_agent")
app_graph = workflow.compile()

# --- API Endpoints ---
@app.post("/api/research")
async def generate_research(request: ResearchRequest):
    if not request.topic:
        raise HTTPException(status_code=400, detail="Topic is required")
        
    try:
        # Execute the LangGraph chain using Gemini dynamically
        final_state = app_graph.invoke({"topic": request.topic, "error": ""})
        return final_state["final_report"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Mocks (Fallbacks) ---
def _mock_patents(topic):
    return [
        {
          "publication_number": "US-11029384-B2",
          "title": f"System and Method for Accelerated {topic.title()}",
          "abstract": f"A novel approach to {topic} utilizing distributed micro-architectures to enhance efficiency and reduce computational overhead.",
          "cpc_codes": ["G06F8/60", "H04L67/02"],
          "assignee": "Global Tech Innovations LLC",
          "date": "2023-11-14"
        },
        {
          "publication_number": "US-2024098765-A1",
          "title": f"Framework for Intelligent {topic.title()} Analysis",
          "abstract": "Disclosed is a software framework that intercepts runtime operations and compiles them JIT for optimal execution on specialized hardware accelerators.",
          "cpc_codes": ["G06N3/08", "G06F8/443"],
          "assignee": "Microsoft Corp",
          "date": "2024-02-02"
        }
    ]

def _mock_keywords(topic):
    return [
        {"keyword": f"{topic} optimization", "cluster": "Methods", "score": 0.96},
        {"keyword": "distributed computing", "cluster": "Infrastructure", "score": 0.88}
    ]

# Mount static files correctly
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
