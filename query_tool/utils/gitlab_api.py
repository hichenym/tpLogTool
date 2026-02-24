"""
GitLab API 封装
提供 GitLab 服务器交互功能
"""
import urllib.parse
from query_tool.utils.logger import logger
from query_tool.utils.session_manager import SessionManager


class GitLabAPI:
    """GitLab API 封装"""
    
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token
        self.timeout = 10  # 请求超时时间（秒）
        self.session = SessionManager().get_session('gitlab')
    
    def api_get(self, endpoint, params=None, retry=3):
        """
        发送 GET 请求到 GitLab API，带重试机制
        
        Args:
            endpoint: API 端点（如 '/projects'）
            params: 查询参数字典
            retry: 重试次数
            
        Returns:
            JSON 响应数据
            
        Raises:
            Exception: API 请求失败时抛出异常
        """
        headers = {'PRIVATE-TOKEN': self.token}
        url = f'{self.url}/api/v4{endpoint}'
        
        last_error = None
        for attempt in range(retry):
            try:
                response = self.session.get(
                    url, 
                    headers=headers, 
                    params=params or {}, 
                    timeout=self.timeout,
                    verify=False  # 禁用 SSL 验证
                )
                
                if response.status_code == 401:
                    raise Exception("认证失败，请检查 Token 是否有效")
                elif response.status_code == 429:
                    # 速率限制，等待后重试
                    last_error = "服务器限流，请稍后重试"
                    if attempt < retry - 1:
                        import time
                        time.sleep(2 ** attempt)
                        continue
                elif response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                
                return response.json()
            
            except Exception as e:
                # 检查是否是超时或连接错误
                error_str = str(e)
                if "timeout" in error_str.lower():
                    last_error = "请求超时"
                    if attempt < retry - 1:
                        import time
                        time.sleep(2 ** attempt)
                elif "connection" in error_str.lower():
                    last_error = "无法连接到服务器"
                    if attempt < retry - 1:
                        import time
                        time.sleep(2 ** attempt)
                else:
                    # 如果是认证错误，不需要重试
                    if "认证失败" in error_str:
                        raise
                    last_error = error_str
                    if attempt < retry - 1:
                        import time
                        time.sleep(1)
        
        raise Exception(f"API 请求失败（重试{retry}次）: {last_error}")
    
    def get_all_projects(self):
        """
        获取所有项目列表
        
        Returns:
            项目列表
        """
        projects = []
        page = 1
        
        while True:
            data = self.api_get('/projects', {
                'per_page': 100, 
                'page': page, 
                'order_by': 'path'
            })
            
            if not data:
                break
            
            projects.extend(data)
            page += 1
        
        return projects
    
    def get_branches(self, project_path):
        """
        获取项目的分支列表
        
        Args:
            project_path: 项目路径（如 'group/project'）
            
        Returns:
            分支列表
        """
        encoded = urllib.parse.quote(project_path, safe='')
        branches = []
        page = 1
        
        while True:
            data = self.api_get(
                f'/projects/{encoded}/repository/branches',
                {'per_page': 100, 'page': page}
            )
            
            if not data:
                break
            
            branches.extend(data)
            page += 1
        
        return branches
    
    def get_commits(self, project_path, since_date, until_date=None, branch=None, max_pages=50):
        """
        获取项目的提交记录，限制最大页数
        
        Args:
            project_path: 项目路径
            since_date: 开始日期（YYYY-MM-DD）
            until_date: 结束日期（YYYY-MM-DD，可选）
            branch: 分支名称（可选）
            max_pages: 最大页数限制（默认 50 页 = 5000 条提交）
            
        Returns:
            提交记录列表
        """
        encoded = urllib.parse.quote(project_path, safe='')
        commits = []
        page = 1
        
        while page <= max_pages:
            params = {
                'since': f'{since_date}T00:00:00Z',
                'per_page': 100,
                'page': page
            }
            
            if until_date:
                params['until'] = f'{until_date}T23:59:59Z'
            
            if branch:
                params['ref_name'] = branch
            
            data = self.api_get(
                f'/projects/{encoded}/repository/commits',
                params
            )
            
            if not data:
                break
            
            commits.extend(data)
            
            # 如果返回的数据少于 100 条，说明已经是最后一页
            if len(data) < 100:
                break
            
            page += 1
        
        # 如果达到最大页数限制，发出警告
        if page > max_pages:
            print(f"警告：提交记录超过 {max_pages * 100} 条，仅返回前 {len(commits)} 条")
        
        return commits
    
    def get_commit_diff(self, project_path, commit_sha):
        """
        获取提交的文件差异列表
        
        Args:
            project_path: 项目路径
            commit_sha: 提交 SHA
            
        Returns:
            文件差异列表
        """
        encoded = urllib.parse.quote(project_path, safe='')
        
        try:
            return self.api_get(f'/projects/{encoded}/repository/commits/{commit_sha}/diff')
        except Exception:
            return []
