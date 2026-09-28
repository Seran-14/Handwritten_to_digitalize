# Document & Handwritten Text Digitizer

A modular, high-performance web application and REST API built with **Python**, **FastAPI**, **Google Gemini Vision**, and **Qwen Vision AI** to digitize handwritten documents, printed scans, multi-page PDFs, and Word documents in seconds.

---

## 📁 Architecture

```
Digitalise AI/
├── static/
│   ├── index.html        # Clean HTML5 UI
│   ├── style.css         # Glassmorphic Dark Design System
│   └── app.js            # Client-side dropzone, upload, & export logic
├── main.py               # Lightweight FastAPI Backend & REST Endpoints
├── test_system.py        # Automated test suite
├── requirements.txt      # Project dependencies
└── .env                  # API keys configuration
```

---

## 🚀 Features & Exports

- **Supported Vision Models**:
  1. **✨ gemini-2.0-flash / 2.5** — High accuracy handwriting & multi-page layouts.
  2. **⚡ Qwen2.5-VL-7B** — Lightweight, high-speed vision via Groq.
  3. **🚀 qwen/qwen3.8-27b** — Strong language & vision reasoning via Groq.
- **Export Formats**:
  - 📄 **Word Document (`.docx`)**: Download formatted Word documents directly.
  - 📑 **PDF Document (`.pdf`)**: Download formatted, wrapped PDF pages.
  - 📋 **Copy to Clipboard**: Quick copy raw digitized text.

---

## 🛠️ Setup & Running

### 1. Configure API Keys
Set your keys in [`.env`](file:///d:/Digitalise%20AI/.env):
```env
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

### 2. Run the Application
```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- **Web App**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Run Automated Tests
```powershell
python test_system.py
```

### 4. Deployment link 
 click here :  https://handwritten-to-digitalize.onrender.com
