"""
DataFrame Agent Service — Google Sheets / CSV / XLSX query interface.

This module provides DataFrame loading and LLM-powered querying via LangChain.
Supports Google Sheets (via gspread), CSV, and Excel files.
"""

import asyncio
import json
import logging
import os
import re
import string
from io import BytesIO
from pathlib import Path

import gspread
import pandas as pd
from dotenv import load_dotenv
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

load_dotenv()
logger = logging.getLogger(__name__)


class DataFrameAgentService:
    """Service for loading and querying DataFrames with LLM agents."""

    def __init__(self):
        """Initialize service (LLM is initialized lazily on first use)."""
        self._llm = None
        self._gs_client = None
        self._dataframes = {}  # session_id -> DataFrame
        self._sources = {}  # session_id -> source label

    @property
    def default_file_path(self) -> str | None:
        """Path to the default local spreadsheet used by the frontend sheet mode."""
        return os.getenv("DEFAULT_DATAFRAME_FILE_PATH")

    @property
    def default_google_sheet_ref(self) -> str | None:
        """Google Sheet ID or URL for the secondary default spreadsheet source."""
        return os.getenv("DEFAULT_GOOGLE_SHEET_ID")

    def _extract_google_sheet_id(self, sheet_ref: str) -> str | None:
        """Extract Google Sheet ID from either a raw ID or full share URL."""
        if not sheet_ref:
            return None

        stripped = sheet_ref.strip()
        if "/" not in stripped:
            return stripped

        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", stripped)
        if not match:
            return None
        return match.group(1)

    def _service_account_email(self) -> str | None:
        """Read service account email from the configured credentials file, when available."""
        credentials_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not credentials_path:
            return None

        try:
            with open(credentials_path, "r", encoding="utf-8") as f:
                creds_dict = json.load(f)
            return creds_dict.get("client_email")
        except Exception:
            return None

    def _load_google_sheet_dataframe(self, sheet_ref: str) -> tuple[pd.DataFrame | None, str | None, str | None]:
        """Load a Google Sheet and return dataframe, source title, and optional error."""
        sheet_id = self._extract_google_sheet_id(sheet_ref)
        if not sheet_id:
            return None, None, "Invalid Google Sheet reference in DEFAULT_GOOGLE_SHEET_ID"

        try:
            sh = self.gs_client.open_by_key(sheet_id)
            ws = sh.get_worksheet(0)
            data = ws.get_all_records()

            if not data:
                return None, ws.title, "Configured Google Sheet is empty"

            return pd.DataFrame(data), f"Google:{ws.title}", None
        except Exception as e:
            service_email = self._service_account_email()
            if service_email and "permission" in str(type(e)).lower():
                return (
                    None,
                    None,
                    (
                        "Failed to load configured Google Sheet: permission denied. "
                        f"Share the sheet with service account '{service_email}' as Viewer or Editor."
                    ),
                )

            error_text = str(e).strip() or repr(e)
            return None, None, f"Failed to load configured Google Sheet: {error_text}"

    def _cache_dataframe(self, session_id: str, df: pd.DataFrame, source_label: str) -> dict:
        """Store a cleaned DataFrame and return response metadata."""
        normalized_df = df.fillna("")
        self._dataframes[session_id] = normalized_df
        self._sources[session_id] = source_label
        return {
            "session_id": session_id,
            "rows": len(normalized_df),
            "columns": normalized_df.columns.tolist(),
            "sheet_title": source_label,
            "error": None,
        }

    @property
    def llm(self):
        """Lazy-load the LLM on first use."""
        if self._llm is None:
            self._llm = ChatOpenAI(
                openai_api_base=os.getenv("LITELLM_PROXY_URL"),
                openai_api_key=os.getenv("LITELLM_API_KEY"),
                model_name=os.getenv("LLM_MODEL"),
                temperature=0,
                request_timeout=60,
            )
        return self._llm

    @property
    def gs_client(self):
        """Lazy-load gspread client."""
        if self._gs_client is None:
            try:
                credentials_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
                if not credentials_path:
                    raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not configured")
                with open(credentials_path, "r") as f:
                    creds_dict = json.load(f)
                self._gs_client = gspread.service_account_from_dict(creds_dict)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize gspread client: {str(e)}")
        return self._gs_client

    def load_google_sheet(self, sheet_id: str, session_id: str) -> dict:
        try:
            sh = self.gs_client.open_by_key(sheet_id)
            ws = sh.get_worksheet(0)
            data = ws.get_all_records()

            if not data:
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "sheet_title": ws.title,
                    "error": "Sheet is empty",
                }

            df = pd.DataFrame(data)
            return self._cache_dataframe(session_id, df, ws.title)
        except Exception as e:
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "sheet_title": None,
                "error": str(e),
            }

    def load_file(self, file_bytes: bytes, filename: str, session_id: str) -> dict:
        """
        Load a CSV or XLSX file into a DataFrame and cache it.

        Args:
            file_bytes: Raw file content.
            filename: Original filename (used to determine format).
            session_id: Unique session identifier for caching.

        Returns:
            dict with keys: session_id, rows, columns, error
        """
        try:
            if filename.lower().endswith(".csv"):
                df = pd.read_csv(BytesIO(file_bytes))
            elif filename.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(BytesIO(file_bytes))
            else:
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "error": "Unsupported file type. Must be .csv or .xlsx",
                }

            if df.empty:
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "error": "File is empty",
                }

            return self._cache_dataframe(session_id, df, filename)
        except Exception as e:
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "error": str(e),
            }

    def load_default_file(self, session_id: str, force_reload: bool = False) -> dict:
        """Load configured default spreadsheet sources (local file + optional Google Sheet)."""
        if not force_reload and session_id in self._dataframes:
            df = self._dataframes[session_id]
            return {
                "session_id": session_id,
                "rows": len(df),
                "columns": df.columns.tolist(),
                "sheet_title": self._sources.get(session_id),
                "error": None,
            }

        source_frames: list[pd.DataFrame] = []
        source_labels: list[str] = []

        default_file_path = self.default_file_path
        if default_file_path:
            file_path = Path(default_file_path)
            if not file_path.exists():
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "sheet_title": None,
                    "error": f"Default spreadsheet not found: {default_file_path}",
                }

            try:
                if file_path.suffix.lower() == ".csv":
                    local_df = pd.read_csv(file_path)
                elif file_path.suffix.lower() in {".xlsx", ".xls"}:
                    local_df = pd.read_excel(file_path)
                else:
                    return {
                        "session_id": session_id,
                        "rows": 0,
                        "columns": [],
                        "sheet_title": None,
                        "error": "Default spreadsheet must be .csv, .xls, or .xlsx",
                    }

                if not local_df.empty:
                    local_df = local_df.copy()
                    local_df["__source"] = file_path.name
                    source_frames.append(local_df)
                    source_labels.append(file_path.name)
            except Exception as e:
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "sheet_title": None,
                    "error": str(e),
                }

        default_google_sheet_ref = self.default_google_sheet_ref
        if default_google_sheet_ref:
            google_df, google_label, google_error = self._load_google_sheet_dataframe(default_google_sheet_ref)
            if google_error:
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "sheet_title": google_label,
                    "error": google_error,
                }
            if google_df is not None and google_label:
                google_df = google_df.copy()
                google_df["__source"] = google_label
                source_frames.append(google_df)
                source_labels.append(google_label)

        if not source_frames:
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "sheet_title": None,
                "error": "No default data source configured. Set DEFAULT_DATAFRAME_FILE_PATH and/or DEFAULT_GOOGLE_SHEET_ID",
            }

        try:
            df = pd.concat(source_frames, ignore_index=True, sort=False)

            if df.empty:
                return {
                    "session_id": session_id,
                    "rows": 0,
                    "columns": [],
                    "sheet_title": ", ".join(source_labels) if source_labels else None,
                    "error": "Configured default sources are empty",
                }

            return self._cache_dataframe(session_id, df, ", ".join(source_labels))
        except Exception as e:
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "sheet_title": None,
                "error": str(e),
            }

    def query(self, question: str, session_id: str) -> dict:
        """
        Query a cached DataFrame using a natural-language question.

        Args:
            question: The user's natural-language question about the data.
            session_id: Session ID referencing a cached DataFrame.

        Returns:
            dict with keys: answer, error
        """
        try:
            if session_id not in self._dataframes:
                return {
                    "answer": None,
                    "error": f"No DataFrame found for session_id: {session_id}",
                }

            df = self._dataframes[session_id]

            agent = create_pandas_dataframe_agent(
                llm=self.llm,
                df=df,
                verbose=True,
                allow_dangerous_code=True,
                agent_type="zero-shot-react-description",
                max_iterations=6,
                handle_parsing_errors=True,
            )

            result = agent.invoke({"input": question})

            answer = result.get("output", str(result))

            return {"answer": answer, "error": None}
        except Exception as e:
            return {"answer": None, "error": str(e)}

    async def query_async(self, question: str, session_id: str) -> dict:
        """Async wrapper for query that handles blocking operations."""
        logger.info(f"Query request: session_id={session_id}, question={question[:50]}...")
        try:
            if session_id not in self._dataframes:
                auto_load_result = await self.load_default_file_async(session_id)
                if auto_load_result["error"]:
                    logger.warning(f"No DataFrame found for session_id: {session_id}")
                    return {
                        "answer": None,
                        "error": auto_load_result["error"],
                    }

            df = self._dataframes[session_id]
            logger.info(f"Found DataFrame with {len(df)} rows and {len(df.columns)} columns")

            # Run blocking operations in thread pool
            result = await asyncio.to_thread(
                self._run_agent_query,
                question,
                df,
            )
            return result
        except Exception as e:
            logger.exception("Error in query_async")
            return {"answer": None, "error": str(e)}

    def _run_agent_query(self, question: str, df: pd.DataFrame) -> dict:
        """Blocking agent query (runs in thread pool)."""
        try:
            deterministic_answer = self._try_deterministic_query(question, df)
            if deterministic_answer:
                return {"answer": deterministic_answer, "error": None}

            constrained_question = (
                "Answer only from the provided spreadsheet dataframe. "
                "Do not use outside knowledge. If the spreadsheet does not contain the answer, say that explicitly. "
                "Prefer exact values from rows and columns, and keep the answer concise.\n\n"
                f"Question: {question}"
            )
            agent = create_pandas_dataframe_agent(
                llm=self.llm,
                df=df,
                verbose=False,
                allow_dangerous_code=True,
                agent_type="tool-calling",
                max_iterations=4,
            )
            result = agent.invoke({"input": constrained_question})
            answer = result.get("output", str(result))
            answer = self._fallback_answer_for_common_sheet_questions(question, df, answer)

            if not answer or "does not contain" in answer.lower():
                deterministic_answer = self._try_deterministic_query(question, df)
                if deterministic_answer:
                    return {"answer": deterministic_answer, "error": None}

            logger.info("Agent query completed successfully")
            return {"answer": answer, "error": None}
        except Exception as e:
            logger.exception("Agent query failed")
            return {"answer": None, "error": str(e)}

    def _try_deterministic_query(self, question: str, df: pd.DataFrame) -> str | None:
        """Answer common spreadsheet intents directly from dataframe data, independent of sheet schema."""
        question_lc = question.lower().strip()

        headers_or_columns_answer = self._answer_headers_or_columns(question_lc, df)
        if headers_or_columns_answer:
            return headers_or_columns_answer

        all_rows_answer = self._answer_all_rows(question_lc, df)
        if all_rows_answer:
            return all_rows_answer

        row_by_index_answer = self._answer_row_by_index(question_lc, df)
        if row_by_index_answer:
            return row_by_index_answer

        list_questions_answer = self._answer_list_of_questions(question_lc, df)
        if list_questions_answer:
            return list_questions_answer

        if "how many rows" in question_lc or "row count" in question_lc or "number of rows" in question_lc:
            return f"The currently loaded sheet has {len(df)} rows."

        if "column names" in question_lc or "list columns" in question_lc or "what are the columns" in question_lc:
            return "The column names are: " + ", ".join(df.columns.astype(str).tolist()) + "."

        column_values_answer = self._answer_list_values_for_column(question, df)
        if column_values_answer:
            return column_values_answer

        metric_for_entity_answer = self._answer_metric_for_entity(question, df)
        if metric_for_entity_answer:
            return metric_for_entity_answer

        return None

    def _answer_headers_or_columns(self, question_lc: str, df: pd.DataFrame) -> str | None:
        """Return sheet headers/columns deterministically."""
        asks_headers = "header" in question_lc or "headers" in question_lc
        asks_columns = (
            "column names" in question_lc
            or "list columns" in question_lc
            or "what are the columns" in question_lc
            or "show columns" in question_lc
        )
        if not asks_headers and not asks_columns:
            return None
        return "The column names are: " + ", ".join(df.columns.astype(str).tolist()) + "."

    def _answer_all_rows(self, question_lc: str, df: pd.DataFrame) -> str | None:
        """Return all rows when user explicitly asks for all rows/data."""
        asks_all_rows = (
            ("all rows" in question_lc)
            or ("show rows" in question_lc)
            or ("display rows" in question_lc)
            or ("show all data" in question_lc)
            or ("display all data" in question_lc)
            or ("list all rows" in question_lc)
        )
        if not asks_all_rows:
            return None

        records = df.fillna("").to_dict(orient="records")
        if not records:
            return "The sheet has no rows."

        return "All rows (JSON): " + json.dumps(records, ensure_ascii=True)

    def _answer_row_by_index(self, question_lc: str, df: pd.DataFrame) -> str | None:
        """Handle prompts like 'show row 2'. Uses 1-based indexing."""
        row_match = re.search(r"\brow\s+(\d+)\b", question_lc)
        if not row_match:
            return None

        row_number = int(row_match.group(1))
        if row_number <= 0:
            return "Row numbers are 1-based. Please provide a row number >= 1."
        if row_number > len(df):
            return f"Row {row_number} is out of range. The sheet has {len(df)} rows."

        row_data = df.iloc[row_number - 1].fillna("").to_dict()
        return f"Row {row_number} (JSON): " + json.dumps(row_data, ensure_ascii=True)

    def _answer_list_of_questions(self, question_lc: str, df: pd.DataFrame) -> str | None:
        """Answer list-of-questions prompts across varying sheet layouts."""
        asks_for_questions = (
            "list of questions" in question_lc
            or "questions from the sheet" in question_lc
            or "display all the list of questions" in question_lc
            or question_lc == "share the list of questions"
            or "share the list of questions" in question_lc
        )
        if not asks_for_questions:
            return None

        # Prefer values from explicit question columns (e.g. "List of Questions").
        question_value_columns = [
            str(col)
            for col in df.columns
            if "question" in self._normalize_text(str(col))
        ]
        for col in question_value_columns:
            values = [str(v).strip() for v in df[col].tolist() if str(v).strip()]
            if values:
                ordered_unique_values = list(dict.fromkeys(values))
                quoted_values = ", ".join([f"'{val}'" for val in ordered_unique_values])
                return f"The questions from the sheet are: {quoted_values}."

        # Otherwise infer question headers from non-metadata columns.
        metadata_cols = {
            "s.no",
            "name",
            "dept",
            "source",
            "__source",
            "emp name",
            "genesis manager",
            "option1",
            "option 1",
            "option2",
            "option 2",
            "option3",
            "option 3",
            "option4",
            "option 4",
            "answer",
            "answers",
        }
        question_headers = [
            str(col)
            for col in df.columns
            if self._normalize_text(str(col)) not in metadata_cols
        ]
        if question_headers:
            quoted_headers = ", ".join([f"'{col}'" for col in question_headers])
            return f"The questions from the sheet are: {quoted_headers}."

        return None

    def _answer_list_values_for_column(self, question: str, df: pd.DataFrame) -> str | None:
        """Handle prompts like 'list values in <column>' with loose column matching."""
        question_lc = question.lower()
        if not (
            "list" in question_lc
            or "show" in question_lc
            or "what are" in question_lc
            or "values" in question_lc
        ):
            return None

        if "column" not in question_lc:
            return None

        col_match = re.search(r"(?:in|from)\s+the\s+(.+?)\s+column", question_lc)
        if not col_match:
            col_match = re.search(r"(.+?)\s+column", question_lc)
        if not col_match:
            return None

        requested_col = col_match.group(1).strip()
        col_name = self._find_first_matching_column(df, [requested_col])
        if not col_name:
            return None

        values = [str(v).strip() for v in df[col_name].tolist() if str(v).strip()]
        if "not empty" in question_lc or "non-empty" in question_lc:
            values = [value for value in values if value]

        if not values:
            return f"The '{col_name}' column has no non-empty values."

        unique_values = ", ".join(sorted(set(values)))
        return f"The values in the '{col_name}' column are: {unique_values}."

    def _answer_metric_for_entity(self, question: str, df: pd.DataFrame) -> str | None:
        """Handle prompts like '<metric> for <entity>' across arbitrary schemas."""
        match = re.search(r"\bfor\s+([a-zA-Z0-9\s._-]+)$", question.strip(), re.IGNORECASE)
        if not match:
            return None

        entity = match.group(1).strip()
        entity_norm = self._normalize_text(entity)
        if not entity_norm:
            return None

        # Prefer identity-like columns (name/id) to avoid false matches in free-text fields.
        selector_col = self._find_first_matching_column(
            df,
            ["emp name", "employee name", "name", "person", "user", "id"],
        )
        selector_matches = None
        best_match_count = 0

        if selector_col:
            series = df[selector_col].astype(str).fillna("")
            selector_matches = series.apply(
                lambda v: self._entity_matches_value(entity_norm, self._normalize_text(v))
            )
            best_match_count = int(selector_matches.sum())

        # Fallback to scanning all columns only when identity columns produce no match.
        if best_match_count == 0:
            selector_col = None
            selector_matches = None
            for col in df.columns:
                series = df[col].astype(str).fillna("")
                matches = series.apply(
                    lambda v: self._entity_matches_value(entity_norm, self._normalize_text(v))
                )
                count = int(matches.sum())
                if count > best_match_count:
                    best_match_count = count
                    selector_col = str(col)
                    selector_matches = matches

        if not selector_col or selector_matches is None or best_match_count == 0:
            return None

        candidate_rows = df[selector_matches]

        # Metric hint comes from text before 'for <entity>'.
        metric_hint = re.sub(r"\bfor\s+[a-zA-Z0-9\s._-]+$", "", question, flags=re.IGNORECASE).strip()
        metric_hint_norm = self._normalize_text(metric_hint)
        if not metric_hint_norm:
            return None

        metric_tokens = [
            tok
            for tok in metric_hint_norm.split()
            if tok not in {"show", "list", "give", "me", "the", "what", "is", "are", "of", "for"}
        ]
        if not metric_tokens:
            return None

        metric_col = None
        best_score = 0
        for col in df.columns:
            col_name = str(col)
            col_norm = self._normalize_text(col_name)
            if col_name == selector_col:
                continue
            score = sum(1 for tok in metric_tokens if tok in col_norm)
            if score > best_score:
                best_score = score
                metric_col = col_name

        if not metric_col or best_score == 0:
            return None

        metric_values = [str(v).strip() for v in candidate_rows[metric_col].tolist() if str(v).strip()]
        entity_values = [str(v).strip() for v in candidate_rows[selector_col].tolist() if str(v).strip()]
        if not metric_values:
            resolved_entity = ", ".join(sorted(set(entity_values))) or entity
            return f"{metric_col} is empty for {resolved_entity}."

        resolved_entity = ", ".join(sorted(set(entity_values))) or entity
        unique_values = ", ".join(sorted(set(metric_values)))
        return f"{metric_col} for {resolved_entity}: {unique_values}."

    def _entity_matches_value(self, entity_norm: str, value_norm: str) -> bool:
        """Safer entity match that excludes empty cells and noisy matches."""
        if not entity_norm or not value_norm:
            return False
        return entity_norm in value_norm or value_norm in entity_norm

    def _fallback_answer_for_common_sheet_questions(
        self,
        question: str,
        df: pd.DataFrame,
        answer: str | None,
    ) -> str | None:
        """Provide deterministic answers for common spreadsheet questions when agent output is weak."""
        question_lc = question.lower().strip()
        answer_lc = (answer or "").lower()

        list_questions_answer = self._answer_list_of_questions(question_lc, df)
        if list_questions_answer:
            return list_questions_answer

        looks_unresolved = (
            not answer
            or "does not contain" in answer_lc
            or "cannot find" in answer_lc
            or "no answer" in answer_lc
            or answer_lc.strip() in {"", "none", "null"}
        )

        if not looks_unresolved:
            return answer

        if "how many rows" in question_lc or "row count" in question_lc:
            return f"The currently loaded sheet has {len(df)} rows."

        if "column names" in question_lc or "list columns" in question_lc:
            return "The column names are: " + ", ".join(df.columns.astype(str).tolist()) + "."

        person_area_answer = self._answer_areas_of_improvement_for_person(question, df)
        if person_area_answer:
            return person_area_answer

        return answer

    def _answer_areas_of_improvement_for_person(self, question: str, df: pd.DataFrame) -> str | None:
        """Deterministically answer 'areas of improvement for <name>' style questions."""
        question_lc = question.lower().strip()
        if "areas of improvement" not in question_lc:
            return None

        person_match = re.search(r"\bfor\s+([a-zA-Z\s\.]+)$", question.strip(), re.IGNORECASE)
        if not person_match:
            return None

        requested_name = person_match.group(1).strip()
        requested_name_norm = self._normalize_text(requested_name)
        if not requested_name_norm:
            return None

        name_col = self._find_first_matching_column(df, ["emp name", "name"])
        improvement_col = self._find_first_matching_column(df, ["areas of improvement"])
        if not name_col or not improvement_col:
            return None

        matched_rows = []
        for _, row in df.iterrows():
            candidate_name = str(row.get(name_col, "")).strip()
            candidate_name_norm = self._normalize_text(candidate_name)
            if not candidate_name_norm:
                continue
            if requested_name_norm in candidate_name_norm or candidate_name_norm in requested_name_norm:
                matched_rows.append(row)

        if not matched_rows:
            return None

        values = []
        resolved_names = []
        for row in matched_rows:
            resolved_names.append(str(row.get(name_col, "")).strip())
            value = str(row.get(improvement_col, "")).strip()
            if value:
                values.append(value)

        resolved_name_text = ", ".join(sorted({name for name in resolved_names if name}))
        if not values:
            if resolved_name_text:
                return f"Areas of Improvement is empty for {resolved_name_text}."
            return "Areas of Improvement is empty for the requested employee."

        unique_values = ", ".join(sorted(set(values)))
        if resolved_name_text:
            return f"Areas of Improvement for {resolved_name_text}: {unique_values}."
        return f"Areas of Improvement: {unique_values}."

    def _find_first_matching_column(self, df: pd.DataFrame, candidates: list[str]) -> str | None:
        """Find the first dataframe column whose normalized form contains any candidate text."""
        normalized_candidates = [self._normalize_text(candidate) for candidate in candidates]
        normalized_cols = [(str(col), self._normalize_text(str(col))) for col in df.columns]

        # Respect candidate priority order (e.g. prefer "Emp Name" over generic "Name").
        for candidate in normalized_candidates:
            if not candidate:
                continue
            for original_col, col_norm in normalized_cols:
                if candidate == col_norm:
                    return original_col
            for original_col, col_norm in normalized_cols:
                if candidate in col_norm:
                    return original_col
        return None

    def _normalize_text(self, value: str) -> str:
        """Lowercase and remove punctuation/extra spaces for loose matching."""
        lowered = value.lower()
        translator = str.maketrans("", "", string.punctuation)
        stripped = lowered.translate(translator)
        return " ".join(stripped.split())

    async def load_google_sheet_async(self, sheet_id: str, session_id: str) -> dict:
        """Async wrapper for load_google_sheet."""
        logger.info(f"Load sheet request: sheet_id={sheet_id}, session_id={session_id}")
        try:
            result = await asyncio.to_thread(
                self.load_google_sheet,
                sheet_id,
                session_id,
            )
            if result["error"]:
                logger.error(f"Failed to load sheet: {result['error']}")
            else:
                logger.info(f"Sheet loaded: {result['rows']} rows, {len(result['columns'])} columns")
            return result
        except Exception as e:
            logger.exception("Error in load_google_sheet_async")
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "sheet_title": None,
                "error": str(e),
            }

    async def load_default_file_async(self, session_id: str, force_reload: bool = False) -> dict:
        """Async wrapper for load_default_file."""
        logger.info(
            f"Load default file request: session_id={session_id}, force_reload={force_reload}"
        )
        try:
            result = await asyncio.to_thread(self.load_default_file, session_id, force_reload)
            if result["error"]:
                logger.error(f"Failed to load default file: {result['error']}")
            else:
                logger.info(
                    f"Default file loaded: {result['rows']} rows, {len(result['columns'])} columns"
                )
            return result
        except Exception as e:
            logger.exception("Error in load_default_file_async")
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "sheet_title": None,
                "error": str(e),
            }

    async def load_file_async(self, file_bytes: bytes, filename: str, session_id: str) -> dict:
        """Async wrapper for load_file."""
        logger.info(f"Load file request: filename={filename}, session_id={session_id}")
        try:
            result = await asyncio.to_thread(
                self.load_file,
                file_bytes,
                filename,
                session_id,
            )
            if result["error"]:
                logger.error(f"Failed to load file: {result['error']}")
            else:
                logger.info(f"File loaded: {result['rows']} rows, {len(result['columns'])} columns")
            return result
        except Exception as e:
            logger.exception("Error in load_file_async")
            return {
                "session_id": session_id,
                "rows": 0,
                "columns": [],
                "error": str(e),
            }
