"""SDK 桥接层。

将 astrbot_sdk (子进程插件架构) 接入 astrbot/core (同进程插件架构)。

主要组件：
- CoreCapabilityBridge: 将 Core Context 的能力注册到 SDK CapabilityRouter
- SdkPluginBridge: 管理 SupervisorRuntime，将 SDK handlers 注册到 Core
- EventConverter: AstrMessageEvent ↔ SDK payload 双向转换
- TriggerConverter: SDK Trigger → Core HandlerFilter 转换
"""

from .capability_bridge import CoreCapabilityBridge
from .event_converter import EventConverter
from .plugin_bridge import SdkPluginBridge
from .trigger_converter import TriggerConverter

__all__ = [
    "CoreCapabilityBridge",
    "SdkPluginBridge",
    "EventConverter",
    "TriggerConverter",
]
