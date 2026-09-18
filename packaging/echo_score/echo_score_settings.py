"""Visible settings card for the portable Echo Score package."""

from ok import BaseTask

from echo_score import DEFAULT_TEMPLATE, resolve_template_name, template_names


class EchoScoreSettingsTask(BaseTask):
    """Expose package settings on the imported-script page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "声骸评分设置"
        self.description = "配置评分模板、词条框体和 OCR 调试框；修改后立即生效"
        self.default_config.update({
            "启用声骸评分": True,
            "角色评分模板": DEFAULT_TEMPLATE,
            "显示主副词条框体": True,
            "Show Debug Boxes": False,
        })
        self.config_type.update({
            "角色评分模板": {"type": "drop_down", "options": template_names()},
        })
        self.config_description.update({
            "启用声骸评分": "启用后台识别、ECHO-ON 和评分绘制",
            "角色评分模板": "选择 XW-UID 角色/流派评分模板",
            "显示主副词条框体": "只在查看或调谐单个声骸时显示识别框和评分",
            "Show Debug Boxes": "显示 OK 框架的 OCR 调试框",
        })

    def validate_config(self, key, value):
        if key == "角色评分模板" and resolve_template_name(value) != value:
            return "请选择列表中的评分模板"
        return None

    def run(self):
        self.log_info("声骸评分设置已应用；后台识别任务会自动运行。")
