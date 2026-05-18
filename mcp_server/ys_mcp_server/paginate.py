"""Auto-pagination helper: if page_index absent, loop all pages; else single page."""

from collections.abc import Callable


def paginate(arguments: dict, default_page_size: int, fetch: Callable[[int, int], list[dict]]) -> list[dict]:
    page_index = arguments.get("page_index")
    page_size = arguments.get("page_size", default_page_size)

    if page_index is not None:
        return fetch(page_index, page_size)

    all_records = []
    pi = 1
    while True:
        batch = fetch(pi, page_size)
        all_records.extend(batch)
        if len(batch) < page_size:
            break
        pi += 1
    return all_records
