"""
设备查询API封装
提供设备信息查询、唤醒等功能
"""
import time
import hashlib
import base64
import json
import ddddocr
from .config import config_manager
from .session_manager import session_manager
from .logger import logger
from threading import Lock


class DeviceQuery:
    """设备查询类"""
    def __init__(self, env, username, password, use_cache=True):
        self.username = username
        self.password = password
        self.host = 'console.seetong.com' if env == 'pro' else 'console-test.seetong.com'
        self.env = env
        self.token = None
        self.refresh_token = None
        self.init_error = None  # 记录初始化错误
        self._token_lock = Lock()  # Token刷新锁
        self._dev_id_by_sn = {}
        self._sn_by_dev_id = {}
        self._siot_platform_cache = {}
        
        # 获取Session
        self.session = session_manager.get_session(f'device_query_{env}_{username}')
        
        try:
            if use_cache:
                cached_tokens = config_manager.load_token_cache(env, username)
                if isinstance(cached_tokens, (tuple, list)) and len(cached_tokens) >= 2:
                    self.token, self.refresh_token = cached_tokens[0], cached_tokens[1]
                else:
                    self.token, self.refresh_token = None, None
                if not self.token:
                    self.token, self.refresh_token = self._get_token()
                    if self.token is None:
                        self.init_error = "登录失败：无法获取访问令牌，请检查网络连接或账号密码"
                    else:
                        config_manager.save_token_cache(env, username, self.token, self.refresh_token)
            else:
                self.token, self.refresh_token = self._get_token()
                if self.token is None:
                    self.init_error = "登录失败：无法获取访问令牌，请检查网络连接或账号密码"
        except Exception as e:
            self.init_error = f"初始化失败: {str(e)}"
            logger.exception("DeviceQuery初始化失败")

    def _build_auth_headers(self, token=None):
        return {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": token or self.token,
        }

    def _cache_device_identity(self, dev_id=None, sn=None, is_siot=None):
        dev_id = str(dev_id or "").strip()
        sn = str(sn or "").strip()

        if dev_id and sn:
            self._dev_id_by_sn[sn] = dev_id
            self._sn_by_dev_id[dev_id] = sn
        elif dev_id and dev_id in self._sn_by_dev_id:
            sn = self._sn_by_dev_id[dev_id]
        elif sn and sn in self._dev_id_by_sn:
            dev_id = self._dev_id_by_sn[sn]

        if is_siot is not None and dev_id:
            self._siot_platform_cache[dev_id] = bool(is_siot)

    def _cache_device_records(self, records):
        for record in records or []:
            self._cache_device_identity(
                dev_id=record.get('devId') or record.get('id') or record.get('deviceId'),
                sn=record.get('devSN') or record.get('deviceSn') or record.get('sn'),
            )

    def _get_captcha(self):
        """获取验证码"""
        url = f'https://{self.host}/api/seetong-auth/oauth/captcha'
        try:
            r = self.session.get(url, verify=False, timeout=10)
            r.raise_for_status()
            res = r.json()
            
            img_data = base64.b64decode(res['image'].split('base64,')[-1])
            ocr = ddddocr.DdddOcr(show_ad=False)
            captcha_code = ocr.classification(img_data)
            logger.debug(f"验证码识别成功: {captcha_code}")
            return res['key'], captcha_code
        except Exception as e:
            logger.error(f"获取验证码失败: {e}")
            raise

    def _get_token(self, retry=3):
        """获取登录token，失败时抛出异常"""
        last_error = None
        for i in range(retry):
            try:
                captcha_key, captcha_code = self._get_captcha()
                url = f'https://{self.host}/api/seetong-auth/oauth/token'
                headers = {
                    "Content-Type": "application/json",
                    "Captcha-Code": captcha_code,
                    "Captcha-Key": captcha_key,
                    "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                    "Tenant-Id": "000000",
                }
                params = {
                    "tenantId": "000000",
                    "username": self.username,
                    "password": hashlib.md5(self.password.encode()).hexdigest(),
                    "grant_type": "captcha",
                    "scope": "all",
                    "type": "account",
                }
                r = self.session.post(url, params=params, headers=headers, verify=False, timeout=10)
                r.raise_for_status()
                res = r.json()
                if res.get('access_token'):
                    logger.info(f"登录成功: {self.username}@{self.env}")
                    return res['access_token'], res['refresh_token']
                else:
                    last_error = f"服务器返回错误: {res.get('error_description', '未知错误')}"
                    logger.warning(f"登录失败（尝试{i+1}/{retry}）: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"登录尝试 {i+1}/{retry} 失败: {last_error}")
                if i < retry - 1:
                    time.sleep(2 ** i)  # 指数退避
        
        # 明确抛出异常而不是返回 None
        error_msg = f"登录失败（重试{retry}次）: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _request(self, api_path, params, retry=3):
        """发送 API 请求，带重试机制"""
        url = f'https://{self.host}{api_path}'
        
        logger.debug(f"API请求: {api_path}, 参数: {params}")
        
        last_error = None
        for attempt in range(retry):
            try:
                headers = self._build_auth_headers()
                r = self.session.get(url, params=params, headers=headers, verify=False, timeout=10)
                
                if r.status_code == 401:
                    # Token 过期，使用锁避免并发重复刷新
                    with self._token_lock:
                        logger.info(f"Token过期，重新登录: {self.username}@{self.env}")
                        self.token, self.refresh_token = self._get_token()
                        config_manager.save_token_cache(self.env, self.username, self.token, self.refresh_token)
                    # 刷新成功后 continue，下一次循环用新 token 重试
                    continue
                
                r.raise_for_status()
                logger.debug(f"API请求成功: {api_path}, 状态码: {r.status_code}")
                return r.json()
            
            except Exception as e:
                last_error = str(e)
                logger.warning(f"API请求尝试 {attempt+1}/{retry} 失败: {api_path}, {last_error}")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)
        
        error_msg = f"API 请求失败（重试{retry}次）: {api_path}, {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _request_json(self, api_path, payload, retry=3):
        """发送 JSON POST 请求，带重试机制。"""
        url = f'https://{self.host}{api_path}'

        logger.debug(f"API请求: {api_path}, 数据: {payload}")

        last_error = None
        for attempt in range(retry):
            try:
                headers = self._build_auth_headers()
                r = self.session.post(url, json=payload, headers=headers, verify=False, timeout=10)

                if r.status_code == 401:
                    with self._token_lock:
                        logger.info(f"Token过期，重新登录: {self.username}@{self.env}")
                        self.token, self.refresh_token = self._get_token()
                        config_manager.save_token_cache(self.env, self.username, self.token, self.refresh_token)
                    continue

                r.raise_for_status()
                logger.debug(f"API请求成功: {api_path}, 状态码: {r.status_code}")
                return r.json()

            except Exception as e:
                last_error = str(e)
                logger.warning(f"API请求尝试 {attempt+1}/{retry} 失败: {api_path}, {last_error}")
                if attempt < retry - 1:
                    time.sleep(2 ** attempt)

        error_msg = f"API 请求失败（重试{retry}次）: {api_path}, {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def get_device_info(self, dev_sn=None, dev_id=None):
        params = {"current": "1", "size": "10", "descs": "devId"}
        if dev_sn:
            params['deviceSn'] = dev_sn
        if dev_id:
            params['devId'] = dev_id
        res = self._request('/api/seetong-device/device-basic-info/list', params)
        self._cache_device_records(res.get('data', {}).get('records', []) if res else [])
        return res

    def get_cloud_password(self, dev_id):
        params = {"deviceId": dev_id, "password": hashlib.md5(self.password.encode()).hexdigest()}
        res = self._request('/api/seetong-device/device-basic-info/get-cloud-password', params)
        return res.get('data')

    def get_device_online_detail(self, dev_id):
        params = {"id": dev_id}
        return self._request('/api/seetong-devonline/siot-media/dev/detail', params)

    def get_device_header(self, dev_sn):
        params = {"sn": dev_sn}
        return self._request('/api/seetong-siot-device/console/device/header', params)

    def get_device_detail(self, dev_id):
        params = {"devId": dev_id}
        res = self._request('/api/seetong-device/device-basic-info/detail', params)
        if res and res.get('data'):
            data = res.get('data') or {}
            self._cache_device_identity(
                dev_id=data.get('devId') or dev_id,
                sn=data.get('devSN') or data.get('deviceSn') or data.get('sn'),
            )
        return res

    def get_device_version(self, dev_id):
        res = self.get_device_detail(dev_id)
        if res and res.get('data'):
            return res['data'].get('fileVersion', '')
        return ''

    def get_device_running_status(self, dev_id):
        """获取设备运行状态详情。"""
        params = {"devId": dev_id}
        res = self._request('/api/seetong-device/device-running-status/running_info', params)
        if res and res.get('data'):
            return res.get('data') or {}
        return {}

    def get_device_last_heartbeat(self, dev_id):
        """获取设备最后心跳时间"""
        return self.get_device_running_status(dev_id).get('devLastLoginTM', '')

    def get_non_siot_online_status(self, dev_sn):
        """获取非 siot 设备的 P2P 在线状态（刷新接口）。"""
        params = {"sn": dev_sn}
        res = self._request('/api/seetong-device/device-running-status/online-status-info', params)
        if res and res.get('data'):
            return res.get('data', {}).get('onlineStatus')
        return None

    def check_siot_platform(self, dev_ids):
        """批量查询设备是否为 siot 平台设备。"""
        normalized_ids = [str(dev_id).strip() for dev_id in (dev_ids or []) if str(dev_id).strip()]
        if not normalized_ids:
            return {}

        res = self._request_json(
            '/api/seetong-siot-device/console/device/siot-platform/check',
            {"devIds": normalized_ids},
        )
        data = res.get('data') if res else {}

        if not isinstance(data, dict):
            return {}

        normalized = {}
        for raw_dev_id, is_siot in data.items():
            normalized[str(raw_dev_id)] = bool(is_siot)
            self._cache_device_identity(dev_id=raw_dev_id, is_siot=is_siot)
        return normalized

    def is_siot_platform_device(self, dev_id=None, sn=None):
        """判断设备是否为 siot 平台设备。"""
        resolved_dev_id = str(dev_id or "").strip()
        resolved_sn = str(sn or "").strip()

        if not resolved_dev_id and resolved_sn:
            resolved_dev_id = self._dev_id_by_sn.get(resolved_sn, '')
        if not resolved_sn and resolved_dev_id:
            resolved_sn = self._sn_by_dev_id.get(resolved_dev_id, '')

        if resolved_dev_id in self._siot_platform_cache:
            return self._siot_platform_cache[resolved_dev_id]

        if not resolved_dev_id and resolved_sn:
            info = self.get_device_info(dev_sn=resolved_sn)
            records = info.get('data', {}).get('records', []) if info else []
            if records:
                record = records[0]
                resolved_dev_id = str(record.get('devId') or record.get('id') or "").strip()
                resolved_sn = str(record.get('devSN') or record.get('deviceSn') or resolved_sn).strip()
                self._cache_device_identity(dev_id=resolved_dev_id, sn=resolved_sn)

        if not resolved_dev_id:
            return None

        try:
            mapping = self.check_siot_platform([resolved_dev_id])
        except Exception as e:
            logger.warning(f"查询设备 siot 平台标记失败 {resolved_dev_id}: {e}")
            return None
        if resolved_dev_id in mapping:
            self._cache_device_identity(dev_id=resolved_dev_id, sn=resolved_sn, is_siot=mapping[resolved_dev_id])
            return mapping[resolved_dev_id]
        return None

    def query_device_online_state(self, sn, dev_id=None):
        """查询设备在线状态，返回 True/False/None（None 表示查询失败或无法判定）。"""
        resolved_sn = str(sn or "").strip()
        resolved_dev_id = str(dev_id or "").strip()
        if not resolved_sn:
            return None

        if not resolved_dev_id and resolved_sn:
            resolved_dev_id = self._dev_id_by_sn.get(resolved_sn, '')

        is_siot = self.is_siot_platform_device(dev_id=resolved_dev_id, sn=resolved_sn)
        if not resolved_dev_id and resolved_sn:
            resolved_dev_id = self._dev_id_by_sn.get(resolved_sn, '')
        if is_siot is True:
            res = self.get_device_header(resolved_sn)
            data = res.get('data', {}) if res else {}
            normalized = _normalize_online_status_value(data.get('onlineStatus'), default=None)
            return normalized == 1 if normalized is not None else None

        if is_siot is False:
            normalized = _normalize_online_status_value(self.get_non_siot_online_status(resolved_sn), default=None)
            if normalized is not None:
                return normalized == 1

            if resolved_dev_id:
                running_data = self.get_device_running_status(resolved_dev_id)
                normalized = _normalize_online_status_value(running_data.get('devOnLine'), default=None)
                return normalized == 1 if normalized is not None else None
            return None

        normalized = _normalize_online_status_value(
            self.get_non_siot_online_status(resolved_sn) if resolved_sn else None,
            default=None,
        )
        if normalized is not None:
            return normalized == 1

        if resolved_dev_id:
            running_data = self.get_device_running_status(resolved_dev_id)
            normalized = _normalize_online_status_value(running_data.get('devOnLine'), default=None)
            if normalized is not None:
                return normalized == 1

        if resolved_sn:
            res = self.get_device_header(resolved_sn)
            data = res.get('data', {}) if res else {}
            normalized = _normalize_online_status_value(data.get('onlineStatus'), default=None)
            if normalized is not None:
                return normalized == 1

        return None

    def get_device_status_snapshot(self, dev_id=None, sn=None, is_siot=None):
        """统一返回设备页所需的在线状态和最后心跳时间。"""
        resolved_dev_id = str(dev_id or "").strip()
        resolved_sn = str(sn or "").strip()

        if not resolved_dev_id and resolved_sn:
            resolved_dev_id = self._dev_id_by_sn.get(resolved_sn, '')
        if not resolved_sn and resolved_dev_id:
            resolved_sn = self._sn_by_dev_id.get(resolved_dev_id, '')

        if is_siot is None:
            is_siot = self.is_siot_platform_device(dev_id=resolved_dev_id, sn=resolved_sn)
            if not resolved_dev_id and resolved_sn:
                resolved_dev_id = self._dev_id_by_sn.get(resolved_sn, '')
            if not resolved_sn and resolved_dev_id:
                resolved_sn = self._sn_by_dev_id.get(resolved_dev_id, '')

        running_data = self.get_device_running_status(resolved_dev_id) if resolved_dev_id else {}
        last_heartbeat = str(running_data.get('devLastLoginTM') or '')

        if is_siot is True:
            header_data = self.get_device_header(resolved_sn).get('data', {}) if resolved_sn else {}
            online_status = _normalize_online_status_value(header_data.get('onlineStatus'), default=-2)
        elif is_siot is False:
            online_status = _normalize_online_status_value(
                self.get_non_siot_online_status(resolved_sn) if resolved_sn else None,
                default=None,
            )
            if online_status is None:
                online_status = _normalize_online_status_value(running_data.get('devOnLine'), default=-2)
        else:
            online_status = _normalize_online_status_value(
                self.get_non_siot_online_status(resolved_sn) if resolved_sn else None,
                default=None,
            )
            if online_status is None:
                online_status = _normalize_online_status_value(running_data.get('devOnLine'), default=None)
            if online_status is None and resolved_sn:
                header_data = self.get_device_header(resolved_sn).get('data', {}) if resolved_sn else {}
                online_status = _normalize_online_status_value(header_data.get('onlineStatus'), default=None)
            if online_status is None:
                online_status = -2

        return {
            'is_siot': is_siot,
            'online': online_status,
            'last_heartbeat': last_heartbeat,
        }

    def get_device_bind_user(self, dev_id):
        """获取设备绑定用户信息"""
        params = {"deviceId": dev_id}
        return self._request('/api/seetong-member-device/device-bind-user/list', params)

    def get_user_by_account(self, account_type, account_value):
        """根据账号类型查询用户信息"""
        params = {
            account_type: account_value,
            "current": "1",
            "size": "10",
            "descs": "id",
        }
        return self._request('/api/seetong-client/client/member/list', params)

    def get_user_by_mobile(self, mobile):
        """根据手机号查询用户ID"""
        return self.get_user_by_account("mobile", mobile)

    def get_user_bind_devices(self, user_id):
        """根据用户ID查询绑定设备列表"""
        params = {"userId": user_id}
        return self._request('/api/seetong-member-device/user-bind-device/list', params)

    def get_device_name(self, dev_id):
        """获取设备名称"""
        res = self.get_device_bind_user(dev_id)
        if res and res.get('data'):
            bind_user_list = res['data'].get('bindUserList', [])
            if bind_user_list:
                return bind_user_list[0].get('deviceName', '')
        return ''

    def get_access_node(self, dev_sn=None, dev_id=None):
        if dev_sn and not dev_id:
            res = self.get_device_info(dev_sn=dev_sn)
            records = res.get('data', {}).get('records', [])
            dev_id = records[0]['devId'] if records else None
        if not dev_id:
            return None
        res = self.get_device_online_detail(dev_id)
        if not res or not res.get('data'):
            return None
        data = res['data']
        return {'serverId': data.get('serverId')}
    
    def send_reboot_command(self, dev_id, reboot_time, return_detail=False):
        """
        发送重启命令
        
        Args:
            dev_id: 设备ID
            reboot_time: 重启时间，"now" 或 "after_five_minute"
            return_detail: 是否返回详细结果
        
        Returns:
            bool | tuple[str, str]: 是否成功或详细结果
        """
        try:
            url = f'https://{self.host}/api/seetong-siot-device/console/device/operate/sendCommand'
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Seetong-Auth": self.token,
            }
            
            # 构建参数
            params_dict = {"reboot_time": reboot_time}
            params_json = json.dumps(params_dict)
            
            # 通过 dev_id 获取 SN
            device_info = self.get_device_info(dev_id=dev_id)
            records = device_info.get('data', {}).get('records', [])
            if not records:
                return ('failed', '未找到设备信息') if return_detail else False
            sn = records[0].get('devSN', '')
            if not sn:
                return ('failed', '设备SN为空') if return_detail else False
            
            data = {
                "moduleCode": "default",
                "code": "reboot",
                "params": params_json,
                "sn": sn,
                "sourceType": "1"
            }
            
            response = self.session.post(url, json=data, headers=headers, verify=False, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == 200 and result.get('success', False):
                return ('success', '重启命令已发送') if return_detail else True
            if result.get('code') == 20001:
                return ('offline', '设备不在线，操作失败') if return_detail else False
            msg = result.get('msg', '操作失败')
            return ('failed', msg) if return_detail else False
        except Exception as e:
            logger.error(f"发送重启命令失败: {e}")
            return ('failed', str(e)) if return_detail else False


def _resolve_auth_context(token_or_query, host='console.seetong.com'):
    """统一解析 DeviceQuery 或裸 token，避免 host/token 逻辑分叉。"""
    if isinstance(token_or_query, DeviceQuery):
        return token_or_query.token, token_or_query.host, token_or_query
    return token_or_query, host, None


def _build_auth_headers(token):
    return {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }


def _request_with_token(api_path, token, host='console.seetong.com', params=None, payload=None, method='get', retry=3):
    """在只有 token 的场景下直接发请求，不做自动登录刷新。"""
    session = session_manager.get_session(f'device_query_{method}_direct')
    url = f'https://{host}{api_path}'
    last_error = None

    for attempt in range(retry):
        try:
            headers = _build_auth_headers(token)
            if method.lower() == 'post':
                response = session.post(url, json=payload, headers=headers, verify=False, timeout=10)
            else:
                response = session.get(url, params=params, headers=headers, verify=False, timeout=10)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_error = str(e)
            logger.warning(f"API请求尝试 {attempt+1}/{retry} 失败: {api_path}, {last_error}")
            if attempt < retry - 1:
                time.sleep(2 ** attempt)

    raise Exception(f"API 请求失败（重试{retry}次）: {api_path}, {last_error}")


def _normalize_online_status_value(online_status, default=-2):
    """统一把在线状态归一化为 1/0/None 或指定默认值。"""
    if online_status is None or online_status == "":
        return default

    if isinstance(online_status, bool):
        return 1 if online_status else 0

    if isinstance(online_status, str):
        lowered = online_status.strip().lower()
        if lowered in {"true", "online", "在线"}:
            return 1
        if lowered in {"false", "offline", "离线"}:
            return 0

    try:
        normalized = int(online_status)
    except (TypeError, ValueError):
        return default

    if normalized in (1, 0, -1, -2):
        return normalized
    return default


def _is_online_status(online_status):
    """统一解析在线状态字段，兼容 int / str / bool。"""
    return _normalize_online_status_value(online_status, default=0) == 1


def wake_device(dev_id, sn, token_or_query, host='console.seetong.com', times=3):
    """唤醒设备"""
    token, host, _ = _resolve_auth_context(token_or_query, host)
    session = session_manager.get_session('wake_device')
    url = f'https://{host}/api/seetong-device-media-command/siot-media/command/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }
    for i in range(times):
        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': f'wake-{i+1}'}
        try:
            session.post(url, data=json.dumps(data), headers=headers, verify=False, timeout=5)
        except Exception as e:
            logger.warning(f"唤醒请求失败 (尝试 {i+1}/{times}): {e}")
        time.sleep(1)


def query_device_online_state(sn, token_or_query, host='console.seetong.com', dev_id=None):
    """查询设备在线状态，返回 True/False/None（None 表示查询失败）。"""
    try:
        token, host, query = _resolve_auth_context(token_or_query, host)

        if query is not None:
            return query.query_device_online_state(sn, dev_id=dev_id)

        resolved_sn = str(sn or "").strip()
        resolved_dev_id = str(dev_id or "").strip()
        if not resolved_sn:
            return None

        if not resolved_dev_id:
            info = _request_with_token(
                '/api/seetong-device/device-basic-info/list',
                token,
                host,
                params={
                    "current": "1",
                    "size": "10",
                    "descs": "devId",
                    "deviceSn": resolved_sn,
                },
            )
            records = info.get('data', {}).get('records', []) if info else []
            if records:
                record = records[0]
                resolved_dev_id = str(record.get('devId') or record.get('id') or '').strip()
                resolved_sn = str(record.get('devSN') or record.get('deviceSn') or resolved_sn).strip()

        if not resolved_dev_id:
            return None

        siot_check = _request_with_token(
            '/api/seetong-siot-device/console/device/siot-platform/check',
            token,
            host,
            payload={"devIds": [resolved_dev_id]},
            method='post',
        )
        is_siot = bool((siot_check.get('data') or {}).get(resolved_dev_id))

        if is_siot:
            res = _request_with_token(
                '/api/seetong-siot-device/console/device/header',
                token,
                host,
                params={"sn": resolved_sn},
            )
            data = res.get('data', {}) if res else {}
            normalized = _normalize_online_status_value(data.get('onlineStatus'), default=None)
            return normalized == 1 if normalized is not None else None

        res = _request_with_token(
            '/api/seetong-device/device-running-status/online-status-info',
            token,
            host,
            params={"sn": resolved_sn},
        )
        data = res.get('data', {}) if res else {}
        normalized = _normalize_online_status_value(data.get('onlineStatus'), default=None)
        if normalized is not None:
            return normalized == 1

        running_info = _request_with_token(
            '/api/seetong-device/device-running-status/running_info',
            token,
            host,
            params={"devId": resolved_dev_id},
        )
        running_data = running_info.get('data', {}) if running_info else {}
        normalized = _normalize_online_status_value(running_data.get('devOnLine'), default=None)
        return normalized == 1 if normalized is not None else None
    except Exception as e:
        logger.warning(f"查询在线状态失败: {e}")
        return None


def check_device_online(sn, token_or_query, host='console.seetong.com', dev_id=None):
    """查询设备在线状态。

    优先复用 DeviceQuery，确保与主查询页使用同一套 host、token 刷新和接口逻辑。
    """
    return query_device_online_state(sn, token_or_query, host, dev_id=dev_id) is True


def ensure_device_online_for_upgrade(dev_id, sn, token_or_query, host='console.seetong.com', max_wake_times=3):
    """升级前确保设备在线。

    Returns:
        tuple[bool, str, str]:
            - 是否允许继续下发升级
            - 预处理结果: online/status_unknown/woken/wake_failed
            - 结果描述
    """
    token, host, query = _resolve_auth_context(token_or_query, host)
    auth_context = query if query is not None else token

    online_state = query_device_online_state(sn, auth_context, host, dev_id=dev_id)
    if online_state is True:
        return True, 'online', '设备在线'
    if online_state is None:
        logger.warning(f"设备 {sn} 在线状态查询失败，继续尝试直接下发升级")
        return True, 'status_unknown', '在线状态查询失败，继续尝试直接下发升级'

    resolved_dev_id = dev_id
    if not resolved_dev_id and query is not None:
        try:
            res = query.get_device_info(dev_sn=sn)
            records = res.get('data', {}).get('records', []) if res else []
            if records:
                resolved_dev_id = records[0].get('devId') or records[0].get('id') or ''
        except Exception as e:
            logger.warning(f"查询设备ID失败 {sn}: {e}")

    if not resolved_dev_id:
        logger.warning(f"设备 {sn} 离线且缺少 dev_id，无法执行唤醒")
        return False, 'wake_failed', '设备离线，且缺少 dev_id，无法唤醒'

    if wake_device_smart(
        resolved_dev_id,
        sn,
        auth_context,
        host,
        max_times=max_wake_times,
    ):
        return True, 'woken', '设备唤醒成功'

    return False, 'wake_failed', '设备离线，唤醒失败'


def wake_device_smart(dev_id, sn, token_or_query, host='console.seetong.com', max_times=3):
    """智能唤醒设备：唤醒后查询状态，在线则停止，离线则继续唤醒"""
    token, host, query = _resolve_auth_context(token_or_query, host)
    session = session_manager.get_session('wake_device_smart')
    url = f'https://{host}/api/seetong-device-media-command/siot-media/command/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }
    
    for i in range(max_times):
        # 发送唤醒命令
        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': f'wake-{i+1}'}
        try:
            session.post(url, data=json.dumps(data), headers=headers, verify=False, timeout=5)
        except Exception as e:
            logger.warning(f"唤醒请求失败 (尝试 {i+1}/{max_times}): {e}")
        
        # 等待 2 秒后查询在线状态
        time.sleep(2)
        if check_device_online(sn, query if query is not None else token, host, dev_id=dev_id):
            logger.info(f"设备 {sn} 唤醒成功")
            return True  # 设备已在线，停止唤醒
        
        # 如果不是最后一次，再等 1 秒后继续
        if i < max_times - 1:
            time.sleep(1)
    
    logger.warning(f"设备 {sn} 唤醒失败（尝试{max_times}次）")
    return False  # 多次唤醒后仍离线
