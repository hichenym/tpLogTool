# 文件哈希验证功能指南

## 概述

文件哈希验证功能用于确保下载文件的完整性和安全性，特别是在断点续传场景下，可以有效防止文件损坏或被篡改。

## 功能特点

### 1. 完整性验证

- 下载完成后自动验证文件哈希
- 支持 SHA256、MD5 等多种哈希算法
- 验证失败自动重试下载

### 2. 断点续传支持

- 验证部分下载文件的有效性
- 检测损坏的临时文件并自动清理
- 保护断点续传的可靠性

### 3. 安全保障

- 防止文件在传输过程中被篡改
- 确保下载的文件与发布的文件一致
- 提供可追溯的验证日志

## 工作流程

### 下载流程

```
开始下载
  ↓
检查临时文件
  ↓
验证部分文件（如果存在）
  ├─ 文件太小（<1KB）→ 删除，重新下载
  ├─ 文件正常 → 断点续传
  └─ 文件不存在 → 开始下载
  ↓
下载文件
  ↓
下载完成
  ↓
验证完整文件哈希
  ├─ 验证通过 → 重命名为正式文件
  ├─ 验证失败 → 删除文件，重试下载
  └─ 无哈希值 → 跳过验证
  ↓
完成
```

## 配置说明

### version.json 配置

在 `version.json` 中添加哈希相关字段：

```json
{
  "version": "3.1.0",
  "download_url": "https://github.com/.../TPQueryTool.exe",
  "file_size_bytes": 181465088,
  "file_hash": "a1b2c3d4e5f6...",
  "hash_algorithm": "sha256",
  "checksum_url": "https://github.com/.../TPQueryTool.exe.sha256"
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| file_hash | string | 可选 | 文件的哈希值（十六进制字符串） |
| hash_algorithm | string | 可选 | 哈希算法（sha256, md5等），默认 sha256 |
| checksum_url | string | 可选 | 校验和文件的下载地址 |
| file_size_bytes | number | 可选 | 文件大小（字节），用于验证 |

## 使用方法

### 自动验证

程序会自动使用 `version.json` 中的哈希值进行验证：

```python
# UpdateManager 会自动传递哈希值
update_manager.download_update(version_info)
```

### 手动验证

如果需要手动验证文件：

```python
from query_tool.utils.update_downloader import DownloadThread

# 创建下载线程
thread = DownloadThread(
    url="https://example.com/file.exe",
    save_path="/path/to/save.exe",
    expected_hash="a1b2c3d4e5f6...",
    hash_algorithm="sha256"
)

# 验证文件
is_valid = thread._verify_complete_file("/path/to/file.exe")
```

### 计算文件哈希

```python
from query_tool.utils.update_downloader import DownloadThread

thread = DownloadThread("", "")
file_hash = thread._calculate_file_hash("/path/to/file.exe", "sha256")
print(f"SHA256: {file_hash}")
```

## 验证逻辑

### 部分文件验证

在断点续传前验证临时文件：

```python
def _verify_partial_file(self, temp_path: str) -> bool:
    """验证部分下载的文件"""
    
    # 1. 文件不存在 → 可以开始下载
    if not os.path.exists(temp_path):
        return True
    
    # 2. 文件太小（<1KB）→ 可能损坏，删除
    file_size = os.path.getsize(temp_path)
    if file_size < 1024:
        os.remove(temp_path)
        return True
    
    # 3. 文件正常 → 可以断点续传
    return True
```

### 完整文件验证

下载完成后验证完整文件：

```python
def _verify_complete_file(self, file_path: str) -> bool:
    """验证完整文件哈希"""
    
    # 1. 没有期望哈希值 → 跳过验证
    if not self.expected_hash:
        return True
    
    # 2. 计算实际哈希值
    actual_hash = self._calculate_file_hash(file_path, self.hash_algorithm)
    
    # 3. 比较哈希值
    if actual_hash.lower() == self.expected_hash.lower():
        return True  # 验证通过
    else:
        return False  # 验证失败
```

## 错误处理

### 哈希验证失败

当哈希验证失败时：

1. 记录错误日志
2. 删除损坏的文件
3. 如果还有重试机会，自动重试下载
4. 达到最大重试次数后，返回失败

```python
# 验证文件哈希
if not self._verify_complete_file(temp_path):
    logger.error("文件哈希验证失败，删除损坏的文件")
    os.remove(temp_path)
    
    # 如果还有重试机会，继续重试
    if attempt < max_retries - 1:
        logger.info("将重新下载...")
        continue
    else:
        self.finished.emit(False, "文件哈希验证失败，文件可能已损坏")
        return
```

### 部分文件损坏

当检测到部分文件损坏时：

1. 记录警告日志
2. 删除损坏的临时文件
3. 重新开始下载

```python
if file_size < 1024:
    logger.warning(f"临时文件太小 ({file_size} 字节)，可能已损坏，将重新下载")
    os.remove(temp_path)
    return True
```

## 日志输出

### 正常流程

```
INFO - 开始下载更新: TPQueryTool_3.1.0.exe
INFO - 将使用 SHA256 验证文件完整性
INFO - 期望哈希: a1b2c3d4e5f6...
INFO - 发现未完成的下载，已下载 50.00 MB，尝试断点续传
INFO - 服务器支持断点续传，继续下载
INFO - 总大小: 173.06 MB, 已下载: 50.00 MB
INFO - 下载完成，开始验证文件...
INFO - 开始验证文件哈希 (SHA256)...
INFO - 期望哈希: a1b2c3d4e5f6...
INFO - 实际哈希: a1b2c3d4e5f6...
INFO - ✓ 文件哈希验证通过
INFO - 下载完成: /path/to/TPQueryTool_3.1.0.exe (173.06 MB)
```

### 验证失败

```
ERROR - ✗ 文件哈希验证失败，文件可能已损坏
ERROR - 文件哈希验证失败，删除损坏的文件
INFO - 将重新下载...
```

### 部分文件损坏

```
WARNING - 临时文件太小 (100 字节)，可能已损坏，将重新下载
INFO - 开始下载: https://...
```

## GitHub Actions 集成

### 自动计算哈希

在 GitHub Actions 工作流中自动计算文件哈希：

```yaml
- name: Calculate file hash
  run: |
    $hash = (Get-FileHash -Path "dist/TPQueryTool.exe" -Algorithm SHA256).Hash
    echo "FILE_HASH=$hash" >> $env:GITHUB_ENV
    echo "File hash: $hash"

- name: Create checksum file
  run: |
    $hash = (Get-FileHash -Path "dist/TPQueryTool.exe" -Algorithm SHA256).Hash
    "$hash  TPQueryTool.exe" | Out-File -FilePath "dist/TPQueryTool.exe.sha256" -Encoding ASCII
```

### 更新 version.json

```yaml
- name: Update version.json with hash
  run: |
    $versionJson = Get-Content version.json | ConvertFrom-Json
    $versionJson.file_hash = $env:FILE_HASH
    $versionJson | ConvertTo-Json -Depth 10 | Set-Content version.json
```

## 测试验证

### 运行测试脚本

```bash
python test_hash_verification.py
```

### 测试内容

1. 哈希计算功能测试
2. 哈希验证功能测试
3. 部分文件验证测试
4. version.json 哈希读取测试

### 测试结果示例

```
============================================================
测试哈希计算功能
============================================================
SHA256: 18fe53c99511c8be3aba63a17a876c1f49090d1b89fce69c1463a9a59c5ae9b6
MD5: 791b69568971cab66444a98ea1eb6f5f
✓ 哈希计算功能正常

============================================================
测试哈希验证功能
============================================================
✓ 测试1: 正确哈希验证通过
✓ 测试2: 错误哈希验证失败（符合预期）
✓ 测试3: 无哈希值时跳过验证

============================================================
测试部分文件验证功能
============================================================
测试1 - 文件不存在: ✓ 通过
测试2 - 文件太小: ✓ 通过
测试3 - 正常大小文件: ✓ 通过
```

## 安全建议

### 1. 使用 HTTPS

确保下载链接使用 HTTPS 协议：

```json
{
  "download_url": "https://github.com/.../TPQueryTool.exe"
}
```

### 2. 使用强哈希算法

推荐使用 SHA256 或更强的算法：

```json
{
  "hash_algorithm": "sha256"
}
```

避免使用 MD5（已被证明不安全）。

### 3. 保护 version.json

- 使用 HTTPS 传输 version.json
- 考虑对 version.json 进行签名
- 定期更新哈希值

### 4. 验证失败处理

- 不要忽略验证失败
- 记录详细的错误日志
- 通知用户验证失败

## 性能考虑

### 哈希计算性能

- SHA256 计算速度：约 200-300 MB/s
- 对于 173 MB 的文件，计算时间约 0.5-1 秒
- 使用 8KB 块大小平衡内存和性能

### 优化建议

1. **异步计算**：在后台线程计算哈希
2. **缓存结果**：缓存已验证文件的哈希值
3. **增量验证**：对于大文件，考虑分块验证

## 故障排查

### 问题 1：验证总是失败

**可能原因**：
- 哈希值不正确
- 文件在传输过程中被修改
- 哈希算法不匹配

**解决方法**：
1. 检查 version.json 中的哈希值
2. 手动计算文件哈希并对比
3. 确认哈希算法一致

### 问题 2：断点续传后验证失败

**可能原因**：
- 服务器不支持断点续传（返回 200 而不是 206）
- 临时文件已损坏

**解决方法**：
1. 检查服务器是否支持 Range 请求
2. 删除临时文件重新下载
3. 查看日志确认问题

### 问题 3：性能问题

**可能原因**：
- 文件太大
- 磁盘 I/O 慢

**解决方法**：
1. 增加块大小（8KB → 64KB）
2. 使用 SSD 存储临时文件
3. 考虑异步计算

## 相关文档

- [断点续传功能](test_resume_download.py)
- [下载重试机制](test_download_retry.py)
- [自动更新功能总结](update-feature-summary.md)
- [GitHub Actions 指南](github-actions-guide.md)

## 未来改进

### 可能的增强

1. **分块哈希**：
   - 支持大文件的分块哈希验证
   - 断点续传时验证已下载部分的哈希

2. **多哈希支持**：
   - 同时提供 SHA256 和 SHA512
   - 增强安全性

3. **签名验证**：
   - 使用数字签名验证文件
   - 防止中间人攻击

4. **增量更新**：
   - 只下载文件差异部分
   - 使用二进制差分算法

## 总结

文件哈希验证功能为自动更新系统提供了重要的安全保障：

- ✅ 确保文件完整性
- ✅ 支持断点续传
- ✅ 自动重试机制
- ✅ 详细的日志记录
- ✅ 灵活的配置选项

通过合理使用哈希验证，可以大大提高自动更新的可靠性和安全性。
