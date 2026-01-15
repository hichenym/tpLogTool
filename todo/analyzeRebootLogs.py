#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析远程日志中2026年1月6日及之后的reboot日志
"""
import os
import re
from datetime import datetime
from pathlib import Path

def extract_sn(filename):
    """从文件名中提取SN号（中间的16位字符）"""
    parts = filename.split('_')
    if len(parts) >= 2:
        return parts[1]
    return None

def parse_log_date(line):
    """从日志行中提取日期"""
    # 尝试匹配常见的日期格式
    date_patterns = [
        r'(\d{4})-(\d{2})-(\d{2})',  # YYYY-MM-DD
        r'(\d{4})/(\d{2})/(\d{2})',  # YYYY/MM/DD
        r'\[(\d{4})-(\d{2})-(\d{2})',  # [YYYY-MM-DD
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, line)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(year, month, day)
            except:
                continue
    return None

def is_reboot_line(line):
    """检查行是否包含reboot关键字"""
    return bool(re.search(r'reboot', line, re.IGNORECASE))

def is_after_target_date(log_date):
    """检查日期是否在2026年1月6日及之后"""
    if log_date is None:
        return False
    target_date = datetime(2026, 1, 6)
    return log_date >= target_date

def analyze_logs():
    """分析所有日志文件"""
    log_dir = "远程日志"
    results = {}
    
    if not os.path.exists(log_dir):
        print(f"错误：{log_dir} 目录不存在")
        return
    
    # 遍历所有日志文件
    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        
        if not os.path.isfile(filepath):
            continue
        
        sn = extract_sn(filename)
        if not sn:
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reboot_lines = []
                for line in f:
                    if is_reboot_line(line):
                        log_date = parse_log_date(line)
                        if is_after_target_date(log_date):
                            reboot_lines.append(line.strip())
                
                if reboot_lines:
                    if sn not in results:
                        results[sn] = []
                    results[sn].extend(reboot_lines)
        
        except Exception as e:
            print(f"处理文件 {filename} 时出错: {e}")
    
    return results

def write_report(results):
    """生成分析报告"""
    report_file = "reboot_analysis_report.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("远程日志重启分析报告\n")
        f.write("分析时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write("分析范围: 2026年1月6日及之后的reboot日志\n")
        f.write("=" * 80 + "\n\n")
        
        if not results:
            f.write("未找到符合条件的重启日志\n")
            print("未找到符合条件的重启日志")
            return
        
        total_devices = len(results)
        total_logs = sum(len(logs) for logs in results.values())
        
        f.write(f"统计信息:\n")
        f.write(f"  设备总数: {total_devices}\n")
        f.write(f"  重启日志总数: {total_logs}\n")
        f.write("=" * 80 + "\n\n")
        
        # 按SN号排序
        for idx, (sn, logs) in enumerate(sorted(results.items()), 1):
            f.write(f"设备 {idx}: {sn}\n")
            f.write(f"重启日志数: {len(logs)}\n")
            f.write("-" * 80 + "\n")
            
            for log in logs:
                f.write(log + "\n")
            
            f.write("=" * 80 + "\n\n")
        
        print(f"报告已生成: {report_file}")
        print(f"统计: 发现 {total_devices} 个设备的 {total_logs} 条重启日志")

if __name__ == '__main__':
    print("开始分析日志文件...")
    results = analyze_logs()
    write_report(results)
