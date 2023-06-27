import json as _json
import time
from itertools import zip_longest

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def chinese_font_support() -> None:
    """matplotlib的中文显示支持的自动设置函数"""
    plt.rcParams["font.sans-serif"] = ["MicroSoft YaHei"]  # 用来正常显示中文标签
    # plt.rcParams["axes.unicode_minus"] = False  # 用来正常显示负号


def set_figsize(*size):
    """
    设置画幅(先宽后高)(似乎需要在画图之前就设置画幅)

    size
        (w,h)
    """
    if len(size) == 1 and isinstance(size[0], tuple):
        plt.rcParams["figure.figsize"] = size[0]
    elif len(size) == 2:
        plt.rcParams["figure.figsize"] = size


def set_color_palette_from_seaborn(color_palette_name="Set1"):
    """常用: tab20c, tab20, Set1"""
    sns.set_palette(sns.color_palette("Set1"))


class JsonFile:
    @staticmethod
    def load(jsonFile="data.json", encoding="utf-8"):
        """读取Json文件"""
        with open(jsonFile, "r", encoding=encoding) as f:
            return _json.load(f)

    @staticmethod
    def write(item, jsonFile="data.json", encoding="utf-8", ensure_ascii=False):
        """写入Json文件"""
        with open(jsonFile, "w", encoding=encoding) as f:
            _json.dump(item, f, ensure_ascii=ensure_ascii)


def format_time(with_date=False):
    time_struct = time.localtime()
    date_str = f"{time_struct.tm_year}-{time_struct.tm_mon}-{time_struct.tm_mday}"
    time_str = f"{time_struct.tm_hour}-{time_struct.tm_min}-{time_struct.tm_sec}"
    return f"{date_str}--{time_str}" if with_date else f"{time_str}"

def gene_markdown_table(data: dict):
    index_arr, value_arr = zip(*data.items())

    text = f"""|{"|".join(map(str, index_arr))}|
|{'|'.join(map(lambda x:":-:", range(len(index_arr))))}|\n"""

    for values in zip_longest(*value_arr, fillvalue=""):
        text += f"""|{"|".join(map(str, values))}|\n"""
    return text