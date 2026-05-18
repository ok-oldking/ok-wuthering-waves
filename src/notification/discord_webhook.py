import io
import json
from datetime import datetime


DISCORD_COLORS = {
    "INFO": 0x3498DB,
    "ERROR": 0xE74C3C,
}


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str, username: str = "", timeout: int = 15):
        self.webhook_url = webhook_url.strip()
        self.username = username.strip()
        self.timeout = timeout

    def send(
        self,
        title: str,
        message: str,
        level: str,
        task_name: str = "",
        screenshot=None,
        mention_user_id: str = "",
    ) -> None:
        if not self.webhook_url:
            return

        image_bytes = self._image_to_bytes(screenshot) if screenshot is not None else None
        payload = self._build_payload(title, message, level, task_name, mention_user_id, image_bytes is not None)
        if self.username:
            payload["username"] = self.username

        import requests

        if image_bytes is None:
            response = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
        else:
            response = requests.post(
                self.webhook_url,
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files={"files[0]": ("screenshot.jpg", image_bytes, "image/jpeg")},
                timeout=self.timeout,
            )

        response.raise_for_status()

    @staticmethod
    def _build_payload(
        title: str,
        message: str,
        level: str,
        task_name: str,
        mention_user_id: str,
        has_screenshot: bool,
    ) -> dict:
        payload = {}
        mention_user_id = mention_user_id.strip()
        if mention_user_id:
            payload["content"] = f"<@{mention_user_id}>"

        fields = [{"name": "Level", "value": level, "inline": True}]
        if task_name:
            fields.insert(0, {"name": "Task", "value": task_name, "inline": True})

        embed = {
            "title": title,
            "description": str(message),
            "color": DISCORD_COLORS.get(level, 0x95A5A6),
            "fields": fields,
            "timestamp": datetime.now().astimezone().isoformat(),
        }
        if has_screenshot:
            embed["image"] = {"url": "attachment://screenshot.jpg"}
        payload["embeds"] = [embed]
        return payload

    @staticmethod
    def _image_to_bytes(image):
        import cv2

        success, encoded = cv2.imencode(".jpg", image)
        if not success:
            return None
        return io.BytesIO(encoded.tobytes())
