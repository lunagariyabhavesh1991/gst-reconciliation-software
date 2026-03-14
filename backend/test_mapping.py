import pytest
from fastapi.testclient import TestClient
from app.main import app
import pandas as pd
import io

client = TestClient(app)

def create_mock_excel(data, filename):
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    buffer.seek(0)
    return buffer

def test_detect_headers_and_mapping():
    data = {
        'GSTIN/UIN of Supplier': ['27AAAAA1234A1Z5'],
        'Invoice #': ['INV-001'],
        'Date': ['01-01-2023'],
        'Taxable Amount': [1000.0],
        'Total Tax': [180.0]
    }
    excel_file = create_mock_excel(data, 'test.xlsx')

    # Upload
    res_upload = client.post("/upload", files={"file": ("test.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert res_upload.status_code == 200
    file_id = res_upload.json()['file_id']

    # Detect headers and get suggestions
    res_detect = client.post("/detect-headers", json={
        "file_id": file_id,
        "sheet_name": "Sheet1"
    })

    assert res_detect.status_code == 200
    data = res_detect.json()

    assert data['header_row'] == 1
    assert 'GSTIN/UIN of Supplier' in data['headers']

    # Check if mappings are correctly suggested using fuzzywuzzy
    suggestions = data['suggested_mappings']
    assert suggestions['GSTIN/UIN of Supplier'] == 'gstin'
    assert suggestions['Invoice #'] == 'invoice_number'
    assert suggestions['Taxable Amount'] == 'taxable_value'
    assert suggestions['Total Tax'] == 'tax_amount'
    assert suggestions['Date'] == 'date'

def test_missing_column_validation():
    # Attempt reconciliation with missing mappings
    res_recon = client.post("/reconcile", json={
        "portal_file_id": "dummy",
        "portal_sheet": "Sheet1",
        "books_file_id": "dummy2",
        "books_sheet": "Sheet1",
        "portal_mappings": [
            {"column_name": "Some Column", "mapped_field": "taxable_value"}
        ],
        "books_mappings": [
            {"column_name": "Some Column", "mapped_field": "taxable_value"}
        ]
    })

    assert res_recon.status_code == 400
    assert "Missing required mapping 'gstin'" in res_recon.json()['detail']
