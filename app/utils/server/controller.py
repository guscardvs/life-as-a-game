from typing import override

from blacksheep.server.controllers import Controller, abstract


@abstract()
class DefaultController(Controller):
    @classmethod
    @override
    def class_name(cls) -> str:
        return cls.__name__.removesuffix("Controller")

    @classmethod
    @override
    def route(cls) -> str:
        return f"/{cls.class_name().lower()}"
