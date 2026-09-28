import base64
import io
import os
import sys
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Document & Handwritten Text Digitizer",
    description="Microservice API for digitizing documents via Gemini and Qwen Vision models.",
    version="5.0.0",
)

# Mount static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Supported file types
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_DOC_EXTS = {".pdf", ".docx", ".doc"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTS.union(ALLOWED_DOC_EXTS)

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}

PROMPT = (
    "You are an expert document OCR and handwriting transcription engine.\n"
    "Transcribe all handwritten and printed text in this document/image verbatim with high precision.\n"
    "Rules:\n"
    "- Maintain original line breaks, formatting, headings, and tabular layout structure where logical.\n"
    "- If some handwriting is degraded or unclear, make your best high-confidence interpretation.\n"
    "- Do NOT add conversational greetings, explanations, markdown commentary, or code wrapping.\n"
    "- Return ONLY the verbatim transcribed text."
)

SUPPORTED_MODELS = [
    {
        "id": "gemini-2.0-flash",
        "name": "✨ gemini-2.0-flash / 2.5 (Accurate & Perfect)",
        "provider": "google",
        "tag": "Accurate & Perfect"
    },
    {
        "id": "qwen/qwen-2.5-vl-7b-instruct",
        "name": "⚡ Qwen2.5-VL-7B (Good)",
        "provider": "groq",
        "tag": "Good"
    },
    {
        "id": "qwen/qwen3.8-27b",
        "name": "🚀 qwen/qwen3.8-27b (Good)",
        "provider": "groq",
        "tag": "Good"
    },
]


def log(msg: str):
    """Utility logger to guarantee immediate, formatted terminal logging."""
    print(msg, flush=True)


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        log("[CONFIG] ❌ GEMINI_API_KEY is not set in .env")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gemini API key not found. Please set GEMINI_API_KEY in your .env file.",
        )
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        log(f"[CONFIG] ❌ Failed to initialize Google GenAI Client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Gemini Client: {str(e)}",
        )


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        log("[CONFIG] ❌ GROQ_API_KEY is not set in .env")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Groq API key not found. Please set GROQ_API_KEY in your .env file.",
        )
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception as e:
        log(f"[CONFIG] ❌ Failed to initialize Groq Client: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Groq Client: {str(e)}",
        )


def extract_text_from_docx(content_bytes: bytes) -> str:
    """Extracts text and tables directly from Word (.docx) documents."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(content_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_text:
                    paragraphs.append(row_text)
        return "\n\n".join(paragraphs).strip()
    except Exception as e:
        log(f"[DOCX] ❌ DOCX Parse Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read DOCX file: {str(e)}",
        )


def extract_text_from_pdf(content_bytes: bytes) -> str:
    """Extracts text from PDF text-layer if present."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content_bytes))
        pages_text = [page.extract_text() for page in reader.pages if page.extract_text()]
        if pages_text:
            return "\n\n--- Page Break ---\n\n".join(pages_text).strip()
    except Exception:
        pass
    return ""


def process_with_gemini(content_bytes: bytes, mime_type: str, model_id: str = "gemini-2.0-flash") -> str:
    log(f"\n[GEMINI] 🤖 Connecting to Gemini API (Target Model: '{model_id}')...")
    client = get_gemini_client()
    from google.genai import types

    # Dynamically find valid live Gemini models from the API
    try:
        live_gemini = [
            m.name.replace("models/", "")
            for m in client.models.list()
            if m.name and "gemini" in m.name.lower() and "embed" not in m.name.lower()
        ]
        log(f"[GEMINI] 📡 Connected to Google AI. Live models available: {', '.join(live_gemini[:4])}...")
    except Exception as e:
        log(f"[GEMINI] ⚠️ Could not fetch live models list ({e}). Using priority fallback chain.")
        live_gemini = []

    priority_order = [
        model_id,
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest"
    ]
    
    candidate_models = []
    for m in priority_order + live_gemini:
        if m and m not in candidate_models:
            candidate_models.append(m)

    last_error = None
    for m in candidate_models:
        try:
            log(f"[GEMINI] 🚀 Uploading payload ({len(content_bytes) / 1024:.1f} KB, {mime_type}) -> Prompting '{m}'...")
            part = types.Part.from_bytes(data=content_bytes, mime_type=mime_type)
            response = client.models.generate_content(
                model=m,
                contents=[part, PROMPT],
            )
            if response and response.text:
                extracted_len = len(response.text.strip())
                log(f"[GEMINI] ✅ Successfully transcribed with '{m}' ({extracted_len} chars generated).")
                return response.text.strip()
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            log(f"[GEMINI] ⚠️ Candidate '{m}' returned: {e}. Trying next model...")
            if "401" in err_str or "unauthorized" in err_str or "api_key_invalid" in err_str:
                log("[GEMINI] ❌ Unauthorized: Check GEMINI_API_KEY.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Gemini API key. Please check GEMINI_API_KEY in .env.",
                )
            continue

    log(f"[GEMINI] ❌ All Gemini candidates exhausted. Error: {last_error}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Gemini transcription failed. Last error: {str(last_error)}",
    )


def process_with_groq(content_bytes: bytes, mime_type: str, model_id: str) -> str:
    log(f"\n[GROQ] 🤖 Connecting to Groq Vision API (Model: '{model_id}')...")
    groq_client = get_groq_client()

    if "pdf" in mime_type:
        log("[GROQ] 📄 PDF file received. Checking digital text layer...")
        text = extract_text_from_pdf(content_bytes)
        if text:
            log(f"[GROQ] ✅ Extracted {len(text)} chars from digital PDF layer.")
            return text
        log("[GROQ] ⚠️ Scanned PDF with no text layer. Routing to Gemini Vision...")
        return process_with_gemini(content_bytes, mime_type, "gemini-2.0-flash")

    base64_image = base64.b64encode(content_bytes).decode('utf-8')
    image_url = f"data:{mime_type};base64,{base64_image}"

    try:
        log(f"[GROQ] 🚀 Uploading image payload ({len(content_bytes) / 1024:.1f} KB) -> Querying '{model_id}'...")
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                }
            ],
            model=model_id,
        )
        if chat_completion.choices and len(chat_completion.choices) > 0:
            extracted = chat_completion.choices[0].message.content.strip()
            log(f"[GROQ] ✅ Transcribed successfully ({len(extracted)} chars returned).")
            return extracted
    except Exception as e:
        err_str = str(e)
        log(f"[GROQ] ⚠️ Groq API Error: {err_str}")
        if "model_not_found" in err_str or "does not exist" in err_str or "not found" in err_str.lower():
            log("[GROQ] 🔄 Model ID unavailable. Gracefully falling over to Gemini 2.0 Flash...")
            return process_with_gemini(content_bytes, mime_type, "gemini-2.0-flash")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Groq API error with {model_id}: {err_str}",
        )
    return ""


def process_single_file(
    content_bytes: bytes,
    filename: str,
    mime_type: str,
    selected_model: str,
) -> tuple[str, str]:
    file_ext = Path(filename).suffix.lower()
    file_size_kb = len(content_bytes) / 1024
    log("\n" + "=" * 60)
    log(f"[PIPELINE] 📥 Processing: '{filename}' ({file_size_kb:.1f} KB | {mime_type})")
    log(f"[PIPELINE] 🎯 Model Selected: '{selected_model}'")

    # Native DOCX parsing
    if file_ext == ".docx":
        log("[PIPELINE] 📝 Parsing Word Document (.docx) natively...")
        docx_text = extract_text_from_docx(content_bytes)
        if docx_text:
            log(f"[PIPELINE] ✅ Word document parsed ({len(docx_text)} chars).")
            return docx_text, "docx-native-parser"

    model_choice = selected_model.strip() if selected_model else "gemini-2.0-flash"
    
    if "qwen" in model_choice.lower():
        try:
            extracted = process_with_groq(content_bytes, mime_type, model_choice)
            if extracted:
                return extracted, model_choice
        except Exception as e:
            log(f"[PIPELINE] ⚠️ Groq pipeline error ({e}). Falling back to Gemini 2.0 Flash...")
            extracted = process_with_gemini(content_bytes, mime_type, "gemini-2.0-flash")
            return extracted, f"{model_choice} (Fallback: gemini-2.0-flash)"
    
    extracted = process_with_gemini(content_bytes, mime_type, model_choice)
    return extracted, model_choice


class ExportRequest(BaseModel):
    text: str
    filename: Optional[str] = "digitized_document"


def build_docx_buffer(text: str) -> io.BytesIO:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = docx.Document()
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    heading = doc.add_paragraph()
    heading_run = heading.add_run("Digitized Document Output")
    heading_run.font.name = "Calibri"
    heading_run.font.size = Pt(18)
    heading_run.font.bold = True
    heading_run.font.color.rgb = RGBColor(30, 41, 59)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    doc.add_paragraph()

    for line in text.split("\n"):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(line if line.strip() else "")
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(15, 23, 42)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def build_pdf_buffer(text: str) -> io.BytesIO:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.colors import HexColor

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter

        margin = 54
        line_height = 14
        y = height - margin

        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(HexColor("#1e293b"))
        c.drawString(margin, y, "Digitized Document Output")
        y -= 25

        c.setStrokeColor(HexColor("#cbd5e1"))
        c.setLineWidth(1)
        c.line(margin, y, width - margin, y)
        y -= 20

        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#0f172a"))

        for raw_line in text.split("\n"):
            line = raw_line.rstrip()
            if not line:
                y -= line_height
                if y < margin:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    c.setFillColor(HexColor("#0f172a"))
                    y = height - margin
                continue

            words = line.split(" ")
            curr_line = ""
            for w in words:
                test_line = f"{curr_line} {w}".strip()
                if c.stringWidth(test_line, "Helvetica", 10) < (width - 2 * margin):
                    curr_line = test_line
                else:
                    c.drawString(margin, y, curr_line)
                    y -= line_height
                    if y < margin:
                        c.showPage()
                        c.setFont("Helvetica", 10)
                        c.setFillColor(HexColor("#0f172a"))
                        y = height - margin
                    curr_line = w
            if curr_line:
                c.drawString(margin, y, curr_line)
                y -= line_height
                if y < margin:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    c.setFillColor(HexColor("#0f172a"))
                    y = height - margin

        c.save()
        buf.seek(0)
        return buf
    except ImportError:
        # Minimalist valid PDF generator without external dependencies
        buf = io.BytesIO()
        escaped_lines = []
        for line in text.split("\n"):
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            escaped_lines.append(f"({safe_line}) Tj T*")
        stream_content = "BT\n/F1 12 Tf\n50 750 Td\n15 TL\n" + "\n".join(escaped_lines) + "\nET"
        stream_len = len(stream_content.encode("latin-1", "replace"))

        pdf_data = (
            f"%PDF-1.4\n"
            f"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            f"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            f"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
            f"4 0 obj\n<< /Length {stream_len} >>\nstream\n{stream_content}\nendstream\nendobj\n"
            f"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
            f"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n"
            f"0000000{300 + stream_len:03d} 00000 n \n"
            f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{400 + stream_len}\n%%EOF"
        )
        buf.write(pdf_data.encode("latin-1", "replace"))
        buf.seek(0)
        return buf



# --- REST ENDPOINTS ---

@app.get("/", summary="Web Interface")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/models", summary="List Live Models")
async def list_models():
    return JSONResponse(status_code=status.HTTP_200_OK, content={"models": SUPPORTED_MODELS})


@app.post("/extract-text", summary="Extract Text from Images, PDFs, or DOCX")
async def extract_text(
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    model: Optional[str] = Form(None, description="Model ID to use")
):
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file:
        upload_list.append(file)

    if not upload_list:
        log("[API] ⚠️ Received /extract-text request with 0 files.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. Please upload at least one image, PDF, or DOCX file.",
        )

    selected_model = (model or "").strip() or "gemini-2.0-flash"
    log("\n" + "=" * 60)
    log(f"[API] 📬 Received Batch Upload: {len(upload_list)} file(s)")
    log(f"[API] ⚙️ Selected Engine: '{selected_model}'")
    log("=" * 60)

    results = []
    used_models = set()

    for idx, item in enumerate(upload_list, 1):
        filename = item.filename or "uploaded_file"
        file_ext = Path(filename).suffix.lower()
        log(f"\n[FILE {idx}/{len(upload_list)}] 📄 Ingesting: '{filename}'")

        if file_ext not in ALLOWED_EXTENSIONS:
            log(f"[FILE {idx}] ❌ Unsupported file format: '{file_ext}'")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file '{filename}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        mime_type = item.content_type if item.content_type and item.content_type != "application/octet-stream" else MIME_MAP.get(file_ext, "application/pdf" if file_ext == ".pdf" else "image/jpeg")

        try:
            content_bytes = await item.read()
            log(f"[FILE {idx}] 💾 Memory buffer loaded: {len(content_bytes) / 1024:.1f} KB")
        except Exception as e:
            log(f"[FILE {idx}] ❌ Read error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read file {filename}: {str(e)}",
            )

        if not content_bytes:
            log(f"[FILE {idx}] ⚠️ File is empty, skipping.")
            continue

        text, model_used = process_single_file(
            content_bytes=content_bytes,
            filename=filename,
            mime_type=mime_type,
            selected_model=selected_model,
        )

        results.append({
            "filename": filename,
            "text": text,
            "model": model_used
        })
        used_models.add(model_used)

    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded files were empty.",
        )

    log("\n" + "=" * 60)
    log(f"[API] ✨ Completed batch of {len(results)} file(s).")
    log(f"[API] 📦 Models utilized: {', '.join(used_models)}")
    log("=" * 60 + "\n")

    if len(results) == 1:
        aggregated_text = results[0]["text"]
    else:
        aggregated_text = "\n\n" + ("=" * 50) + "\n\n".join(
            f"📄 FILE: {res['filename']} (Engine: {res['model']})\n{'-' * 50}\n{res['text']}"
            for res in results
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "text": aggregated_text,
            "model": ", ".join(used_models),
            "files_processed": len(results),
            "details": results,
        },
    )


@app.post("/export/docx", summary="Download Output as Microsoft Word (.docx)")
async def export_docx(req: ExportRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="No text provided for export.")
    log(f"[EXPORT] 📄 Generating DOCX export ({len(req.text)} chars)...")
    buf = build_docx_buffer(req.text)
    filename = f"{req.filename or 'digitized_output'}.docx"
    log("[EXPORT] ✅ DOCX generated successfully.")
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/export/pdf", summary="Download Output as PDF Document (.pdf)")
async def export_pdf(req: ExportRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="No text provided for export.")
    log(f"[EXPORT] 📑 Generating PDF export ({len(req.text)} chars)...")
    buf = build_pdf_buffer(req.text)
    filename = f"{req.filename or 'digitized_output'}.pdf"
    log("[EXPORT] ✅ PDF generated successfully.")
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
