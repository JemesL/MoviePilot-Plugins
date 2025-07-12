import json
import traceback
import os
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional

from app.db import SessionFactory
from app.db.models import TransferHistory
from app.log import logger
from app.plugins import _PluginBase
from app.utils.http import RequestUtils

from app.db.transferhistory_oper import TransferHistoryOper
from app.db.models.transferhistory import TransferHistory
class RecoverOriginMedia(_PluginBase):
    # 插件名称
    plugin_name = "恢复源媒体文件"
    # 插件描述
    plugin_desc = "根据整理记录, 将刮削后的媒体文件恢复至源文件."
    # 插件图标
    plugin_icon = "Linkease_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "jemesl"
    # 作者主页
    author_url = "https://github.com/JemesL"
    # 插件配置项ID前缀
    plugin_config_prefix = "recoveroriginmedia_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    # 打印模式, 不执行具体操作, 只打印日志
    _only_print = 0
    # 恢复记录数量, 0 代表所有 
    _recover_number: int = 10

    _enabled = False
    _onlyonce = False

    def init_plugin(self, config: dict = None):
        self.transferhis = TransferHistoryOper()
        if config:
            self._enabled = config.get("enabled")
            self._only_print = config.get("only_print")
            self._recover_number = int(config.get("recover_number"))
            self._onlyonce = config.get("onlyonce")
        
        if self._onlyonce:
            logger.info("恢复源媒体文件，立即运行一次")
            self.recover_opr()
            # 关闭一次性开关
            self._onlyonce = False
            # 保存配置
            self.__update_config()        

    def recover_opr(self):
        logger.info("开始恢复源数据 ...")
        if self._only_print:
            logger.info("模拟模式(只打印不操作)")

        with SessionFactory() as db:
            page = 1
            count = 10
            handle_count = 0
            while True:
                transferhistories = TransferHistory.list_by_page(db, page, count, True)
                for item in transferhistories:
                    if handle_count >= self._recover_number:
                        break
                    skip = self.__handle_file(item)
                    if not skip:
                        handle_count += 1
                page += 1
                if handle_count >= self._recover_number:
                    break
                if len(transferhistories) == 0:  # 退出条件
                    break
    
    def __handle_file(self, item: TransferHistory):
        logger.info(f"准备恢复文件: {item.dest} => {item.src}")
        if not item.dest or not item.src:
            logger.error(f"缺少路径. 源文件: {item.src}, 刮削文件: {item.dest}")
            return
        dest_path = Path(item.dest)
        src_path = Path(item.src)
        try:
            # 如果刮削后的文件不存在则跳过
            if not dest_path.exists():
                logger.info(f"刮削文件不存在, 跳过. 刮削文件: {item.dest}")
                # logger.info(f"刮削文件不存在, 跳过.")
                return 1
            # 如果源文件存在则跳过, 无需恢复
            if src_path.exists():
                logger.info(f"源文件已存在, 跳过. 源文件: {item.src}")
                # logger.info(f"源文件已存在, 跳过.")
                return 1
            
            if not self._only_print:
                # 开始硬链接
                self.__hard_link(item.dest, item.src)
            else:
                logger.info(f"源文件模拟恢复成功. 源文件: {item.src}")
        except Exception as e:
            logger.error("恢复源文件发生错误：%s - %s" % (str(e), traceback.format_exc()))

    def __hard_link(self, source: str, dest: str):
        def verify_hardlink(source, link_name):
            # 检查是否是同一个文件
            if Path.samefile(source, link_name):
                pass
                # logger.info(f"硬链接验证成功: {link_name}")
                # logger.info(f"硬链接验证成功: {source} 和 {link_name} 是同一个文件")
                # print(f"源文件 inode: {os.stat(source).st_ino}")
                # print(f"硬链接 inode: {os.stat(link_name).st_ino}")
            else:
                logger.error(f"验证失败: 不是有效的硬链接: {link_name}")

        source = Path(source)
        link_name = Path(dest)

        # 创建父目录（如果不存在）
        link_name.parent.mkdir(parents=True, exist_ok=True)
        try:
            link_name.hardlink_to(source)
            # logger.info(f"成功创建硬链接: {source} -> {link_name}")
            logger.info(f"成功创建硬链接: {link_name}")

            verify_hardlink(source, dest)
        except FileExistsError:
            logger.error(f"错误: 目标文件 {link_name} 已存在")
        except OSError as e:
            logger.error(f"创建硬链接失败: {e}")

    
     
    def __close_config(self):
        """
        关闭开关
        """
        self._enabled = False
        self.__update_config()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def __update_config(self):
        """
        更新配置
        """
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "only_print": self._only_print,
            "recover_number": self._recover_number,
        })

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'only_print',
                                            'label': '模拟模式(不执行文件恢复操作，只输出日志)',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'recover_number',
                                            'label': '恢复的条目数量（整理记录）',
                                            'placeholder': '例如: 10。0 代表恢复所有记录',
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "host": None,
            "username": None,
            "password": None
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        pass
