import math
import time
from pathlib import Path
import shutil

from loguru import logger
from tikilib import plot as tp
from tikilib import text as tt
from tikilib import system as ts

from materlib import materials
from task_item import *

tp.chinese_font_support()


def format_time():
    time_struct = time.localtime()
    date_str = f"{time_struct.tm_year}-{time_struct.tm_mon}-{time_struct.tm_mday}"
    time_str = f"{time_struct.tm_hour}-{time_struct.tm_min}-{time_struct.tm_sec}"
    return f"{date_str}--{time_str}"


def gene(*args, **kwargs):
    fm_time = format_time()
    # ===材料参数
    concrete = materials.Concrete.from_table("C60")
    steel = materials.Steel.from_table("Q390")
    steelbar = materials.SteelBar.from_table("HRB400")
    # ===几何参数
    mesh_table = {
        "super": ((18, 18, 50), (18, 18, 50)),  # 3h
        "better": ((12, 12, 24), (12, 12, 30)),  # 7min
        "nice": ((9, 9, 16), (8, 8, 20)),  # 2min
        "normal": ((6, 6, 16), (5, 5, 20)),
    }
    geo = Geometry(150, 300, 1200, 6, *mesh_table["nice"])

    bar_e_0 = 0.233  # 偏心距
    rp_top = ReferencePoint([0, geo.len_y * bar_e_0, 0], [0, 0, -200, 0, 0, 0])
    rp_bottom = ReferencePoint([0, geo.len_y * bar_e_0, 0], [0, 0, 0, 0, 0, 0])
    # ===拉杆参数
    roll = Pullroll(
        geo,
        math.pi * (14 / 2) ** 2,
        1,
        1,
        7,
        x_exist=False,
        y_exist=False,
        ushape=True,
    )

    # ===元参数
    taskpath = Path(r"D:\Casual\T_abaqus") / f"{kwargs['name']}_{fm_time}"
    meta = TaskMeta.from2(fm_time, taskpath)
    meta.submit = True

    # ===生成json
    abadata = AbaqusData(meta, concrete, steel, steelbar, geo, roll, rp_top, rp_bottom)
    taskjson_name = Path("tasks") / f"{kwargs['id']}.json"
    tt.JsonFile.write(
        abadata.json_task,
        taskjson_name,
    )
    # ===生成工作文件夹
    taskfolder = Path(meta.taskfolder)
    taskfolder.mkdir(exist_ok=True, parents=True)
    (taskfolder / "script").mkdir(exist_ok=True, parents=True)
    for i in (
        "abaqus_executable.py",
        "task_generator.py",
        "task_item.py",
        taskjson_name,
    ):
        (taskfolder / "script" / i).parent.mkdir(exist_ok=True, parents=True)
        shutil.copy(i, taskfolder / "script" / i)

    # ===输出信息
    markdown_table = f"""| 试件编号 | $D\\times B \\times L\\times t $        | $a_s \\times b_s \\times n_s$ | $\\bar e_0$ | 钢管钢材 | 拉杆钢筋 | 混凝土标号 |
| -------- | ------------------------------------ | --------------------------- | ---------- | -------- | -------- | ---------- |
|          | $ {geo.len_y} \\times {geo.len_x} \\times {geo.len_z} \\times {geo.tubelar_thickness}$ | ${round(roll.area, 2)} \\times {roll.z_distance} \\times {roll.xy_number}$   | ${bar_e_0}$    | ${steel.grade}$ | ${steelbar.grade}$ | ${concrete.grade}$    |"""
    print(markdown_table)


@logger.catch
def main():
    gene(name="CFST_1", id=1)


if __name__ == "__main__":
    main()
