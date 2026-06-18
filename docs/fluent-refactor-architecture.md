# Fluent 重构架构说明

## 当前项目结构

- `query_tool/main.py`
  负责应用启动、主窗体、页面切换、系统托盘、更新流程。
- `query_tool/pages/`
  业务页面层。每个页面继承 `BasePage`，通过 `PageRegistry` 注册。
- `query_tool/widgets/`
  复用对话框和自定义控件层。
- `query_tool/utils/`
  账号配置、线程、接口访问、日志、主题、打包运行时支撑。

## 旧架构问题

- 主框架仍是 `QMainWindow + 自定义菜单按钮 + 全局 QSS`，并未真正使用 Fluent Widgets 的导航壳层。
- 主题系统只维护本项目 token，未和 Fluent 组件主题同步，导致后续替换控件时会出现双套主题状态。
- 页面注册表只有名称、顺序、图标，不足以支撑 Fluent 导航路由和后续多端壳层切换。
- 打包脚本未显式包含 Fluent 相关包和资源，切换框架后发布存在缺件风险。

## 本轮重构落点

- 新增 `query_tool/ui/fluent.py`
  作为 Fluent 兼容层，集中管理 `qfluentwidgets` 导入、主题同步和图标回退。
- 扩展 `PageRegistry`
  为页面补充 `route_key`，主窗体可直接基于注册表生成导航结构。
- 改造 `ThemeManager`
  主题切换时同时同步 Fluent 主题，避免新旧控件主题割裂。
- 改造 `MainWindow`
  用 `NavigationInterface` 替换顶部旧菜单条，页面导航、设置、主题切换、任务中心统一纳入 Fluent 导航壳。
- 更新打包脚本
  继续沿用现有 Nuitka / PyInstaller 路径，但显式纳入 `qfluentwidgets`、`qframelesswindow` 和相关资源。

## 后续迭代方向

- 把 `widgets/` 下的模态对话框逐步替换为 Fluent 对话框、InfoBar、输入控件。
- 将页面内仍然依赖全局 QSS 的标准控件，逐批迁移到 Fluent 控件或统一适配层。
- 把 Windows 专有能力（标题栏、托盘、注册表）继续收敛到壳层和平台适配层，为 Android 构建保留业务层复用空间。
