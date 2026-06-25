from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, chat_id: str, text: str) -> None:
        ...
