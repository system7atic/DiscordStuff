from discordstuff.notifications.base import Notification
from discordstuff.notifications.discord_notifier import (
    _build_failure_message,
    _build_mention_prefix,
)


def test_build_mention_prefix_joins_subscriber_mentions():
    assert _build_mention_prefix([111, 222, 333]) == "<@111> <@222> <@333>"


def test_build_mention_prefix_empty_when_no_subscribers():
    assert _build_mention_prefix([]) == ""


def test_build_failure_message_combines_title_and_body():
    notification = Notification(title="Job 'cineplex' failed", body="boom")

    assert _build_failure_message(notification) == "Job 'cineplex' failed: boom"
