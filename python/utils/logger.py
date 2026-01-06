# python/utils/logger.py
# External dependencies / 外部依赖
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
import logging
import re


def setup_logger(
    logs_dir: Path = None, log_level: int = logging.INFO
) -> logging.Logger:
    """
    设置日志记录器，只输出到文件
    Setup logger that outputs only to file

    Args:
        logs_dir (Path): 日志目录，如果为 None 则使用默认目录 / Log directory, use default if None
        log_level (int): 日志级别 / Log level

    Returns:
        logging.Logger: 配置好的日志记录器 / Configured logger
    """
    # 设置日志目录 / Set log directory
    if logs_dir is None:
        logs_dir = Path("logs")
    else:
        logs_dir = Path(logs_dir)

    logs_dir.mkdir(parents=True, exist_ok=True)

    # 根据时间构造日志文件名 / Construct log filename based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"doihive_{timestamp}.log"
    log_file_path = logs_dir / log_filename

    # 创建日志记录器 / Create logger
    logger = logging.getLogger("doihive")
    logger.setLevel(log_level)

    # 清除已有的处理器 / Clear existing handlers
    logger.handlers.clear()

    # 创建自定义格式化器，移除 Rich 标记并改进对齐 / Create custom formatter to remove Rich markup and improve alignment
    class CleanFormatter(logging.Formatter):
        """移除 Rich 标记的格式化器 / Formatter that removes Rich markup"""

        # Rich 标记正则表达式 / Rich markup regex pattern
        MARKUP_PATTERN = re.compile(r"\[/?[^\]]+\]")

        def format(self, record):
            # 保存原始消息 / Save original message
            original_msg = record.msg

            # 移除消息中的 Rich 标记 / Remove Rich markup from message
            if isinstance(record.msg, str):
                record.msg = self.MARKUP_PATTERN.sub("", record.msg)

            # 格式化消息 / Format message
            formatted = super().format(record)

            # 处理多行消息，为后续行添加缩进 / Handle multi-line messages, add indentation for continuation lines
            if "\n" in formatted:
                lines = formatted.split("\n")
                if len(lines) > 1:
                    # 计算第一行的前缀长度（时间戳 + 级别 + 分隔符）/ Calculate prefix length of first line
                    # 格式: "YYYY-MM-DD HH:MM:SS | LEVELNAME | "
                    timestamp_str = self.formatTime(record, self.datefmt)
                    level_str = record.levelname
                    prefix_len = (
                        len(timestamp_str) + 3 + len(level_str) + 3
                    )  # +3 for each " | "
                    indent = " " * prefix_len
                    # 为后续行添加缩进 / Add indentation for subsequent lines
                    formatted = (
                        lines[0] + "\n" + "\n".join(indent + line for line in lines[1:])
                    )

            # 恢复原始消息（避免影响其他处理器）/ Restore original message (to avoid affecting other handlers)
            record.msg = original_msg

            return formatted

    # 创建格式化器 / Create formatter
    file_formatter = CleanFormatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件处理器（带轮转） / File handler (with rotation)
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 不再添加控制台处理器，所有日志只写入文件 / No longer add console handler, all logs only written to file

    return logger


def log_to_file_only(level: int, message: str):
    """
    只写入文件，不输出到控制台
    Log to file only, not to console

    Args:
        level (int): 日志级别 / Log level (logging.INFO, logging.WARNING, etc.)
        message (str): 日志消息 / Log message
    """
    logger = logging.getLogger("doihive")
    # 如果还没有初始化，使用默认设置初始化 / If not initialized, use default settings
    if not logger.handlers:
        setup_logger()
        logger = logging.getLogger("doihive")

    # 移除 Rich 标记 / Remove Rich markup
    if isinstance(message, str):
        MARKUP_PATTERN = re.compile(r"\[/?[^\]]+\]")
        clean_message = MARKUP_PATTERN.sub("", message)
    else:
        clean_message = message

    # 直接记录日志（现在只有文件处理器，所以直接使用 logger.log 即可）
    # Directly log (now only file handler exists, so logger.log is sufficient)
    logger.log(level, clean_message)
