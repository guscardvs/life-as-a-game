import contextlib
from collections.abc import Callable, Collection, Hashable
from typing import Any, override

import sqlalchemy as sa
from escudeiro.data import call_init, data

from app.utils.database.query import comparison, helpers, interface

CACHE_MAXLEN = 250


class _BindCache:
    def __init__(self) -> None:
        self._cached: dict[Hashable, interface.Comparison] = {}
        self.maxlen = CACHE_MAXLEN

    def get(self, key: Hashable) -> interface.Comparison | None:
        try:
            return self._cached.get(key)
        except TypeError:
            return None

    def set(
        self, key: Hashable, value: interface.Comparison
    ) -> interface.Comparison:
        if len(self._cached) >= CACHE_MAXLEN:
            _ = self._cached.pop(tuple(self._cached)[0])
        with contextlib.suppress(TypeError):
            self._cached[key] = value
        return value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.clear()

    def clear(self):
        self._cached.clear()


_cache = _BindCache()


@data
class Resolver[T]:
    val: Any

    def resolve(self, mapper: interface.Mapper):
        _ = mapper
        val = self.val
        if isinstance(val, list):
            return tuple(val)
        elif isinstance(val, set):
            return frozenset(val)
        return val

    def __bool__(self):
        return self.val is not None


class FieldResolver(Resolver[str]):
    @override
    def resolve(self, mapper: interface.Mapper):
        return helpers.retrieve_attr(mapper, self.val)


@data(frozen=False)
class Where[T](interface.BindClause):
    field: str
    expected: Resolver[T]
    comp: interface.Comparator[T] = comparison.equals

    def __init__(
        self,
        field: str,
        expected: T | None = None,
        comp: interface.Comparator[T] = comparison.equals,
        resolver_class: type[Resolver[T]] = Resolver,
    ) -> None:
        call_init(
            self,
            field,
            resolver_class(expected),
            comp,
        )

    @override
    def bind(self, mapper: interface.Mapper) -> interface.Comparison:
        if self.comp is comparison.always_true:
            return AlwaysTrue().bind(mapper)
        resolved = self.expected.resolve(mapper)
        if not isinstance(mapper, Hashable):
            return self._get_comparison(  # pyright: ignore[reportUnreachable]
                helpers.retrieve_attr(mapper, self.field),
                resolved,
            )
        if (
            value := _cache.get((mapper, self.field, resolved, self.comp))
        ) is not None:
            return value
        attr = helpers.retrieve_attr(mapper, self.field)

        return _cache.set(
            (mapper, self.field, resolved, self.comp),
            self._get_comparison(attr, resolved),
        )

    def _get_comparison(self, attr: interface.FieldType, resolved: Any):
        return self.comp(attr, resolved) if self.expected else sa.true()


class _JoinBind(interface.BindClause):
    def __init__(
        self,
        items: Collection[interface.BindClause],
        operator: Callable[..., interface.Comparison],
    ) -> None:
        self.items = items
        self.operator = operator

    def __bool__(self):
        return bool(self.items)

    @override
    def bind(self, mapper: interface.Mapper) -> interface.Comparison:
        return (
            self.operator(*(item.bind(mapper) for item in self.items))
            if self
            else sa.true()
        )


def and_(*bind: interface.BindClause) -> _JoinBind:
    return _JoinBind(bind, sa.and_)


def or_(*bind: interface.BindClause) -> _JoinBind:
    return _JoinBind(bind, sa.or_)


_placeholder_column = sa.Column("placeholder")


class AlwaysTrue(interface.BindClause):
    @override
    def bind(self, mapper: interface.Mapper) -> interface.Comparison:
        return comparison.always_true(_placeholder_column, mapper)


class RawQuery(interface.BindClause):
    def __init__(self, cmp: interface.Comparison) -> None:
        self._cmp = cmp

    @override
    def bind(self, mapper: interface.Mapper) -> interface.Comparison:
        del mapper
        return self._cmp


class ApplyWhere[T: interface.ExecutableType](interface.ApplyClause[T]):
    def __init__(
        self, mapper: interface.Mapper, *where: interface.BindClause
    ) -> None:
        self.where = and_(*where).bind(mapper)

    @override
    def apply(self, query: T) -> T:
        return query.where(self.where)
