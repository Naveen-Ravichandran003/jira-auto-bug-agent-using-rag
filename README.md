# 🐜 Jira Auto-Bug Mapping AI Agent Using RAG

An Enterprise AI Agent that automatically converts screenshots, PDFs, and text into structured, hallucination-free Jira bug tickets using a local RAG pipeline and Groq.

## 🌟 Overview

**jira-auto-bug-agent-using-rag** is an enterprise-grade automation tool designed to eliminate manual bug reporting. Using a local RAG (Retrieval-Augmented Generation) pipeline and high-speed LLM inference, this agent ingests evidence, extracts context, and generates highly structured Jira bug payloads.

Built with strict anti-hallucination guardrails, the agent guarantees zero assumptions—if the evidence isn't there, it won't make it up. 

## ✨ Key Features

- **Multi-Source Evidence Ingestion:** Accepts screenshots, PDFs, linked Jira tickets, or raw text descriptions.
- **Local RAG Pipeline:** Utilizes `FAISS` and `SentenceTransformers` to index and retrieve relevant evidence chunks locally, ensuring data privacy.
- **Anti-Hallucination Enforcement:** Strict systemic guardrails ensure the LLM only generates bug details explicitly found in the evidence.
- **Deterministic API Mapping:** Validates generated bug payloads against Jira's API schemas before submission (No LLM hallucinations touching the API).
- **Automated Evidence Attachment:** Automatically uploads your original screenshots or PDFs directly to the created Jira ticket.
- **Enterprise UI:** A dark-themed, 3-panel dashboard for managing configurations, uploading evidence, and reviewing bugs before submission.

## 🏗️ Architecture Stack

- **Backend:** FastAPI, Uvicorn, Python
- **AI / LLM:** Groq API, LangChain
- **Vector Database:** FAISS (Local)
- **Embeddings:** SentenceTransformers (Local)
- **Data Extraction:** PyTesseract, EasyOCR, PyPDF2, pdfplumber
- **Validation:** Pydantic

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- A Jira Cloud account (Base URL, Email, and API Token)
- A Groq API Key

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Naveen-Ravichandran003/jira-auto-bug-agent-using-rag.git
   cd jira-auto-bug-agent-using-rag
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   *Note: You can also configure credentials directly via the Enterprise UI.*

4. **Run the Application:**
   ```bash
   python src/main.py
   ```
   *The server will start at `http://localhost:8000`. Note: On the very first run, it will download the local embedding model from HuggingFace.*

## 🔒 Security & Privacy
- **No Direct LLM API Calls:** The LLM is never given direct access to your Jira API. All submissions go through a deterministic validation layer.
- **Local Vector Storage:** FAISS runs locally. Your evidence is not sent to external vector databases.
- **Zero Persistence:** User session data and temporary files are automatically cleaned up after bug submission.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
