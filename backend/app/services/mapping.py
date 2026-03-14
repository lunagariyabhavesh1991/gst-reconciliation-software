from typing import List, Dict
from fuzzywuzzy import process, fuzz

class MappingService:
    def __init__(self):
        # Target standard fields we want to map to
        self.standard_fields = [
            'gstin',
            'invoice_number',
            'date',
            'taxable_value',
            'tax_amount',
            'igst',
            'cgst',
            'sgst'
        ]

        # Common aliases for each standard field to improve fuzzy matching
        self.aliases = {
            'gstin': ['gstin', 'gstin/uin', 'supplier gstin', 'gstin of supplier', 'customer gstin', 'party gstin', 'gst number'],
            'invoice_number': ['invoice number', 'inv no', 'bill no', 'document number', 'doc no', 'invoice #'],
            'date': ['date', 'invoice date', 'bill date', 'document date', 'doc date'],
            'taxable_value': ['taxable value', 'basic value', 'taxable amount', 'base amount', 'assessable value'],
            'tax_amount': ['tax amount', 'total tax', 'tax', 'gst amount'],
            'igst': ['igst', 'integrated tax', 'igst amount'],
            'cgst': ['cgst', 'central tax', 'cgst amount'],
            'sgst': ['sgst', 'state tax', 'sgst amount', 'utgst', 'utgst amount']
        }

    def suggest_mappings(self, headers: List[str]) -> Dict[str, str]:
        """Suggest standard field mapping for a list of headers using fuzzy matching."""
        suggestions = {}

        for header in headers:
            if not header or not isinstance(header, str):
                continue

            header_lower = header.lower().strip()

            best_match_field = None
            best_score = 0

            for field, field_aliases in self.aliases.items():
                # Direct match check first
                if header_lower in field_aliases:
                    best_match_field = field
                    best_score = 100
                    break

                # Fuzzy matching against aliases
                match = process.extractOne(header_lower, field_aliases, scorer=fuzz.token_set_ratio)
                if match:
                    score = match[1]
                    if score > best_score and score >= 80: # Threshold for a good match
                        best_score = score
                        best_match_field = field

            if best_match_field:
                suggestions[header] = best_match_field

        return suggestions

mapping_service = MappingService()
