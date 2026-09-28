import io
from fastapi.testclient import TestClient
from main import app, build_docx_buffer, build_pdf_buffer

client = TestClient(app)

def test_static_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "Document &amp; Handwritten Text Digitizer" in response.text
    print("✅ Test 1 Passed: GET / serves index.html")

def test_models_endpoint():
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) == 3
    print("✅ Test 2 Passed: GET /api/models returns all 3 models")

def test_docx_export_buffer():
    text = "Project : Internal Works | Client Work\nStatus : Completed"
    buf = build_docx_buffer(text)
    assert buf.getvalue().startswith(b"PK")  # Standard ZIP / DOCX header
    print(f"✅ Test 3 Passed: DOCX buffer generated ({len(buf.getvalue())} bytes)")

def test_pdf_export_buffer():
    text = "Project : Internal Works | Client Work\nStatus : Completed"
    buf = build_pdf_buffer(text)
    assert buf.getvalue().startswith(b"%PDF")  # Standard PDF header
    print(f"✅ Test 4 Passed: PDF buffer generated ({len(buf.getvalue())} bytes)")

def test_docx_endpoint():
    response = client.post("/export/docx", json={"text": "Hello World", "filename": "sample"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    print("✅ Test 5 Passed: POST /export/docx works")

def test_pdf_endpoint():
    response = client.post("/export/pdf", json={"text": "Hello World", "filename": "sample"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    print("✅ Test 6 Passed: POST /export/pdf works")

if __name__ == "__main__":
    print("\n🚀 Running Automated System Tests...")
    test_static_index()
    test_models_endpoint()
    test_docx_export_buffer()
    test_pdf_export_buffer()
    test_docx_endpoint()
    test_pdf_endpoint()
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!\n")
