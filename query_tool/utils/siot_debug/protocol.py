import ctypes
import re
import struct
from typing import Optional, Tuple
from xml.sax.saxutils import escape

from .models import ParsedPayload


HEADER_FLAG = 0x51589158
HEADER_ENCRYPT_FLAG = 0x52598157
MSG_HEAD_LEN = 12

PAYLOAD_TYPE_XML = 0x01
PAYLOAD_TYPE_JSON = 0x02

XML_END_TAG = b"</XML_TOPSEE>"


def decode_text(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _call_crypt(fn, method: int, payload: bytes, key: bytes, output_scale: int) -> bytes:
    buffer = ctypes.create_string_buffer(max(len(payload) * output_scale, 1024))
    result_len = fn(
        method,
        ctypes.c_char_p(payload),
        len(payload),
        buffer,
        len(buffer),
        ctypes.c_char_p(key),
    )
    if result_len <= 0:
        raise RuntimeError(f"加解密接口返回异常: {result_len}")
    return bytes(buffer[:result_len])


def pack_message(
    payload: bytes,
    payload_type: int,
    *,
    encrypt: bool,
    method: int,
    key: bytes,
    crypt_lib,
) -> bytes:
    if encrypt and method >= 1 and key:
        body = _call_crypt(crypt_lib.TpsProtocolEncode, method, payload, key, 2)
        flag = HEADER_ENCRYPT_FLAG
    else:
        body = payload
        flag = HEADER_FLAG
    return struct.pack("<IIBxxx", flag, len(body), payload_type) + body


def unpack_message(data: bytes, *, method: int, key: bytes, crypt_lib) -> Optional[bytes]:
    if len(data) < MSG_HEAD_LEN:
        return None
    flag, data_len, _ = struct.unpack_from("<IIB", data, 0)
    if flag not in (HEADER_FLAG, HEADER_ENCRYPT_FLAG):
        return None
    if len(data) < MSG_HEAD_LEN + data_len:
        return None

    body = data[MSG_HEAD_LEN: MSG_HEAD_LEN + data_len]
    if flag == HEADER_ENCRYPT_FLAG and method >= 1 and key:
        try:
            return _call_crypt(crypt_lib.TpsProtocolDecode, method, body, key, 2)
        except RuntimeError:
            return None
    return body


def build_system_log_xml(command: str, channel: int = 0) -> bytes:
    escaped_command = escape(command)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<XML_TOPSEE>\n"
        f'  <MESSAGE_HEADER Msg_type="SYSTEM_LOG_MESSAGE" Msg_code="1" Msg_flag="0" Msg_chn="{channel}"/>\n'
        "  <MESSAGE_BODY>\n"
        f"    <cmd>{escaped_command}</cmd>\n"
        "  </MESSAGE_BODY>\n"
        "</XML_TOPSEE>"
    )
    return xml.encode("utf-8")


def build_auth_xml(password: str, sn: str, username: str, crypt_lib) -> bytes:
    encoded_password = password
    try:
        encoded = _call_crypt(
            crypt_lib.TpsProtocolEncode,
            1,
            password.encode("utf-8"),
            sn.encode("utf-8"),
            3,
        )
        encoded_password = encoded.decode("latin-1", errors="ignore")
    except RuntimeError:
        encoded_password = password

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<XML_TOPSEE>\n"
        '  <MESSAGE_HEADER Msg_type="USER_AUTH_MESSAGE" Msg_code="CMD_USER_AUTH" Msg_flag="0"/>\n'
        "  <MESSAGE_BODY>\n"
        f'    <USER_AUTH_PARAM Username="{escape(username)}" Password="{escape(encoded_password)}" '
        f'AuthMethod="3" SessionId="{escape(sn)}" ClientUser="{escape(sn)}" MetaDataVer="1"/>\n'
        '    <ENCRYPT Capbility="SUPPORT_TPE" Version="1" KeyTypeVer="1"/>\n'
        "  </MESSAGE_BODY>\n"
        "</XML_TOPSEE>"
    )
    return xml.encode("utf-8")


def extract_xml_attr(xml: str, element: str, attr: str) -> str:
    pattern = re.compile(rf"<{element}\b[^>]*\b{attr}=\"([^\"]*)\"", re.IGNORECASE | re.DOTALL)
    match = pattern.search(xml)
    return match.group(1) if match else ""


def extract_xml_element(xml: str, element: str) -> str:
    pattern = re.compile(rf"<{element}\b[^>]*>(.*?)</{element}>", re.IGNORECASE | re.DOTALL)
    match = pattern.search(xml)
    return match.group(1).strip() if match else ""


def extract_resp_str(text: str) -> Optional[str]:
    matches = re.findall(r'RespStr="([^"]*)"', text)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    non_empty = [item for item in matches if item]
    if not non_empty:
        return ""
    return "\n".join(non_empty)


def _split_xml_and_binary(data: bytes) -> Tuple[str, bytes]:
    xml_start = data.find(b"<?xml")
    if xml_start < 0:
        xml_start = data.find(b"<XML_TOPSEE>")
    if xml_start < 0:
        return decode_text(data), b""

    xml_end = data.find(XML_END_TAG, xml_start)
    if xml_end < 0:
        return decode_text(data), b""

    xml_end += len(XML_END_TAG)
    xml_bytes = data[xml_start:xml_end]
    tail = data[xml_end:]
    if tail.startswith(b"\x00\x00\x00\x00"):
        tail = tail[4:]
    return decode_text(xml_bytes), tail


def parse_device_payload(data: bytes) -> ParsedPayload:
    xml_text, tail = _split_xml_and_binary(data)
    response_param = extract_xml_element(xml_text, "RESPONSE_PARAM")
    message_body = extract_xml_element(xml_text, "MESSAGE_BODY")
    data_len = int(extract_xml_attr(xml_text, "POS", "DataLen") or "0")
    binary_payload = tail[:data_len] if data_len > 0 else b""

    return ParsedPayload(
        message_type=extract_xml_attr(xml_text, "MESSAGE_HEADER", "Msg_type"),
        msg_code=extract_xml_attr(xml_text, "MESSAGE_HEADER", "Msg_code"),
        msg_flag=extract_xml_attr(xml_text, "MESSAGE_HEADER", "Msg_flag"),
        xml_text=xml_text,
        response_param=response_param,
        message_body=message_body,
        resp_str=extract_resp_str(response_param or xml_text),
        filename=extract_xml_attr(xml_text, "POS", "Filename") or None,
        start_pos=int(extract_xml_attr(xml_text, "POS", "StartPos") or "0"),
        data_len=data_len,
        binary_payload=binary_payload,
    )


def looks_like_xml(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("<")


def extract_printable_text(payload: ParsedPayload) -> str:
    if payload.resp_str is not None and payload.resp_str.strip():
        return payload.resp_str.strip()
    if payload.response_param and "RespStr=" in payload.response_param:
        return ""
    if payload.message_body and not looks_like_xml(payload.message_body):
        return payload.message_body.strip()
    if payload.response_param and not looks_like_xml(payload.response_param):
        return payload.response_param.strip()
    return ""


def make_text_output(data: bytes) -> str:
    if not data:
        return ""
    raw_text = decode_text(data)
    text = "".join(
        ch for ch in raw_text
        if ch in "\r\n\t" or ord(ch) >= 32
    )
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\r\n\t")
    if printable / max(len(text), 1) < 0.80:
        return data[:128].hex(" ")
    return text


def decode_secret_key(rand_key: str, device_sn: str, crypt_lib) -> bytes:
    if not rand_key:
        return b""
    try:
        return _call_crypt(
            crypt_lib.TpsProtocolDecode,
            1,
            rand_key.encode("latin-1"),
            device_sn.encode("utf-8"),
            10,
        )
    except RuntimeError:
        return rand_key.encode("latin-1", errors="ignore")
