import io
from fastapi.testclient import TestClient
from main import app, build_docx_buffer, build_pdf_buffer, clean_latex_symbols

client = TestClient(app)

def test_latex_symbol_cleaning():
    raw_sample = (
        "- $\\underline{\\text{Topic}} \\Rightarrow$ Improving Image reconstruction using StyleGAN\n"
        "Instead of forcing Style GAN\n"
        "$\\downarrow$\n"
        "They added Projection Head\n"
        "$\\downarrow$\n"
        "- Style GAN v-2 $\\rightarrow$ Pretrained Image Generator.\n"
        "- $MSE + LPIPS$ loss $\\rightarrow$ measure how close"
    )
    cleaned = clean_latex_symbols(raw_sample)
    assert "\\underline" not in cleaned
    assert "\\text" not in cleaned
    assert "↓" in cleaned
    assert "→" in cleaned
    assert "⇒" in cleaned
    assert "$" not in cleaned
    assert "- Topic ⇒ Improving Image reconstruction using StyleGAN" in cleaned
    print("✅ Test 0 Passed: LaTeX symbols correctly converted to clean Unicode arrows (↓, →, ⇒) and formatted text")

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
    text = "Project : Internal Works | Client Work\nStatus : Completed\nFlow: Step A → Step B ↓ Step C"
    buf = build_docx_buffer(text)
    assert buf.getvalue().startswith(b"PK")  # Standard ZIP / DOCX header
    print(f"✅ Test 3 Passed: DOCX buffer generated with Unicode symbols ({len(buf.getvalue())} bytes)")

def test_docx_endpoint():
    response = client.post("/export/docx", json={"text": "Hello World → Next Step", "filename": "sample"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    print("✅ Test 4 Passed: POST /export/docx works")

if __name__ == "__main__":
    print("\n🚀 Running Automated System Tests...")
    test_latex_symbol_cleaning()
    test_static_index()
    test_models_endpoint()
    test_docx_export_buffer()
    test_docx_endpoint()
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!\n")


