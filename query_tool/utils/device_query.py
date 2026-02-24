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
        
        # 获取Session
        self.session = session_manager.get_session(f'device_query_{env}_{username}')
        
        try:
            if use_cache:
                self.token, self.refresh_token = config_manager.load_token_cache(env, username)
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
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": self.token,
        }
        
        logger.debug(f"API请求: {api_path}, 参数: {params}")
        
        last_error = None
        for attempt in range(retry):
            try:
                r = self.session.get(url, params=params, headers=headers, verify=False, timeout=10)
                
                if r.status_code == 401:
                    # Token 过期，重新获取（使用锁避免并发刷新）
                    with self._token_lock:
                        # 双重检查，可能其他线程已经刷新了
                        if r.status_code == 401:
                            try:
                                logger.info(f"Token过期，刷新Token: {self.username}@{self.env}")
                                self.token, self.refresh_token = self._get_token()
                                config_manager.save_token_cache(self.env, self.username, self.token, self.refresh_token)
                                headers["Seetong-Auth"] = self.token
                                r = self.session.get(url, params=params, headers=headers, verify=False, timeout=10)
                            except Exception as e:
                                raise Exception(f"Token 刷新失败: {str(e)}")
                
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
        return self._request('/api/seetong-device/device-basic-info/list', params)

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
        return self._request('/api/seetong-device/device-basic-info/detail', params)

    def get_device_version(self, dev_id):
        res = self.get_device_detail(dev_id)
        if res and res.get('data'):
            return res['data'].get('fileVersion', '')
        return ''

    def get_device_last_heartbeat(self, dev_id):
        """获取设备最后心跳时间"""
        params = {"devId": dev_id}
        res = self._request('/api/seetong-device/device-running-status/running_info', params)
        if res and res.get('data'):
            return res['data'].get('devLastLoginTM', '')
        return ''

    def get_device_bind_user(self, dev_id):
        """获取设备绑定用户信息"""
        params = {"deviceId": dev_id}
        return self._request('/api/seetong-member-device/device-bind-user/list', params)

    def get_user_by_mobile(self, mobile):
        """根据手机号查询用户ID"""
        params = {"mobile": mobile, "current": "1", "size": "10", "descs": "id"}
        return self._request('/api/seetong-client/client/member/list', params)

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
    
    def send_reboot_command(self, dev_id, reboot_time):
        """
        发送重启命令
        
        Args:
            dev_id: 设备ID
            reboot_time: 重启时间，"now" 或 "after_five_minute"
        
        Returns:
            bool: 是否成功
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
                return False
            sn = records[0].get('devSN', '')
            if not sn:
                return False
            
            data = {
                "code": "reboot",
                "params": params_json,
                "sn": sn,
                "sourceType": "1"
            }
            
            response = self.session.post(url, json=data, headers=headers, verify=False, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            return result.get('code') == 200 and result.get('success', False)
        except Exception as e:
            logger.error(f"发送重启命令失败: {e}")
            return False


def wake_device(dev_id, sn, token, host='console.seetong.com', times=3):
    """唤醒设备"""
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


def check_device_online(sn, token, host='console.seetong.com'):
    """查询设备在线状态"""
    try:
        session = session_manager.get_session('check_online')
        url = f'https://{host}/api/seetong-siot-device/console/device/header'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": token,
        }
        params = {"sn": sn}
        r = session.get(url, params=params, headers=headers, verify=False, timeout=5)
        r.raise_for_status()
        res = r.json()
        data = res.get('data', {})
        online_status = data.get('onlineStatus', 0)
        return online_status == 1
    except Exception as e:
        logger.warning(f"查询在线状态失败: {e}")
        return False


def wake_device_smart(dev_id, sn, token, host='console.seetong.com', max_times=3):
    """智能唤醒设备：唤醒后查询状态，在线则停止，离线则继续唤醒"""
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
        if check_device_online(sn, token, host):
            logger.info(f"设备 {sn} 唤醒成功")
            return True  # 设备已在线，停止唤醒
        
        # 如果不是最后一次，再等 1 秒后继续
        if i < max_times - 1:
            time.sleep(1)
    
    logger.warning(f"设备 {sn} 唤醒失败（尝试{max_times}次）")
    return False  # 多次唤醒后仍离线
