from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from app.services.file_handler import file_handler
from app.services.reconciliation import reconciliation_service
from app.services.mapping import mapping_service
from app.models.schemas import (
    FileUploadResponse,
    HeaderDetectionRequest,
    HeaderDetectionResponse,
    MappingRequest,
    ReconciliationRequest,
    ReconciliationReport
)

router = APIRouter()

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(status_code=400, detail="Invalid file type")

        result = await file_handler.upload_file(file)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect-headers", response_model=HeaderDetectionResponse)
async def detect_headers(request: HeaderDetectionRequest):
    try:
        header_row, headers = file_handler.detect_header_row(
            request.file_id,
            request.sheet_name,
            request.manual_header_row
        )

        preview_data = file_handler.get_preview_data(
            request.file_id,
            request.sheet_name,
            header_row
        )

        suggested_mappings = mapping_service.suggest_mappings(headers)

        return {
            "header_row": header_row,
            "headers": headers,
            "preview_data": preview_data,
            "suggested_mappings": suggested_mappings
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="File ID or sheet name not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/map-columns")
async def map_columns(request: MappingRequest):
    try:
        is_portal = request.voucher_type == "portal"
        reconciliation_service.set_mappings(
            file_id=request.file_id,
            mappings=request.mappings,
            is_portal=is_portal
        )
        return {"status": "success", "message": "Mappings saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reconcile", response_model=ReconciliationReport)
async def reconcile(request: ReconciliationRequest):
    try:
        # Validate that required mappings exist
        required_fields = ['gstin', 'invoice_number']

        # If mappings are provided in the request, validate them
        if request.portal_mappings is not None:
            portal_map_fields = [m.mapped_field for m in request.portal_mappings]
            for field in required_fields:
                if field not in portal_map_fields:
                    raise HTTPException(status_code=400, detail=f"Missing required mapping '{field}' for Portal Data")

        # Otherwise, check the stored mappings
        else:
            portal_map = reconciliation_service.portal_mappings.get(request.portal_file_id, {})
            for field in required_fields:
                if field not in portal_map:
                    raise HTTPException(status_code=400, detail=f"Missing required mapping '{field}' for Portal Data")

        if request.books_mappings is not None:
            books_map_fields = [m.mapped_field for m in request.books_mappings]
            for field in required_fields:
                if field not in books_map_fields:
                    raise HTTPException(status_code=400, detail=f"Missing required mapping '{field}' for Books Data")
        else:
            books_map = reconciliation_service.books_mappings.get(request.books_file_id, {})
            for field in required_fields:
                if field not in books_map:
                    raise HTTPException(status_code=400, detail=f"Missing required mapping '{field}' for Books Data")

        # Load portal data
        portal_df = file_handler.read_data(
            request.portal_file_id,
            request.portal_sheet,
            header_row=request.portal_header_row
        )

        # Load books data
        books_df = file_handler.read_data(
            request.books_file_id,
            request.books_sheet,
            header_row=request.books_header_row
        )

        report = reconciliation_service.reconcile(portal_df, books_df, request)
        return report
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="File ID or sheet name not found. Ensure files are uploaded and headers detected.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
