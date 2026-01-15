"""
设备信息查询工具 - 精简版
支持根据SN查询云ID，根据云ID查询SN
优化：延迟加载ddddocr，支持token缓存
"""
import os
import sys
import json
import time
import hashlib
import requests

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()

# Token缓存文件路径
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.token_cache.json')


class DeviceQuery:
    def __init__(self, env, username, password, use_cache=True):
        """
        :param env: pro-生产环境 / test-测试环境
        :param username: 用户名
        :param password: 密码
        :param use_cache: 是否使用token缓存
        """
        self.username = username
        self.password = password
        self.host = 'console.seetong.com' if env == 'pro' else 'console-test.seetong.com'
        self.env = env
        
        # 尝试从缓存加载token
        if use_cache and self._load_token_cache():
            print('从缓存加载token成功')
        else:
            self.token, self.refresh_token = self._get_token()
            if use_cache:
                self._save_token_cache()

    def _load_token_cache(self):
        """从缓存文件加载token"""
        try:
            if os.path.exists(TOKEN_CACHE_FILE):
                with open(TOKEN_CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                # 检查是否同一环境和用户
                if cache.get('env') == self.env and cache.get('username') == self.username:
                    # 检查是否过期（假设2小时有效期）
                    if time.time() - cache.get('timestamp', 0) < 7200:
                        self.token = cache['token']
                        self.refresh_token = cache['refresh_token']
                        return True
        except Exception:
            pass
        return False

    def _save_token_cache(self):
        """保存token到缓存文件"""
        try:
            cache = {
                'env': self.env,
                'username': self.username,
                'token': self.token,
                'refresh_token': self.refresh_token,
                'timestamp': time.time()
            }
            with open(TOKEN_CACHE_FILE, 'w') as f:
                json.dump(cache, f)
        except Exception:
            pass

    def _get_captcha(self):
        """获取并识别验证码"""
        import ddddocr  # 延迟导入
        import base64
        
        url = f'https://{self.host}/api/seetong-auth/oauth/captcha'
        r = requests.get(url, verify=False)
        res = r.json()
        
        img_data = base64.b64decode(res['image'].split('base64,')[-1])
        ocr = ddddocr.DdddOcr(show_ad=False)
        return res['key'], ocr.classification(img_data)

    def _get_token(self, retry=3):
        """获取登录token"""
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
                    print(f'第{i+1}次登录成功')
                    return res['access_token'], res['refresh_token']
            except Exception as e:
                print(f'第{i+1}次登录失败: {e}')
            time.sleep(1)
        print('登录失败，退出')
        sys.exit(1)

    def _request(self, api_path, params):
        """通用请求方法，自动处理token刷新"""
        url = f'https://{self.host}{api_path}'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": self.token,
        }
        r = requests.get(url, params=params, headers=headers, verify=False)
        if r.status_code == 401:
            print('token过期，重新获取')
            self.token, self.refresh_token = self._get_token()
            self._save_token_cache()
            headers["Seetong-Auth"] = self.token
            r = requests.get(url, params=params, headers=headers, verify=False)
        return r.json()

    def get_device_info(self, dev_sn=None, dev_id=None):
        """查询设备基础信息"""
        params = {"current": "1", "size": "10", "descs": "devId"}
        if dev_sn:
            params['deviceSn'] = dev_sn
        if dev_id:
            params['devId'] = dev_id
        return self._request('/api/seetong-device/device-basic-info/list', params)

    def sn_to_id(self, dev_sn):
        """根据SN查询云ID"""
        res = self.get_device_info(dev_sn=dev_sn)
        records = res.get('data', {}).get('records', [])
        return records[0]['devId'] if records else None

    def id_to_sn(self, dev_id):
        """根据云ID查询SN"""
        res = self.get_device_info(dev_id=dev_id)
        records = res.get('data', {}).get('records', [])
        return records[0]['devSN'] if records else None

    def get_cloud_password(self, dev_id):
        """获取设备云密码"""
        params = {"deviceId": dev_id, "password": hashlib.md5(self.password.encode()).hexdigest()}
        res = self._request('/api/seetong-device/device-basic-info/get-cloud-password', params)
        return res.get('data')

    def get_device_online_detail(self, dev_id):
        """
        查询设备在线详情（包含接入节点信息）
        :param dev_id: 设备云ID
        :return: 设备在线详情
        """
        params = {"id": dev_id}
        return self._request('/api/seetong-devonline/siot-media/dev/detail', params)

    def get_device_header(self, dev_sn):
        """
        查询设备头部信息（包含在线状态）
        :param dev_sn: 设备SN
        :return: 设备头部信息
        """
        params = {"sn": dev_sn}
        return self._request('/api/seetong-siot-device/console/device/header', params)

    def get_device_detail(self, dev_id):
        """
        查询设备详细信息（包含版本号）
        :param dev_id: 设备云ID
        :return: 设备详细信息
        """
        params = {"devId": dev_id}
        return self._request('/api/seetong-device/device-basic-info/detail', params)

    def get_device_version(self, dev_id):
        """
        获取设备版本号
        :param dev_id: 设备云ID
        :return: 版本号字符串
        """
        res = self.get_device_detail(dev_id)
        if res and res.get('data'):
            return res['data'].get('fileVersion', '')
        return ''

    def get_access_node(self, dev_sn=None, dev_id=None):
        """
        查询设备接入节点
        :param dev_sn: 设备SN（二选一）
        :param dev_id: 设备云ID（二选一）
        :return: 接入节点信息字典
        """
        if dev_sn and not dev_id:
            dev_id = self.sn_to_id(dev_sn)
        if not dev_id:
            return None
        res = self.get_device_online_detail(dev_id)
        if not res or not res.get('data'):
            return None
        data = res['data']
        return {
            'sn': data.get('sn'),
            'serverId': data.get('serverId'),      # 接入节点ID
            'clusterId': data.get('clusterId'),    # 集群ID
            'host': data.get('host'),              # 接入IP
            'port': data.get('port'),              # 接入端口
            'onlineStatus': data.get('onlineStatus'),      # 在线状态
            'onlineStatus4g': data.get('onlineStatus4g'),  # 4G在线状态
            'netType': data.get('netType'),        # 网络类型
            'accessTime': data.get('accessTime'),  # 接入时间
        }

    def print_online_detail(self, dev_sn=None, dev_id=None):
        """打印设备在线详情"""
        if dev_sn and not dev_id:
            dev_id = self.sn_to_id(dev_sn)
        res = self.get_device_online_detail(dev_id)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return res

    def batch_query_by_sn(self, sn_list):
        """批量根据SN查询设备信息"""
        results = []
        for sn in sn_list:
            try:
                dev_id = self.sn_to_id(sn)
                if dev_id:
                    password = self.get_cloud_password(dev_id)
                    result = {'sn': sn, 'id': dev_id, 'password': password}
                    results.append(result)
                    print(f"{sn},{dev_id},{password}")
                else:
                    print(f"{sn},未找到")
            except Exception as e:
                print(f"{sn},查询失败: {e}")
        return results

    def batch_query_by_id(self, id_list):
        """批量根据云ID查询设备信息"""
        results = []
        for dev_id in id_list:
            try:
                sn = self.id_to_sn(dev_id)
                if sn:
                    password = self.get_cloud_password(dev_id)
                    result = {'sn': sn, 'id': dev_id, 'password': password}
                    results.append(result)
                    print(f"{sn},{dev_id},{password}")
                else:
                    print(f"{dev_id},未找到")
            except Exception as e:
                print(f"{dev_id},查询失败: {e}")
        return results


if __name__ == '__main__':
    # 使用示例
    app = DeviceQuery('pro', 'yinjia', 'Yjtest123456.')
    
    # 根据SN查云ID
    # dev_id = app.sn_to_id("0C5C94C4A8923C36")
    # print(f"云ID: {dev_id}")
    
    # 根据云ID查SN
    # sn = app.id_to_sn(36240360)
    # print(f"SN: {sn}")
    
    # 批量查询
    # app.batch_query_by_sn(["0C5C94C4A8923C36", "0C2D4257A4963A46"])
    # app.batch_query_by_id([39850964, 39851171, 39851465])
    
    # 查询设备接入节点
    # node = app.get_access_node(dev_id=39851465)
    # print(f"接入节点: {node}")
    
    # 打印设备在线详情
    # app.print_online_detail(dev_id=39851465)
