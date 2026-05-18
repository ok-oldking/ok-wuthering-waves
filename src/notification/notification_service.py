from ok import Logger, og
import threading

from src.notification.discord_webhook import DiscordWebhookNotifier

logger = Logger.get_logger(__name__)


class NotificationService:
    def __init__(self, config: dict | None):
        self.config = config or {}

    def notify(self, level: str, message: str, task=None) -> None:
        if level == "INFO" and not self.config.get("Notify On Info", True):
            return
        if level == "ERROR" and not self.config.get("Notify On Error", True):
            return
        if not self._task_notification_enabled(task):
            return

        webhook_url = self.config.get("Discord Webhook URL", "")
        if not webhook_url:
            logger.error(self._translate("Discord Webhook URL is empty. Please set it in Notification Config."))
            return

        screenshot = self._get_screenshot(task)

        task_name = ""
        if task is not None:
            task_name = getattr(task, "name", "") or task.__class__.__name__
        notifier = DiscordWebhookNotifier(
            webhook_url=webhook_url,
            username=self.config.get("Discord Username", ""),
        )
        thread = threading.Thread(
            target=self._send_safely,
            args=(notifier, level, message, task_name, screenshot, self.config.get("Mention User ID", "")),
            daemon=True,
            name="DiscordNotification",
        )
        thread.start()

    def _get_screenshot(self, task):
        if not self.config.get("Attach Screenshot", True) or task is None:
            return None
        try:
            frame = task.executor.nullable_frame()
            return frame.copy() if frame is not None else None
        except Exception:
            logger.debug("Could not capture notification screenshot")
            return None

    @staticmethod
    def _task_notification_enabled(task) -> bool:
        if task is None:
            return True
        return bool(getattr(task, "config", {}).get("Send Discord Notification", False))

    @staticmethod
    def _translate(message: str) -> str:
        try:
            return og.app.tr(message)
        except Exception:
            return message

    @staticmethod
    def _send_safely(notifier, level: str, message: str, task_name: str, screenshot, mention_user_id: str) -> None:
        try:
            notifier.send(
                title="OK-WW",
                message=message,
                level=level,
                task_name=task_name,
                screenshot=screenshot,
                mention_user_id=mention_user_id,
            )
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
