"""
设备日志下载工具 - 精简版
优化：token缓存、减少唤醒次数、修复多进程错误
"""
import os
import sys
import time
import json
import platform
import hashlib
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from ctypes import *

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()

# 全局变量
func_lib = None
cloud_test = {}
log_name = ""
current_device = ""  # 当前处理的设备标识
thread_local = threading.local()  # 线程本地存储

# 回调函数类型
callback_type = CFUNCTYPE(c_int, c_uint, POINTER(c_char), c_uint, POINTER(c_void_p), c_uint)
log_callback_type = CFUNCTYPE(c_int, c_uint, c_char_p)

# Token缓存（进程间共享）
TOKEN_CACHE = {'token': None, 'refresh_token': None, 'timestamp': 0}


def get_token(username, password, host='console.seetong.com'):
    """获取token，带缓存"""
    global TOKEN_CACHE
    
    # 检查缓存是否有效（2小时）
    if TOKEN_CACHE['token'] and time.time() - TOKEN_CACHE['timestamp'] < 7200:
        return TOKEN_CACHE['token']
    
    # 延迟导入ddddocr
    import ddddocr
    import base64
    
    for i in range(3):
        try:
            # 获取验证码
            url = f'https://{host}/api/seetong-auth/oauth/captcha'
            r = requests.get(url, verify=False)
            res = r.json()
            img_data = base64.b64decode(res['image'].split('base64,')[-1])
            ocr = ddddocr.DdddOcr(show_ad=False)
            captcha_code = ocr.classification(img_data)
            
            # 登录获取token
            url = f'https://{host}/api/seetong-auth/oauth/token'
            headers = {
                "Content-Type": "application/json",
                "Captcha-Code": captcha_code,
                "Captcha-Key": res['key'],
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Tenant-Id": "000000",
            }
            params = {
                "tenantId": "000000",
                "username": username,
                "password": hashlib.md5(password.encode()).hexdigest(),
                "grant_type": "captcha",
                "scope": "all",
                "type": "account",
            }
            r = requests.post(url, params=params, headers=headers, verify=False)
            res = r.json()
            if res.get('access_token'):
                TOKEN_CACHE['token'] = res['access_token']
                TOKEN_CACHE['refresh_token'] = res['refresh_token']
                TOKEN_CACHE['timestamp'] = time.time()
                print(f'第{i+1}次登录成功')
                return TOKEN_CACHE['token']
        except Exception as e:
            print(f'第{i+1}次登录失败: {e}')
        time.sleep(1)
    return None


def check_device_online(sn, token, host='console.seetong.com'):
    """通过接口查询设备是否在线"""
    url = f'https://{host}/api/seetong-siot-device/console/device/header'
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
        "Seetong-Auth": token,
    }
    params = {"sn": sn}
    try:
        r = requests.get(url, params=params, headers=headers, verify=False)
        res = r.json()
        log_print(f'查询在线状态返回: {res}')
        data = res.get('data', {})
        online_status = data.get('onlineStatus', 0)
        log_print(f'onlineStatus={online_status}')
        return online_status == 1
    except Exception as e:
        log_print(f'查询在线状态失败: {e}')
        return False


def wake_device(dev_id, name, token, host='console.seetong.com', times=3):
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
            r = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            log_print(f'唤醒第{i+1}次: {r.json().get("msg", "ok")}')
        except Exception as e:
            log_print(f'唤醒失败: {e}')
        time.sleep(1)


def log_print(msg):
    """带设备标识的日志输出（线程安全）"""
    device_id = getattr(thread_local, 'current_device', 'Unknown')
    print(f'[{device_id}] {msg}')


def python_callback(nMsgType, pData, nDataLen, pExtData, nExtDataLen):
    """回调函数处理设备返回数据（线程安全）"""
    # 获取当前线程的数据
    if not hasattr(thread_local, 'cloud_test'):
        thread_local.cloud_test = {}
    if not hasattr(thread_local, 'log_name'):
        thread_local.log_name = ""
    
    if nMsgType == 8263:
        log_print("登录主服务器成功")
    elif nMsgType == 8223:
        log_print("登录P2P服务器成功，等待连接...")
    elif nMsgType == 8202:
        thread_local.cloud_test[nMsgType] = True
        log_print("P2P连接成功")
    elif nMsgType == 8205:
        thread_local.cloud_test['error'] = '密码错误'
        log_print("密码错误")
    elif nMsgType == 8201:
        error_msg = ""
        if pData:
            try:
                error_msg = string_at(pData, nDataLen).decode('utf-8', errors='ignore')
            except:
                pass
        thread_local.cloud_test['error'] = f'P2P连接失败: {error_msg}'
        log_print(f"P2P连接失败: {error_msg}")
    elif nMsgType == 8207:
        thread_local.cloud_test['error'] = '连接超时'
        log_print("连接超时")
    elif nMsgType == 8238 and pData:
        data_bytes = string_at(pData, nDataLen)
        if b'Msg_type="SYSTEM_LOG_DATA"' in data_bytes:
            # 跳过前4个\0
            null_count = 0
            offset = nDataLen
            for i in range(nDataLen):
                if data_bytes[i] == 0:
                    null_count += 1
                    if null_count == 4:
                        offset = i + 1
                        break
            
            if nDataLen > offset:
                # 还有数据，继续写入
                with open(thread_local.log_name, "ab") as f:
                    f.write(data_bytes[offset:])
            elif nDataLen == offset:
                log_print("日志下载完成")
                thread_local.cloud_test[8238] = True
    return 0


def python_log_callback(uLevel, lpszOut):
    """日志回调（空实现）"""
    return 0


def init_func_lib():
    """初始化DLL库"""
    global func_lib
    dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Funclib.dll')
    os.add_dll_directory(os.path.dirname(dll_path))
    
    if platform.system().lower() == 'windows':
        func_lib = CDLL(dll_path, winmode=0)
    else:
        func_lib = cdll.LoadLibrary(dll_path)
    
    # 设置回调
    callback_instance = callback_type(python_callback)
    log_callback_instance = log_callback_type(python_log_callback)
    func_lib.FC_SetMsgRspCallBack(callback_instance)
    func_lib.FC_SetfcLogCallBack(log_callback_instance)
    func_lib.FC_init()
    
    return func_lib, callback_instance, log_callback_instance


def download_log(yun_id, pwd, name, sn, timeout=60):
    """下载单个设备日志（线程安全）"""
    # 初始化线程本地数据
    if not hasattr(thread_local, 'cloud_test'):
        thread_local.cloud_test = {}
    if not hasattr(thread_local, 'log_name'):
        thread_local.log_name = ""
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '远程日志')
    os.makedirs(log_dir, exist_ok=True)
    
    thread_local.log_name = os.path.join(log_dir, f'{name}_{sn}_{yun_id}.txt')
    thread_local.cloud_test.clear()
    
    # P2P登录（先不创建文件）
    log_print(f"开始P2P连接... 用户名:admin 密码:{pwd}")
    
    # 尝试登录
    login_result = func_lib.FC_Login("admin".encode('utf-8'), pwd.encode('utf-8'), str(yun_id).encode('utf-8'), 80, "", "", "")
    log_print(f"FC_Login返回值: {login_result}")
    
    # 等待连接成功，增加超时时间
    log_print("等待P2P连接...")
    for i in range(timeout):
        time.sleep(1)
        if 8202 in thread_local.cloud_test:
            log_print("P2P连接成功，开始下载日志")
            break
        if i % 10 == 9:  # 每10秒输出一次等待状态
            log_print(f"等待P2P连接中... ({i+1}/{timeout}秒)")
    
    if 8202 not in thread_local.cloud_test:
        error = thread_local.cloud_test.get('error', '未知原因（未收到任何响应）')
        log_print(f'P2P连接失败: {error}')
        log_print(f'cloud_test内容: {thread_local.cloud_test}')
        func_lib.FC_Logout()
        return False
    
    # 连接成功后才创建日志文件
    with open(thread_local.log_name, 'w') as f:
        pass
    
    # 发送获取日志命令
    log_print("发送日志下载命令...")
    cmd = b"<cmd>GetSystemCfg /tmp/sd_room/IPC_Log/Tps_RecordLogNew.log</cmd>"
    cmd_result = func_lib.FC_RemoteDiagnose(str(yun_id).encode(), 1, cmd, -1)
    log_print(f"FC_RemoteDiagnose返回值: {cmd_result}")
    
    # 等待日志下载完成（检测文件大小是否稳定）
    last_size = 0
    stable_count = 0
    for i in range(120):  # 最多等待2分钟
        time.sleep(1)
        if 8238 in thread_local.cloud_test:
            log_print("下载成功")
            func_lib.FC_Logout()
            return True
        
        # 检查文件大小是否稳定（连续3秒不变则认为下载完成）
        try:
            current_size = os.path.getsize(thread_local.log_name)
            if current_size > 0 and current_size == last_size:
                stable_count += 1
                if stable_count >= 3:
                    log_print(f"下载成功（{current_size}字节）")
                    func_lib.FC_Logout()
                    return True
            else:
                stable_count = 0
            last_size = current_size
            
            # 每30秒输出一次下载状态
            if i % 30 == 29 and current_size > 0:
                log_print(f"下载中... 当前文件大小: {current_size}字节")
        except:
            pass
    
    # 超时检查文件是否有内容
    try:
        file_size = os.path.getsize(thread_local.log_name)
        if file_size > 0:
            log_print(f"下载成功（{file_size}字节，超时）")
            func_lib.FC_Logout()
            return True
        else:
            os.remove(thread_local.log_name)
    except:
        pass
    
    log_print("下载超时或文件为空")
    func_lib.FC_Logout()
    return False


def wake_and_wait_online(yun_id, sn, name, token, timeout=60):
    """唤醒设备并等待在线"""
    start_time = time.time()
    wake_count = 0
    
    while time.time() - start_time < timeout:
        wake_count += 1
        log_print(f'第{wake_count}次唤醒')
        
        # 单次唤醒
        url = f'https://console.seetong.com/api/seetong-device-media-command/siot-media/command/send'
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": token,
        }
        data = {'devId': yun_id, 'type': 'LOW_POWER_WAKE', 'msg': f'wake-{wake_count}'}
        try:
            r = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
            log_print(f'唤醒结果: {r.json().get("msg", "ok")}')
        except Exception as e:
            log_print(f'唤醒失败: {e}')
        
        # 等待3秒后查询在线状态
        time.sleep(3)
        if check_device_online(sn, token):
            log_print(f'设备已在线（用时{int(time.time() - start_time)}秒）')
            return True
        
        # 等待2秒后继续下次唤醒（总共5秒间隔）
        time.sleep(2)
    
    log_print(f'唤醒超时（{timeout}秒），设备未在线')
    return False


def process_device(device_info, username, password):
    """处理单个设备（唤醒+下载）"""
    global current_device, func_lib
    yun_id, (name, sn, pwd) = device_info
    current_device = f'{name}({yun_id})'
    
    # 如果DLL未初始化，则初始化（单进程模式）
    if func_lib is None:
        func, cb1, cb2 = init_func_lib()
    
    # 获取token
    token = get_token(username, password)
    if not token:
        log_print('获取token失败')
        return f'{name}({yun_id}) 获取token失败'
    
    # 唤醒设备并等待在线（最多1分钟）
    if not wake_and_wait_online(yun_id, sn, name, token, timeout=60):
        return f'{name}({yun_id}) 跳过: 唤醒超时'
    
    # 最多重试2次下载
    for retry in range(2):
        # 下载日志
        if download_log(yun_id, pwd, name, sn):
            return f'{name}({yun_id}) 成功'
        
        if retry < 1:
            log_print('下载失败，重试...')
            time.sleep(5)
    
    return f'{name}({yun_id}) 失败'


def read_csv_to_dict(file_path):
    """读取CSV设备列表"""
    import csv
    data_dict = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 4:
                data_dict[row[2]] = [row[0], row[1], row[3]]
    return data_dict


def main():
    """主函数"""
    # 配置
    username = 'yinjia'
    password = 'Yjtest123456.'
    csv_file = 'syj.csv'
    
    # 读取设备列表
    if not os.path.exists(csv_file):
        print(f'设备列表文件 {csv_file} 不存在')
        return
    
    device_dict = read_csv_to_dict(csv_file)
    print(f'共 {len(device_dict)} 台设备')
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '远程日志')
    os.makedirs(log_dir, exist_ok=True)
    
    # 单进程顺序处理（避免DLL多进程冲突）
    results = []
    for i, (yun_id, device_info) in enumerate(device_dict.items(), 1):
        print(f'\n处理第 {i}/{len(device_dict)} 台设备')
        try:
            result = process_device((yun_id, device_info), username, password)
            results.append(result)
            print(f'[结果] {result}')
        except Exception as e:
            result = f'{device_info[0]}({yun_id}) 异常: {e}'
            results.append(result)
            print(f'[异常] {result}')
        
        # 每台设备处理完后稍作休息
        time.sleep(2)
    
    # 输出汇总
    print('\n===== 汇总 =====')
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for r in results:
        print(r)
        if '成功' in r:
            success_count += 1
        elif '跳过' in r:
            skip_count += 1
        else:
            fail_count += 1
    
    print(f'\n统计: 成功 {success_count} 台, 跳过 {skip_count} 台, 失败 {fail_count} 台')


if __name__ == '__main__':
    main()
