
from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
import io
import re
import math
from backend.db_connection import execute_write_async, get_db_type

router = APIRouter()

def clean_table_name(filename: str) -> str:
    """Sanitize filename to be a valid SQL table name."""
    name = filename.rsplit('.', 1)[0]
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = name.lower().strip('_')
    return name or "uploaded_data"

def map_dtype_to_sql(dtype: str) -> str:
    """Map pandas dtype to SQL type (generic)."""
    if 'int' in dtype:
        return 'INTEGER'
    elif 'float' in dtype:
        return 'REAL'
    elif 'datetime' in dtype:
        return 'TIMESTAMP'
    else:
        return 'TEXT'

def sanitize_value(v):
    """Convert pandas value to a safe SQL-ready Python value."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file and create a table in the database.
    
    - Infers schema from CSV columns
    - Creates table if not exists
    - Inserts data row by row with parameterized queries
    """
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    table_name = clean_table_name(file.filename)
    db_type = get_db_type()
    
    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        
        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file is empty.")
        
        # Sanitize column names
        safe_cols = [re.sub(r'[^a-zA-Z0-9_]', '_', str(c)).lower() for c in df.columns]
        
        # 1. Generate and execute CREATE TABLE
        columns_sql = []
        for safe_col, (_, dtype) in zip(safe_cols, df.dtypes.items()):
            sql_type = map_dtype_to_sql(str(dtype))
            columns_sql.append(f"{safe_col} {sql_type}")
        
        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_sql)});"
        await execute_write_async(create_sql)
        
        # 2. Insert data row by row with parameterized queries
        cols_str = ", ".join(safe_cols)
        n_cols = len(safe_cols)
        
        if db_type == "sqlite":
            placeholders = ", ".join(["?"] * n_cols)
        else:
            placeholders = ", ".join(["%s"] * n_cols)
        
        insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
        
        success_count = 0
        records = df.to_dict(orient='records')
        
        for record in records:
            # Build values tuple in column order, sanitizing NaN/inf
            values = tuple(sanitize_value(record.get(orig_col)) for orig_col in df.columns)
            try:
                await execute_write_async(insert_sql, values)
                success_count += 1
            except Exception as e:
                print(f"[Upload] Row insert failed: {e}")
                
        return {
            "status": "success",
            "table": table_name,
            "columns": safe_cols,
            "rows_processed": len(df),
            "rows_inserted": success_count
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
