"""
    查找设备录像片段脚本, 输出丢失录像时长、人形录像时长
"""
import shutil
import os
import xlrd
import sys
import time
import datetime
import json
import csv
import base64
import hashlib
import random
import ddddocr
import requests
import platform
import multiprocessing
import concurrent.futures
from urllib.parse import urlencode
from multiprocessing import Process
from ctypes import *

global func_lib
add_path = os.path.dirname(os.path.abspath(__file__))
if hasattr(os, 'add_dll_directory'):  # Only available on Windows
    os.add_dll_directory(add_path)
test = False
# 定义回调函数类型
callback_type = CFUNCTYPE(c_int, c_uint, POINTER(c_char),  c_uint, POINTER(c_void_p), c_uint)
log_callback_type = CFUNCTYPE(c_int, c_uint, c_char_p)

# 定义临时数据存放字典
cloud_test = {}
log_name = ""


class Console_Admin_System:
    def __init__(self, env, username, password):
        """
        初始化相关参数
        生产环境使用wake与wake_many_times进行,生产环境需要鉴权，不能直接访问最底层的接口
        测试环境可以使用ake与wake_many_times进行，也可以使用wake_test与wake_many_times_test进行，测试环境公司内网不需要鉴权，直接可以调用最底层的接口
        :param env: pro：生产环境/test:测试环境
        :param username: 用户名
        :param password：密码
        """
        self.username = username
        self.password = password
        if env == 'pro':
            self.host = 'console.seetong.com'
        else:
            self.host = 'console-test.seetong.com'
        self.token, self.refresh_token = self.token_get()

    def refresh_token_wrap():
        """
        token过期后重新获取新token
        """
        def _refresh_token_wrap(func):
            def __refresh_token_wrap(self, *args, **kargs):

                info = func(self, *args, **kargs)
                # http状态码为401表示token过期
                if info[1] == 401:
                    print('token过期，重新获取token')
                    self.token, self.refresh_token = self.refresh_token_get(self.refresh_token)
                    info = func(self, *args, **kargs)
                return info

            return __refresh_token_wrap

        return _refresh_token_wrap

    def login_retry(times=3, interval=1):
        """
        captcha函数识别验证码可能不准，如获取token失败，可以尝试重新获取验证码
        :param app: 重试次数，默认重试3次
        :param app: 重试间隔，默认重试间隔1s
        """

        def _login_retry(func):
            def __login_retry(*args, **kargs):
                for index in range(times):
                    res = func(*args, **kargs)
                    if res[0]:
                        print(f'第{index+1}次调用{func.__name__}验证成功')
                        break
                    else:
                        print(f'第{index+1}次调用{func.__name__}验证失败')
                        if index < times - 1:
                            time.sleep(interval)
                if res:
                    return res
                else:
                    print(f'调用{func.__name__}验证失败，退出执行')
                    sys.exit()

            return __login_retry

        return _login_retry

    def captcha(self):
        """
        获取图片验证码captcha_code以及对应captcha_key
        """
        api_path = '/api/seetong-auth/oauth/captcha'
        url = f'https://{self.host}{api_path}'
        r = requests.get(url, verify=False)
        res = r.content.decode()
        res_dict = json.loads(res)

        image = res_dict.get('image')
        captcha_key = res_dict.get('key')

        # image中data:image/png;base64,后面的是图片的二进制base64编码数据
        img_data_base64 = image.split('data:image/png;base64,')[-1]
        img_data = base64.b64decode(img_data_base64.encode())

        # 根据图片数据识别图片二维码
        ocr = ddddocr.DdddOcr(show_ad=False)
        captcha_code = ocr.classification(img_data)

        return captcha_key, captcha_code

    @login_retry(3, 1)
    def token_get(self):
        """
        获取登录token用于调用其他函数鉴权
        :param app: 重试次数，默认重试3次
        :param app: 重试间隔，默认重试间隔1s
        """
        captcha_key, captcha_code = self.captcha()
        api_path = '/api/seetong-auth/oauth/token'
        url = f'https://{self.host}{api_path}'
        headers = {
            "User-Agent": "topsee/product-retrospect",
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
        res = r.content.decode()
        res_dict = json.loads(res)
        token = res_dict.get('access_token')
        refresh_token = res_dict.get('refresh_token')
        return token, refresh_token

    def refresh_token_get(self, refresh_token):
        """
        发送唤醒设备消息
        :param dev_id: 设备云id
        :param msg: 唤醒消息内容
        """
        api_path = '/api/seetong-auth/oauth/token'
        url = f'https://{self.host}{api_path}'
        headers = {
            "User-Agent": "topsee/product-retrospect",
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Tenant-Id": "000000",
        }

        params = {"grant_type": "refresh_token", "scope": "all", "refresh_token": refresh_token}
        r = requests.post(url, params=params, headers=headers, verify=False)
        res = r.content.decode()
        res_dict = json.loads(res)
        token = res_dict.get('access_token')
        refresh_token = res_dict.get('refresh_token')
        return token, refresh_token

    @refresh_token_wrap()
    def wake(self, dev_id, msg='test'):
        """
        发送唤醒设备消息
        :param dev_id: 设备云id
        :param msg: 唤醒消息内容
        """
        api_path = '/api/seetong-device-media-command/siot-media/command/send'
        url = f'https://{self.host}{api_path}'
        headers = {
            "User-Agent": "topsee/product-retrospect",
            "Content-Type": "application/json",
            "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
            "Seetong-Auth": self.token,
        }

        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': msg}
        r = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
        http_code = r.status_code
        res = r.content.decode()
        return res, http_code

    def wake_many_times(self, dev_id, msg, count, interval):
        """
        持续发送唤醒消息
        :param dev_id: 设备云id
        :param msg: 唤醒消息内容
        :param count: 循环次数
        :param interval: 循环间隔时间，list类型，随机list中2个数字之间的数字
        """
        for i in range(0, 0 + count):
            msg1 = f'{msg}-{i + 1}'
            res = self.wake(dev_id, msg1)[0]
            print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 第{i + 1}次唤醒，发送消息：{msg1} 结果: {res}')
            t = random.randint(interval[0], interval[1])
            time.sleep(t)

    def wake_test(self, dev_id, msg):
        """_summary_

        :param dev_id: 设备云id
        :param msg: 唤醒消息内容
        :return: 唤醒返回消息
        """
        url = 'http://114.116.200.81:20077/siot-media/command/send'
        headers = {"Content-Type": "application/json"}
        data = {'devId': dev_id, 'type': 'LOW_POWER_WAKE', 'msg': msg}
        r = requests.post(url, data=json.dumps(data), headers=headers)
        res = r.content.decode()
        return res

    def wake_many_times_test(self, dev_id, msg, count, interval):
        """
        持续发送唤醒消息
        :param dev_id: 设备云id
        :param msg: 唤醒消息内容
        :param count: 循环次数
        :param interval: 循环间隔时间，list类型，随机list中2个数字之间的数字
        """
        for i in range(0, 0 + count):
            msg1 = f'{msg}-{i + 1}'
            res = self.wake(dev_id, msg1)
            print(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 第{i + 1}次唤醒，发送消息：{msg1} 结果: {res}')
            t = random.randint(interval[0], interval[1])
            time.sleep(t)


def clear_folder(folder_name):
    """
    清空指定文件夹中的所有内容。
    """
    # 获取当前脚本的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 创建保存截图的文件夹
    save_folder = os.path.join(current_dir, folder_name)
    # 检查文件夹是否存在
    if not os.path.exists(save_folder):
        print(f"文件夹 {save_folder} 不存在")
        return

    # 遍历文件夹中的所有文件和子文件夹
    for filename in os.listdir(save_folder):
        file_path = os.path.join(save_folder, filename)
        try:
            # 如果是文件或链接，删除它
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            # 如果是目录，递归删除
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"删除 {file_path} 时出错: {e}")


def func_lib_init():
    """
    调用动态链接库函数
    """
    global func_lib
    path = os.path.join(os.getcwd(), 'Funclib.dll')

    if platform.system().lower() == 'windows':
        func_lib = CDLL(path, winmode=0)
    else:
        func_lib = cdll.LoadLibrary(path)

    return func_lib


def func_lib_login(username, pwd, vms_ip):
    """
    登录
    :param username: 登录用户名
    :param pwd: 登录密码
    :param vms_ip: 服务器地址,设备云ID
    :return: 0-成功；非0-失败
    """
    # 远程调试工具端口固定80
    return func_lib.FC_Login(username.encode('utf-8'), pwd.encode('utf-8'), vms_ip.encode('utf-8'), 80, "", "", "")


def func_lib_logout():
    """
    登出
    :return: 0-成功；非0-失败
    """
    return func_lib.FC_Logout()


def func_lib_send(dev_id, command, pxml, channel):
    """
    设备远程调试命令  CMD
    :param dev_id: 设备ID
    :param command: 消息code
    :param pxml: xml文本内容
    :param channel: 通道(设备直接交互-1,NVR通道相应通道号)
    :return: 0-函数调用成功
    """
    # pxml = "<cmd>syscmd " + pxml + "</cmd>"
    return func_lib.FC_RemoteDiagnose(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()), channel)


def func_lib_getconfig(dev_id, command, pxml):
    """
    读取设备配置  SYSTEM_CONFIG_GET_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :return: 0:函数调用成功；具体响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
    """
    return func_lib.FC_GetP2PDevConfig(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()))


def func_lib_getconfig_pte(dev_id, command, pxml, channel):
    """
    读取设备配置  SYSTEM_CONFIG_GET_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :param channel: nvr端ipc对应的通道值，通道值用来判断是否需要透传消息
    :return: 0:函数调用成功；具体地响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同
    """
    return func_lib.FC_GetP2PDevConfigWithPte(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()), channel)


def func_lib_setconfig(dev_id, command, pxml):
    """
    设置设备配置  SYSTEM_CONFIG_SET_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :return: 0:函数调用成功；具体响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同
    """
    return func_lib.FC_SetP2PDevConfig(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()))


def func_lib_setconfig_pte(dev_id, command, pxml, channel):
    """
    设置设备配置  SYSTEM_CONFIG_SET_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :param channel: nvr端ipc对应的通道值，通道值用来判断是否需要透传消息
    :return: 0:函数调用成功；具体地响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同
    """
    return func_lib.FC_SetP2PDevConfigWithPte(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()), channel)


def func_lib_system_control(dev_id, command, pxml):
    """
    对设备进行高级系统控制  SYSTEM_CONTROL_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :return: 0:函数调用成功；具体响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同。
    """
    return func_lib.FC_P2PDevSystemControl(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()))


def func_lib_system_control_pte(dev_id, command, pxml, channel):
    """
    对设备进行高级系统控制  SYSTEM_CONTROL_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :param channel: nvr端ipc对应的通道值，通道值用来判断是否需要透传消息
    :return: 0:函数调用成功；具体地响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同
    """
    return func_lib.FC_P2PDevSystemControlWithPte(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()), channel)


def func_lib_iot_system_control(dev_id, command, pxml):
    """
    对设备进行高级系统控制  IOT_CAMERA_MESSAGE
    :param dev_id: 设备ID
    :param command: 配置对应信息，请参考文档;如：协议中的Msg_code
    :param pxml: xml文本内容
    :return: 0:函数调用成功；具体地响应结果都通过辅助通道回调函数返回，如果成功则回调函数错误标记为0，消息类型（注意后面24位的值）与nCommand相同
    """
    return func_lib.FC_P2PIoTSystemControl(c_char_p(dev_id.encode()), command, c_char_p(pxml.encode()))


def func_lib_search_rec(dev_id, pDate):
    """
    查询录像回放
    :param dev_id: 设备ID
    :param pDate: 查询日期，如:“20151015”
    :return: 0：成功，！＝0：失败
    """
    return func_lib.FC_P2PSearchNvrRecByTimeEx(c_char_p(dev_id.encode()), c_char_p(pDate.encode()))


def python_log_callback(uLevel, lpszOut):
    """
    python日志回调函数
    """
    # print("====================log=================")
    # print("uLevel:", uLevel)
    # print("lpszOut:", lpszOut)
    # print("====================log=================")
    # if "NVR_REPLAY_MESSAGE" in str(lpszOut) and "TimeSliceInfo" in str(lpszOut):
    #     # 得到消息若为录像信息，保存到日志与临时字典，需要兼容返回多个包的情况
    #     try:
    #         cloud_test[3017] = {"pData": cloud_test[3017]["pData"] + str(lpszOut)}
    #     except:
    #         cloud_test[3017] = {"pData": str(lpszOut)}

    return 0


def python_callback(nMsgType, pData, nDataLen, pExtData, nExtDataLen):
    """
    python回调函数
    """
    # 心跳
    # if nMsgType == 1112:
    #     print("心跳消息")
    if nMsgType == 8263:
        print("##8263登录主服务器成功##")
    elif nMsgType == 8223:
        print("##8223登录P2P服务器成功,等待P2P连接设备中##")
    elif nMsgType == 8202:
        # 将数据转换为字节对象
        data_bytes = string_at(pData, nDataLen)
        cloud_test[nMsgType] = {"pData": data_bytes, "nDataLen": str(nDataLen), "pExtData": str(pExtData),
                                "nExtDataLen": str(nExtDataLen)}
        print("##P2P连接设备成功##")
    elif nMsgType == 8238:
        # print("##8238##")
        if pData:
            # 将数据转换为字节对象
            data_bytes = string_at(pData, nDataLen)
            if b'Msg_type="SYSTEM_LOG_DATA"' in data_bytes:
                # print("##8238下载日志##")
                # print(data_bytes)
                # 查找前四个 \0 的位置
                null_count = 0
                end_index = nDataLen  # 默认结束索引为数据长度

                for i in range(nDataLen):
                    if data_bytes[i] == 0:  # 找到 \0
                        null_count += 1
                        if null_count == 4:  # 找到四个 \0
                            end_index = i  # 设置结束索引
                            break

                offset = end_index + 1
                if nDataLen > offset:
                    with open(log_name, "ab") as file:
                        file.write(data_bytes[offset:])  # 写入文件
                elif nDataLen == offset:
                    print("下载日志完成")
                    cloud_test[nMsgType] = {}
                else:
                    print("数据长度不足以进行偏移。")
            # else:
            #     print("##8238其他协议数据##")
            #     print(data_bytes)
        else:
            print("读取文件失败或文件为空")

    # else:
        # print("##其他设备信息##")
        # data_bytes = string_at(pData, nDataLen)
        # print("nMsgType", str(nMsgType))
        # print(data_bytes)

    return 0


def func_lib_recv(callback_instance):
    """
    接收库返回的数据
    """
    # 接收库返回的数据
    func_lib.FC_SetMsgRspCallBack(callback_instance)


def func_lib_recv_log(callback_log):
    """
    接收库返回的日志数据
    """
    # 接收库返回的日志数据
    func_lib.FC_SetfcLogCallBack(callback_log)


def read_excel_to_dict(file_path):
    # 打开工作簿
    workbook = xlrd.open_workbook(file_path)
    # 获取第一个工作表
    sheet = workbook.sheet_by_index(0)
    # 创建字典
    data_dict = {}
    # 遍历每一行
    for row_idx in range(sheet.nrows):
        # 获取第 1 列到第 4 列的数据
        row_data = sheet.row_values(row_idx, start_colx=0, end_colx=4)
        data_dict[str(int(row_data[2]))] = [row_data[0], row_data[1], row_data[3]]

    return data_dict

def read_csv_to_dict(file_path):
    data_dict = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            if len(row) >= 4:
                data_dict[str(int(row[2]))] = [row[0], row[1], row[3]]
    return data_dict

def get_yun_log(yun_id, pwd, name, sn, timeout):
    """str
    :param yun_id: 云ID
    :param pwd: 云密码
    :param name: 设备名称
    :param sn: 设备sn
    :param timeout: p2p连接超时时间
    :return:
    """
    global log_name
    log_name = os.path.join(os.getcwd(), "远程日志", f"{name}_{sn}_{str(yun_id)}.txt")
    with open(log_name, "w", encoding="utf-8", errors='ignore') as f1:
        f1.write("")
    cloud_test.clear()    # 清空  临时数据存放字典
    mark = True

    # 登录
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    func_lib_login("admin", pwd, yun_id)

    str2 = "<cmd>GetSystemCfg /tmp/sd_room/IPC_Log/Tps_RecordLogNew.log</cmd>"
    #str2 = "<cmd>GetSystemCfg /tmp/sd_room/IPC_Log/Tps_RecordLog1.log</cmd>"
    #str2 = "<cmd>GetSystemCfg /mnt/nand/keylog.data</cmd>"
    #str2 = "<cmd>GetSystemCfg /mnt/nand/dmsg_suspend_failed.txt</cmd>"
    # 循环等待登录，超时30秒
    for time_out1 in range(timeout):
        time.sleep(1)
        # 登录成功,开始发送命令.
        if 8202 in cloud_test.keys():
            # 设备远程调试命令---- ok
            func_lib_send(yun_id, 1, str2, -1)    # 常规命令交互,获取日志
            # func_lib_send(yun_id, 1, str2, -1)    # 常规命令交互,获取日志
            break

    # 如果登录成功
    download = False
    if 8202 in cloud_test.keys():
        # 循环等待登录，超时5分钟
        for i in range(30):
            time.sleep(10)
            if 8238 in cloud_test.keys():
                print(f"\\远程日志\\{name}_{sn}_{str(yun_id)}下载成功")
                with open("run_log.txt", "a", encoding="utf-8", errors='ignore') as f123:
                    f123.write(f"\\远程日志\\{name}_{sn}_{str(yun_id)}下载成功\n")
                download = True
                break
        if download is False:
            # 超时5分钟退出
            mark = False
            print(f"\\远程日志\\{name}_{sn}_{str(yun_id)}下载失败--超时")
            with open("run_log.txt", "a", encoding="utf-8", errors='ignore') as f123:
                f123.write(f"\\远程日志\\{name}_{sn}_{str(yun_id)}下载失败--超时\n")
    else:
        print(f"\\远程日志\\{name}_{sn}_{str(yun_id)}下载失败--P2P连接设备失败")
        mark = False
        with open("run_log.txt", "a", encoding="utf-8", errors='ignore') as f123:
            f123.write(f"\\远程日志\\{name}_{sn}_{str(yun_id)}下载失败--P2P连接设备失败\n")
    print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 注销登录
    print("注销登录返回结果：", func_lib_logout())
    time.sleep(2)

    return mark


def main(information):
    """
    循环对设备进行远程下载日志
    """
    func = func_lib_init()    # 调用动态链接库函数

    # 设置回调函数，用来接收库返回的消息通知和数据
    callback_instance = callback_type(python_callback)  # python转换为c
    func_lib_recv(callback_instance)

    # 设置日志回调函数，用来接收库交互过程中返回的日志消息
    log_callback_instance = log_callback_type(python_log_callback)  # python转换为c
    func_lib_recv_log(log_callback_instance)

    func.FC_init()    # 初始化库

    # 唤醒设备 + 下载日志，重试最大3次
    time1 = 15
    for yun_data in information:
        for up_log in range(3):
            try:
                app = Console_Admin_System('pro', 'yinjia', 'Yjtest123456.')
                # app.wake(up_id)
                app.wake_many_times(yun_data[0], 'wake test', 3, [1, 1])
                time.sleep(4)
                app.wake_many_times(yun_data[0], 'wake test', 3, [1, 1])
                result_mark = get_yun_log(yun_data[0], yun_data[1][2], yun_data[1][0], yun_data[1][1], time1)
                time1 += 5

                if result_mark is True:
                    break
            except Exception as e:
                time.sleep(1)
            time.sleep(30)


if __name__ == '__main__':
    """
    多进程运行程序
    """
    clear_folder("远程日志")  # 清空文件夹
    with open("run_log.txt", "w", encoding="utf-8", errors='ignore') as f:
        f.write("start\n")

    # 从列表输出待查询设备
    device_dict = read_csv_to_dict("syj.csv")
    print("设备目录\n", device_dict)

    # # # 非局域网设备信息，{"云ID": {"username": "账号", "pwd": "云密码"}}，自行修改
    # device_dict = {'36361924': ['3AR-河南商丘张', '0C5C9516A8923C89', 'Jhx9z8mwupsZHOel']}

    # while True:
    #     time_now = time.strftime("%H:%M:%S", time.localtime())  # 刷新
    #     if time_now == "16:22:00":  # 此处设置每天定时的时间
    # 多进程并行下载日志
    num_processes = multiprocessing.cpu_count() * 2  # 设置进程数为 CPU 核心数的 2 倍
    # 获取设备总数
    num_devices = len(device_dict)

    # 如果设备数量少于进程数，调整进程数为设备数量
    if num_devices < num_processes:
        num_processes = num_devices

    # 计算每个进程处理的设备数量
    devices_per_process = num_devices // num_processes
    # 计算剩余设备数量（用于处理无法整除的情况）
    remainder = num_devices % num_processes

    # 创建设备分组
    devices = list(device_dict.items())
    chunks = []
    start_index = 0
    for i in range(num_processes):
        # 对于前 remainder 个进程，每个进程多分配一个设备
        if i < remainder:
            chunk_size = devices_per_process + 1
        else:
            chunk_size = devices_per_process
        end_index = start_index + chunk_size
        chunks.append(devices[start_index:end_index])
        start_index = end_index

    # 创建进程池
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_processes) as executor:
        # 提交每组设备的测试任务到进程池
        futures = [executor.submit(main, chunk) for chunk in chunks]

        # 收集并打印所有结果
        for future in concurrent.futures.as_completed(futures):
            try:
                results = future.result()
                for result in results:
                    print(result)
            except Exception as e:
                print(f"任务出错: {e}")

    with open("run_log.txt", "r", encoding="utf-8", errors='ignore') as f:
        print("输出测试结果：", f.read())

        # time.sleep(1)
