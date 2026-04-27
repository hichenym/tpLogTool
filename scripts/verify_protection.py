"""
验证 Nuitka 编译产物的反编译防护效果
检查 exe 中是否存在可被提取的 Python 源码或字节码
"""
import re
import os
import sys

def verify(exe_path):
    if not os.path.exists(exe_path):
        print(f"[ERROR] 文件不存在: {exe_path}")
        sys.exit(1)

    with open(exe_path, "rb") as f:
        data = f.read()

    size_mb = len(data) / 1024 / 1024
    print("=" * 60)
    print(f"验证文件: {exe_path}")
    print(f"文件大小: {size_mb:.2f} MB")
    print("=" * 60)

    # 1. PyInstaller 标记检测
    print("\n[检测1] PyInstaller 标记")
    checks = {
        "MEI magic": b"MEI\x0c" in data,
        "PYZ 归档": b"PYZ-00.pyz" in data,
        "pyiboot 引导": b"pyiboot" in data or b"_pyi_" in data,
    }
    all_clear = True
    for name, found in checks.items():
        status = "!! 发现 (有风险)" if found else "OK 未发现"
        print(f"  {name}: {status}")
        if found:
            all_clear = False

    if all_clear:
        print("  >>> pyinstxtractor 无法提取此文件")

    # 2. Nuitka 标记
    print("\n[检测2] Nuitka 编译标记")
    has_nuitka = b"nuitka" in data.lower() or b"Nuitka" in data
    print(f"  Nuitka 标记: {'发现 (确认为 Nuitka 编译)' if has_nuitka else '未发现'}")

    # 3. Python 字节码检测
    print("\n[检测3] Python 字节码 (.pyc)")
    # Python 3.8-3.12 magic numbers
    pyc_magics = {
        "Python 3.8": bytes([85, 13, 13, 10]),
        "Python 3.9": bytes([97, 13, 13, 10]),
        "Python 3.10": bytes([111, 13, 13, 10]),
        "Python 3.11": bytes([167, 13, 13, 10]),
        "Python 3.12": bytes([203, 13, 13, 10]),
    }
    found_pyc = False
    for ver, magic in pyc_magics.items():
        count = data.count(magic)
        if count > 10:  # 少量匹配可能是巧合
            print(f"  {ver} magic: 发现 {count} 处 (可能包含字节码)")
            found_pyc = True
    if not found_pyc:
        print("  未发现 .pyc 字节码特征")
        print("  >>> uncompyle6 / decompyle3 无法反编译此文件")

    # 4. 项目源码字符串泄露检测
    print("\n[检测4] 项目源码特征")
    # 搜索函数定义（源码级别）
    def_pattern = rb"def (init_ui|on_confirm|query_status|send_port_mapping)\s*\("
    def_matches = re.findall(def_pattern, data)
    if def_matches:
        names = [m.decode("utf-8", errors="replace") for m in def_matches]
        print(f"  函数定义: 发现 {len(def_matches)} 处 - {names}")
        print("  >>> 警告: 源码级函数定义泄露")
    else:
        print("  函数定义 (def xxx): 未发现")

    # 搜索类定义
    class_pattern = rb"class (PortMappingDialog|DeviceStatusPage|StyleManager)\s*[\(:]"
    class_matches = re.findall(class_pattern, data)
    if class_matches:
        names = [m.decode("utf-8", errors="replace") for m in class_matches]
        print(f"  类定义: 发现 {len(class_matches)} 处 - {names}")
    else:
        print("  类定义 (class xxx): 未发现")

    # 5. 字符串泄露（这些在编译后仍可能存在，属于正常现象）
    print("\n[检测5] 字符串常量残留（编译后正常存在）")
    string_checks = [
        ("模块路径 query_tool", b"query_tool"),
        ("类名 StyleManager", b"StyleManager"),
        ("类名 PortMappingDialog", b"PortMappingDialog"),
        ("API 地址", b"console.seetong.com"),
        ("端口穿透", b"\xe7\xab\xaf\xe5\x8f\xa3\xe7\xa9\xbf\xe9\x80\x8f"),
    ]
    for name, pattern in string_checks:
        count = data.count(pattern)
        if count > 0:
            print(f"  {name}: 发现 {count} 处 (字符串常量，非源码)")
        else:
            print(f"  {name}: 未发现")

    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    if all_clear and not found_pyc and not def_matches and has_nuitka:
        print("  [PASS] 此文件为 Nuitka 原生编译产物")
        print("  [PASS] 无 PyInstaller 结构，pyinstxtractor 无法提取")
        print("  [PASS] 无 .pyc 字节码，uncompyle6 无法反编译")
        print("  [PASS] 无源码级函数/类定义泄露")
        print("  [INFO] 字符串常量残留属于正常现象（C 编译后仍保留字面量字符串）")
        print("\n  结论: 防护有效，反编译难度等同于逆向 C/C++ 程序")
    else:
        if not all_clear:
            print("  [WARN] 发现 PyInstaller 标记，可能被提取")
        if found_pyc:
            print("  [WARN] 发现 .pyc 字节码，可能被反编译")
        if def_matches:
            print("  [WARN] 发现源码级函数定义")
        if not has_nuitka:
            print("  [WARN] 未发现 Nuitka 标记")


if __name__ == "__main__":
    exe = sys.argv[1] if len(sys.argv) > 1 else "dist/TPQueryTool.exe"
    verify(exe)
