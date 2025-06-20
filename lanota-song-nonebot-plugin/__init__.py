from nonebot.log import logger
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Event, MessageEvent
from nonebot.message import run_preprocessor, event_postprocessor
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from .function import *
from .whitelist import *
from .config import *
from .changecolor import *
from .trade import *
from .lanota_command import *

# 初始化
driver = get_driver()
@driver.on_startup
async def _():
    # 初始化创建文件
    init_data()
    logger.info("LanotaBot已开启")

