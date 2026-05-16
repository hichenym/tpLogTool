from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CommandFamily:
    name: str
    trigger: str
    message_type: str
    keywords: Tuple[str, ...]
    description: str


COMMAND_FAMILIES = (
    CommandFamily(
        name="Syscmd",
        trigger="先输入 syscmd start，后续继续输入带 syscmd 前缀的命令",
        message_type="SYSTEM_LOG_MESSAGE",
        keywords=("syscmd",),
        description="cloud_service/tpsrtc_client.cpp 中 syscmd 只有 start 开关分支，后续命令仍需以 syscmd 开头，不存在 syscmd end 协议分支；其中 syscmd start 本身通常只有空应答。",
    ),
    CommandFamily(
        name="SyscmdEx",
        trigger="若设备端实现了 syscmdEx，可输入 syscmdEx start，后续继续输入带 syscmdEx 前缀的命令",
        message_type="SYSTEM_LOG_MESSAGE",
        keywords=("syscmdEx",),
        description="cloud_service/cloud_p2p.cpp 中存在 syscmdEx 分支，会把参数拼成 shell 命令后走 mysystem；但当前设备实际走的是 tpsrtc_client.cpp 链路，是否支持 syscmdEx 取决于设备固件是否也实现了该分支。",
    ),
    CommandFamily(
        name="GetSystemCfg",
        trigger="直接输入 GetSystemCfg <路径>",
        message_type="SYSTEM_LOG_MESSAGE / SYSTEM_LOG_DATA",
        keywords=("GetSystemCfg",),
        description="设备端日志/文件拉取都走 GetSystemCfg 这一类 SYSTEM_LOG_MESSAGE，请求成功后可能直接返回文件内容。",
    ),
)


def get_command_keyword(command: str) -> str:
    command = command.strip()
    if not command:
        return ""
    return command.split(None, 1)[0]


def is_syscmd_command(command: str) -> bool:
    return get_command_keyword(command) == "syscmd"


def is_syscmdex_command(command: str) -> bool:
    return get_command_keyword(command) == "syscmdEx"


def is_syscmd_family_command(command: str) -> bool:
    return is_syscmd_command(command) or is_syscmdex_command(command)


def is_getsystemcfg_command(command: str) -> bool:
    return get_command_keyword(command) == "GetSystemCfg"


def build_catalog_text() -> str:
    lines = ["当前项目里和源码对应的 P2P 命令类型："]
    for family in COMMAND_FAMILIES:
        keywords = ", ".join(family.keywords)
        lines.append(f"- {family.name}: {family.message_type}")
        lines.append(f"  触发方式: {family.trigger}")
        lines.append(f"  关键词: {keywords}")
        lines.append(f"  说明: {family.description}")
    lines.append("补充说明: 未匹配 syscmd / syscmdEx / GetSystemCfg 前缀的输入，当前客户端会直接忽略。")
    return "\n".join(lines)
