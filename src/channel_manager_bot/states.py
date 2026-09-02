from aiogram.fsm.state import State, StatesGroup


class PublicationFlow(StatesGroup):
    waiting_content = State()
    waiting_button_text = State()
    waiting_button_url = State()
    selecting_channels = State()
    waiting_schedule = State()


class ChannelWelcomeFlow(StatesGroup):
    waiting_content = State()
    waiting_button_text = State()
    waiting_button_url = State()


class TemplateFlow(StatesGroup):
    waiting_name = State()
    waiting_content = State()
    waiting_button_text = State()
    waiting_button_url = State()
