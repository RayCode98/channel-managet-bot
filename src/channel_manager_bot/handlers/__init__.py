from aiogram import Dispatcher

from . import (
    channels,
    common,
    content_plan,
    farewells,
    joins,
    publications,
    settings,
    stats,
    templates,
)


def include_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(common.router)
    dispatcher.include_router(channels.router)
    dispatcher.include_router(farewells.router)
    dispatcher.include_router(publications.router)
    dispatcher.include_router(templates.router)
    dispatcher.include_router(content_plan.router)
    dispatcher.include_router(joins.router)
    dispatcher.include_router(stats.router)
    dispatcher.include_router(settings.router)
