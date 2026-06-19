"""Local drag-and-drop web panel for creating Anki import files."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from sheet_to_anki import SheetToAnkiError, read_table, require_columns, clean_cell


PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / ".runtime" / "uploads"
ALLOWED_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".csv", ".txt"}

app = Flask(__name__)


def json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def upload_path(token: str, filename: str) -> Path:
    safe_name = secure_filename(filename) or "upload"
    return UPLOAD_DIR / f"{token}_{safe_name}"


def find_upload(token: str) -> Path:
    matches = list(UPLOAD_DIR.glob(f"{token}_*"))
    if not matches:
        raise SheetToAnkiError("Uploaded file was not found. Upload it again.")
    return matches[0]


def table_columns(path: Path, sheet: str | None = None) -> list[str]:
    df = read_table(path, sheet)
    return [str(column) for column in df.columns]


def excel_sheets(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    engine = "xlrd" if suffix == ".xls" else "openpyxl"
    try:
        workbook = pd.ExcelFile(path, engine=engine)
    except ImportError as exc:
        raise SheetToAnkiError(
            f"Reading {suffix} files requires {engine}. Install dependencies with: "
            ".\\run_web_panel.ps1."
        ) from exc
    return workbook.sheet_names


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/inspect")
def inspect_file():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return json_error("No file uploaded.")

    suffix = Path(uploaded.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        return json_error("Unsupported file type. Upload .xlsx, .xlsm, .xls, .csv, or .txt.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    path = upload_path(token, uploaded.filename)
    uploaded.save(path)

    try:
        sheets = excel_sheets(path) if suffix == ".xlsx" else []
        columns = table_columns(path, sheets[0] if sheets else None)
    except SheetToAnkiError as exc:
        path.unlink(missing_ok=True)
        return json_error(str(exc))
    except Exception as exc:  # pragma: no cover - defensive UI boundary
        path.unlink(missing_ok=True)
        return json_error(f"Could not read file: {exc}")

    return jsonify(
        {
            "token": token,
            "filename": uploaded.filename,
            "fileType": suffix[1:],
            "sheets": sheets,
            "columns": columns,
        }
    )


@app.post("/api/columns")
def columns_for_sheet():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    sheet = data.get("sheet")

    try:
        path = find_upload(token)
        columns = table_columns(path, str(sheet) if sheet else None)
    except SheetToAnkiError as exc:
        return json_error(str(exc))
    except Exception as exc:  # pragma: no cover - defensive UI boundary
        return json_error(f"Could not read columns: {exc}")

    return jsonify({"columns": columns})


@app.post("/api/generate")
def generate_cards():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    sheet = data.get("sheet")
    front = str(data.get("front", ""))
    back = str(data.get("back", ""))

    if not front or not back:
        return json_error("Choose both front and back columns.")

    try:
        path = find_upload(token)
        df = read_table(path, str(sheet) if sheet else None)
        require_columns(df, front, back)
    except SheetToAnkiError as exc:
        return json_error(str(exc))
    except Exception as exc:  # pragma: no cover - defensive UI boundary
        return json_error(f"Could not generate cards: {exc}")

    output = io.StringIO()
    count = 0
    for _, row in df.iterrows():
        front_value = clean_cell(row[front])
        back_value = clean_cell(row[back])
        if not front_value or not back_value:
            continue
        output.write(f"{front_value}\t{back_value}\n")
        count += 1

    if count == 0:
        return json_error("No cards were generated. Check for empty selected columns.")

    data_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    data_bytes.seek(0)
    stem = Path(path.name).stem.split("_", 1)[-1] or "anki_cards"
    download_name = f"{stem}_anki_cards.txt"
    return send_file(
        data_bytes,
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=download_name,
    )


def main() -> None:
    app.run(host="127.0.0.1", port=8765, debug=False)


if __name__ == "__main__":
    main()
