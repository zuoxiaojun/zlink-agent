"""Auto-pagination helper.

Returns a :class:`PaginatedResult` with records and a human-readable
note that the LLM can use to understand whether the result is complete.

If *page_index* is passed explicitly → single page fetch.
If omitted → loops all pages until the API returns fewer records than the
page size (end of data) or :data:`MAX_PAGES` is reached.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

MAX_PAGES = 200


@dataclass
class PaginatedResult:
    """Result of a paginated query.

    Attributes:
        records: The collected records.
        note: A human-readable note describing completeness.
    """

    records: list[dict]
    note: str


def paginate(
    arguments: dict,
    default_page_size: int,
    fetch: Callable[[int, int], list[dict]],
) -> PaginatedResult:
    page_index = arguments.get("page_index")
    page_size = arguments.get("page_size", default_page_size)

    # Explicit page_index requested → single page
    if page_index is not None:
        batch = fetch(int(page_index), page_size)
        return PaginatedResult(
            records=batch,
            note=f"单页查询结果（第 {page_index} 页，每页 {page_size} 条，返回 {len(batch)} 条）",
        )

    # No page_index → auto-paginate all pages
    all_records: list[dict] = []
    pages_fetched = 0
    for pi in range(1, MAX_PAGES + 1):
        batch = fetch(pi, page_size)
        if not batch:
            break
        all_records.extend(batch)
        pages_fetched += 1
        if len(batch) < page_size:
            break

    return PaginatedResult(
        records=all_records,
        note=f"已自动翻页获取全部数据（共 {pages_fetched} 页，{len(all_records)} 条）",
    )
