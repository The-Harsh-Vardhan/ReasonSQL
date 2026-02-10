"""
Database tools for schema inspection and safe SQL execution.
These are custom CrewAI tools that provide controlled database access.
"""
import sqlite3
import time
import re
from typing import Any, Type, List, Dict, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from backend.models import (
    ColumnInfo, TableInfo, ForeignKeyRelation, SchemaContext,
    ExecutionResult, ValidationResult, ExecutionStatus
)
from backend.db_connection import get_connection_context, get_db_type, execute_query as db_execute
from configs import DATABASE_PATH, DEFAULT_LIMIT, FORBIDDEN_KEYWORDS, MAX_RESULT_ROWS



class SchemaInspectorInput(BaseModel):
    """Input for schema inspector tool."""
    table_name: Optional[str] = Field(
        default=None,
        description="Specific table to inspect. If None, inspects entire database."
    )


class SchemaInspectorTool(BaseTool):
    """
    Tool for exploring database schema.
    Retrieves tables, columns, data types, and foreign key relationships.
    """
    name: str = "schema_inspector"
    description: str = """
    Inspects the database schema to retrieve information about tables, columns, 
    data types, primary keys, and foreign key relationships.
    Use this tool to understand the database structure before writing queries.
    Input: Optional table_name to inspect a specific table, or leave empty for full schema.
    """
    args_schema: Type[BaseModel] = SchemaInspectorInput
    
    def _run(self, table_name: Optional[str] = None) -> str:
        """Execute schema inspection."""
        try:
            with get_connection_context() as conn:
                cursor = conn.cursor()
                
                if table_name:
                    # Inspect specific table
                    result = self._inspect_table(cursor, table_name)
                else:
                    # Inspect entire schema
                    result = self._inspect_full_schema(cursor)
                
                return result
            
        except Exception as e:
            return f"Error inspecting schema: {str(e)}"
    
    def _inspect_table(self, cursor, table_name: str) -> str:
        """Inspect a specific table."""
        db_type = get_db_type()
        
        if db_type == "sqlite":
            # Get column info via PRAGMA
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            if not columns:
                return f"Table '{table_name}' not found in database."
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()
        else:
            # PostgreSQL: Use information_schema
            cursor.execute("""
                SELECT column_name, data_type, is_nullable = 'NO', NULL, NULL, 
                       CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END as is_pk
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu 
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY' 
                        AND tc.table_name = %s
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_schema = 'public' AND c.table_name = %s
                ORDER BY c.ordinal_position
            """, (table_name, table_name))
            columns = cursor.fetchall()
            
            if not columns:
                return f"Table '{table_name}' not found in database."
            
            # Get foreign keys for PostgreSQL
            cursor.execute("""
                SELECT 0, 0, ccu.table_name, kcu.column_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu 
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
            """, (table_name,))
            foreign_keys = cursor.fetchall()
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        # Format output
        output = [f"=== Table: {table_name} ({row_count} rows) ===\n"]
        output.append("Columns:")
        for col in columns:
            pk_marker = " [PK]" if col[5] else ""
            null_marker = " NOT NULL" if col[3] else ""
            output.append(f"  - {col[1]} ({col[2]}){pk_marker}{null_marker}")
        
        if foreign_keys:
            output.append("\nForeign Keys:")
            for fk in foreign_keys:
                output.append(f"  - {fk[3]} -> {fk[2]}.{fk[4]}")
        
        return "\n".join(output)
    
    def _inspect_full_schema(self, cursor) -> str:
        """Inspect the entire database schema."""
        db_type = get_db_type()
        
        # Get all tables
        if db_type == "sqlite":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        else:
            cursor.execute("""
                SELECT table_name as name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
        tables = cursor.fetchall()
        
        output = ["=== DATABASE SCHEMA ===\n"]
        output.append(f"Total tables: {len(tables)}\n")
        
        all_relationships = []
        
        for (table_name,) in tables:
            if table_name.startswith('sqlite_'):
                continue
                
            # Get column info (use database-specific queries)
            if db_type == "sqlite":
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                foreign_keys = cursor.fetchall()
            else:
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable = 'NO', NULL, NULL, 0
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                columns = cursor.fetchall()
                cursor.execute("""
                    SELECT 0, 0, ccu.table_name, kcu.column_name, ccu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
                """, (table_name,))
                foreign_keys = cursor.fetchall()
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            output.append(f"\n--- {table_name} ({row_count} rows) ---")
            for col in columns:
                pk_marker = " [PK]" if col[5] else ""
                output.append(f"  {col[1]}: {col[2]}{pk_marker}")
            
            for fk in foreign_keys:
                all_relationships.append(f"  {table_name}.{fk[3]} -> {fk[2]}.{fk[4]}")
        
        if all_relationships:
            output.append("\n=== RELATIONSHIPS ===")
            output.extend(all_relationships)
        
        return "\n".join(output)


class SQLValidatorInput(BaseModel):
    """Input for SQL validation."""
    sql: str = Field(description="The SQL query to validate")


class SQLValidatorTool(BaseTool):
    """
    Tool for validating SQL queries before execution.
    Checks for safety rules, proper LIMIT usage, and no SELECT *.
    """
    name: str = "sql_validator"
    description: str = """
    Validates a SQL query for safety and best practices.
    Checks: read-only operations, LIMIT clause presence, no SELECT *, 
    no dangerous keywords (DROP, DELETE, INSERT, etc.)
    Returns validation result with any errors or warnings.
    """
    args_schema: Type[BaseModel] = SQLValidatorInput
    
    def _run(self, sql: str) -> str:
        """Validate the SQL query."""
        result = self._validate(sql)
        
        if result.is_valid:
            return f"✓ SQL is valid.\nWarnings: {result.warnings if result.warnings else 'None'}"
        else:
            return f"✗ SQL validation failed.\nErrors: {result.errors}\nWarnings: {result.warnings}"
    
    def _validate(self, sql: str) -> ValidationResult:
        """Perform validation checks."""
        errors = []
        warnings = []
        sql_upper = sql.upper().strip()
        
        # Check for forbidden keywords (write operations)
        is_read_only = True
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                errors.append(f"Forbidden keyword '{keyword}' detected - only read operations allowed")
                is_read_only = False
        
        # Check for SELECT *
        has_select_star = bool(re.search(r'SELECT\s+\*', sql_upper))
        if has_select_star:
            errors.append("SELECT * is not allowed - specify columns explicitly")
        
        # Check for LIMIT clause
        has_limit = 'LIMIT' in sql_upper
        if not has_limit:
            errors.append(f"LIMIT clause is required - add LIMIT {DEFAULT_LIMIT}")
        
        # Check for basic SQL structure
        if not sql_upper.startswith('SELECT'):
            if not any(sql_upper.startswith(kw) for kw in ['WITH', 'SELECT']):
                errors.append("Query must start with SELECT or WITH")
        
        # Warnings for potential issues
        if 'JOIN' in sql_upper and 'ON' not in sql_upper:
            warnings.append("JOIN without ON clause detected - ensure proper join conditions")
        
        if sql_upper.count('SELECT') > 2:
            warnings.append("Multiple subqueries detected - consider query complexity")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            has_limit=has_limit,
            has_select_star=has_select_star,
            is_read_only=is_read_only
        )


class SQLExecutorInput(BaseModel):
    """Input for SQL execution."""
    sql: str = Field(description="The SQL query to execute")
    validate_first: bool = Field(default=True, description="Whether to validate before executing")


class SQLExecutorTool(BaseTool):
    """
    Tool for safely executing SQL queries against the database.
    Validates queries before execution and captures results/errors.
    """
    name: str = "sql_executor"
    description: str = """
    Executes a SQL query against the database after validation.
    Returns results as a formatted table, or error message if execution fails.
    Automatically validates for safety (read-only, has LIMIT, no SELECT *).
    """
    args_schema: Type[BaseModel] = SQLExecutorInput
    
    def _run(self, sql: str, validate_first: bool = True) -> str:
        """Execute the SQL query."""
        # Validate first
        if validate_first:
            validator = SQLValidatorTool()
            validation = validator._validate(sql)
            
            if not validation.is_valid:
                return f"Execution blocked - validation failed:\n" + "\n".join(validation.errors)
        
        # Execute query
        try:
            start_time = time.time()
            
            with get_connection_context() as conn:
                cursor = conn.cursor()
                
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                execution_time = (time.time() - start_time) * 1000
                
                # Get column names
                column_names = [description[0] for description in cursor.description] if cursor.description else []
                
                # Convert to list of dicts (handle both SQLite Row and PostgreSQL RealDictCursor)
                db_type = get_db_type()
                if db_type == "sqlite":
                    data = [dict(row) for row in rows]
                else:
                    data = [dict(row) if hasattr(row, 'keys') else dict(zip(column_names, row)) for row in rows]
            
            # Format result
            row_count = len(data)
            
            if row_count == 0:
                return f"Query executed successfully.\nResult: 0 rows returned (empty result set)\nExecution time: {execution_time:.2f}ms"
            
            # Format as table
            result_lines = [
                f"Query executed successfully.",
                f"Rows returned: {row_count}",
                f"Execution time: {execution_time:.2f}ms",
                f"Columns: {', '.join(column_names)}",
                "\nResults:"
            ]
            
            # Show first 10 rows
            preview_rows = data[:10]
            for i, row in enumerate(preview_rows, 1):
                row_str = " | ".join(f"{k}: {v}" for k, v in row.items())
                result_lines.append(f"  {i}. {row_str}")
            
            if row_count > 10:
                result_lines.append(f"  ... and {row_count - 10} more rows")
            
            return "\n".join(result_lines)
            
        except sqlite3.Error as e:
            return f"SQL Error: {str(e)}\nQuery: {sql}"
        except Exception as e:
            return f"Execution Error: {str(e)}"
    
    def execute_and_return_result(self, sql: str, validate_first: bool = True) -> ExecutionResult:
        """Execute and return structured result (for internal use)."""
        # Validate first
        if validate_first:
            validator = SQLValidatorTool()
            validation = validator._validate(sql)
            
            if not validation.is_valid:
                return ExecutionResult(
                    status=ExecutionStatus.VALIDATION_FAILED,
                    sql=sql,
                    error_message="; ".join(validation.errors)
                )
        
        try:
            start_time = time.time()
            
            with get_connection_context() as conn:
                cursor = conn.cursor()
                
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                execution_time = (time.time() - start_time) * 1000
                
                column_names = [description[0] for description in cursor.description] if cursor.description else []
                
                # Handle both SQLite and PostgreSQL row formats
                db_type = get_db_type()
                if db_type == "sqlite":
                    data = [dict(row) for row in rows]
                else:
                    data = [dict(row) if hasattr(row, 'keys') else dict(zip(column_names, row)) for row in rows]
                
                status = ExecutionStatus.SUCCESS if data else ExecutionStatus.EMPTY
                
                return ExecutionResult(
                    status=status,
                    sql=sql,
                    data=data,
                    row_count=len(data),
                    column_names=column_names,
                    execution_time_ms=execution_time
                )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                sql=sql,
                error_message=str(e)
            )


class GetSchemaContextTool(BaseTool):
    """
    Tool that returns a structured SchemaContext object.
    Used by agents that need programmatic access to schema information.
    """
    name: str = "get_schema_context"
    description: str = """
    Returns a structured schema context with all tables, columns, and relationships.
    Use this to get a complete understanding of the database structure.
    """
    
    def _run(self) -> str:
        """Get full schema context."""
        try:
            context = self._get_schema_context()
            return context.summary
        except Exception as e:
            return f"Error getting schema context: {str(e)}"
    
    def _get_schema_context(self) -> SchemaContext:
        """Get structured schema context."""
        db_type = get_db_type()
        tables = []
        relationships = []
        
        with get_connection_context() as conn:
            cursor = conn.cursor()
            
            # Get all tables
            if db_type == "sqlite":
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                table_names = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
            else:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                table_names = [row[0] if isinstance(row, tuple) else row['table_name'] for row in cursor.fetchall()]
            
            for table_name in table_names:
                # Get columns based on database type
                if db_type == "sqlite":
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns_data = cursor.fetchall()
                    
                    columns = []
                    for col in columns_data:
                        columns.append(ColumnInfo(
                            name=col[1],
                            data_type=col[2],
                            nullable=not col[3],
                            primary_key=bool(col[5])
                        ))
                    
                    # Get foreign keys
                    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                    fk_data = cursor.fetchall()
                    
                    for fk in fk_data:
                        relationships.append(ForeignKeyRelation(
                            from_table=table_name,
                            from_column=fk[3],
                            to_table=fk[2],
                            to_column=fk[4]
                        ))
                        for col in columns:
                            if col.name == fk[3]:
                                col.foreign_key = f"{fk[2]}.{fk[4]}"
                else:
                    # PostgreSQL
                    cursor.execute("""
                        SELECT c.column_name, c.data_type, c.is_nullable = 'YES',
                               EXISTS(SELECT 1 FROM information_schema.table_constraints tc
                                      JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                                      WHERE tc.constraint_type = 'PRIMARY KEY' 
                                        AND tc.table_name = %s AND kcu.column_name = c.column_name)
                        FROM information_schema.columns c
                        WHERE c.table_schema = 'public' AND c.table_name = %s
                        ORDER BY c.ordinal_position
                    """, (table_name, table_name))
                    
                    columns = []
                    for row in cursor.fetchall():
                        col_name = row[0] if isinstance(row, tuple) else row['column_name']
                        col_type = row[1] if isinstance(row, tuple) else row['data_type']
                        nullable = row[2] if isinstance(row, tuple) else row.get('is_nullable', True)
                        is_pk = row[3] if isinstance(row, tuple) else row.get('exists', False)
                        columns.append(ColumnInfo(
                            name=col_name,
                            data_type=col_type,
                            nullable=nullable,
                            primary_key=is_pk
                        ))
                    
                    # Get foreign keys for PostgreSQL
                    cursor.execute("""
                        SELECT kcu.column_name, ccu.table_name, ccu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = %s
                    """, (table_name,))
                    
                    for row in cursor.fetchall():
                        from_col = row[0] if isinstance(row, tuple) else row['column_name']
                        to_table = row[1] if isinstance(row, tuple) else row['table_name']
                        to_col = row[2] if isinstance(row, tuple) else row.get('column_name')
                        relationships.append(ForeignKeyRelation(
                            from_table=table_name,
                            from_column=from_col,
                            to_table=to_table,
                            to_column=to_col
                        ))
                        for col in columns:
                            if col.name == from_col:
                                col.foreign_key = f"{to_table}.{to_col}"
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                tables.append(TableInfo(
                    name=table_name,
                    columns=columns,
                    row_count=row_count
                ))
        
        # Generate summary
        summary_lines = [
            f"Database has {len(tables)} tables:",
            ""
        ]
        for table in tables:
            col_names = [c.name for c in table.columns]
            pk_cols = [c.name for c in table.columns if c.primary_key]
            summary_lines.append(f"• {table.name} ({table.row_count} rows)")
            summary_lines.append(f"  Columns: {', '.join(col_names)}")
            if pk_cols:
                summary_lines.append(f"  Primary Key: {', '.join(pk_cols)}")
        
        if relationships:
            summary_lines.append("\nRelationships:")
            for rel in relationships:
                summary_lines.append(f"  {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}")
        
        return SchemaContext(
            tables=tables,
            relationships=relationships,
            summary="\n".join(summary_lines)
        )


# ============================================================
# NEW TOOLS FOR ADDITIONAL AGENTS
# ============================================================

class DataSamplerInput(BaseModel):
    """Input for data sampler tool."""
    table_name: str = Field(description="Table to sample data from")
    column_name: Optional[str] = Field(
        default=None, 
        description="Specific column to analyze. If None, samples all columns."
    )
    sample_size: int = Field(
        default=10,
        description="Number of sample rows to retrieve"
    )


class DataSamplerTool(BaseTool):
    """
    Tool for sampling data to inform query decisions.
    Provides value distributions, date ranges, and distinct values.
    """
    name: str = "data_sampler"
    description: str = """
    Samples data from a table to understand value distributions and ranges.
    Use this to:
    - Find date ranges (min/max dates in a column)
    - Get distinct values in a column
    - Understand value distributions
    - Check if data exists before querying
    
    This helps resolve ambiguity like "recent orders" by showing actual date ranges.
    """
    args_schema: Type[BaseModel] = DataSamplerInput
    
    def _run(self, table_name: str, column_name: Optional[str] = None, 
             sample_size: int = 10) -> str:
        """Sample data from the specified table/column."""
        try:
            db_type = get_db_type()
            
            with get_connection_context() as conn:
                cursor = conn.cursor()
                
                # Verify table exists (database-agnostic)
                if db_type == "sqlite":
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
                                  (table_name,))
                else:
                    cursor.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = %s
                    """, (table_name,))
                
                if not cursor.fetchone():
                    return f"Error: Table '{table_name}' not found."
                
                result_lines = [f"=== Data Sample: {table_name} ===\n"]
                
                if column_name:
                    # Analyze specific column
                    result_lines.extend(self._analyze_column(cursor, table_name, column_name, db_type))
                else:
                    # Get sample rows
                    result_lines.extend(self._sample_rows(cursor, table_name, sample_size))
                
                return "\n".join(result_lines)
            
        except Exception as e:
            return f"Error sampling data: {str(e)}"
    
    def _analyze_column(self, cursor: sqlite3.Cursor, table_name: str, 
                        column_name: str) -> List[str]:
        """Analyze a specific column for value distribution."""
        lines = [f"Column: {table_name}.{column_name}\n"]
        
        try:
            # Get column type
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_type = "UNKNOWN"
            for col in columns:
                if col[1].lower() == column_name.lower():
                    col_type = col[2]
                    break
            
            lines.append(f"Type: {col_type}")
            
            # Count total and NULL values
            cursor.execute(f"SELECT COUNT(*), COUNT({column_name}) FROM {table_name}")
            total, non_null = cursor.fetchone()
            null_count = total - non_null
            lines.append(f"Total rows: {total}")
            lines.append(f"NULL values: {null_count}")
            
            # Get distinct count
            cursor.execute(f"SELECT COUNT(DISTINCT {column_name}) FROM {table_name}")
            distinct = cursor.fetchone()[0]
            lines.append(f"Distinct values: {distinct}")
            
            # Type-specific analysis
            if 'DATE' in col_type.upper() or 'TIME' in col_type.upper():
                # Date range
                cursor.execute(f"SELECT MIN({column_name}), MAX({column_name}) FROM {table_name}")
                min_val, max_val = cursor.fetchone()
                lines.append(f"Date range: {min_val} to {max_val}")
            
            elif 'INT' in col_type.upper() or 'REAL' in col_type.upper() or 'NUM' in col_type.upper():
                # Numeric range
                cursor.execute(f"SELECT MIN({column_name}), MAX({column_name}), AVG({column_name}) FROM {table_name}")
                min_val, max_val, avg_val = cursor.fetchone()
                lines.append(f"Range: {min_val} to {max_val}")
                if avg_val:
                    lines.append(f"Average: {avg_val:.2f}")
            
            else:
                # Categorical - show top values
                cursor.execute(f"""
                    SELECT {column_name}, COUNT(*) as cnt 
                    FROM {table_name} 
                    WHERE {column_name} IS NOT NULL
                    GROUP BY {column_name} 
                    ORDER BY cnt DESC 
                    LIMIT 10
                """)
                top_values = cursor.fetchall()
                if top_values:
                    lines.append("\nTop values:")
                    for val, cnt in top_values:
                        lines.append(f"  • {val}: {cnt} rows")
            
        except Exception as e:
            lines.append(f"Error analyzing column: {str(e)}")
        
        return lines
    
    def _sample_rows(self, cursor: sqlite3.Cursor, table_name: str, 
                     sample_size: int) -> List[str]:
        """Get sample rows from table."""
        lines = []
        
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT {sample_size}")
            rows = cursor.fetchall()
            
            if not rows:
                lines.append("No data in table.")
                return lines
            
            # Get column names
            col_names = [desc[0] for desc in cursor.description]
            lines.append(f"Columns: {', '.join(col_names)}")
            lines.append(f"\nSample rows ({len(rows)}):")
            
            for i, row in enumerate(rows, 1):
                row_str = " | ".join(f"{col}={val}" for col, val in zip(col_names, row))
                lines.append(f"  {i}. {row_str[:200]}")
            
        except Exception as e:
            lines.append(f"Error sampling rows: {str(e)}")
        
        return lines


class SafetyCheckInput(BaseModel):
    """Input for safety check tool."""
    sql: str = Field(description="The SQL query to check for safety")


class SafetyCheckerTool(BaseTool):
    """
    Tool for comprehensive SQL safety validation.
    Produces explicit APPROVED/REJECTED decisions.
    """
    name: str = "safety_checker"
    description: str = """
    Performs comprehensive safety validation on SQL queries.
    Returns an explicit APPROVED or REJECTED decision with detailed reasoning.
    
    Checks:
    1. Read-only (SELECT/WITH only)
    2. No SELECT *
    3. Has LIMIT clause
    4. No forbidden keywords (INSERT, UPDATE, DELETE, DROP, etc.)
    5. No dangerous patterns
    """
    args_schema: Type[BaseModel] = SafetyCheckInput
    
    def _run(self, sql: str) -> str:
        """Perform comprehensive safety check."""
        violations = []
        warnings = []
        sql_upper = sql.upper().strip()
        
        # Check 1: Read-only operations
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            violations.append("NOT READ-ONLY: Query must start with SELECT or WITH")
        
        # Check 2: Forbidden keywords
        for keyword in FORBIDDEN_KEYWORDS:
            # Match whole word only
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                violations.append(f"FORBIDDEN KEYWORD: '{keyword}' detected")
        
        # Check 3: No SELECT *
        if re.search(r'SELECT\s+\*', sql_upper):
            violations.append("SELECT * DETECTED: Must specify columns explicitly")
        
        # Check 4: LIMIT clause required
        if 'LIMIT' not in sql_upper:
            violations.append(f"NO LIMIT: Query must include LIMIT clause (default: {DEFAULT_LIMIT})")
        
        # Check 5: Dangerous patterns
        dangerous_patterns = [
            (r';\s*SELECT', "MULTIPLE STATEMENTS: Chained queries not allowed"),
            (r'--', "SQL COMMENT: Comments might hide malicious code"),
            (r'/\*', "BLOCK COMMENT: Comments might hide malicious code"),
            (r'UNION\s+ALL\s+SELECT', "UNION injection pattern detected"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, sql_upper):
                warnings.append(message)
        
        # Build decision
        if violations:
            decision = "❌ REJECTED"
            status = "UNSAFE - DO NOT EXECUTE"
        else:
            decision = "✅ APPROVED"
            status = "SAFE TO EXECUTE"
        
        # Format output
        output = [
            "=" * 50,
            f"SAFETY CHECK RESULT: {decision}",
            "=" * 50,
            f"Status: {status}",
            "",
            "SQL Query:",
            sql[:500] + ("..." if len(sql) > 500 else ""),
            ""
        ]
        
        if violations:
            output.append("VIOLATIONS:")
            for v in violations:
                output.append(f"  ✗ {v}")
        
        if warnings:
            output.append("\nWARNINGS:")
            for w in warnings:
                output.append(f"  ⚠ {w}")
        
        if not violations and not warnings:
            output.append("All safety checks passed.")
        
        output.append("")
        output.append("=" * 50)
        
        return "\n".join(output)
