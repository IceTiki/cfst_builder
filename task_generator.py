import math
import time
from pathlib import Path

from loguru import logger
from tikilib import plot as tp
from tikilib import text as tt

from materlib import materials
from task_item import *

tp.chinese_font_support()


def format_time():
    time_struct = time.localtime()
    date_str = f"{time_struct.tm_year}-{time_struct.tm_mon}-{time_struct.tm_mday}"
    time_str = f"{time_struct.tm_hour}-{time_struct.tm_min}-{time_struct.tm_sec}"
    return f"{date_str}--{time_str}"


@logger.catch
def main():
    fm_time = format_time()
    concrete = materials.Concrete.from_table("C55")
    steel = materials.Steel.from_table("Q460")
    steelbar = materials.SteelBar.from_table("HRB400")
    caepath = Path(r"D:\Casual\T_abaqus") / fm_time
    meta = TaskMeta(
        "job-" + fm_time,
        "cae-" + fm_time,
        caepath,
        "model-" + fm_time,
        True,
        3600,
        False,
    )

    geo = Geometry(150, 300, 1200, 6, (6, 6, 12), (5, 5, 10))
    roll = Pullroll(math.pi * (14 / 2) ** 2, 150, 1, False)
    bar_e_0 = 0.233  # 偏心距
    rp_top = ReferencePoint([0, geo.high * bar_e_0, 0], [0, 0, -100, None, 0, 0])
    rp_bottom = ReferencePoint([0, geo.high * bar_e_0, 0], [0, 0, 0, None, 0, 0])

    abadata = AbaqusData(meta, concrete, steel, steelbar, geo, roll, rp_top, rp_bottom)
    tt.JsonFile.write(
        abadata.json_task,
        "abatmp.json",
    )

    markdown_table = f"""| 试件编号 | $D\\times B \\times L\\times t $        | $a_s \\times b_s \\times d_s$ | $\\bar e_0$ | 钢管钢材 | 拉杆钢筋 | 混凝土标号 |
| -------- | ------------------------------------ | --------------------------- | ---------- | -------- | -------- | ---------- |
|          | $ {geo.high}\\times {geo.width} \\times {geo.deep} \\times {geo.tubelar_thickness}$ | ${roll.distance}\\times {geo.high / roll.number} \\times {math.sqrt(roll.area/math.pi)}$   | ${bar_e_0}$    | ${steel.grade}$ | ${steelbar.grade}$ | ${concrete.grade}$    |"""
    print(markdown_table)


if __name__ == "__main__":
    main()
    # m = materials.Concrete.from_table("C30")
    # tmp = 5.80107
