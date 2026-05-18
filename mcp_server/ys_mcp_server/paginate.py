"""Auto-pagination helper: if page_index absent, loop all pages; else single page."""

from collections.abc import Callable

MAX_PAGES = 200


def paginate(arguments: dict, default_page_size: int, fetch: Callable[[int, int], list[dict]]) -> list[dict]:
    page_index = arguments.get("page_index")
    page_size = arguments.get("page_size", default_page_size)

    # Explicit page_index requested → single page
    if page_index is not None:
        return fetch(int(page_index), page_size)

    # No page_index → auto-paginate all pages
    all_records = []
    for pi in range(1, MAX_PAGES + 1):
        batch = fetch(pi, page_size)
        if not batch:
            break
        all_records.extend(batch)
        if len(batch) < page_size:
            break
    return all_records
