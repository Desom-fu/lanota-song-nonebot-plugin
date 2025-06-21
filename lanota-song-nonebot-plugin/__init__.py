from nonebot.log import logger
from nonebot import get_driver
from .function import *
from .whitelist import *
from .config import *
from .changecolor import *
from .trade import *
from .backup import *
from .lanota_command import *

# 初始化
driver = get_driver()
@driver.on_startup
async def _():
    # 初始化创建文件
    init_data()
    logger.info("LanotaBot已开启")

