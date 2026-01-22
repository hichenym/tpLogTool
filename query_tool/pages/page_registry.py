"""
页面注册表
统一管理所有页面的注册和创建
"""


class PageRegistry:
    """页面注册表"""
    _pages = []  # 存储页面配置
    
    @classmethod
    def register(cls, page_class, name, order=0, icon=None):
        """
        注册页面
        
        Args:
            page_class: 页面类
            name: 页面名称（显示在菜单上）
            order: 排序顺序（数字越小越靠前）
            icon: 页面图标路径（可选）
        """
        cls._pages.append({
            'class': page_class,
            'name': name,
            'order': order,
            'icon': icon
        })
        # 按order排序
        cls._pages.sort(key=lambda x: x['order'])
    
    @classmethod
    def get_all_pages(cls):
        """获取所有注册的页面配置"""
        return cls._pages
    
    @classmethod
    def create_page(cls, page_class, parent=None):
        """创建页面实例"""
        return page_class(parent)
    
    @classmethod
    def clear(cls):
        """清空注册表（用于测试）"""
        cls._pages = []


# 装饰器：简化页面注册
def register_page(name, order=0, icon=None):
    """
    页面注册装饰器
    
    使用示例：
    @register_page("设备状态", order=1, icon=":/icon/system/device.png")
    class DeviceStatusPage(BasePage):
        pass
    
    Args:
        name: 页面名称
        order: 排序顺序
        icon: 图标路径（可选）
    """
    def decorator(page_class):
        PageRegistry.register(page_class, name, order, icon)
        return page_class
    return decorator
