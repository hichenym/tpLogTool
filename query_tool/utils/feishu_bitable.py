"""
飞书多维表格记录 CRUD 通用库
"""

import json
import time
from typing import Any, Dict, List, Optional

import lark_oapi as lark
from lark_oapi.core.exception import ObtainAccessTokenException, NoAuthorizationException
from lark_oapi.api.bitable.v1 import *


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

    def add_or_update_record(self, **fields) -> Dict[str, Any]:
        """
        新增或更新记录（按 User 去重）。
        - User 不存在：新增，Count=1，Date=当前时间戳。
        - User 已存在：Count+1，Date=当前时间戳，更新 Version。
        """
        user = fields.get("User")
        if user is None:
            raise ValueError("add_or_update_record 必须提供 User 字段")

        for rec in self.list_records():
            rec_fields = rec.get("fields", {})
            rec_user = rec_fields.get("User")
            # 飞书文本字段可能返回富文本 list[dict]，兼容处理
            if isinstance(rec_user, list):
                rec_user = rec_user[0].get("text", "") if rec_user else ""
            if rec_user != user:
                continue

            old_count = rec_fields.get("Count", 0)
            if not isinstance(old_count, (int, float)):
                old_count = 0
            new_count = int(old_count) + 1

            update_data = {"Count": new_count, "Date": int(time.time() * 1000)}
            if "Version" in fields:
                update_data["Version"] = fields["Version"]

            # print(f"[FeishuBitable] User={user} 已存在 (record_id={rec['record_id']})，Count: {int(old_count)} -> {new_count}")
            return self.update_record(rec["record_id"], **update_data)

        fields["Count"] = 1
        fields["Date"] = int(time.time() * 1000)
        # print(f"[FeishuBitable] User={user} 不存在，新增记录 (Count=1)")
        return self.add_record(**fields)

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

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _call(self, fn, request) -> Dict[str, Any]:
        """统一调用入口，处理鉴权异常和响应错误"""
        try:
            response = fn(request)
        except ObtainAccessTokenException as e:
            # print(f"获取 tenant_access_token 失败: code={e.code}, msg={e.msg}")
            raise FeishuBitableError(code=e.code, msg=e.msg) from e
        except NoAuthorizationException as e:
            # print(f"鉴权信息缺失: {e}")
            raise FeishuBitableError(code=-1, msg=str(e)) from e

        if not response.success():
            try:
                detail = json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)
            except Exception:
                detail = str(response.raw.content) if response.raw else ""
            # print(detail)
            raise FeishuBitableError(response.code, response.msg, response.get_log_id())

        return json.loads(lark.JSON.marshal(response.data))
