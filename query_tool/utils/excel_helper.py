"""
Excel 导出辅助工具
提供 Excel 文件生成功能
"""
import zipfile
import xml.etree.ElementTree as ET


def create_gitlab_xlsx(commits, output_path, keywords=None):
    """
    创建 GitLab 提交记录的 Excel 文件
    
    Args:
        commits: 提交记录列表
        output_path: 输出文件路径
        keywords: 关键词字符串（用分号分隔）
        
    Raises:
        Exception: 文件操作失败时抛出异常
    """
    import os
    import shutil
    
    try:
        # 检查输出目录是否存在
        output_dir = os.path.dirname(output_path) or '.'
        if not os.path.exists(output_dir):
            raise Exception(f"输出目录不存在: {output_dir}")
        
        # 检查磁盘空间（至少需要 10MB）
        stat = shutil.disk_usage(output_dir)
        if stat.free < 10 * 1024 * 1024:
            raise Exception(f"磁盘空间不足（需要 10MB，可用 {stat.free / 1024 / 1024:.1f}MB）")
        
        # 检查文件是否已存在且可写
        if os.path.exists(output_path):
            if not os.access(output_path, os.W_OK):
                raise Exception(f"文件已存在且无写入权限: {output_path}")
        
        NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        
        ET.register_namespace('', NS)
        ET.register_namespace('r', NS_R)
        
        # 解析关键词
        keyword_list = []
        if keywords:
            keyword_list = [k.strip() for k in keywords.split(';') if k.strip()]
        
        # 准备数据
        data = []
        for c in commits:
            date_str = c['committed_date'][:19].replace('T', ' ')
            message = c['message'].strip() if c['message'] else ''
            author = c.get('author_name', '')
            
            # 排除前面有合并标识的提交（如【合并】、[合并]等）
            if message and (message.startswith('【合并】') or message.startswith('[合并]') or 
                           message.startswith('Merge ') or message.startswith('merge ')):
                continue
            
            message_lower = message.lower()
            highlight = any(kw.lower() in message_lower for kw in keyword_list) if keyword_list else False
            
            # 获取文件变化列表
            files_changed = c.get('files_changed', '')
            
            data.append({
                'commit_short': c['short_id'],
                'commit_full': c['id'],
                'web_url': c['web_url'],
                'message': message,
                'author': author,
                'date': date_str,
                'files_changed': files_changed,
                'highlight': highlight
            })
        
        # 构建共享字符串表
        shared_strings = []
        for row in data:
            for val in [row['commit_short'], row['message'], row['author'], row['date'], row['files_changed']]:
                if val not in shared_strings:
                    shared_strings.append(val)
        
        # 创建共享字符串 XML
        sst = ET.Element(f'{{{NS}}}sst')
        sst.set('count', str(len(data) * 5))
        sst.set('uniqueCount', str(len(shared_strings)))
        
        for s in shared_strings:
            si = ET.SubElement(sst, f'{{{NS}}}si')
            t = ET.SubElement(si, f'{{{NS}}}t')
            t.text = s
        
        # 创建工作表
        worksheet = ET.Element(f'{{{NS}}}worksheet')
        hyperlinks = ET.SubElement(worksheet, f'{{{NS}}}hyperlinks')
        sheet_data = ET.SubElement(worksheet, f'{{{NS}}}sheetData')
        
        # 填充数据行
        for row_idx, row_data in enumerate(data, start=1):
            row_elem = ET.SubElement(sheet_data, f'{{{NS}}}row')
            row_elem.set('r', str(row_idx))
            
            # 根据是否高亮选择样式
            style_normal = '2' if row_data['highlight'] else '0'
            style_link = '3' if row_data['highlight'] else '1'
            
            # 提交 ID（带超链接）
            cell_a = ET.SubElement(row_elem, f'{{{NS}}}c')
            cell_a.set('r', f'A{row_idx}')
            cell_a.set('t', 's')
            cell_a.set('s', style_link)
            v_a = ET.SubElement(cell_a, f'{{{NS}}}v')
            v_a.text = str(shared_strings.index(row_data['commit_short']))
            
            # 添加超链接
            hyperlink = ET.SubElement(hyperlinks, f'{{{NS}}}hyperlink')
            hyperlink.set('ref', f'A{row_idx}')
            hyperlink.set(f'{{{NS_R}}}id', f'rId{row_idx}')
            
            # 提交消息
            cell_b = ET.SubElement(row_elem, f'{{{NS}}}c')
            cell_b.set('r', f'B{row_idx}')
            cell_b.set('t', 's')
            cell_b.set('s', style_normal)
            v_b = ET.SubElement(cell_b, f'{{{NS}}}v')
            v_b.text = str(shared_strings.index(row_data['message']))
            
            # 提交者
            cell_c = ET.SubElement(row_elem, f'{{{NS}}}c')
            cell_c.set('r', f'C{row_idx}')
            cell_c.set('t', 's')
            cell_c.set('s', style_normal)
            v_c = ET.SubElement(cell_c, f'{{{NS}}}v')
            v_c.text = str(shared_strings.index(row_data['author']))
            
            # 提交时间
            cell_d = ET.SubElement(row_elem, f'{{{NS}}}c')
            cell_d.set('r', f'D{row_idx}')
            cell_d.set('t', 's')
            cell_d.set('s', style_normal)
            v_d = ET.SubElement(cell_d, f'{{{NS}}}v')
            v_d.text = str(shared_strings.index(row_data['date']))
            
            # 文件变化
            cell_e = ET.SubElement(row_elem, f'{{{NS}}}c')
            cell_e.set('r', f'E{row_idx}')
            cell_e.set('t', 's')
            cell_e.set('s', style_normal)
            v_e = ET.SubElement(cell_e, f'{{{NS}}}v')
            v_e.text = str(shared_strings.index(row_data['files_changed']))
        
        # 调整超链接位置
        worksheet.remove(hyperlinks)
        worksheet.append(hyperlinks)
        
        # 创建超链接关系 XML
        rels_root = ET.Element('Relationships')
        rels_root.set('xmlns', 'http://schemas.openxmlformats.org/package/2006/relationships')
        
        for row_idx, row_data in enumerate(data, start=1):
            rel = ET.SubElement(rels_root, 'Relationship')
            rel.set('Id', f'rId{row_idx}')
            rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink')
            rel.set('Target', row_data['web_url'])
            rel.set('TargetMode', 'External')
        
        # Excel 文件结构 XML
        content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''

        rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''

        workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''

        workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

        styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2">
<font><sz val="11"/><name val="Calibri"/></font>
<font><sz val="11"/><color rgb="FF0000FF"/><u/><name val="Calibri"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF8CDDFA"/><bgColor rgb="FF8CDDFA"/></patternFill></fill>
</fills>
<borders count="2">
<border/>
<border><left style="thin"><color auto="1"/></left><right style="thin"><color auto="1"/></right><top style="thin"><color auto="1"/></top><bottom style="thin"><color auto="1"/></bottom></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="4">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="0" fillId="2" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
</cellXfs>
</styleSheet>'''

        # 创建 ZIP 文件（Excel 格式）
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', content_types)
                zf.writestr('_rels/.rels', rels)
                zf.writestr('xl/workbook.xml', workbook)
                zf.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
                zf.writestr('xl/styles.xml', styles)
                zf.writestr('xl/sharedStrings.xml', 
                           '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + 
                           ET.tostring(sst, encoding='unicode'))
                zf.writestr('xl/worksheets/sheet1.xml', 
                           '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + 
                           ET.tostring(worksheet, encoding='unicode'))
                zf.writestr('xl/worksheets/_rels/sheet1.xml.rels', 
                           '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + 
                           ET.tostring(rels_root, encoding='unicode'))
        except Exception as e:
            # 清理部分写入的文件
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            raise Exception(f"Excel 导出失败: {str(e)}")
    except Exception as e:
        raise Exception(f"Excel 导出失败: {str(e)}")
