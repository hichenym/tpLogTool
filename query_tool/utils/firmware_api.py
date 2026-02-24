from bs4 import BeautifulSoup
import json
import pickle
import base64
import time
from query_tool.utils.logger import logger
from query_tool.utils.session_manager import SessionManager

# 登录配置
LOGIN_PAGE_URL = "https://update.seetong.com/admin/auth/login"
LOGIN_URL = "https://update.seetong.com/admin/auth/login"

# 固件列表页面基础URL
FIRMWARE_BASE_URL = "https://update.seetong.com/admin/update/debug-firmware"

# Session 有效期（秒）- 默认2小时
SESSION_EXPIRE_TIME = 7200

# 全局 session 缓存
_cached_session = None
_session_timestamp = None


def get_firmware_credentials():
    """从配置获取固件账号密码"""
    try:
        from .config import get_firmware_account_config
        username, password = get_firmware_account_config()
        
        # 如果配置为空，返回空值（不再使用默认值）
        if not username or not password:
            return "", ""
        
        return username, password
    except Exception as e:
        print(f"获取固件账号配置失败: {e}")
        return "", ""


def save_session_to_registry(session):
    """保存 session cookies 到注册表"""
    reg_key = None
    try:
        import winreg
        # 序列化 cookies - 使用 session_manager 的方法
        cookies_dict = {}
        for cookie in session.cookies:
            cookies_dict[cookie.name] = cookie.value
        
        cookies_str = json.dumps(cookies_dict)
        cookies_encoded = base64.b64encode(cookies_str.encode()).decode()
        
        # 保存到注册表
        reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\TPQueryTool\Firmware")
        winreg.SetValueEx(reg_key, "session_cookies", 0, winreg.REG_SZ, cookies_encoded)
        winreg.SetValueEx(reg_key, "timestamp", 0, winreg.REG_SZ, str(time.time()))
        return True
    except Exception as e:
        logger.warning(f"保存session到注册表失败: {e}")
        return False
    finally:
        if reg_key:
            try:
                winreg.CloseKey(reg_key)
            except Exception as e:
                logger.debug(f"关闭注册表键失败: {e}")


def load_session_from_registry():
    """从注册表加载 session cookies"""
    reg_key = None
    try:
        import winreg
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\TPQueryTool\Firmware",
            0,
            winreg.KEY_READ
        )
        
        cookies_encoded, _ = winreg.QueryValueEx(reg_key, "session_cookies")
        timestamp_str, _ = winreg.QueryValueEx(reg_key, "timestamp")
        
        # 检查是否过期
        timestamp = float(timestamp_str)
        if time.time() - timestamp > SESSION_EXPIRE_TIME:
            return None
        
        # 反序列化 cookies
        cookies_str = base64.b64decode(cookies_encoded.encode()).decode()
        cookies_dict = json.loads(cookies_str)
        
        # 创建新 session 并设置 cookies
        session = SessionManager().get_session('firmware')
        
        # 将字典转换为 cookies
        for name, value in cookies_dict.items():
            session.cookies.set(name, value)
        
        return session
        
    except (WindowsError, FileNotFoundError, OSError, ValueError, KeyError) as e:
        logger.debug(f"从注册表加载session失败: {e}")
        return None
    finally:
        if reg_key:
            try:
                winreg.CloseKey(reg_key)
            except Exception as e:
                logger.debug(f"关闭注册表键失败: {e}")

def get_csrf_token(session):
    """获取登录页面的 CSRF token"""
    try:
        response = session.get(LOGIN_PAGE_URL, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            token_input = soup.find('input', {'name': '_token'})
            if token_input:
                token = token_input.get('value')
                if token:
                    return token
                else:
                    logger.warning("找到_token输入框但值为空")
            else:
                logger.warning("页面中未找到_token输入框")
        else:
            logger.warning(f"获取登录页面失败: HTTP {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"获取CSRF token异常: {e}")
        return None

def is_session_valid(session):
    """检查 session 是否仍然有效"""
    if session is None:
        return False
    
    try:
        # 尝试访问一个需要登录的页面
        response = session.get(FIRMWARE_BASE_URL, timeout=5)
        # 如果返回200且不是登录页面，说明session有效
        return response.status_code == 200 and 'login' not in response.url.lower()
    except Exception as e:
        logger.debug(f"检查session有效性失败: {e}")
        return False

def login(force_new=False):
    """执行登录操作，返回已登录的 session
    
    Args:
        force_new: 是否强制创建新session（默认False，会尝试复用已有session）
    """
    global _cached_session, _session_timestamp
    
    # 获取账号密码
    USERNAME, PASSWORD = get_firmware_credentials()
    
    # 检查账号密码是否配置
    if not USERNAME or not PASSWORD:
        print("固件账号未配置，请在设置页面配置固件账号")
        # 清除缓存的 session
        _cached_session = None
        _session_timestamp = None
        # 清除注册表中的缓存
        clear_session_cache()
        return None
    
    # 如果不强制创建新session，先尝试使用内存缓存
    if not force_new and _cached_session is not None:
        # 检查内存缓存是否过期
        if _session_timestamp and time.time() - _session_timestamp < SESSION_EXPIRE_TIME:
            if is_session_valid(_cached_session):
                return _cached_session
    
    # 内存缓存失效，尝试从注册表加载
    if not force_new:
        session = load_session_from_registry()
        if session and is_session_valid(session):
            _cached_session = session
            _session_timestamp = time.time()
            return session
    
    # 创建新session
    session = SessionManager().get_session('firmware')
    
    token = get_csrf_token(session)
    if not token:
        return None
    
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "_token": token
    }
    
    response = session.post(LOGIN_URL, data=payload, allow_redirects=False)
    
    if response.status_code in [200, 302]:
        # 缓存到内存
        _cached_session = session
        _session_timestamp = time.time()
        # 保存到注册表
        save_session_to_registry(session)
        return session
    else:
        return None


def clear_session_cache():
    """清除 session 缓存（内存和注册表）"""
    from query_tool.utils.logger import logger
    
    global _cached_session, _session_timestamp
    
    # 清除内存缓存
    _cached_session = None
    _session_timestamp = None
    
    # 清除注册表缓存
    reg_key = None
    try:
        import winreg
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\TPQueryTool\Firmware",
            0,
            winreg.KEY_WRITE
        )
        try:
            winreg.DeleteValue(reg_key, "session_cookies")
        except Exception:
            pass
        try:
            winreg.DeleteValue(reg_key, "timestamp")
        except Exception:
            pass
        logger.info("已清除固件 session 缓存")
    except FileNotFoundError:
        # 注册表键不存在是正常情况（首次使用或已清除），不需要警告
        logger.debug("固件 session 缓存不存在，无需清除")
    except Exception as e:
        logger.warning(f"清除缓存失败: {e}")
    finally:
        if reg_key:
            try:
                winreg.CloseKey(reg_key)
            except Exception as e:
                logger.debug(f"关闭注册表键失败: {e}")


def test_firmware_login(username, password):
    """测试固件账号登录
    
    Args:
        username: 用户名
        password: 密码
    
    Returns:
        tuple: (success: bool, message: str)
    """
    import time
    
    try:
        # 使用时间戳创建唯一的session key，避免复用旧session
        session_key = f'firmware_test_{int(time.time() * 1000)}'
        session = SessionManager().get_session(session_key)
        
        try:
            # 获取CSRF token
            logger.debug("正在获取CSRF token...")
            token = get_csrf_token(session)
            if not token:
                return False, "无法获取CSRF token，请检查网络连接"
            
            logger.debug(f"获取到CSRF token: {token[:20]}...")
            
            # 尝试登录
            payload = {
                "username": username,
                "password": password,
                "_token": token
            }
            
            logger.debug("正在尝试登录...")
            response = session.post(LOGIN_URL, data=payload, allow_redirects=False, timeout=10)
            
            logger.debug(f"登录响应状态码: {response.status_code}")
            
            if response.status_code in [200, 302]:
                # 验证session是否有效
                logger.debug("正在验证session...")
                if is_session_valid(session):
                    return True, "登录成功"
                else:
                    return False, "登录失败，请检查账号密码"
            else:
                return False, f"登录失败: HTTP {response.status_code}"
        finally:
            # 测试完成后关闭session，释放资源
            SessionManager().close_session(session_key)
    
    except Exception as e:
        logger.error(f"测试登录异常: {e}")
        return False, f"连接失败: {str(e)}"

def parse_pagination_info(html_content):
    """解析分页信息，返回总条数和总页数"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    total_count = 0
    max_page = 1
    
    # 查找所有分页区域（可能有多个box-footer）
    footers = soup.find_all('div', class_='box-footer')
    
    for footer in footers:
        footer_str = str(footer)
        
        # 1. 提取总条数：总共 <b>1615</b> 条
        import re
        match = re.search(r'总共\s*<b>(\d+)</b>\s*条', footer_str)
        if match:
            total_count = int(match.group(1))
        
        # 2. 提取最大页码：从所有分页链接中找最大的page参数
        pagination = footer.find('ul', class_='pagination')
        if pagination:
            page_links = pagination.find_all('a', class_='page-link')
            for link in page_links:
                href = link.get('href', '')
                # 从URL中提取page参数，使用更精确的正则：匹配 &page= 或 ?page=
                page_match = re.search(r'[?&]page=(\d+)', href)
                if page_match:
                    page_num = int(page_match.group(1))
                    max_page = max(max_page, page_num)
    
    # 3. 如果没有找到分页链接，通过总条数计算（备用方案）
    if max_page == 1 and total_count > 0:
        # 假设每页100条
        max_page = (total_count + 100 - 1) // 100
    
    return total_count, max_page


def parse_firmware_data(html_content):
    """解析固件列表页面，提取固件信息"""
    soup = BeautifulSoup(html_content, 'html.parser')
    firmware_list = []
    
    # 查找表格
    table = soup.find('table', class_='table')
    if not table:
        return firmware_list
    
    # 查找所有数据行（排除嵌套的展开行）
    tbody = table.find('tbody')
    if not tbody:
        return firmware_list
    
    # 只获取主数据行（有 data-key 属性的行）
    rows = tbody.find_all('tr', attrs={'data-key': True})
    
    for row in rows:
        try:
            firmware_info = {}
            
            # 提取 data-key (固件ID)
            data_key = row.get('data-key', '')
            if data_key:
                firmware_info['id'] = data_key
            
            # 提取固件标识 (column-device_identify)
            identifier_td = row.find('td', class_='column-device_identify')
            if identifier_td:
                identifier_link = identifier_td.find('a')
                if identifier_link:
                    # 提取固件标识，去掉前面的图标
                    identifier_text = identifier_link.get_text(strip=True)
                    firmware_info['identifier'] = identifier_text
            
            # 提取审核结果 (column-audit_result)
            audit_td = row.find('td', class_='column-audit_result')
            if audit_td:
                firmware_info['audit_result'] = audit_td.get_text(strip=True)
            
            # 提取下载链接 (column-file_url)
            file_url_td = row.find('td', class_='column-file_url')
            if file_url_td:
                download_link = file_url_td.find('a')
                if download_link:
                    firmware_info['download_url'] = download_link.get('href', '')
            
            # 提取开始时间 (column-start_time)
            start_time_td = row.find('td', class_='column-start_time')
            if start_time_td:
                firmware_info['start_time'] = start_time_td.get_text(strip=True)
            
            # 提取结束时间 (column-end_time)
            end_time_td = row.find('td', class_='column-end_time')
            if end_time_td:
                firmware_info['end_time'] = end_time_td.get_text(strip=True)
            
            # 提取创建时间 (column-created_at)
            created_at_td = row.find('td', class_='column-created_at')
            if created_at_td:
                firmware_info['created_at'] = created_at_td.get_text(strip=True)
            
            # 提取更新时间 (column-updated_at)
            updated_at_td = row.find('td', class_='column-updated_at')
            if updated_at_td:
                firmware_info['updated_at'] = updated_at_td.get_text(strip=True)
            
            # 提取发布备注 (column-create_comment)
            comment_td = row.find('td', class_='column-create_comment')
            if comment_td:
                firmware_info['remark'] = comment_td.get_text(strip=True)
            
            # 提取发布人员 (column-create_user)
            user_td = row.find('td', class_='column-create_user')
            if user_td:
                firmware_info['publisher'] = user_td.get_text(strip=True)
            
            # 提取查询次数 (column-query_count)
            query_count_td = row.find('td', class_='column-query_count')
            if query_count_td:
                firmware_info['query_count'] = query_count_td.get_text(strip=True)
            
            # 提取下载次数 (column-down_count)
            down_count_td = row.find('td', class_='column-down_count')
            if down_count_td:
                firmware_info['download_count'] = down_count_td.get_text(strip=True)
            
            if firmware_info:
                firmware_list.append(firmware_info)
                
        except Exception as e:
            print(f"解析行数据时出错: {str(e)}")
            continue
    
    return firmware_list

def fetch_firmware_data(create_user='cur', device_identify='', audit_result='', page=1, per_page=100):
    """
    获取固件数据的主函数
    
    Args:
        create_user: 发布人员筛选
            - 'cur': 当前用户（默认）
            - 'all': 全部用户
        device_identify: 固件标识筛选（可为空）
        audit_result: 审核状态筛选（可为空）
            - '': 全部
            - '1': 无需审核
            - '2': 待审核
            - '3': 审核通过
            - '4': 审核不通过
        page: 页码（默认第1页）
        per_page: 每页条数（默认100条）
    
    Returns:
        tuple: (firmware_list, total_count, total_pages)
    """
    # 登录（会自动复用已有session）
    session = login()
    if not session:
        return None, 0, 0
    
    # 构建URL参数（移除_pjax参数以获取完整HTML）
    params = {
        'device_identify': device_identify,
        'device_sn': '',
        'audit_result': audit_result,
        'create_comment': '',
        'create_user': create_user,
        'per_page': per_page,
        'page': page
    }
    
    try:
        response = session.get(FIRMWARE_BASE_URL, params=params)
        
        # 如果返回的是登录页面，说明session失效，需要重新登录
        if 'login' in response.url.lower() or response.status_code == 401:
            print("Session 失效，重新登录...")
            session = login(force_new=True)
            if not session:
                return None, 0, 0
            response = session.get(FIRMWARE_BASE_URL, params=params)
        
        if response.status_code == 200:
            # 解析分页信息
            total_count, total_pages = parse_pagination_info(response.text)
            
            # 解析数据
            firmware_list = parse_firmware_data(response.text)
            
            return firmware_list, total_count, total_pages
        else:
            print(f"✗ 页面访问失败: {response.status_code}")
            return None, 0, 0
            
    except Exception as e:
        return None, 0, 0


def delete_firmware(firmware_id):
    """
    删除固件
    
    Args:
        firmware_id: 固件ID (data-key值)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # 登录（会自动复用已有session）
    session = login()
    if not session:
        return False, "登录失败"
    
    # 构建删除URL
    delete_url = f"{FIRMWARE_BASE_URL}/{firmware_id}/delete"
    
    # 获取CSRF token
    try:
        # 先访问固件列表页面获取token
        response = session.get(FIRMWARE_BASE_URL)
        if response.status_code != 200:
            return False, "获取页面失败"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        token_input = soup.find('input', {'name': '_token'})
        if not token_input:
            # 尝试从meta标签获取
            token_meta = soup.find('meta', {'name': 'csrf-token'})
            if token_meta:
                token = token_meta.get('content')
            else:
                return False, "无法获取CSRF token"
        else:
            token = token_input.get('value')
        
        # 发送删除请求
        data = {
            '_method': 'put',
            '_token': token
        }
        
        response = session.post(delete_url, data=data)
        
        # 检查响应
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('status'):
                    return True, result.get('message', '删除成功')
                else:
                    return False, result.get('message', '删除失败')
            except Exception as e:
                logger.debug(f"解析JSON响应失败: {e}")
                # 如果不是JSON响应，检查是否重定向成功
                if 'debug-firmware' in response.url:
                    return True, "删除成功"
                else:
                    return False, "删除失败"
        else:
            return False, f"删除失败: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"删除出错: {str(e)}"


def get_firmware_detail(firmware_id):
    """
    获取固件详情
    
    Args:
        firmware_id: 固件ID (data-key值)
    
    Returns:
        dict: 固件详情数据，失败返回None
    """
    # 登录（会自动复用已有session）
    session = login()
    if not session:
        return None
    
    # 构建详情URL - 需要访问 /edit 页面
    detail_url = f"{FIRMWARE_BASE_URL}/{firmware_id}/edit"
    
    try:
        response = session.get(detail_url)
        
        # 如果返回500或者重定向到登录页，说明session失效，重新登录
        if response.status_code == 500 or 'login' in response.url.lower():
            session = login(force_new=True)
            if not session:
                return None
            response = session.get(detail_url)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        detail = {}
        
        # 提取CSRF token - 优先从meta标签获取（更可靠）
        token_meta = soup.find('meta', {'name': 'csrf-token'})
        if token_meta:
            detail['_token'] = token_meta.get('content', '')
        else:
            # 备用：从input获取 - 查找所有 _token 输入框，取最后一个（通常是表单底部的真实 token）
            token_inputs = soup.find_all('input', {'name': '_token'})
            if token_inputs:
                # 遍历所有token，找到第一个有效的（不是模板占位符）
                valid_token = ''
                for token_input in token_inputs:
                    token_value = token_input.get('value', '')
                    # 确保不是模板占位符
                    if token_value and '{{' not in token_value and 'csrf_token()' not in token_value:
                        valid_token = token_value
                        break
                
                detail['_token'] = valid_token
            else:
                detail['_token'] = ''
        
        # 提取所有表单字段
        form_fields = [
            'device_identify', 'file_md5', 'create_comment', 'phone_number',
            'support_sn', 'start_time', 'end_time', 'create_user',
            'file_temp_path', 'file_formal_path', 'file_url', 'file_path',
            'model_id', 'version_info', 'audit_result', 'audit_user_id',
            'audit_remark', 'audit_time', '_previous_', '_method',
            'id', 'created_at', 'updated_at'  # 添加缺失的字段
        ]
        
        for field in form_fields:
            # 查找input字段
            input_elem = soup.find('input', {'name': field})
            if input_elem:
                detail[field] = input_elem.get('value', '')
                continue
            
            # 查找textarea字段
            textarea_elem = soup.find('textarea', {'name': field})
            if textarea_elem:
                detail[field] = textarea_elem.get_text(strip=False)  # 保留换行
                continue
            
            # 查找select字段
            select_elem = soup.find('select', {'name': field})
            if select_elem:
                selected_option = select_elem.find('option', {'selected': True})
                if selected_option:
                    detail[field] = selected_option.get('value', '')
                else:
                    detail[field] = ''
                continue
            
            # 默认为空
            detail[field] = ''
        
        return detail
        
    except Exception as e:
        return None


def update_firmware(firmware_id, data):
    """
    更新固件信息
    
    Args:
        firmware_id: 固件ID (data-key值)
        data: 更新的数据字典（包含所有字段）
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # 登录（会自动复用已有session）
    session = login()
    if not session:
        return False, "登录失败"
    
    # 构建更新URL
    update_url = f"{FIRMWARE_BASE_URL}/{firmware_id}"
    
    try:
        # 调试 support_sn 字段
        support_sn = data.get('support_sn', '')
        
        # 关键修复：将 Unix 换行符转换为 Windows 换行符
        # 浏览器发送的是 \r\n，我们也需要使用相同的格式
        if support_sn and '\r\n' not in support_sn and '\n' in support_sn:
            support_sn = support_sn.replace('\n', '\r\n')
            data['support_sn'] = support_sn
        
        # 设置请求头（完全模拟浏览器的请求）
        headers = {
            'Accept': 'text/html, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'X-PJAX': 'true',
            'X-PJAX-Container': '#pjax-container',
            'Referer': f'{update_url}/edit',
            'Origin': 'https://update.seetong.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        # 发送POST请求（使用 data 参数，requests 会自动使用 multipart/form-data）
        response = session.post(update_url, data=data, headers=headers, allow_redirects=True)
        
        # 如果返回500或者重定向到登录页，说明session失效，重新登录并重试
        if response.status_code == 500 or 'login' in response.url.lower():
            session = login(force_new=True)
            if not session:
                return False, "重新登录失败"
            
            # 重新获取CSRF token
            detail = get_firmware_detail(firmware_id)
            if detail and '_token' in detail:
                data['_token'] = detail['_token']
                print(f"[更新函数] 更新 token: {data['_token'][:20]}...")
            
            response = session.post(update_url, data=data, headers=headers, allow_redirects=True)
        
        # 检查响应
        if response.status_code == 200:
            # 检查是否重定向到列表页（表示成功）
            if 'debug-firmware' in response.url and firmware_id not in response.url:
                return True, "修改成功"
            else:
                # 检查页面中是否有错误信息
                soup = BeautifulSoup(response.text, 'html.parser')
                error_alert = soup.find('div', class_='alert-danger')
                if error_alert:
                    error_msg = error_alert.get_text(strip=True)
                    return False, f"修改失败: {error_msg}"
                else:
                    return True, "修改成功"
        else:
            return False, f"修改失败: HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"更新出错: {str(e)}"
