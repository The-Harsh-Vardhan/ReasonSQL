"""
File Upload Router — supports CSV, Excel, and SQLite database files.

Endpoints:
- POST /upload  — Upload a file and create/import table(s) into the active database.

Supported formats:
  .csv            → Single table created from CSV rows.
  .xlsx / .xls    → Single table created from the first sheet.
  .db / .sqlite   → All tables in the SQLite file are imported.

Response shape:
  {
    "status": "success",
    "file_type": "csv" | "excel" | "sqlite",
    "tables": [
      { "table": str, "columns": [str], "rows_processed": int, "rows_inserted": int }
    ]
  }
"""

import io
import re
import math
import sqlite3
import tempfile
import os
import logging

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.db_connection import execute_write_async, get_db_type

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".db", ".sqlite"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_extension(filename: str) -> str:
    """Return lowercase file extension including the dot."""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _clean_table_name(name: str) -> str:
    """Sanitize a string to be a valid SQL table name."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = name.lower().strip("_")
    return name or "uploaded_data"


def _map_dtype_to_sql(dtype: str) -> str:
    """Map a pandas dtype string to a SQL column type."""
    if "int" in dtype:
        return "INTEGER"
    if "float" in dtype:
        return "REAL"
    if "datetime" in dtype:
        return "TIMESTAMP"
    return "TEXT"


def _sanitize_value(v):
    """Convert a pandas value to a safe Python value for SQL parameters."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _build_placeholder(db_type: str, n_cols: int) -> str:
    """Build parameterized placeholder string for INSERT."""
    if db_type == "sqlite":
        return ", ".join(["?"] * n_cols)
    return ", ".join(["%s"] * n_cols)


async def _import_dataframe(df: pd.DataFrame, table_name: str) -> dict:
    """
    Create a table (if not exists) and insert all rows from a DataFrame.
    Returns a result dict: { table, columns, rows_processed, rows_inserted }.
    """
    db_type = get_db_type()

    # Sanitize column names
    orig_cols = list(df.columns)
    safe_cols = [re.sub(r"[^a-zA-Z0-9_]", "_", str(c)).lower() for c in orig_cols]

    # CREATE TABLE
    columns_sql = [
        f"{safe_col} {_map_dtype_to_sql(str(dtype))}"
        for safe_col, dtype in zip(safe_cols, df.dtypes)
    ]
    create_sql = (
        f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns_sql)});"
    )
    await execute_write_async(create_sql)

    # INSERT rows
    cols_str = ", ".join(safe_cols)
    placeholders = _build_placeholder(db_type, len(safe_cols))
    insert_sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"

    rows_inserted = 0
    records = df.to_dict(orient="records")
    for record in records:
        values = tuple(_sanitize_value(record.get(orig)) for orig in orig_cols)
        try:
            await execute_write_async(insert_sql, values)
            rows_inserted += 1
        except Exception as exc:
            logger.warning("[Upload] Row insert skipped: %s", exc)

    return {
        "table": table_name,
        "columns": safe_cols,
        "rows_processed": len(df),
        "rows_inserted": rows_inserted,
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV, Excel, or SQLite database file and import its data.

    - CSV / Excel  : Creates a single table named after the file.
    - SQLite DB    : Imports every table from the uploaded database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = _file_extension(file.filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # Read content (with a size guard)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    try:
        # ------------------------------------------------------------------ #
        # CSV
        # ------------------------------------------------------------------ #
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(content))
            if df.empty:
                raise HTTPException(status_code=400, detail="CSV file is empty.")
            table_name = _clean_table_name(file.filename)
            result = await _import_dataframe(df, table_name)
            return {
                "status": "success",
                "file_type": "csv",
                "tables": [result],
            }

        # ------------------------------------------------------------------ #
        # Excel (.xlsx / .xls)
        # ------------------------------------------------------------------ #
        if ext in {".xlsx", ".xls"}:
            engine = "openpyxl" if ext == ".xlsx" else "xlrd"
            try:
                df = pd.read_excel(io.BytesIO(content), engine=engine)
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse Excel file: {exc}",
                ) from exc
            if df.empty:
                raise HTTPException(status_code=400, detail="Excel file is empty.")
            table_name = _clean_table_name(file.filename)
            result = await _import_dataframe(df, table_name)
            return {
                "status": "success",
                "file_type": "excel",
                "tables": [result],
            }

        # ------------------------------------------------------------------ #
        # SQLite database (.db / .sqlite)
        # ------------------------------------------------------------------ #
        if ext in {".db", ".sqlite"}:
            # Write to a temp file so sqlite3 can open it
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            imported_tables = []
            try:
                src_conn = sqlite3.connect(tmp_path)
                src_conn.row_factory = sqlite3.Row
                src_cur = src_conn.cursor()

                # Discover tables
                src_cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
                )
                table_names = [row[0] for row in src_cur.fetchall()]

                if not table_names:
                    raise HTTPException(
                        status_code=400,
                        detail="The uploaded SQLite database contains no tables.",
                    )

                for src_table in table_names:
                    safe_name = _clean_table_name(src_table)
                    try:
                        df = pd.read_sql_query(
                            f"SELECT * FROM \"{src_table}\"", src_conn
                        )
                        result = await _import_dataframe(df, safe_name)
                        imported_tables.append(result)
                    except Exception as exc:
                        logger.warning(
                            "[Upload] Skipping table '%s': %s", src_table, exc
                        )

                src_conn.close()
            finally:
                os.unlink(tmp_path)

            if not imported_tables:
                raise HTTPException(
                    status_code=500,
                    detail="No tables could be imported from the uploaded database.",
                )

            return {
                "status": "success",
                "file_type": "sqlite",
                "tables": imported_tables,
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[Upload] Unexpected error during file upload")
        raise HTTPException(
            status_code=500, detail=f"Upload failed: {exc}"
        ) from exc
