import pytest
from fastapi.testclient import TestClient
from app.main import app
import pandas as pd
import io
from app.services.reconciliation import reconciliation_service
from app.models.schemas import ReconciliationRequest, ColumnMapping

client = TestClient(app)

def create_mock_excel(data, filename):
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer) as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    buffer.seek(0)
    return buffer

def test_null_matching():
    # 1. Create Portal Data with missing GSTIN and Invoice
    portal_data = {
        'GSTIN of Supplier': [None, None],
        'Invoice number': [None, None],
        'Invoice Date': ['01-01-2023', '02-01-2023'],
        'Taxable Value': [1000.0, 2000.0],
        'Tax Amount': [180.0, 360.0]
    }
    portal_excel = create_mock_excel(portal_data, 'portal.xlsx')

    # 2. Create Books Data with missing GSTIN and Invoice
    books_data = {
        'Supplier GSTIN': [None, None],
        'Bill No': [None, None],
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

    # Reconcile with explicit mappings to test the state fix as well
    res_recon = client.post("/reconcile", json={
        "portal_file_id": portal_id,
        "portal_sheet": "Sheet1",
        "books_file_id": books_id,
        "books_sheet": "Sheet1",
        "amount_tolerance": 1.0,
        "date_tolerance": 3,
        "portal_mappings": [
            {"column_name": "GSTIN of Supplier", "mapped_field": "gstin"},
            {"column_name": "Invoice number", "mapped_field": "invoice_number"},
            {"column_name": "Taxable Value", "mapped_field": "taxable_value"}
        ],
        "books_mappings": [
            {"column_name": "Supplier GSTIN", "mapped_field": "gstin"},
            {"column_name": "Bill No", "mapped_field": "invoice_number"},
            {"column_name": "Basic Amount", "mapped_field": "taxable_value"}
        ]
    })

    assert res_recon.status_code == 200
    report = res_recon.json()

    assert report['total_portal_records'] == 2
    assert report['total_books_records'] == 2
    # Before the fix, this would have returned exact matches because None == None
    assert report['exact_matches'] == 0
    # Everything should be unmatched because without invoice or gstin, we cannot link records confidently
    assert report['missing_in_books'] == 2
    assert report['missing_in_portal'] == 2
