import pandas as pd
from typing import List, Dict, Any, Tuple
from fuzzywuzzy import fuzz
from datetime import datetime
import math
from app.models.schemas import ReconciliationMatch, ReconciliationReport, ColumnMapping, ReconciliationRequest

class ReconciliationService:
    def __init__(self):
        self.portal_mappings = {}
        self.books_mappings = {}

    def set_mappings(self, file_id: str, mappings: List[ColumnMapping], is_portal: bool):
        """Store column mappings for later use in reconciliation."""
        mapped_dict = {m.mapped_field: m for m in mappings}
        if is_portal:
            self.portal_mappings[file_id] = mapped_dict
        else:
            self.books_mappings[file_id] = mapped_dict

    def _get_value(self, row: pd.Series, mapping: ColumnMapping) -> Any:
        if mapping.is_multi_column and mapping.additional_columns:
            # e.g., sum up multiple tax columns
            val = row.get(mapping.column_name, 0)
            if pd.isna(val): val = 0
            for col in mapping.additional_columns:
                add_val = row.get(col, 0)
                if not pd.isna(add_val):
                    val += add_val
            return val
        else:
            val = row.get(mapping.column_name)
            return val if not pd.isna(val) else None

    def _extract_standardized_record(self, row: pd.Series, mappings: Dict[str, ColumnMapping]) -> Dict[str, Any]:
        """Extract standard fields based on mappings."""
        record = {}
        # We need standard fields to compare: gstin, invoice_number, date, taxable_value, tax_amount
        for field in ['gstin', 'invoice_number', 'date', 'taxable_value', 'tax_amount']:
            if field in mappings:
                record[field] = self._get_value(row, mappings[field])
            else:
                record[field] = None

        # Store original data for reference, converting NaNs to None for JSON serialization
        record['original_data'] = row.where(pd.notnull(row), None).to_dict()
        return record

    def reconcile(self, portal_df: pd.DataFrame, books_df: pd.DataFrame, request: ReconciliationRequest) -> ReconciliationReport:
        """Main reconciliation logic"""
        if request.portal_mappings is not None:
            portal_map = {m.mapped_field: m for m in request.portal_mappings}
        else:
            portal_map = self.portal_mappings.get(request.portal_file_id, {})

        if request.books_mappings is not None:
            books_map = {m.mapped_field: m for m in request.books_mappings}
        else:
            books_map = self.books_mappings.get(request.books_file_id, {})

        portal_records = [self._extract_standardized_record(row, portal_map) for _, row in portal_df.iterrows()]
        books_records = [self._extract_standardized_record(row, books_map) for _, row in books_df.iterrows()]

        matches = []
        unmatched_portal = []
        unmatched_books = list(books_records) # Start with all, remove as they match

        exact_count = 0
        near_count = 0

        # Exact Matches
        for p_rec in portal_records:
            matched_b = None
            for b_rec in unmatched_books:
                # Basic criteria for exact match: GSTIN, Invoice No, and Amount within tiny tolerance
                p_gstin = str(p_rec.get('gstin')).strip().upper() if p_rec.get('gstin') is not None else None
                b_gstin = str(b_rec.get('gstin')).strip().upper() if b_rec.get('gstin') is not None else None
                p_inv = str(p_rec.get('invoice_number')).strip().upper() if p_rec.get('invoice_number') is not None else None
                b_inv = str(b_rec.get('invoice_number')).strip().upper() if b_rec.get('invoice_number') is not None else None

                if p_gstin and b_gstin and p_inv and b_inv and p_gstin == b_gstin and p_inv == b_inv:

                    p_amt = float(p_rec.get('taxable_value') or 0)
                    b_amt = float(b_rec.get('taxable_value') or 0)

                    if abs(p_amt - b_amt) <= 0.01: # Essentially exact
                        matched_b = b_rec
                        break

            if matched_b:
                matches.append(ReconciliationMatch(
                    match_type="Exact Match",
                    portal_invoice=p_rec['original_data'],
                    books_invoice=matched_b['original_data'],
                    confidence_score=100.0
                ))
                exact_count += 1
                unmatched_books.remove(matched_b)
            else:
                unmatched_portal.append(p_rec)

        still_unmatched_portal = []

        # Near Matches
        for p_rec in unmatched_portal:
            best_match = None
            best_score = 0
            best_reason = ""

            for b_rec in unmatched_books:
                score = 0
                reasons = []

                # Check GSTIN
                p_gstin = str(p_rec.get('gstin')).strip().upper() if p_rec.get('gstin') is not None else ""
                b_gstin = str(b_rec.get('gstin')).strip().upper() if b_rec.get('gstin') is not None else ""
                if p_gstin and b_gstin and p_gstin == b_gstin:
                    score += 40
                elif p_gstin and b_gstin and fuzz.ratio(p_gstin, b_gstin) > 80:
                    score += 20
                    reasons.append("GSTIN typo")

                # Check Invoice Number
                p_inv = str(p_rec.get('invoice_number')).strip().upper() if p_rec.get('invoice_number') is not None else ""
                b_inv = str(b_rec.get('invoice_number')).strip().upper() if b_rec.get('invoice_number') is not None else ""
                inv_ratio = fuzz.ratio(p_inv, b_inv) if p_inv and b_inv else 0
                if p_inv and b_inv and p_inv == b_inv:
                    score += 40
                elif p_inv and b_inv and inv_ratio > 80:
                    score += 20
                    reasons.append(f"Invoice fuzzy match ({inv_ratio}%)")

                # Check Amount with Tolerance
                p_amt = float(p_rec.get('taxable_value') or 0)
                b_amt = float(b_rec.get('taxable_value') or 0)
                amt_diff = abs(p_amt - b_amt)

                if amt_diff <= 0.01:
                    score += 20
                elif amt_diff <= request.amount_tolerance:
                    score += 10
                    reasons.append(f"Amount difference within tolerance ({amt_diff:.2f})")

                # If score is good enough (e.g., > 60), it's a near match
                if score > best_score and score >= 60:
                    best_score = score
                    best_match = b_rec
                    best_reason = ", ".join(reasons) if reasons else "Near match criteria met"

            if best_match:
                matches.append(ReconciliationMatch(
                    match_type="Near Match",
                    portal_invoice=p_rec['original_data'],
                    books_invoice=best_match['original_data'],
                    confidence_score=float(best_score),
                    mismatch_reason=best_reason
                ))
                near_count += 1
                unmatched_books.remove(best_match)
            else:
                still_unmatched_portal.append(p_rec)

        # Missing In Books / Portal
        missing_in_books_count = len(still_unmatched_portal)
        missing_in_portal_count = len(unmatched_books)

        for p_rec in still_unmatched_portal:
            matches.append(ReconciliationMatch(
                match_type="Missing in Books",
                portal_invoice=p_rec['original_data'],
                confidence_score=0.0,
                mismatch_reason="No matching record found in books"
            ))

        for b_rec in unmatched_books:
            matches.append(ReconciliationMatch(
                match_type="Missing in Portal",
                books_invoice=b_rec['original_data'],
                confidence_score=0.0,
                mismatch_reason="No matching record found in portal"
            ))

        return ReconciliationReport(
            total_portal_records=len(portal_records),
            total_books_records=len(books_records),
            exact_matches=exact_count,
            near_matches=near_count,
            missing_in_books=missing_in_books_count,
            missing_in_portal=missing_in_portal_count,
            gstin_mismatch=0,
            tax_mismatch=0,
            cross_tax_mismatch=0,
            blocked_credit_detected=0,
            matches=matches
        )

reconciliation_service = ReconciliationService()
