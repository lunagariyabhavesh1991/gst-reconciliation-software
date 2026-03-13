from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from app.services.file_handler import file_handler
from app.services.reconciliation import reconciliation_service
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

        return {
            "header_row": header_row,
            "headers": headers,
            "preview_data": preview_data
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
    except KeyError:
        raise HTTPException(status_code=404, detail="File ID or sheet name not found. Ensure files are uploaded and headers detected.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
