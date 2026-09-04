from aiogram import Dispatcher

from . import (
    channel_texts,
    channels,
    common,
    content_plan,
    farewells,
    feature_navigation,
    join_filters,
    joins,
    publications,
    requirement_chats,
    settings,
    stats,
    templates,
)


def include_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(common.router)
    dispatcher.include_router(channels.router)
    dispatcher.include_router(requirement_chats.router)
    dispatcher.include_router(channel_texts.router)
    dispatcher.include_router(farewells.router)
    dispatcher.include_router(feature_navigation.router)
    dispatcher.include_router(join_filters.router)
    dispatcher.include_router(publications.router)
    dispatcher.include_router(templates.router)
    dispatcher.include_router(content_plan.router)
    dispatcher.include_router(joins.router)
    dispatcher.include_router(stats.router)
    dispatcher.include_router(settings.router)
