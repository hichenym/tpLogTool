# 打包说明

## 当前打包方案

当前项目统一使用 **PyInstaller** 打包，入口脚本为：

- [scripts/build.py](/D:/GIT/tpLogTool/scripts/build.py)

## 快速打包

```bash
python scripts/build.py
```

调试模式：

```bash
python scripts/build.py --debug
```

脚本会自动：

1. 更新 `query_tool/version.py` 中的 `BUILD_DATE`
2. 清理旧的 PyInstaller 构建目录
3. 调用 PyInstaller 生成单文件 `exe`
4. 输出打包结果与文件大小

## 打包前检查清单

- [ ] 已激活虚拟环境
- [ ] `pip install -r requirements.txt`
- [ ] 本地 `python run.py` 可正常启动
- [ ] 调试页、命令页相关改动已验证
- [ ] `resources/icon_res.py` 已和 `icon_res.qrc` 同步
- [ ] 版本号和编译日期已确认
- [ ] 相关文档已更新

## 关键打包资源

### 图标资源

打包会包含：

```text
resources/icons/
```

### SIOT 动态库

调试页与命令页依赖的 DLL 已统一放在：

```text
query_tool/dll/
```

当前打包脚本会逐个校验并显式打入以下必要 DLL：

- `Funclib.dll`
- `libsiot.dll`
- `libtps_crypt.dll`
- `libgcc_s_seh-1.dll`
- `libstdc++-6.dll`
- `libwinpthread-1.dll`

说明：

- 当前项目已经不再依赖旧的 `windows-siot-command-client` 目录
- 如果打包后调试页或命令页无法连接，优先检查 `query_tool/dll` 是否被带入产物

## PyInstaller 关键参数

当前核心参数包括：

- `--onefile`
- `--name TPQueryTool`
- `--icon ./resources/icons/app/logo.ico`
- `--hidden-import ddddocr`
- `--hidden-import onnxruntime`
- `--hidden-import cv2`
- `--hidden-import numpy`
- `--hidden-import pkg_resources`
- `--collect-all ddddocr`
- `--collect-binaries onnxruntime`
- `--collect-data onnxruntime`

## 打包输出

```text
dist/
└── TPQueryTool.exe
```

中间目录：

- `build`
- `TPQueryTool.spec`

## 打包后建议测试

### 基础验证

- [ ] 程序能正常启动
- [ ] 图标显示正常
- [ ] 设置页能正常打开
- [ ] 主题切换正常

### 设备相关

- [ ] 设备页查询正常
- [ ] 记录页查询正常
- [ ] 固件页查询正常

### 调试页专项

- [ ] 能读取 Seetong 账号
- [ ] 输入 SN 后可正常连接设备
- [ ] 连接中可以取消
- [ ] 连接成功后可发送命令
- [ ] `GetSystemCfg` 可下载文件
- [ ] 下载目录双击打开正常

### 命令页专项

- [ ] 可批量执行命令
- [ ] 可下载 `GetSystemCfg` 文件
- [ ] 运行中可取消
- [ ] 结果表格显示正常

## 常见问题

### Q1: 打包成功但调试页连接失败

优先检查：

1. `query_tool/dll` 是否已随包带入
2. DLL 是否齐全
3. Seetong 账号是否已配置

### Q2: 打包后图标不显示

请确认：

1. `resources/icon_res.qrc` 已更新
2. `resources/icon_res.py` 已重新生成
3. `resources/icons/app/logo.ico` 文件存在

### Q3: 打包后命令页运行时报 DLL 错误

通常说明：

- `query_tool/dll` 未被正确打包
- 或 DLL 缺失/损坏

### Q4: 构建失败提示缺少 PyInstaller

```bash
pip install -r requirements.txt
```

最后更新时间：2026-06-22
