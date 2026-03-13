from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    sheets: List[str]
    row_count: int
    upload_time: datetime

class HeaderDetectionRequest(BaseModel):
    file_id: str
    sheet_name: str
    manual_header_row: Optional[int] = None

class HeaderDetectionResponse(BaseModel):
    header_row: int
    headers: List[str]
    preview_data: List[Dict[str, Any]]

class ColumnMapping(BaseModel):
    column_name: str
    mapped_field: str
    is_multi_column: bool = False
    additional_columns: Optional[List[str]] = None

class MappingRequest(BaseModel):
    file_id: str
    sheet_name: str
    voucher_type: str
    mappings: List[ColumnMapping]

class ReconciliationRequest(BaseModel):
    portal_file_id: str
    portal_sheet: str
    books_file_id: str
    books_sheet: str
    amount_tolerance: float = 1.0
    date_tolerance: int = 3
    ignore_keywords: Optional[List[str]] = None

class ReconciliationMatch(BaseModel):
    match_type: str
    portal_invoice: Optional[Dict[str, Any]] = None
    books_invoice: Optional[Dict[str, Any]] = None
    confidence_score: float
    mismatch_reason: Optional[str] = None

class ReconciliationReport(BaseModel):
    total_portal_records: int
    total_books_records: int
    exact_matches: int
    near_matches: int
    missing_in_books: int
    missing_in_portal: int
    gstin_mismatch: int
    tax_mismatch: int
    cross_tax_mismatch: int
    blocked_credit_detected: int
    matches: List[ReconciliationMatch]

class ProfileSave(BaseModel):
    profile_name: str
    client_name: str
    mappings: Dict[str, List[ColumnMapping]]
    ignore_keywords: List[str]
    reconciliation_settings: Dict[str, Any]
