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

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_upload_and_reconcile():
    # 1. Create Portal Data
    portal_data = {
        'GSTIN of Supplier': ['27AAAAA1234A1Z5', '27BBBBB1234B1Z5'],
        'Invoice number': ['INV-001', 'INV-002'],
        'Invoice Date': ['01-01-2023', '02-01-2023'],
        'Taxable Value': [1000.0, 2000.0],
        'Tax Amount': [180.0, 360.0]
    }
    portal_excel = create_mock_excel(portal_data, 'portal.xlsx')

    # 2. Create Books Data
    books_data = {
        'Supplier GSTIN': ['27AAAAA1234A1Z5', '27CCCCC1234C1Z5'],
        'Bill No': ['INV-001', 'INV-003'], # Exact match on INV-001
        'Bill Date': ['01-01-2023', '03-01-2023'],
        'Basic Amount': [1000.0, 1500.0],
        'Tax': [180.0, 270.0]
    }
    books_excel = create_mock_excel(books_data, 'books.xlsx')

    # Upload Portal
    res_portal = client.post("/upload", files={"file": ("portal.xlsx", portal_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert res_portal.status_code == 200
    portal_id = res_portal.json()['file_id']

    # Upload Books
    res_books = client.post("/upload", files={"file": ("books.xlsx", books_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert res_books.status_code == 200
    books_id = res_books.json()['file_id']

    # Map Columns for Portal
    res_map_p = client.post("/map-columns", json={
        "file_id": portal_id,
        "sheet_name": "Sheet1",
        "voucher_type": "portal",
        "mappings": [
            {"column_name": "GSTIN of Supplier", "mapped_field": "gstin"},
            {"column_name": "Invoice number", "mapped_field": "invoice_number"},
            {"column_name": "Taxable Value", "mapped_field": "taxable_value"}
        ]
    })
    assert res_map_p.status_code == 200

    # Map Columns for Books
    res_map_b = client.post("/map-columns", json={
        "file_id": books_id,
        "sheet_name": "Sheet1",
        "voucher_type": "books",
        "mappings": [
            {"column_name": "Supplier GSTIN", "mapped_field": "gstin"},
            {"column_name": "Bill No", "mapped_field": "invoice_number"},
            {"column_name": "Basic Amount", "mapped_field": "taxable_value"}
        ]
    })
    assert res_map_b.status_code == 200

    # Reconcile
    res_recon = client.post("/reconcile", json={
        "portal_file_id": portal_id,
        "portal_sheet": "Sheet1",
        "books_file_id": books_id,
        "books_sheet": "Sheet1",
        "amount_tolerance": 1.0,
        "date_tolerance": 3
    })

    assert res_recon.status_code == 200
    report = res_recon.json()

    assert report['total_portal_records'] == 2
    assert report['total_books_records'] == 2
    assert report['exact_matches'] == 1
    assert report['missing_in_books'] == 1 # INV-002
    assert report['missing_in_portal'] == 1 # INV-003
