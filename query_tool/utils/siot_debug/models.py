from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass(frozen=True)
class DeviceCredentials:
    sn: str
    username: str
    password: str


@dataclass(frozen=True)
class CloudCredentials:
    client_id: str
    access_node: str
    access_jwt_token: str
    relay_jwt_token: str
    relay_nodes: str
    vip_relay_nodes: str
    jwt_key_version: int


@dataclass
class ParsedPayload:
    message_type: str = ""
    msg_code: str = ""
    msg_flag: str = ""
    xml_text: str = ""
    response_param: str = ""
    message_body: str = ""
    resp_str: Optional[str] = None
    filename: Optional[str] = None
    start_pos: int = 0
    data_len: int = 0
    binary_payload: bytes = b""


@dataclass(frozen=True)
class TransferProgress:
    command: str
    filename: str
    start_pos: int
    chunk_size: int
    received_bytes: int
    packet_index: int
    finished: bool = False


@dataclass
class CommandResult:
    command: str
    command_kind: str
    success: bool
    display_text: str
    acknowledged: bool = False
    binary_payload: bytes = b""
    filename: Optional[str] = None
    received_bytes: int = 0
    streamed_packets: int = 0
    content_suppressed: bool = False
    responses: List[ParsedPayload] = field(default_factory=list)
    keep_listening: bool = False


ProgressCallback = Callable[[TransferProgress], None]
