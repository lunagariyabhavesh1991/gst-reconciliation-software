import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any
import uuid
from fastapi import UploadFile
from app.config import settings

class FileHandler:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(exist_ok=True)
        self.file_cache = {}
    
    async def upload_file(self, file: UploadFile) -> Dict[str, Any]:
        """Upload and process Excel file"""
        file_id = str(uuid.uuid4())
        file_path = self.upload_dir / f"{file_id}_{file.filename}"
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Read sheets
        xls = pd.ExcelFile(file_path)
        sheets = xls.sheet_names
        
        # Get row count from first sheet
        df = pd.read_excel(file_path, sheet_name=sheets[0])
        row_count = len(df)
        
        # Cache file info
        self.file_cache[file_id] = {
            "file_path": file_path,
            "sheets": sheets,
            "original_data": {}
        }
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "sheets": sheets,
            "row_count": row_count,
            "upload_time": datetime.now().isoformat()
        }
    
    def detect_header_row(self, file_id: str, sheet_name: str, manual_row: int = None) -> Tuple[int, List[str]]:
        """Auto-detect header row or use manual selection"""
        file_path = self.file_cache[file_id]["file_path"]
        
        if manual_row is not None:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=manual_row-1)
            headers = df.columns.tolist()
            return manual_row, headers
        
        # Auto-detection logic
        for row_idx in range(min(10, pd.read_excel(file_path, sheet_name=sheet_name, header=None).shape[0])):
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=row_idx)
            headers = df.columns.tolist()
            
            if all(isinstance(h, str) and len(str(h).strip()) > 0 for h in headers):
                if not all(str(h).isdigit() for h in headers):
                    return row_idx + 1, headers
        
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=0)
        return 1, df.columns.tolist()
    
    def get_preview_data(self, file_id: str, sheet_name: str, header_row: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get preview data from file"""
        file_path = self.file_cache[file_id]["file_path"]
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row-1)
        
        return df.head(limit).to_dict('records')
    
    def read_data(self, file_id: str, sheet_name: str, header_row: int) -> pd.DataFrame:
        """Read and return complete dataframe"""
        file_path = self.file_cache[file_id]["file_path"]
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row-1)
        
        self.file_cache[file_id]["original_data"][sheet_name] = df.copy()
        
        return df

file_handler = FileHandler()
