# CSV Feature Documentation

This document explains the technical implementation of the CSV upload feature in the ReasonSQL application. The feature allows users to upload CSV files via the frontend, which are then parsed by the backend and stored as new tables in the connected database (SQLite or PostgreSQL).

## 1. Overview

The CSV upload feature consists of three main parts:
1.  **Frontend**: A React component (`CsvUploadModal`) that provides a drag-and-drop interface for selecting files.
2.  **Backend API**: A FastAPI endpoint (`/upload`) that receives the file, infers the schema using Pandas, and generates SQL statements.
3.  **Database Layer**: A unified interface (`db_connection.py`) that executes the generated SQL across different database types.

---

## 2. Frontend Implementation (`frontend-next/app/components/CsvUploadModal.tsx`)

The frontend component manages the user interaction and file transmission.

### Key Features
-   **Modal Interface**: Controlled by an `open` prop.
-   **Drag-and-Drop**: Uses native HTML5 drag-and-drop API (`onDragEnter`, `onDragLeave`, `onDrop`).
-   **File Validation**: Checks if the selected file ends with `.csv`.
-   **Upload Progress**: Displays a loading spinner while the request is in flight.
-   **Feedback**: extensive use of toast notifications for success and error states.

### Workflow
1.  **Selection**: User selects a file.
2.  **Upload**: When "Upload & Create Table" is clicked:
    -   A `FormData` object is created containing the file.
    -   A `POST` request is sent to the backend `/upload` endpoint.
3.  **Response Handling**:
    -   **Success**: The backend returns the new table name and row count. The UI updates to show this success message.
    -   **Error**: Any errors (e.g., invalid file, server error) are caught and displayed via `addToast`.

### Code Highlight
```typescript
const handleUpload = async () => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${apiBase}/upload`, {
        method: "POST",
        body: formData,
    });
    // ... handling response ...
};
```

---

## 3. Backend Implementation (`backend/api/routers/upload.py`)

The backend logic is responsible for parsing the CSV and managing the database schema.

### Endpoint: `POST /upload`
-   **Input**: `file: UploadFile`
-   **Output**: JSON object with `status`, `table`, `columns`, `rows_processed`, `rows_inserted`.

### Processing Steps
1.  **Validation**: Verifies the file extension is `.csv` and the file is not empty.
2.  **Sanitization**:
    -   **Table Name**: Derived from the filename using `clean_table_name()`. It ensures the name is lowercase, alphanumeric (with underscores), and valid for SQL.
    -   **Column Names**: Sanitized similarly to ensure they are valid SQL identifiers.
3.  **Schema Inference**:
    -   The file is read into a Pandas DataFrame (`pd.read_csv`).
    -   Pandas `dtypes` are mapped to SQL types:
        -   `int64` → `INTEGER`
        -   `float64` → `REAL`
        -   `datetime64` → `TIMESTAMP`
        -   Default → `TEXT`
4.  **Table Creation**:
    -   Generates a `CREATE TABLE IF NOT EXISTS` SQL statement.
    -   Executes via `execute_write_async`.
5.  **Data Insertion**:
    -   Rows are converted to a list of dictionaries.
    -   Values are sanitized (e.g., `NaN` becomes `NULL`).
    -   SQL `INSERT` statements are generated using parameterized queries (`?` for SQLite, `%s` for Postgres).
    -   Queries are executed asynchronously.

### Code Highlight
```python
# Mapping Pandas types to SQL
def map_dtype_to_sql(dtype: str) -> str:
    if 'int' in dtype: return 'INTEGER'
    elif 'float' in dtype: return 'REAL'
    elif 'datetime' in dtype: return 'TIMESTAMP'
    else: return 'TEXT'
```

---

## 4. Database Layer (`backend/db_connection.py`)

The `db_connection.py` module abstracts the differences between SQLite and PostgreSQL, allowing the CSV feature to work on both.

-   **`get_db_type()`**: Detects the database type from environment variables (`DATABASE_URL`).
-   **`execute_write_async(sql, params)`**:
    -   Wraps synchronous DB operations in `asyncio.to_thread` to prevent blocking the async event loop.
    -   Uses a context manager to handle connection opening/closing (SQLite) or pooling (Postgres).
    -   Automatically commits transactions.

---

## 5. Security & Robustness

-   **SQL Injection Prevention**:
    -   Table and column names are sanitized using strict regex: `[^a-zA-Z0-9_]`.
    -   Data values are inserted using parameterized queries (never string concatenation).
-   **Error Handling**:
    -   Empty files or invalid formats raise HTTP 400.
    -   Database errors during insertion are caught and reported.
