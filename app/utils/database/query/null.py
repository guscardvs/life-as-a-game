from typing import override

import sqlalchemy as sa

from . import interface


class NullBind(interface.BindClause):
    @override
    def bind(self, mapper: interface.Mapper) -> interface.Comparison:
        del mapper
        return sa.true()
