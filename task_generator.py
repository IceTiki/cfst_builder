import math
import time
from pathlib import Path
import shutil
from itertools import product

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
    return f"{time_str}"


def gene(id: int, name: str, comment_data: dict = {}, *args, **kwargs):
    fm_time = format_time()
    # ===材料参数
    concrete = materials.Concrete.from_table("C60")
    steel = materials.Steel.from_table("Q390")
    steelbar = materials.SteelBar.from_table("HRB400")
    # ===几何参数
    mesh_table = {
        "best": ((18, 18, 50), (18, 18, 50)),  # 3h
        "excel": ((12, 12, 24), (12, 12, 30)),  # 7min
        "nice": ((9, 9, 16), (8, 8, 20)),  # 2min
        "fast": ((6, 6, 16), (5, 5, 20)),
    }
    geo = Geometry(kwargs["width"], 300, 1200, 6, *mesh_table["fast"])

    bar_e_0 = 0.233  # 偏心距
    rp_top = ReferencePoint([0, geo.len_y * bar_e_0, 0], [0, 0, -120, None, 0, 0])
    rp_bottom = ReferencePoint([0, geo.len_y * bar_e_0, 0], [0, 0, 0, None, 0, 0])
    # ===拉杆参数
    roll = Pullroll(
        geo,
        math.pi * (kwargs["dia"] / 2) ** 2,
        1,
        1,
        8,
        x_exist=True,
        y_exist=True,
        ushape=True,
    )

    # ===元参数
    taskname = f"{fm_time}_" + name + f"_{id}"
    taskpath = Path(r"D:\Casual\T_abaqus") / taskname
    meta = TaskMeta.from2(taskname, taskpath)
    meta.submit = True
    meta.time_limit = 2000

    # ===生成json
    abadata = AbaqusData(meta, concrete, steel, steelbar, geo, roll, rp_top, rp_bottom)
    taskjson_name = Path("tasks") / f"{id}.json"
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

    tt.JsonFile.write(comment_data, taskfolder / "script" / "comment_data.json")

    # ===输出信息
    markdown_table = f"""| 试件编号 | $D\\times B \\times L\\times t $        | $b_s \\times n_s \\times d_s$ | $\\bar e_0$ | 钢管钢材 | 拉杆钢筋 | 混凝土标号 |
| -------- | ------------------------------------ | --------------------------- | ---------- | -------- | -------- | ---------- |
|          | $ {geo.len_y} \\times {geo.len_x} \\times {geo.len_z} \\times {geo.tubelar_thickness}$ | ${roll.z_distance} \\times {roll.xy_number} \\times {round(2*math.sqrt(roll.area/math.pi))}$   | ${bar_e_0}$    | ${steel.grade}$ | ${steelbar.grade}$ | ${concrete.grade}$    |"""
    print(markdown_table)


@logger.catch
def main():
    iter_wid = [150, 300]
    iter_dia = range(1, 20)

    i = 0
    for j in product(iter_wid, iter_dia):
        kwargs = {"width": j[0], "dia": j[1]}
        gene(
            i,
            f"w{j[0]}_d{j[1]}",
            comment_data=kwargs,
            **kwargs,
        )
        i += 1


if __name__ == "__main__":
    main()
