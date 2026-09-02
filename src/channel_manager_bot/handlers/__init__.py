from aiogram import Dispatcher

from . import channels, common, joins, publications, settings, stats


def include_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(common.router)
    dispatcher.include_router(channels.router)
    dispatcher.include_router(publications.router)
    dispatcher.include_router(joins.router)
    dispatcher.include_router(stats.router)
    dispatcher.include_router(settings.router)
