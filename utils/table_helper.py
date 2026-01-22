"""
表格工具类
提供表格的通用操作
"""
from PyQt5.QtWidgets import QTableWidget, QApplication
import csv


class TableHelper:
    """表格助手"""
    
    @staticmethod
    def copy_cell_on_double_click(table, row, column, status_callback=None, skip_columns=None):
        """
        双击单元格复制内容
        
        Args:
            table: QTableWidget 实例
            row: 行号
            column: 列号
            status_callback: 状态回调函数，用于显示消息
            skip_columns: 跳过的列（如操作列）
        """
        if skip_columns and column in skip_columns:
            return
        
        item = table.item(row, column)
        if item:
            text = item.text()
            if text and text != "查询中...":
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                if status_callback:
                    status_callback(f"已复制: {text}", 2000)
    
    @staticmethod
    def adjust_columns_proportionally(table, fixed_columns, available_width):
        """
        按比例调整表格列宽
        
        Args:
            table: QTableWidget 实例
            fixed_columns: 固定列配置 {列号: 宽度}
            available_width: 可用宽度
        """
        # 计算固定列总宽度
        fixed_width = sum(fixed_columns.values())
        content_width = available_width - fixed_width
        
        if content_width <= 0:
            return
        
        # 获取所有非固定列
        total_cols = table.columnCount()
        content_cols = [col for col in range(total_cols) if col not in fixed_columns]
        
        if not content_cols:
            return
        
        # 计算当前内容列总宽度
        current_total = sum(table.columnWidth(col) for col in content_cols)
        
        if current_total > 0:
            # 按比例调整
            scale_factor = content_width / current_total
            for col in content_cols:
                current_width = table.columnWidth(col)
                new_width = max(50, int(current_width * scale_factor))
                table.setColumnWidth(col, new_width)
    
    @staticmethod
    def setup_copy_on_double_click(table, status_callback=None, skip_columns=None):
        """
        设置表格双击复制功能
        
        Args:
            table: QTableWidget 实例
            status_callback: 状态回调函数
            skip_columns: 跳过的列
        """
        table.cellDoubleClicked.connect(
            lambda row, col: TableHelper.copy_cell_on_double_click(
                table, row, col, status_callback, skip_columns
            )
        )
    
    @staticmethod
    def export_to_csv(table, file_path, columns, skip_text=None):
        """
        导出表格到 CSV
        
        Args:
            table: QTableWidget 实例
            file_path: 文件路径
            columns: 要导出的列 {列号: 列名}
            skip_text: 跳过的文本列表（如 ["查询中..."]）
        
        Returns:
            导出的行数
        """
        if skip_text is None:
            skip_text = []
        
        exported_count = 0
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow(columns.values())
            
            # 写入数据
            for row in range(table.rowCount()):
                row_data = []
                skip_row = False
                
                for col in columns.keys():
                    item = table.item(row, col)
                    text = item.text() if item else ''
                    
                    # 检查是否跳过
                    if text in skip_text:
                        skip_row = True
                        break
                    
                    row_data.append(text)
                
                if not skip_row and any(row_data):
                    writer.writerow(row_data)
                    exported_count += 1
        
        return exported_count
