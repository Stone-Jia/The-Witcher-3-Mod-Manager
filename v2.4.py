#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《巫师3：狂猎》Mod 智能管理器 v2.4
优化版 - 全窗口拖拽、统一安装、精简菜单
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
import json
import os
import sys
import hashlib
import shutil
import threading
import zipfile
import tempfile
import winreg
import subprocess
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import traceback
import logging
import re

# 尝试导入拖拽支持库
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    logging.warning("未安装tkinterdnd2，拖拽功能将不可用。请运行: pip install tkinterdnd2")

# 尝试导入rar支持库
try:
    import rarfile
    HAS_RARFILE = True
except ImportError:
    HAS_RARFILE = False
    logging.warning("未安装rarfile，RAR支持将不可用。请运行: pip install rarfile")

# 尝试导入7z支持库
try:
    import py7zr
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False
    logging.warning("未安装py7zr，7Z支持将不可用。请运行: pip install py7zr")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='mod_manager.log',
    filemode='a'
)

# 获取程序运行目录
if getattr(sys, 'frozen', False):
    APPLICATION_PATH = os.path.dirname(sys.executable)
else:
    APPLICATION_PATH = os.path.dirname(os.path.abspath(__file__))

class SteamGameLocator:
    """Steam游戏定位器"""
    
    def __init__(self):
        self.steam_paths = []
        self.witcher3_path = None
        self.mod_folder = None
        
    def find_steam_installation(self):
        """查找Steam安装路径"""
        steam_paths = []
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                r"SOFTWARE\WOW6432Node\Valve\Steam")
            steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
            steam_paths.append(steam_path)
            winreg.CloseKey(key)
        except:
            pass
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                r"SOFTWARE\Valve\Steam")
            steam_path = winreg.QueryValueEx(key, "InstallPath")[0]
            steam_paths.append(steam_path)
            winreg.CloseKey(key)
        except:
            pass
        
        common_paths = [
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
            r"D:\Steam",
            r"E:\Steam",
            r"D:\Program Files (x86)\Steam",
            r"E:\Program Files (x86)\Steam",
        ]
        
        for path in common_paths:
            if os.path.exists(path) and path not in steam_paths:
                steam_paths.append(path)
        
        self.steam_paths = steam_paths
        return steam_paths
    
    def find_witcher3_installation(self):
        """查找巫师3游戏安装路径"""
        witcher3_paths = []
        
        for steam_path in self.steam_paths:
            library_folders_file = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
            if os.path.exists(library_folders_file):
                try:
                    with open(library_folders_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    library_paths = re.findall(r'"path"\s+"([^"]+)"', content)
                    
                    for lib_path in library_paths:
                        lib_path = lib_path.replace("\\\\", "\\")
                        witcher_path = os.path.join(lib_path, "steamapps", "common", "The Witcher 3")
                        if os.path.exists(witcher_path):
                            witcher3_paths.append(witcher_path)
                            
                        witcher_path_goty = os.path.join(lib_path, "steamapps", "common", "The Witcher 3 - Game of the Year Edition")
                        if os.path.exists(witcher_path_goty):
                            witcher3_paths.append(witcher_path_goty)
                except:
                    pass
        
        common_witcher_paths = [
            r"C:\Program Files (x86)\Steam\steamapps\common\The Witcher 3",
            r"C:\Program Files\Steam\steamapps\common\The Witcher 3",
            r"D:\Steam\steamapps\common\The Witcher 3",
            r"E:\Steam\steamapps\common\The Witcher 3",
            r"D:\Games\The Witcher 3",
            r"E:\Games\The Witcher 3",
            r"C:\Games\The Witcher 3",
        ]
        
        for path in common_witcher_paths:
            if os.path.exists(path) and path not in witcher3_paths:
                witcher3_paths.append(path)
        
        self.witcher3_path = witcher3_paths[0] if witcher3_paths else None
        return witcher3_paths
    
    def find_mod_folder(self):
        """查找Mod文件夹"""
        if not self.witcher3_path:
            self.find_witcher3_installation()
        
        if not self.witcher3_path:
            return None
        
        possible_mod_folders = [
            os.path.join(self.witcher3_path, "mods"),
            os.path.join(self.witcher3_path, "Mods"),
            os.path.join(self.witcher3_path, "MODS"),
        ]
        
        for mod_folder in possible_mod_folders:
            if os.path.exists(mod_folder):
                self.mod_folder = mod_folder
                return mod_folder
        
        default_mod_folder = os.path.join(self.witcher3_path, "mods")
        try:
            os.makedirs(default_mod_folder, exist_ok=True)
            self.mod_folder = default_mod_folder
            return default_mod_folder
        except:
            return None

class ModConflictDetector:
    """Mod冲突检测器"""
    
    def __init__(self):
        self.file_type_patterns = {
            'script': ['.ws', '.lua', '.script', '.reds'],
            'texture': ['.dds', '.png', '.tga', '.jpg', '.bmp'],
            'mesh': ['.w2mesh', '.w2ent', '.w2rig', '.fbx'],
            'animation': ['.w2anims', '.w2beh', '.w2rig'],
            'definition': ['.xml', '.csv', '.json', '.cfg', '.ini'],
            'bundle': ['.bundle', '.w2scene', '.w2quest'],
            'sound': ['.wav', '.ogg', '.mp3'],
        }
        
        self.critical_files = [
            'player.ws', 'r4player.ws', 'inventory.ws', 
            'combat.ws', 'gameplay.ws', 'character.ws',
            'quest.ws', 'dialog.ws', 'gamemodule.ws',
            'player.w2ent', 'ciri.w2ent', 'geralt.w2ent',
            'inventory.xml', 'abilities.xml', 'items.xml',
        ]
    
    def analyze_mod_files(self, mod_path):
        """分析Mod文件结构"""
        files_info = []
        if not mod_path or not os.path.exists(mod_path):
            return files_info
        
        try:
            for root, dirs, files in os.walk(mod_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, mod_path)
                    file_type = self.get_file_type(file)
                    
                    files_info.append({
                        'path': rel_path.replace('\\', '/'),
                        'type': file_type,
                        'hash': self.get_file_hash(file_path),
                        'size': os.path.getsize(file_path),
                        'name': file
                    })
        except Exception as e:
            logging.error(f"分析Mod文件时出错: {e}")
        
        return files_info
    
    def get_file_type(self, filename):
        """获取文件类型"""
        ext = os.path.splitext(filename)[1].lower()
        for type_name, extensions in self.file_type_patterns.items():
            if ext in extensions:
                return type_name
        return 'other'
    
    def get_file_hash(self, file_path):
        """计算文件哈希值"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except:
            return "unavailable"
    
    def detect_all_conflicts(self, mods_list):
        """检测所有类型的冲突"""
        conflicts = []
        conflicts.extend(self.detect_file_conflicts(mods_list))
        conflicts.extend(self.detect_script_conflicts(mods_list))
        return self.remove_duplicate_conflicts(conflicts)
    
    def detect_file_conflicts(self, mods_list):
        """检测文件覆盖冲突"""
        conflicts = []
        file_owners = defaultdict(list)
        
        for mod in mods_list:
            if 'files' not in mod or not mod['files']:
                continue
            
            for file_info in mod['files']:
                file_key = file_info['path'].lower()
                file_owners[file_key].append({
                    'mod_id': mod['id'],
                    'mod_name': mod['name'],
                    'file_info': file_info,
                    'mod_path': mod.get('path', '')
                })
        
        for file_path, owners in file_owners.items():
            if len(owners) > 1:
                unique_hashes = set()
                for owner in owners:
                    hash_value = owner['file_info'].get('hash', '')
                    if hash_value and hash_value != 'unavailable':
                        unique_hashes.add(hash_value)
                
                if len(unique_hashes) > 1:
                    conflict = {
                        'id': f"conflict_{len(conflicts)}_{datetime.now().strftime('%H%M%S')}",
                        'file_path': file_path,
                        'conflict_type': 'file_override',
                        'has_conflict': True,
                        'mods_involved': owners,
                        'resolution_options': self.generate_resolution_options(owners),
                        'detected_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'resolved': False
                    }
                    conflicts.append(conflict)
        
        return conflicts
    
    def detect_script_conflicts(self, mods_list):
        """检测脚本修改冲突"""
        conflicts = []
        script_modifications = defaultdict(list)
        
        for mod in mods_list:
            mod_path = mod.get('path', '')
            if not mod_path or not os.path.exists(mod_path):
                continue
            
            script_files = []
            for root, dirs, files in os.walk(mod_path):
                for file in files:
                    if file.endswith(('.ws', '.lua', '.script', '.reds')):
                        script_files.append(os.path.join(root, file))
            
            for script_file in script_files:
                try:
                    with open(script_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    modifications = self.extract_script_modifications(content)
                    
                    for modification in modifications:
                        key = f"{os.path.basename(script_file)}:{modification['type']}:{modification['name']}"
                        script_modifications[key].append({
                            'mod_id': mod['id'],
                            'mod_name': mod['name'],
                            'script_file': script_file,
                            'modification': modification
                        })
                except:
                    pass
        
        for key, mods in script_modifications.items():
            if len(mods) > 1:
                script_file = mods[0]['script_file']
                conflicts.append({
                    'id': f"script_conflict_{len(conflicts)}_{datetime.now().strftime('%H%M%S')}",
                    'file_path': os.path.basename(script_file),
                    'conflict_type': 'script_modification',
                    'has_conflict': True,
                    'mods_involved': mods,
                    'resolution_options': self.generate_script_resolution(mods),
                    'detected_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'resolved': False
                })
        
        return conflicts
    
    def extract_script_modifications(self, content):
        """提取脚本修改内容"""
        modifications = []
        
        function_pattern = r'function\s+(\w+)\s*\('
        functions = re.findall(function_pattern, content)
        for func in functions:
            modifications.append({'type': 'function', 'name': func})
        
        class_pattern = r'class\s+(\w+)'
        classes = re.findall(class_pattern, content)
        for cls in classes:
            modifications.append({'type': 'class', 'name': cls})
        
        event_pattern = r'event\s+(\w+)'
        events = re.findall(event_pattern, content)
        for event in events:
            modifications.append({'type': 'event', 'name': event})
        
        return modifications
    
    def generate_resolution_options(self, owners):
        """生成冲突解决选项"""
        options = []
        
        for i, owner in enumerate(owners):
            options.append({
                'type': 'choose_mod',
                'description': f"保留 {owner['mod_name']} 的版本",
                'mod_id': owner['mod_id'],
                'priority': i + 1
            })
        
        options.append({
            'type': 'manual_merge',
            'description': "手动合并两个版本",
            'mod_id': None
        })
        
        options.append({
            'type': 'ignore',
            'description': "暂时忽略此冲突",
            'mod_id': None
        })
        
        return options
    
    def generate_script_resolution(self, mods):
        """生成脚本冲突解决选项"""
        options = []
        
        for i, mod in enumerate(mods):
            options.append({
                'type': 'script_merge',
                'description': f"使用脚本合并工具合并 {mod['mod_name']}",
                'mod_id': mod['mod_id'],
                'priority': i + 1
            })
        
        options.append({
            'type': 'manual_script_merge',
            'description': "手动编辑脚本合并",
            'mod_id': None
        })
        
        return options
    
    def remove_duplicate_conflicts(self, conflicts):
        """去除重复冲突"""
        unique_conflicts = []
        seen = set()
        
        for conflict in conflicts:
            conflict_key = (
                conflict['file_path'],
                conflict['conflict_type'],
                tuple(sorted([mod['mod_id'] for mod in conflict['mods_involved']]))
            )
            
            if conflict_key not in seen:
                seen.add(conflict_key)
                unique_conflicts.append(conflict)
        
        return unique_conflicts

class Witcher3ModManager:
    def __init__(self, root):
        self.root = root
        self.root.title("巫师3 Mod 智能管理器 v2.4")
        
        # 设置窗口大小为屏幕的1/2
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = int(screen_width * 0.5)
        window_height = int(screen_height * 0.5)
        x_position = (screen_width - window_width) // 2
        y_position = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        self.root.minsize(900, 650)
        
        # 初始化组件
        self.steam_locator = SteamGameLocator()
        self.conflict_detector = ModConflictDetector()
        self.mods = []
        self.conflicts = []
        self.install_queue = []
        self.selected_mods = set()
        
        # 配置
        self.config_file = os.path.join(APPLICATION_PATH, 'config.json')
        self.mods_file = os.path.join(APPLICATION_PATH, 'mods_data.json')
        self.conflicts_file = os.path.join(APPLICATION_PATH, 'conflicts_data.json')
        
        # 加载数据
        self.load_config()
        self.load_mods()
        self.load_conflicts()
        
        # UI
        self.setup_styles()
        self.setup_ui()
        self.setup_menu()
        self.setup_context_menu()
        self.setup_drag_drop()
        
        # 静默定位
        self.silent_locate_game()
        
        logging.info("巫师3 Mod管理器 v2.4 启动完成")
    
    def setup_styles(self):
        """设置UI样式"""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('微软雅黑', 14, 'bold'), foreground='#c8a86e')
        style.configure('Header.TFrame', background='#2b2b2b')
        style.configure('Small.TButton', padding=3, font=('微软雅黑', 8))
        style.configure('Big.TCheckbutton', font=('微软雅黑', 10, 'bold'))
    
    def setup_ui(self):
        """设置主界面"""
        main_container = ttk.Frame(self.root, padding="5")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 标题栏
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(title_frame, text="⚔️ 巫师3 Mod 管理器 v2.4", style='Title.TLabel').pack(side=tk.LEFT)
        
        self.conflict_indicator = tk.Label(
            title_frame,
            text="✅ 无冲突",
            bg='#4caf50',
            fg='white',
            font=('微软雅黑', 9, 'bold'),
            padx=8,
            pady=3
        )
        self.conflict_indicator.pack(side=tk.RIGHT, padx=5)
        
        # 游戏路径
        path_frame = ttk.LabelFrame(main_container, text="游戏设置", padding="3")
        path_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(path_frame, text="游戏路径:", font=('微软雅黑', 9)).pack(side=tk.LEFT, padx=(0, 3))
        self.game_path_var = tk.StringVar(value="未检测到游戏")
        game_entry = ttk.Entry(path_frame, textvariable=self.game_path_var, width=35, font=('微软雅黑', 9))
        game_entry.pack(side=tk.LEFT, padx=3)
        ttk.Button(path_frame, text="浏览", command=self.browse_game_path, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        
        ttk.Label(path_frame, text="Mod文件夹:", font=('微软雅黑', 9)).pack(side=tk.LEFT, padx=(10, 3))
        self.mod_folder_var = tk.StringVar(value="未检测到")
        mod_entry = ttk.Entry(path_frame, textvariable=self.mod_folder_var, width=25, font=('微软雅黑', 9))
        mod_entry.pack(side=tk.LEFT, padx=3)
        ttk.Button(path_frame, text="浏览", command=self.browse_mod_folder, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        
        # 主面板
        main_panel = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        main_panel.pack(fill=tk.BOTH, expand=True)
        
        # 左侧 - Mod列表
        left_frame = ttk.Frame(main_panel)
        main_panel.add(left_frame, weight=1)
        
        # 右侧 - 冲突面板
        right_frame = ttk.Frame(main_panel)
        main_panel.add(right_frame, weight=1)
        
        self.setup_mod_list(left_frame)
        self.setup_conflict_panel(right_frame)
        
        # 底部状态栏
        self.status_bar = ttk.Label(main_container, text="就绪 - 支持将Mod文件直接拖入窗口安装", relief=tk.SUNKEN, anchor=tk.W, font=('微软雅黑', 8))
        self.status_bar.pack(fill=tk.X, pady=(5, 0))
    
    def setup_mod_list(self, parent):
        """设置Mod列表"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 3))
        
        ttk.Label(header_frame, text="📦 已安装Mod", font=('微软雅黑', 11, 'bold')).pack(side=tk.LEFT)
        
        # 全选复选框
        self.select_all_var = tk.BooleanVar(value=False)
        select_all_cb = ttk.Checkbutton(
            header_frame, 
            text="全部选中", 
            variable=self.select_all_var,
            command=self.toggle_select_all,
            style='Big.TCheckbutton'
        )
        select_all_cb.pack(side=tk.RIGHT, padx=5)
        
        list_frame = ttk.LabelFrame(parent, text="Mod列表", padding="3")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        columns = ('select', 'name', 'remark', 'conflict')
        self.mod_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)
        
        self.mod_tree.heading('#0', text='')
        self.mod_tree.heading('select', text='选择')
        self.mod_tree.heading('name', text='Mod名称')
        self.mod_tree.heading('remark', text='备注')
        self.mod_tree.heading('conflict', text='冲突')
        
        self.mod_tree.column('#0', width=20, stretch=False)
        self.mod_tree.column('select', width=60, stretch=False)
        self.mod_tree.column('name', width=150)
        self.mod_tree.column('remark', width=200)
        self.mod_tree.column('conflict', width=60, stretch=False)
        
        # 配置标签颜色
        self.mod_tree.tag_configure('conflict', background='#ff4444', foreground='white')
        self.mod_tree.tag_configure('no_conflict', background='#ffffff')
        self.mod_tree.tag_configure('selected', background='#d0e8ff')
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.mod_tree.yview)
        self.mod_tree.configure(yscrollcommand=scrollbar.set)
        
        self.mod_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.mod_tree.bind('<Double-Button-1>', self.edit_mod_description)
        self.mod_tree.bind('<Button-1>', self.on_mod_click)
        self.mod_tree.bind('<<TreeviewSelect>>', self.on_mod_select)
        
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=3)
        
        ttk.Button(btn_frame, text="📦 安装Mod", command=self.install_mod, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔍 检索Mod", command=self.manual_scan_mods, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🗑️ 删除", command=self.delete_mod_with_files, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="✏️ 备注", command=self.edit_mod_description, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="🔄 检测冲突", command=self.auto_detect_conflicts, style='Small.TButton').pack(side=tk.LEFT, padx=2)
    
    def setup_conflict_panel(self, parent):
        """设置冲突面板"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 3))
        
        ttk.Label(header_frame, text="⚠️ 冲突检测", font=('微软雅黑', 11, 'bold')).pack(side=tk.LEFT)
        
        self.conflict_stats = ttk.Label(header_frame, text="", font=('微软雅黑', 9))
        self.conflict_stats.pack(side=tk.RIGHT)
        
        conflict_frame = ttk.LabelFrame(parent, text="检测到的冲突", padding="3")
        conflict_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('conflict', 'file', 'mods')
        self.conflict_tree = ttk.Treeview(conflict_frame, columns=columns, show='tree headings', height=10)
        
        self.conflict_tree.heading('#0', text='')
        self.conflict_tree.heading('conflict', text='冲突')
        self.conflict_tree.heading('file', text='冲突文件')
        self.conflict_tree.heading('mods', text='涉及Mod')
        
        self.conflict_tree.column('#0', width=20, stretch=False)
        self.conflict_tree.column('conflict', width=50, stretch=False)
        self.conflict_tree.column('file', width=180)
        self.conflict_tree.column('mods', width=150)
        
        self.conflict_tree.tag_configure('conflict', background='#ff4444', foreground='white')
        self.conflict_tree.tag_configure('resolved', background='#ccffcc')
        
        scrollbar = ttk.Scrollbar(conflict_frame, orient=tk.VERTICAL, command=self.conflict_tree.yview)
        self.conflict_tree.configure(yscrollcommand=scrollbar.set)
        
        self.conflict_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.conflict_tree.bind('<<TreeviewSelect>>', self.on_conflict_select)
        
        resolve_frame = ttk.LabelFrame(parent, text="解决方案", padding="3")
        resolve_frame.pack(fill=tk.X, pady=3)
        
        self.resolution_text = scrolledtext.ScrolledText(resolve_frame, height=4, wrap=tk.WORD, font=('微软雅黑', 9))
        self.resolution_text.pack(fill=tk.BOTH, expand=True)
        
        resolve_btn_frame = ttk.Frame(resolve_frame)
        resolve_btn_frame.pack(fill=tk.X, pady=3)
        
        ttk.Button(resolve_btn_frame, text="✅ 应用解决", command=self.apply_resolution, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(resolve_btn_frame, text="🔧 自动解决", command=self.auto_resolve_all, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(resolve_btn_frame, text="👁️ 详情", command=self.view_conflict_details, style='Small.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(resolve_btn_frame, text="📋 报告", command=self.export_conflict_report, style='Small.TButton').pack(side=tk.LEFT, padx=2)
    
    def setup_drag_drop(self):
        """设置全窗口拖拽支持"""
        if not HAS_DND:
            self.status_bar.config(text="⚠ 拖拽功能不可用 (请安装 tkinterdnd2)")
            return
        
        try:
            # 让整个根窗口支持拖拽
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
            self.root.dnd_bind('<<DropEnter>>', self.on_drop_enter)
            self.root.dnd_bind('<<DropLeave>>', self.on_drop_leave)
            logging.info("全窗口拖拽功能已启用")
        except Exception as e:
            logging.error(f"拖拽注册失败: {e}")
    
    def setup_context_menu(self):
        """设置右键菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="删除Mod（含文件）", command=self.delete_mod_with_files)
        self.context_menu.add_command(label="编辑备注", command=self.edit_mod_description)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="打开Mod文件夹", command=self.open_mod_folder_from_context)
        
        self.mod_tree.bind('<Button-3>', self.show_context_menu)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        item = self.mod_tree.identify_row(event.y)
        if item:
            self.mod_tree.selection_set(item)
            self.mod_tree.focus(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def setup_menu(self):
        """设置菜单"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="安装Mod", command=self.install_mod)
        file_menu.add_command(label="检索Mod", command=self.manual_scan_mods)
        file_menu.add_separator()
        file_menu.add_command(label="导出Mod列表", command=self.export_mod_list)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="检测冲突", command=self.auto_detect_conflicts)
        tools_menu.add_command(label="自动解决冲突", command=self.auto_resolve_all)
        tools_menu.add_separator()
        tools_menu.add_command(label="打开Mod文件夹", command=self.open_mod_folder)
        
        # 只保留"关于"菜单，去掉"使用说明"
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def silent_locate_game(self):
        """静默定位游戏（只运行一次）"""
        def locate():
            try:
                self.steam_locator.find_steam_installation()
                witcher_paths = self.steam_locator.find_witcher3_installation()
                mod_folder = self.steam_locator.find_mod_folder()
                
                self.root.after(0, lambda: self.update_game_paths(witcher_paths, mod_folder))
            except Exception as e:
                logging.error(f"静默定位失败: {e}")
        
        threading.Thread(target=locate, daemon=True).start()
    
    def update_game_paths(self, witcher_paths, mod_folder):
        """更新游戏路径显示"""
        if witcher_paths:
            self.game_path = witcher_paths[0]
            self.game_path_var.set(witcher_paths[0])
        else:
            if hasattr(self, 'game_path') and self.game_path:
                self.game_path_var.set(self.game_path)
            else:
                self.game_path_var.set("未检测到游戏，请手动选择")
        
        if mod_folder:
            self.mod_folder = mod_folder
            self.mod_folder_var.set(mod_folder)
            self.silent_scan_mods()
        else:
            if hasattr(self, 'mod_folder') and self.mod_folder:
                self.mod_folder_var.set(self.mod_folder)
            else:
                self.mod_folder_var.set("未检测到Mod文件夹")
        
        self.save_config()
    
    def silent_scan_mods(self):
        """静默扫描Mod文件夹"""
        def scan():
            try:
                scanned_mods = []
                
                if not self.mod_folder or not os.path.exists(self.mod_folder):
                    return
                
                for item in os.listdir(self.mod_folder):
                    item_path = os.path.join(self.mod_folder, item)
                    if os.path.isdir(item_path):
                        existing_mod = self.find_mod_by_path(item_path)
                        if existing_mod:
                            existing_mod['files'] = self.conflict_detector.analyze_mod_files(item_path)
                            scanned_mods.append(existing_mod)
                        else:
                            files_info = self.conflict_detector.analyze_mod_files(item_path)
                            new_mod = {
                                'id': f"mod_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(scanned_mods)}",
                                'name': item,
                                'description': f'自动扫描发现',
                                'remark': '',
                                'path': item_path,
                                'files': files_info,
                                'status': '已安装',
                                'merged': False,
                                'install_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'conflict_count': 0,
                                'has_conflict': False
                            }
                            scanned_mods.append(new_mod)
                
                self.mods = [mod for mod in scanned_mods if os.path.exists(mod.get('path', ''))]
                
                self.save_mods()
                self.root.after(0, self.refresh_mod_list)
                self.root.after(0, self.auto_detect_conflicts)
                logging.info(f"静默扫描完成：找到 {len(self.mods)} 个Mod")
                
            except Exception as e:
                logging.error(f"静默扫描失败: {e}")
        
        threading.Thread(target=scan, daemon=True).start()
    
    def manual_scan_mods(self):
        """手动检索Mod"""
        if not self.mod_folder or not os.path.exists(self.mod_folder):
            messagebox.showwarning("警告", "请先设置Mod文件夹")
            return
        
        self.status_bar.config(text="正在检索Mod文件夹...")
        self.root.update()
        
        def scan():
            try:
                scanned_mods = []
                
                for item in os.listdir(self.mod_folder):
                    item_path = os.path.join(self.mod_folder, item)
                    if os.path.isdir(item_path):
                        existing_mod = self.find_mod_by_path(item_path)
                        if existing_mod:
                            existing_mod['files'] = self.conflict_detector.analyze_mod_files(item_path)
                            scanned_mods.append(existing_mod)
                        else:
                            files_info = self.conflict_detector.analyze_mod_files(item_path)
                            new_mod = {
                                'id': f"mod_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(scanned_mods)}",
                                'name': item,
                                'description': f'手动扫描发现',
                                'remark': '',
                                'path': item_path,
                                'files': files_info,
                                'status': '已安装',
                                'merged': False,
                                'install_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                                'conflict_count': 0,
                                'has_conflict': False
                            }
                            scanned_mods.append(new_mod)
                
                self.mods = [mod for mod in scanned_mods if os.path.exists(mod.get('path', ''))]
                
                self.save_mods()
                self.root.after(0, self.refresh_mod_list)
                self.root.after(0, self.auto_detect_conflicts)
                self.root.after(0, lambda: self.status_bar.config(text=f"检索完成：找到 {len(self.mods)} 个Mod"))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"检索完成，共找到 {len(self.mods)} 个Mod"))
                logging.info(f"手动检索完成：找到 {len(self.mods)} 个Mod")
                
            except Exception as e:
                logging.error(f"手动检索失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"检索失败: {str(e)}"))
        
        threading.Thread(target=scan, daemon=True).start()
    
    def browse_game_path(self):
        """浏览选择游戏路径"""
        initial_dir = self.game_path if hasattr(self, 'game_path') and self.game_path and os.path.exists(self.game_path) else "C:\\"
        
        path = filedialog.askdirectory(
            title="选择巫师3游戏根目录",
            initialdir=initial_dir
        )
        
        if path:
            self.game_path = path
            self.game_path_var.set(path)
            
            mod_folder = os.path.join(path, "mods")
            if not os.path.exists(mod_folder):
                os.makedirs(mod_folder, exist_ok=True)
            
            self.mod_folder = mod_folder
            self.mod_folder_var.set(mod_folder)
            self.save_config()
            self.manual_scan_mods()
            self.status_bar.config(text=f"游戏路径已设置: {path}")
    
    def browse_mod_folder(self):
        """浏览Mod文件夹"""
        if hasattr(self, 'mod_folder') and self.mod_folder and os.path.exists(self.mod_folder):
            initial_dir = self.mod_folder
        elif hasattr(self, 'game_path') and self.game_path and os.path.exists(self.game_path):
            initial_dir = self.game_path
        else:
            initial_dir = "C:\\"
        
        path = filedialog.askdirectory(
            title="选择Mod文件夹",
            initialdir=initial_dir
        )
        
        if path:
            self.mod_folder = path
            self.mod_folder_var.set(path)
            self.save_config()
            self.manual_scan_mods()
            self.status_bar.config(text=f"Mod文件夹已设置: {path}")
    
    def install_mod(self):
        """安装Mod - 统一选择文件和文件夹"""
        if not self.mod_folder:
            messagebox.showwarning("警告", "请先设置Mod文件夹")
            return
        
        # 创建自定义选择对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("安装Mod")
        dialog.geometry("450x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="请选择安装方式:", font=('微软雅黑', 11, 'bold')).pack(pady=15)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        
        def select_files():
            dialog.destroy()
            files = filedialog.askopenfilenames(
                title="选择Mod压缩包",
                filetypes=[
                    ("压缩包", "*.zip *.rar *.7z"),
                    ("ZIP文件", "*.zip"),
                    ("RAR文件", "*.rar"),
                    ("7Z文件", "*.7z"),
                    ("所有文件", "*.*")
                ]
            )
            if files:
                self.process_install_queue(list(files))
        
        def select_folder():
            dialog.destroy()
            folder_path = filedialog.askdirectory(
                title="选择要安装的Mod文件夹",
                initialdir="C:\\"
            )
            if folder_path:
                self.process_install_queue([folder_path])
        
        ttk.Button(btn_frame, text="📁 选择文件夹", command=select_folder, width=18).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="📦 选择压缩包", command=select_files, width=18).pack(side=tk.LEFT, padx=10)
        
        ttk.Label(dialog, text="支持: ZIP / RAR / 7Z 压缩包 或 Mod文件夹", font=('微软雅黑', 8), foreground='gray').pack(pady=10)
    
    def process_install_queue(self, items):
        """处理安装队列"""
        self.install_queue = list(items)
        self.process_next_install()
    
    def process_next_install(self):
        """处理下一个安装项"""
        if not self.install_queue:
            self.status_bar.config(text="所有Mod安装完成")
            self.manual_scan_mods()
            return
        
        item = self.install_queue.pop(0)
        self.status_bar.config(text=f"正在安装: {os.path.basename(item)}")
        self.root.update()
        
        def install_thread():
            try:
                if os.path.isfile(item):
                    self.install_from_archive(item)
                elif os.path.isdir(item):
                    self.install_from_folder(item)
            except Exception as e:
                logging.error(f"安装Mod失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"安装失败: {str(e)}"))
            
            self.root.after(0, self.process_next_install)
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def install_from_folder(self, folder_path):
        """从文件夹安装Mod"""
        mod_name = os.path.basename(folder_path)
        dest_path = os.path.join(self.mod_folder, mod_name)
        
        if os.path.exists(dest_path):
            if not messagebox.askyesno("确认覆盖", f"Mod文件夹 '{mod_name}' 已存在，是否覆盖？"):
                return
        
        try:
            shutil.copytree(folder_path, dest_path, dirs_exist_ok=True)
            files_info = self.conflict_detector.analyze_mod_files(dest_path)
            
            new_mod = {
                'id': f"mod_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.mods)}",
                'name': mod_name,
                'description': f'从文件夹安装: {folder_path}',
                'remark': '',
                'path': dest_path,
                'files': files_info,
                'status': '已安装',
                'merged': False,
                'install_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'conflict_count': 0,
                'has_conflict': False
            }
            
            self.mods.append(new_mod)
            self.save_mods()
            self.root.after(0, self.refresh_mod_list)
            self.root.after(0, lambda: self.status_bar.config(text=f"✅ Mod '{mod_name}' 安装成功"))
            logging.info(f"成功安装Mod: {mod_name}")
            
        except Exception as e:
            logging.error(f"从文件夹安装失败: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"安装失败: {str(e)}"))
    
    def install_from_archive(self, archive_path):
        """从压缩包安装Mod - 支持ZIP、RAR、7Z"""
        archive_name = os.path.basename(archive_path)
        archive_ext = os.path.splitext(archive_path)[1].lower()
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            self.status_bar.config(text=f"正在解压: {archive_name}")
            
            if archive_ext == '.zip':
                self.extract_zip(archive_path, temp_dir)
            elif archive_ext == '.rar':
                if not HAS_RARFILE:
                    messagebox.showerror("错误", "RAR支持未安装\n请运行: pip install rarfile")
                    return
                self.extract_rar(archive_path, temp_dir)
            elif archive_ext == '.7z':
                if not HAS_PY7ZR:
                    messagebox.showerror("错误", "7Z支持未安装\n请运行: pip install py7zr")
                    return
                self.extract_7z(archive_path, temp_dir)
            else:
                messagebox.showerror("错误", f"不支持的压缩格式: {archive_ext}")
                return
            
            mod_folders = self.find_mod_folders_in_dir(temp_dir)
            
            if not mod_folders:
                messagebox.showerror("错误", "压缩包中未找到有效的Mod文件夹")
                return
            
            installed_count = 0
            for mod_folder in mod_folders:
                mod_name = os.path.basename(mod_folder)
                dest_path = os.path.join(self.mod_folder, mod_name)
                
                if os.path.exists(dest_path):
                    if not messagebox.askyesno("确认覆盖", f"Mod '{mod_name}' 已存在，是否覆盖？"):
                        continue
                    try:
                        shutil.rmtree(dest_path)
                    except:
                        pass
                
                shutil.copytree(mod_folder, dest_path, dirs_exist_ok=True)
                files_info = self.conflict_detector.analyze_mod_files(dest_path)
                
                existing = self.find_mod_by_path(dest_path)
                if existing:
                    existing['files'] = files_info
                else:
                    new_mod = {
                        'id': f"mod_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.mods)}",
                        'name': mod_name,
                        'description': f'从压缩包安装: {archive_name}',
                        'remark': '',
                        'path': dest_path,
                        'files': files_info,
                        'status': '已安装',
                        'merged': False,
                        'install_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'conflict_count': 0,
                        'has_conflict': False
                    }
                    self.mods.append(new_mod)
                
                installed_count += 1
            
            self.save_mods()
            self.root.after(0, self.refresh_mod_list)
            self.root.after(0, lambda: self.status_bar.config(text=f"✅ 从压缩包安装了 {installed_count} 个Mod"))
            logging.info(f"成功从压缩包安装: {archive_name}，共 {installed_count} 个Mod")
            
        except Exception as e:
            logging.error(f"从压缩包安装失败: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"安装失败: {str(e)}"))
        finally:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    def extract_zip(self, archive_path, extract_to):
        """解压ZIP文件"""
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            for info in zip_ref.infolist():
                try:
                    info.filename = info.filename.encode('cp437').decode('gbk')
                except:
                    try:
                        info.filename = info.filename.encode('cp437').decode('utf-8')
                    except:
                        pass
                zip_ref.extract(info, extract_to)
    
    def extract_rar(self, archive_path, extract_to):
        """解压RAR文件"""
        with rarfile.RarFile(archive_path, 'r') as rar_ref:
            rar_ref.extractall(extract_to)
    
    def extract_7z(self, archive_path, extract_to):
        """解压7Z文件"""
        with py7zr.SevenZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    
    def find_mod_folders_in_dir(self, directory):
        """在目录中查找mod文件夹"""
        mod_folders = []
        
        if self.is_mod_folder(directory):
            mod_folders.append(directory)
            return mod_folders
        
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                if self.is_mod_folder(item_path):
                    mod_folders.append(item_path)
        
        if not mod_folders:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    for sub_item in os.listdir(item_path):
                        sub_path = os.path.join(item_path, sub_item)
                        if os.path.isdir(sub_path) and self.is_mod_folder(sub_path):
                            mod_folders.append(sub_path)
        
        return mod_folders
    
    def is_mod_folder(self, folder_path):
        """判断是否为Mod文件夹"""
        if not os.path.exists(folder_path):
            return False
        
        mod_indicators = ['content', 'mod', 'scripts', 'textures', 'meshes', 'definition', 'gameplay']
        
        try:
            for item in os.listdir(folder_path):
                item_lower = item.lower()
                if item_lower in mod_indicators:
                    return True
                if item_lower.endswith(('.ws', '.w2ent', '.bundle', '.xml', '.w2mesh')):
                    return True
        except:
            pass
        
        return False
    
    def on_drop(self, event):
        """处理拖拽放下事件（全窗口）"""
        files = self.root.tk.splitlist(event.data)
        self.root.config(bg='SystemButtonFace')
        
        if not files:
            return
        
        if not self.mod_folder:
            messagebox.showwarning("警告", "请先设置Mod文件夹")
            return
        
        # 筛选有效文件（文件夹或压缩包）
        valid_items = []
        for f in files:
            if os.path.isdir(f):
                valid_items.append(f)
            elif os.path.isfile(f):
                ext = os.path.splitext(f)[1].lower()
                if ext in ['.zip', '.rar', '.7z']:
                    valid_items.append(f)
        
        if not valid_items:
            messagebox.showwarning("警告", "请拖入Mod文件夹或ZIP/RAR/7Z压缩包")
            return
        
        self.status_bar.config(text=f"检测到 {len(valid_items)} 个待安装项目，开始安装...")
        self.process_install_queue(valid_items)
    
    def on_drop_enter(self, event):
        """处理拖拽进入事件（全窗口高亮）"""
        try:
            self.root.config(bg='#4a6984')
        except:
            pass
        return event.action
    
    def on_drop_leave(self, event):
        """处理拖拽离开事件"""
        try:
            self.root.config(bg='SystemButtonFace')
        except:
            pass
        return event.action
    
    def toggle_select_all(self):
        """切换全选状态"""
        if self.select_all_var.get():
            self.selected_mods = {mod['id'] for mod in self.mods}
        else:
            self.selected_mods.clear()
        
        self.refresh_mod_list()
    
    def on_mod_click(self, event):
        """处理Mod点击事件"""
        region = self.mod_tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.mod_tree.identify_column(event.x)
            if column == "#1":
                item = self.mod_tree.identify_row(event.y)
                if item:
                    mod_index = self.mod_tree.index(item)
                    if mod_index < len(self.mods):
                        mod_id = self.mods[mod_index]['id']
                        if mod_id in self.selected_mods:
                            self.selected_mods.remove(mod_id)
                        else:
                            self.selected_mods.add(mod_id)
                        
                        if len(self.selected_mods) == len(self.mods):
                            self.select_all_var.set(True)
                        else:
                            self.select_all_var.set(False)
                        
                        self.refresh_mod_list()
    
    def delete_mod_with_files(self):
        """删除Mod（含文件）"""
        selection = self.mod_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的Mod")
            return
        
        item = selection[0]
        mod_index = self.mod_tree.index(item)
        mod = self.mods[mod_index]
        
        if messagebox.askyesno("确认删除", f"确定要删除 '{mod['name']}' 吗？\n\n这将同时删除Mod文件夹！"):
            try:
                if mod.get('path') and os.path.exists(mod['path']):
                    shutil.rmtree(mod['path'])
                    logging.info(f"已删除Mod文件夹: {mod['path']}")
                
                del self.mods[mod_index]
                self.save_mods()
                self.refresh_mod_list()
                self.auto_detect_conflicts()
                self.status_bar.config(text=f"已删除 {mod['name']}（含文件）")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败: {str(e)}")
    
    def open_mod_folder_from_context(self):
        """从右键菜单打开Mod文件夹"""
        selection = self.mod_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        mod_index = self.mod_tree.index(item)
        mod = self.mods[mod_index]
        
        if mod.get('path') and os.path.exists(mod['path']):
            try:
                os.startfile(mod['path'])
            except:
                messagebox.showerror("错误", "无法打开Mod文件夹")
        else:
            messagebox.showwarning("警告", "Mod文件夹不存在")
    
    def find_mod_by_path(self, mod_path):
        """根据路径查找Mod"""
        for mod in self.mods:
            if mod.get('path') == mod_path:
                return mod
        return None
    
    def auto_detect_conflicts(self):
        """自动检测冲突"""
        self.status_bar.config(text="正在检测Mod冲突...")
        self.root.update()
        
        def detect():
            try:
                self.conflicts = self.conflict_detector.detect_all_conflicts(self.mods)
                self.update_mod_conflict_info()
                self.save_conflicts()
                
                self.root.after(0, self.refresh_conflict_list)
                self.root.after(0, self.refresh_mod_list)
                self.root.after(0, self.update_conflict_indicator)
                self.root.after(0, lambda: self.status_bar.config(
                    text=f"检测完成：发现 {len(self.conflicts)} 个冲突"
                ))
                
                logging.info(f"冲突检测完成，发现 {len(self.conflicts)} 个冲突")
            except Exception as e:
                logging.error(f"冲突检测失败: {e}")
                self.root.after(0, lambda: messagebox.showerror("错误", f"冲突检测失败: {str(e)}"))
        
        threading.Thread(target=detect, daemon=True).start()
    
    def update_mod_conflict_info(self):
        """更新Mod的冲突信息"""
        for mod in self.mods:
            has_conflict = False
            
            for conflict in self.conflicts:
                for involved_mod in conflict['mods_involved']:
                    if involved_mod['mod_id'] == mod['id']:
                        has_conflict = True
                        break
                if has_conflict:
                    break
            
            mod['has_conflict'] = has_conflict
            mod['conflict_count'] = 1 if has_conflict else 0
    
    def refresh_mod_list(self):
        """刷新Mod列表"""
        for item in self.mod_tree.get_children():
            self.mod_tree.delete(item)
        
        for mod in self.mods:
            if mod['id'] in self.selected_mods:
                select_mark = '☑'
            else:
                select_mark = '☐'
            
            has_conflict = mod.get('has_conflict', False)
            conflict_mark = '⚠ 冲突' if has_conflict else '✅'
            
            if has_conflict:
                tag = 'conflict'
            elif mod['id'] in self.selected_mods:
                tag = 'selected'
            else:
                tag = 'no_conflict'
            
            remark = mod.get('remark', '')
            if not remark:
                remark = mod.get('description', '')
            
            self.mod_tree.insert('', 'end', values=(
                select_mark,
                mod['name'],
                remark,
                conflict_mark
            ), tags=(tag,))
    
    def refresh_conflict_list(self):
        """刷新冲突列表"""
        for item in self.conflict_tree.get_children():
            self.conflict_tree.delete(item)
        
        conflict_count = len([c for c in self.conflicts if not c.get('resolved', False)])
        resolved_count = len([c for c in self.conflicts if c.get('resolved', False)])
        
        stats_text = f"冲突: {conflict_count} | 已解决: {resolved_count}"
        self.conflict_stats.config(text=stats_text)
        
        for conflict in self.conflicts:
            if conflict.get('resolved', False):
                tag = 'resolved'
                conflict_mark = '✅'
            else:
                tag = 'conflict'
                conflict_mark = '⚠'
            
            mods_names = ", ".join([mod['mod_name'] for mod in conflict['mods_involved']])
            
            self.conflict_tree.insert('', 'end', values=(
                conflict_mark,
                conflict['file_path'],
                mods_names
            ), tags=(tag,))
    
    def update_conflict_indicator(self):
        """更新冲突指示器"""
        if not self.conflicts:
            self.conflict_indicator.config(text="✅ 无冲突", bg='#4caf50')
        else:
            conflict_count = len([c for c in self.conflicts if not c.get('resolved', False)])
            if conflict_count > 0:
                self.conflict_indicator.config(
                    text=f"⚠ {conflict_count} 个冲突",
                    bg='#ff4444'
                )
            else:
                self.conflict_indicator.config(text="✅ 无冲突", bg='#4caf50')
    
    def on_conflict_select(self, event):
        """处理冲突选择"""
        selection = self.conflict_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        conflict_index = self.conflict_tree.index(item)
        if conflict_index < len(self.conflicts):
            conflict = self.conflicts[conflict_index]
            self.display_resolution_options(conflict)
    
    def display_resolution_options(self, conflict):
        """显示解决方案"""
        self.resolution_text.delete(1.0, tk.END)
        self.resolution_text.insert(tk.END, f"冲突文件: {conflict['file_path']}\n")
        self.resolution_text.insert(tk.END, "涉及Mod:\n")
        
        for mod in conflict['mods_involved']:
            self.resolution_text.insert(tk.END, f"  • {mod['mod_name']}\n")
        
        self.resolution_text.insert(tk.END, "\n解决方案:\n")
        
        for i, option in enumerate(conflict['resolution_options'], 1):
            self.resolution_text.insert(tk.END, f"{i}. {option['description']}\n")
    
    def apply_resolution(self):
        """应用解决方案"""
        selection = self.conflict_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请先选择要解决的冲突")
            return
        
        item = selection[0]
        conflict_index = self.conflict_tree.index(item)
        conflict = self.conflicts[conflict_index]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("选择解决方案")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="选择解决方案:", font=('微软雅黑', 10, 'bold')).pack(pady=10)
        
        selected_option = tk.IntVar(value=0)
        
        for i, option in enumerate(conflict['resolution_options']):
            ttk.Radiobutton(
                dialog,
                text=option['description'],
                variable=selected_option,
                value=i,
                font=('微软雅黑', 9)
            ).pack(anchor=tk.W, padx=20, pady=3)
        
        def apply():
            option_index = selected_option.get()
            option = conflict['resolution_options'][option_index]
            
            if option['type'] == 'choose_mod':
                self.resolve_by_choosing_mod(conflict, option['mod_id'])
            elif option['type'] == 'ignore':
                conflict['resolved'] = True
                conflict['resolution'] = 'ignored'
            elif option['type'] == 'manual_merge':
                messagebox.showinfo("提示", "请手动合并冲突文件")
                conflict['resolved'] = True
                conflict['resolution'] = 'manual_merge'
            
            self.save_conflicts()
            dialog.destroy()
            self.refresh_conflict_list()
            self.refresh_mod_list()
            self.update_conflict_indicator()
            messagebox.showinfo("完成", "冲突已解决")
        
        ttk.Button(dialog, text="应用", command=apply).pack(pady=15)
    
    def resolve_by_choosing_mod(self, conflict, chosen_mod_id):
        """通过选择特定Mod解决冲突"""
        for mod_info in conflict['mods_involved']:
            mod = self.find_mod_by_id(mod_info['mod_id'])
            if mod:
                if mod['id'] == chosen_mod_id:
                    mod['status'] = '已解决'
                else:
                    mod['status'] = '已覆盖'
                    mod['merged'] = True
        
        conflict['resolved'] = True
        conflict['resolution'] = f'chose_mod_{chosen_mod_id}'
    
    def auto_resolve_all(self):
        """自动解决所有冲突"""
        if not self.conflicts:
            messagebox.showinfo("提示", "没有冲突需要解决")
            return
        
        unresolved = [c for c in self.conflicts if not c.get('resolved', False)]
        if not unresolved:
            messagebox.showinfo("提示", "所有冲突已解决")
            return
        
        if messagebox.askyesno("确认", f"将自动解决 {len(unresolved)} 个冲突，是否继续？"):
            resolved_count = 0
            
            for conflict in unresolved:
                if conflict['resolution_options']:
                    best_option = conflict['resolution_options'][0]
                    
                    if best_option['type'] == 'choose_mod':
                        self.resolve_by_choosing_mod(conflict, best_option['mod_id'])
                        resolved_count += 1
                    elif best_option['type'] == 'ignore':
                        conflict['resolved'] = True
                        conflict['resolution'] = 'ignored'
                        resolved_count += 1
            
            self.save_conflicts()
            self.refresh_conflict_list()
            self.refresh_mod_list()
            self.update_conflict_indicator()
            messagebox.showinfo("完成", f"自动解决了 {resolved_count} 个冲突")
    
    def find_mod_by_id(self, mod_id):
        """根据ID查找Mod"""
        for mod in self.mods:
            if mod['id'] == mod_id:
                return mod
        return None
    
    def view_conflict_details(self):
        """查看冲突详情"""
        selection = self.conflict_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        conflict_index = self.conflict_tree.index(item)
        conflict = self.conflicts[conflict_index]
        
        detail_window = tk.Toplevel(self.root)
        detail_window.title("冲突详情")
        detail_window.geometry("500x350")
        
        text = scrolledtext.ScrolledText(detail_window, wrap=tk.WORD, font=('微软雅黑', 9))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text.insert(tk.END, f"冲突文件: {conflict['file_path']}\n")
        text.insert(tk.END, f"冲突类型: {conflict['conflict_type']}\n\n")
        text.insert(tk.END, "涉及的Mod:\n")
        
        for mod in conflict['mods_involved']:
            text.insert(tk.END, f"  • {mod['mod_name']}\n")
        
        if conflict.get('resolution'):
            text.insert(tk.END, f"\n解决状态: {conflict['resolution']}\n")
        
        text.config(state=tk.DISABLED)
    
    def export_conflict_report(self):
        """导出冲突报告"""
        file_path = filedialog.asksaveasfilename(
            title="导出冲突报告",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("HTML文件", "*.html")]
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.html'):
                self.export_html_report(file_path)
            else:
                self.export_text_report(file_path)
            
            messagebox.showinfo("成功", "冲突报告已导出")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def export_text_report(self, file_path):
        """导出文本报告"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("巫师3 Mod冲突检测报告\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Mod总数: {len(self.mods)}\n")
            f.write(f"冲突总数: {len(self.conflicts)}\n\n")
            
            for i, conflict in enumerate(self.conflicts, 1):
                f.write(f"冲突 #{i}\n")
                f.write(f"  文件: {conflict['file_path']}\n")
                f.write(f"  类型: {conflict['conflict_type']}\n")
                f.write(f"  涉及Mod:\n")
                for mod in conflict['mods_involved']:
                    f.write(f"    - {mod['mod_name']}\n")
                f.write(f"  状态: {'已解决' if conflict.get('resolved') else '未解决'}\n")
                f.write("-" * 30 + "\n")
    
    def export_html_report(self, file_path):
        """导出HTML报告"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>巫师3 Mod冲突报告</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .conflict { border: 1px solid #ccc; margin: 10px 0; padding: 10px; border-left: 5px solid #ff4444; }
                .resolved { border-left: 5px solid #4caf50; }
            </style>
        </head>
        <body>
            <h1>巫师3 Mod冲突检测报告</h1>
            <p>生成时间: {}</p>
            <p>Mod总数: {} | 冲突总数: {}</p>
        """.format(
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            len(self.mods),
            len(self.conflicts)
        )
        
        for conflict in self.conflicts:
            css_class = 'resolved' if conflict.get('resolved') else 'conflict'
            
            html += f"""
            <div class="{css_class}">
                <h3>{conflict['file_path']}</h3>
                <p><strong>类型:</strong> {conflict['conflict_type']}</p>
                <p><strong>涉及Mod:</strong></p>
                <ul>
            """
            
            for mod in conflict['mods_involved']:
                html += f"<li>{mod['mod_name']}</li>"
            
            html += """
                </ul>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)
    
    def export_mod_list(self):
        """导出Mod列表"""
        file_path = filedialog.asksaveasfilename(
            title="导出Mod列表",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("JSON文件", "*.json")]
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.mods, f, ensure_ascii=False, indent=2)
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("巫师3 Mod列表\n")
                    f.write("=" * 50 + "\n\n")
                    for mod in self.mods:
                        f.write(f"名称: {mod['name']}\n")
                        f.write(f"备注: {mod.get('remark', mod.get('description', '无'))}\n")
                        f.write(f"冲突: {'是' if mod.get('has_conflict', False) else '否'}\n")
                        f.write("-" * 30 + "\n")
            
            messagebox.showinfo("成功", "Mod列表已导出")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def open_mod_folder(self):
        """打开Mod文件夹"""
        if self.mod_folder and os.path.exists(self.mod_folder):
            try:
                os.startfile(self.mod_folder)
            except:
                messagebox.showerror("错误", "无法打开Mod文件夹")
        else:
            messagebox.showwarning("警告", "Mod文件夹不存在")
    
    def edit_mod_description(self, event=None):
        """编辑Mod备注"""
        selection = self.mod_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        mod_index = self.mod_tree.index(item)
        mod = self.mods[mod_index]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑Mod备注")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=f"Mod名称: {mod['name']}", font=('微软雅黑', 10, 'bold')).pack(pady=10)
        ttk.Label(dialog, text="备注内容:", font=('微软雅黑', 9)).pack(pady=5)
        
        remark_entry = ttk.Entry(dialog, width=40, font=('微软雅黑', 10))
        remark_entry.pack(pady=5)
        remark_entry.insert(0, mod.get('remark', ''))
        
        def save_remark():
            mod['remark'] = remark_entry.get().strip()
            self.save_mods()
            self.refresh_mod_list()
            dialog.destroy()
            self.status_bar.config(text=f"已更新 '{mod['name']}' 的备注")
        
        ttk.Button(dialog, text="保存", command=save_remark).pack(pady=15)
    
    def on_mod_select(self, event):
        """处理Mod选择事件"""
        selection = self.mod_tree.selection()
        if selection:
            item = selection[0]
            mod_index = self.mod_tree.index(item)
            if mod_index < len(self.mods):
                mod = self.mods[mod_index]
                self.status_bar.config(text=f"已选择: {mod['name']}")
    
    def show_about(self):
        """显示关于"""
        about_text = """
《巫师3 Mod管理器》v2.4

开发者: Witcher3 Mod Manager Team
"""
        messagebox.showinfo("关于", about_text)
    
    def load_config(self):
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.game_path = config.get('game_path')
                    self.mod_folder = config.get('mod_folder')
            except:
                self.game_path = None
                self.mod_folder = None
        else:
            self.game_path = None
            self.mod_folder = None
    
    def save_config(self):
        """保存配置"""
        config = {
            'game_path': getattr(self, 'game_path', None),
            'mod_folder': getattr(self, 'mod_folder', None)
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_mods(self):
        """加载Mod数据"""
        if os.path.exists(self.mods_file):
            try:
                with open(self.mods_file, 'r', encoding='utf-8') as f:
                    self.mods = json.load(f)
            except:
                self.mods = []
        else:
            self.mods = []
    
    def save_mods(self):
        """保存Mod数据"""
        try:
            with open(self.mods_file, 'w', encoding='utf-8') as f:
                json.dump(self.mods, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_conflicts(self):
        """加载冲突数据"""
        if os.path.exists(self.conflicts_file):
            try:
                with open(self.conflicts_file, 'r', encoding='utf-8') as f:
                    self.conflicts = json.load(f)
            except:
                self.conflicts = []
        else:
            self.conflicts = []
    
    def save_conflicts(self):
        """保存冲突数据"""
        try:
            with open(self.conflicts_file, 'w', encoding='utf-8') as f:
                json.dump(self.conflicts, f, ensure_ascii=False, indent=2)
        except:
            pass

def main():
    if HAS_DND:
        try:
            root = TkinterDnD.Tk()
        except:
            root = tk.Tk()
    else:
        root = tk.Tk()
    
    app = Witcher3ModManager(root)
    
    root.bind('<Control-i>', lambda e: app.install_mod())
    root.bind('<Control-d>', lambda e: app.auto_detect_conflicts())
    root.bind('<Control-r>', lambda e: app.auto_resolve_all())
    root.bind('<F2>', lambda e: app.edit_mod_description())
    root.bind('<Delete>', lambda e: app.delete_mod_with_files())
    root.bind('<F5>', lambda e: app.manual_scan_mods())
    
    root.mainloop()

if __name__ == "__main__":
    main()