"""OK-WW 的 macOS 任务能力分级与当前支持状态。

本模块只描述任务依赖和发布声明，不实现任何操作系统后端。能力由 ``ok-script``
的当前 interaction provider 提供；任务状态与能力证据状态是两个独立维度。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ok.device.capabilities import DeviceCapabilities, NO_DEVICE_CAPABILITIES


class MacTaskCapabilityLevel(str, Enum):
    """任务所需输入模型的最高等级。"""

    MAC_BASIC = "MAC_BASIC"
    MAC_LOCKED_GAMEPLAY = "MAC_LOCKED_GAMEPLAY"
    MAC_FULL_CAMERA = "MAC_FULL_CAMERA"


class MacTaskSupportStatus(str, Enum):
    """面向用户的任务状态；不替代 capability evidence state。"""

    VALIDATED = "validated"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class MacTaskCompatibility:
    level: MacTaskCapabilityLevel | None
    required: DeviceCapabilities
    status: MacTaskSupportStatus
    note: str

    def missing_from(self, available: DeviceCapabilities) -> tuple[str, ...]:
        return available.missing(self.required)

    def can_attempt(self, available: DeviceCapabilities) -> bool:
        """实验性或已验收任务在能力满足时允许进入执行前检查。"""
        return (
            self.status is not MacTaskSupportStatus.UNSUPPORTED
            and available.supports(self.required)
        )


# 级别基线用于文档、UI 和测试。具体任务仍按真实调用声明更精确的 required。
MAC_BASIC_CAPABILITIES = DeviceCapabilities(
    keyboard_tap=True,
    absolute_mouse=True,
    mouse_left=True,
    foreground_only=True,
)

MAC_LOCKED_GAMEPLAY_CAPABILITIES = DeviceCapabilities(
    keyboard_tap=True,
    keyboard_hold=True,
    absolute_mouse=True,
    mouse_left=True,
    mouse_right=True,
    mouse_middle=True,
    mouse_button_hold=True,
    foreground_only=True,
)

MAC_FULL_CAMERA_CAPABILITIES = MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(
    relative_mouse=True,
)


def _requirements(**enabled: bool) -> DeviceCapabilities:
    return DeviceCapabilities(**enabled)


# 这里覆盖 config.py 当前登记的全部任务。状态只表示当前工作分支的开放策略：
# - experimental：允许在能力满足后用于真机验收，不等于“已支持”；
# - unsupported：即使底层方法存在也不得运行。
TASK_MACOS_COMPATIBILITY: dict[str, MacTaskCompatibility] = {
    # 基础菜单、领取、背包和固定页面操作。
    "src.task.MergeEchoTask.MergeEchoTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(keyboard_tap=True, absolute_mouse=True, mouse_left=True,
                      foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "合成页面：键盘单击、固定坐标/识别框左键点击。",
    ),
    "src.task.EnhanceEchoTask.EnhanceEchoTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(keyboard_tap=True, absolute_mouse=True, mouse_left=True,
                      foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "声骸强化页面：键盘单击与左键点击。",
    ),
    "src.task.ChangeEchoTask.ChangeEchoTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(keyboard_tap=True, absolute_mouse=True, mouse_left=True,
                      foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "声骸更换页面：键盘单击与左键点击。",
    ),
    "src.task.AutoLoginTask.AutoLoginTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(absolute_mouse=True, mouse_left=True, foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "登录/公告流程：识别框与固定位置左键点击。",
    ),
    "src.task.AutoPickTask.AutoPickTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(keyboard_tap=True, scroll=True, foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "自动拾取发送 F 键，文本候选滚动时需要 scroll；不依赖自由镜头。",
    ),
    "src.task.SkipDialogTask.AutoDialogTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(absolute_mouse=True, mouse_left=True, foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "跳过对话：视觉识别后的左键点击。",
    ),
    "src.task.FastTravelTask.FastTravelTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_BASIC,
        _requirements(absolute_mouse=True, mouse_left=True, foreground_only=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "快速传送触发器：视觉识别后的左键点击。",
    ),

    # 依赖持续方向键、中键居中/锁定或鼠标按钮保持的流程。
    "src.task.AutoCombatTask.AutoCombatTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        _requirements(
            keyboard_tap=True,
            keyboard_hold=True,
            absolute_mouse=True,
            mouse_left=True,
            mouse_middle=True,
            mouse_button_hold=True,
            foreground_only=True,
        ),
        MacTaskSupportStatus.EXPERIMENTAL,
        "当前战斗逻辑依赖按键保持、中键和左键保持；未发现自由镜头 delta 调用。",
    ),
    "src.task.FarmEchoTask.FarmEchoTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        _requirements(
            keyboard_tap=True,
            keyboard_hold=True,
            absolute_mouse=True,
            mouse_left=True,
            mouse_right=True,
            mouse_middle=True,
            mouse_button_hold=True,
            scroll=True,
            foreground_only=True,
        ),
        MacTaskSupportStatus.EXPERIMENTAL,
        "持续 W/A/S/D、右键跑动、中键居中、战斗和滚轮。",
    ),
    "src.task.NightmareNestTask.NightmareNestTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(scroll=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "包含移动、战斗与领取子流程。",
    ),
    "src.task.TacetTask.TacetTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(scroll=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "包含寻路到交互点、持续方向键、中键与战斗。",
    ),
    "src.task.ForgeryTask.ForgeryTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(scroll=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "副本流程会进入移动和战斗辅助。",
    ),
    "src.task.SimulationTask.SimulationTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(scroll=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "副本流程会进入移动和战斗辅助。",
    ),
    "src.task.DailyTask.DailyTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(scroll=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "编排多个日常/副本子任务，按最宽子流程能力进行门控。",
    ),
    "src.task.MultiAccountDailyTask.MultiAccountDailyTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        MAC_LOCKED_GAMEPLAY_CAPABILITIES.with_overrides(scroll=True),
        MacTaskSupportStatus.EXPERIMENTAL,
        "编排 DailyTask，按其最宽子流程能力进行门控。",
    ),
    "src.task.GardenTask.GardenTask": MacTaskCompatibility(
        MacTaskCapabilityLevel.MAC_LOCKED_GAMEPLAY,
        _requirements(
            keyboard_tap=True,
            keyboard_hold=True,
            absolute_mouse=True,
            mouse_left=True,
            foreground_only=True,
        ),
        MacTaskSupportStatus.EXPERIMENTAL,
        "包含固定页面操作和持续按键流程；真机前保持实验性。",
    ),

    # Windows 后台/窗口 workaround，不是原生 Mac P0 的默认能力。
    "src.task.MouseResetTask.MouseResetTask": MacTaskCompatibility(
        None,
        NO_DEVICE_CAPABILITIES,
        MacTaskSupportStatus.UNSUPPORTED,
        "Windows 光标复位 workaround；Mac P0 明确禁用，除非真机证明确有需要。",
    ),
}


def task_identifier(task_or_class: Any) -> str:
    cls = task_or_class if isinstance(task_or_class, type) else type(task_or_class)
    return f"{cls.__module__}.{cls.__name__}"


def get_macos_task_compatibility(task_or_class: Any) -> MacTaskCompatibility:
    identifier = task_identifier(task_or_class)
    return TASK_MACOS_COMPATIBILITY.get(
        identifier,
        MacTaskCompatibility(
            None,
            NO_DEVICE_CAPABILITIES,
            MacTaskSupportStatus.UNSUPPORTED,
            "任务未声明 macOS 能力依赖，按 fail-closed 处理。",
        ),
    )


class MacTaskUnsupportedError(RuntimeError):
    def __init__(self, task_name: str, compatibility: MacTaskCompatibility):
        self.task_name = task_name
        self.compatibility = compatibility
        super().__init__(
            f"Task {task_name!r} is not available on macOS: {compatibility.note}"
        )
