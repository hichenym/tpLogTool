"""
设备查询API封装
提供设备信息查询、唤醒等功能
"""
import time
import hashlib
import requests
import base64
import json
import ddddocr
from .config import config_manager

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()


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

    def _get_captcha(self):
        url = f'https://{self.host}/api/seetong-auth/oauth/captcha'
        r = requests.get(url, verify=False)
        res = r.json()
        
        img_data = base64.b64decode(res['image'].split('base64,')[-1])
        ocr = ddddocr.DdddOcr(show_ad=False)
        return res['key'], ocr.classification(img_data)

    def _get_token(self, retry=3):
        """获取登录token，失败时返回 None"""
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
                r = requests.post(url, params=params, headers=headers, verify=False)
                res = r.json()
                if res.get('access_token'):
                    return res['access_token'], res['refresh_token']
            except Exception as e:
                if i == retry - 1:  # 最后一次重试失败
                    print(f"登录失败: {e}")
            time.sleep(1)
        return None, None  # 登录失败返回 None

    def _request(self, api_path, params):
        url = f'https://{self.host}{api_path}'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": self.token,
        }
        r = requests.get(url, params=params, headers=headers, verify=False)
        if r.status_code == 401:
            self.token, self.refresh_token = self._get_token()
            config_manager.save_token_cache(self.env, self.username, self.token, self.refresh_token)
            headers["Seetong-Auth"] = self.token
            r = requests.get(url, params=params, headers=headers, verify=False)
        return r.json()

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


def wake_device(dev_id, sn, token, host='console.seetong.com', times=3):
    """唤醒设备"""
    url = f'https://{host}/api/seetong-device-media-command/siot-media/command/send'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }
    for i in range(times):
        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': f'wake-{i+1}'}
        try:
            r = requests.post(url, data=json.dumps(data), headers=headers, verify=False, timeout=5)
        except (requests.RequestException, Exception) as e:
            print(f"唤醒请求失败: {e}")
            pass
        time.sleep(1)


def check_device_online(sn, token, host='console.seetong.com'):
    """查询设备在线状态"""
    try:
        url = f'https://{host}/api/seetong-siot-device/console/device/header'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": token,
        }
        params = {"sn": sn}
        r = requests.get(url, params=params, headers=headers, verify=False, timeout=5)
        res = r.json()
        data = res.get('data', {})
        online_status = data.get('onlineStatus', 0)
        return online_status == 1
    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"查询在线状态失败: {e}")
        return False


def wake_device_smart(dev_id, sn, token, host='console.seetong.com', max_times=3):
    """智能唤醒设备：唤醒后查询状态，在线则停止，离线则继续唤醒"""
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
            requests.post(url, data=json.dumps(data), headers=headers, verify=False, timeout=5)
        except (requests.RequestException, Exception) as e:
            print(f"唤醒请求失败: {e}")
            pass
        
        # 等待 2 秒后查询在线状态
        time.sleep(2)
        if check_device_online(sn, token, host):
            return True  # 设备已在线，停止唤醒
        
        # 如果不是最后一次，再等 1 秒后继续
        if i < max_times - 1:
            time.sleep(1)
    
    return False  # 多次唤醒后仍离线
