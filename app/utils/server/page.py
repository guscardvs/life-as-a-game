from uuid import UUID

from escudeiro.contrib.msgspec import CamelStruct

from app.utils.msgspec import DefaultSchema


class Page(CamelStruct):
    last_id: UUID | None = None
    size: int = 10

    def __post_init__(self):
        if self.size < 1:
            raise ValueError("Size must be greater than or equal to 1")

    @property
    def limit(self) -> int:
        return self.size


class PagedResponse[T: DefaultSchema](CamelStruct):
    data: list[T]
    total: int
    page: Page
    has_next: bool

    @classmethod
    def from_data(
        cls, data: list[T], total: int, page: Page
    ) -> "PagedResponse[T]":
        next_page = Page(
            last_id=data[-1].id_ if data else None,
            size=page.size,
        )
        return cls(
            data=data,
            total=total,
            page=next_page,
            has_next=len(data) == page.size, # likely
        )
