"""SQLite tables (SQLModel).

`scans.result_json` holds the complete API response, so history can return exactly
what the app saw. `ingredients` and `findings` are copies of the same data in
queryable form (handy for analysis / evaluation later).
"""
from sqlmodel import Field, SQLModel


class Scan(SQLModel, table=True):
    __tablename__ = "scans"

    id: str = Field(primary_key=True)  # = scan_id in the API
    device_id: str = Field(index=True)  # from the X-Device-Id header
    created_at: str = Field(index=True)  # ISO-8601 UTC, same string the API returned
    food_category: str | None = None
    overall_status: str  # PASS / FLAG / REVIEW (for the history list)
    health_score: int
    assessment: str
    ingredient_count: int
    image_name: str | None = None  # file name inside uploads/ (None for /analyze)
    result_json: str  # full ScanResponse as JSON
    explanation: str | None = None  # cached LLM explanation (filled in Phase 4)


class IngredientRow(SQLModel, table=True):
    __tablename__ = "ingredients"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: str = Field(foreign_key="scans.id", index=True)
    ing_id: str  # "ing_1", "ing_2", ...
    position: int
    original: str
    normalized: str | None = None
    category: str | None = None
    ins_number: str | None = None
    percentage: float | None = None
    match_confidence: float
    known: bool


class FindingRow(SQLModel, table=True):
    __tablename__ = "findings"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: str = Field(foreign_key="scans.id", index=True)
    ingredient_id: str | None = None  # matches IngredientRow.ing_id; None = label-level finding
    rule_id: str
    status: str
    reason: str
    source: str
