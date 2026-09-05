"""Published response fields shared by the tools and their MCP descriptions."""

from typing import Literal, NotRequired, TypedDict


class Source(TypedDict):
    agency: str
    product: str
    vintage: str
    base_year: int | None
    horizon_year: int | None
    retrieved_at: str | None
    citation: str | None
    license: str | None
    url: str | None
    method_notes: str | None


class Geography(TypedDict):
    level: str
    id: str
    name: str


class Candidate(TypedDict):
    geo_id: str
    name: str


class Coverage(TypedDict):
    status: Literal['available', 'not_published', 'state_level_only', 'pdf_only']
    detail: str | None


class Pointer(Coverage):
    geo_level: str


class Point(TypedDict):
    year: int
    datatype: Literal['estimate', 'projection']


class ForecastPoint(Point):
    value: int | float


class ComponentPoint(Point):
    period_start_year: NotRequired[int]
    period_end_year: NotRequired[int]
    births: NotRequired[int | float]
    deaths: NotRequired[int | float]
    net_migration: NotRequired[int | float]


class SeriesResult(TypedDict):
    status: Literal['ok', 'error', 'not_published', 'state_level_only', 'pdf_only',
                    'not_loaded', 'empty_range', 'coverage_unknown']
    state: NotRequired[str]
    variable: NotRequired[str]
    geo_level: NotRequired[str]
    geo: NotRequired[Geography]
    scenario: NotRequired[str | None]
    scenario_note: NotRequired[str | None]
    source: NotRequired[Source | None]
    error: NotRequired[str]
    reason: NotRequired[str]
    candidates: NotRequired[list[Candidate] | None]
    closest_published: NotRequired[list[Pointer] | None]
    available_start_year: NotRequired[int]
    available_end_year: NotRequired[int]


class ForecastResult(SeriesResult):
    series: NotRequired[list[ForecastPoint]]


class ComponentsResult(SeriesResult):
    series: NotRequired[list[ComponentPoint]]


class LoadedSeries(TypedDict):
    variable: str
    geo_level: str
    source_id: str
    row_count: int
    start_year: int
    end_year: int


class CoverageInventory(Coverage):
    load_status: Literal['loaded', 'partially_loaded', 'not_loaded']
    loaded_series: list[LoadedSeries]


class ReviewStatus(TypedDict):
    interval_days: int
    focus: str
    last_reviewed_on: str | None
    next_review_due: str | None
    status: Literal['never_reviewed', 'due', 'not_due']
    as_of: str
    findings: str | None
    evidence: list[str]
    review_links: dict[str, str]


class StateSummary(TypedDict):
    name: str
    agency: str
    current_vintage: str
    geography_floor: str
    scenarios: list[str] | None
    default_scenario: str | None
    scenario_geo_levels: list[str] | None
    employment_note: str
    variables: dict[str, dict[str, CoverageInventory]]
    review: ReviewStatus
    data_loaded: bool


class StatesResult(TypedDict):
    states: dict[str, StateSummary]
    database_release: str | None


class SourceResult(TypedDict, total=False):
    status: Literal['error']
    error: str
    state: str
    name: str
    agency: str
    producer_type: str
    current_vintage: str
    geography_floor: str
    products: list[str]
    methodology: str
    employment_note: str
    license: str
    caveats: list[str]
    links: dict[str, str]
    sources_loaded: list[Source] | None
    variables: dict[str, dict[str, CoverageInventory]]
    review: ReviewStatus
