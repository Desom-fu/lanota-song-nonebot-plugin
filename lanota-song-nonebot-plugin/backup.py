import datetime
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger
from nonebot import get_bot
import asyncio
import shutil
from .config import user_path, backup_path, lanota_group

async def delayed_backup(delay: float = 5.0):
    """延迟执行备份"""
    await asyncio.sleep(delay)
    try:
        bot = get_bot()
        await backup_user_data(bot, lanota_group)
    except Exception as e:
        logger.error(f"延迟备份失败: {e}")

async def cleanup_old_backups(max_backups=100):
    """清理旧备份，保留最多max_backups个"""
    try:
        backups = sorted(backup_path.glob("Backup_*"), key=lambda x: x.stat().st_ctime)
        if len(backups) > max_backups:
            for old_backup in backups[:len(backups)-max_backups]:
                shutil.rmtree(old_backup)
                logger.info(f"已删除旧备份: {old_backup}")
    except Exception as e:
        logger.error(f"清理旧备份时出错: {e}")

async def backup_user_data(bot: Bot = None, group_id: int = None):
    """备份用户数据"""
    if not user_path.exists():
        logger.warning("用户数据目录不存在，跳过备份")
        return False
    
    try:
        backup_path.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_path / f"Backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"

        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        shutil.copytree(user_path, backup_dir)
        logger.success(f"用户数据已备份到：{backup_dir}")

        await cleanup_old_backups()

        if bot and group_id:
            backups = sorted(backup_path.glob("Backup_*"), key=lambda x: x.stat().st_ctime)
            message = f"用户数据备份已完成"
            # 备份数量达到100不显示
            if int(len(backups)) < 100:
                message += f"\n当前备份数量: {len(backups)}/100"
            logger.info(message)
        
        return True
    except Exception as e:
        logger.error(f"备份过程中发生错误: {e}")
        return False
    
# 启动时创建延迟备份任务
@get_driver().on_startup
async def schedule_delayed_backup():
    """启动时调度延迟备份任务"""
    asyncio.create_task(delayed_backup(10.0))
    logger.info("已创建延迟10秒的备份任务")
