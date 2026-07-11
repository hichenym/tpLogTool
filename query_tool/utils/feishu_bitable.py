"""
飞书多维表格记录 CRUD 通用库
"""

import json
import time
from typing import Any, Dict, List, Optional, Sequence

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *
from lark_oapi.core.exception import NoAuthorizationException, ObtainAccessTokenException


class FeishuBitableError(Exception):
    """飞书多维表格操作异常"""

    def __init__(self, code: int, msg: str, log_id: str = ""):
        self.code = code
        self.msg = msg
        self.log_id = log_id
        super().__init__(f"code={code}, msg={msg}, log_id={log_id}")


class FeishuBitable:
    """飞书多维表格记录增删改查通用客户端"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        app_token: str,
        table_id: str,
        log_level: lark.LogLevel = lark.LogLevel.ERROR,
    ):
        self.app_token = app_token
        self.table_id = table_id
        self.client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(log_level)
            .build()
        )

    def add_record(self, **fields) -> Dict[str, Any]:
        """新增一条记录"""
        request = (
            CreateAppTableRecordRequest.builder()
            .app_token(self.app_token)
            .table_id(self.table_id)
            .request_body(AppTableRecord.builder().fields(fields).build())
            .build()
        )
        return self._call(self.client.bitable.v1.app_table_record.create, request)

    @staticmethod
    def _normalize_match_value(value: Any) -> str:
        """Normalize text-ish bitable values into comparable strings."""
        if isinstance(value, list):
            if not value:
                return ""
            first = value[0]
            if isinstance(first, dict):
                return str(first.get("text", "") or "").strip()
            return str(first or "").strip()
        return str(value or "").strip()

    def add_or_update_record(self, *, match_fields: Sequence[str] = ("User",), **fields) -> Dict[str, Any]:
        """
        新增或更新记录。

        - 未找到匹配记录：新增，Count=1，Date=当前时间戳。
        - 找到匹配记录：更新所有传入字段，Count+1，Date=当前时间戳。
        """
        normalized_match_fields = tuple(str(field or "").strip() for field in match_fields if str(field or "").strip())
        if not normalized_match_fields:
            raise ValueError("add_or_update_record 必须提供至少一个匹配字段")

        missing_fields = [field for field in normalized_match_fields if field not in fields]
        if missing_fields:
            raise ValueError(f"add_or_update_record 缺少匹配字段: {', '.join(missing_fields)}")

        match_key = tuple(self._normalize_match_value(fields.get(field)) for field in normalized_match_fields)

        for rec in self.list_records():
            rec_fields = rec.get("fields", {})
            rec_key = tuple(self._normalize_match_value(rec_fields.get(field)) for field in normalized_match_fields)
            if rec_key != match_key:
                continue

            old_count = rec_fields.get("Count", 0)
            if not isinstance(old_count, (int, float)):
                old_count = 0

            update_data = dict(fields)
            update_data["Count"] = int(old_count) + 1
            update_data["Date"] = int(time.time() * 1000)
            return self.update_record(rec["record_id"], **update_data)

        create_data = dict(fields)
        create_data["Count"] = 1
        create_data["Date"] = int(time.time() * 1000)
        return self.add_record(**create_data)

    def list_records(self, page_size: int = 20) -> List[Dict[str, Any]]:
        """查询当前表格的所有记录，自动处理分页"""
        all_records: List[Dict[str, Any]] = []
        page_token: Optional[str] = None

        while True:
            builder = (
                SearchAppTableRecordRequest.builder()
                .app_token(self.app_token)
                .table_id(self.table_id)
                .page_size(page_size)
                .request_body(SearchAppTableRecordRequestBody.builder().build())
            )
            if page_token:
                builder = builder.page_token(page_token)

            data = self._call(self.client.bitable.v1.app_table_record.search, builder.build())
            all_records.extend(data.get("items") or [])

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        return all_records

    def delete_record(self, record_id: str) -> Dict[str, Any]:
        """根据 record_id 删除一条记录"""
        request = (
            DeleteAppTableRecordRequest.builder()
            .app_token(self.app_token)
            .table_id(self.table_id)
            .record_id(record_id)
            .build()
        )
        return self._call(self.client.bitable.v1.app_table_record.delete, request)

    def update_record(self, record_id: str, **fields) -> Dict[str, Any]:
        """增量更新一条记录，只更新传入的字段"""
        request = (
            UpdateAppTableRecordRequest.builder()
            .app_token(self.app_token)
            .table_id(self.table_id)
            .record_id(record_id)
            .request_body(AppTableRecord.builder().fields(fields).build())
            .build()
        )
        return self._call(self.client.bitable.v1.app_table_record.update, request)

    def _call(self, fn, request) -> Dict[str, Any]:
        """统一调用入口，处理鉴权异常和响应错误"""
        try:
            response = fn(request)
        except ObtainAccessTokenException as e:
            raise FeishuBitableError(code=e.code, msg=e.msg) from e
        except NoAuthorizationException as e:
            raise FeishuBitableError(code=-1, msg=str(e)) from e

        if not response.success():
            try:
                detail = json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)
            except Exception:
                detail = str(response.raw.content) if response.raw else ""
            raise FeishuBitableError(response.code, f"{response.msg} {detail}".strip(), response.get_log_id())

        return json.loads(lark.JSON.marshal(response.data))
