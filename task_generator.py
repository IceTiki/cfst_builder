import math
import time
from pathlib import Path
import os
import shutil
from itertools import product

from loguru import logger
from tikilib import plot as tp
from tikilib import text as tt
from tikilib import system as ts

from materlib import materials
from task_item import Geometry, ReferencePoint, RodPattern, TaskMeta, AbaqusData

tp.chinese_font_support()


def format_time():
    time_struct = time.localtime()
    date_str = f"{time_struct.tm_year}-{time_struct.tm_mon}-{time_struct.tm_mday}"
    time_str = f"{time_struct.tm_hour}-{time_struct.tm_min}-{time_struct.tm_sec}"
    return f"{time_str}"


def gene(id: int, name: str, comment_data: dict = {}, *args, **kwargs):
    fm_time = format_time()
    # ===材料参数
    concrete = materials.Concrete.from_table(kwargs["concrete"])
    steel = materials.Steel.from_table(kwargs["steel"])
    steelbar = materials.SteelBar.from_table("HRB400")

    # ===几何参数
    mesh_table = {
        "best": ((18, 18, 50), (18, 18, 50)),  # 3h
        "excel": ((12, 12, 24), (12, 12, 30)),  # 7min
        "nice": ((9, 9, 16), (7, 7, 14)),  # 2min
        "fast": ((6, 6, 16), (5, 5, 12)),
    }
    geo = Geometry(kwargs["width"], kwargs["high"], 1200, 6, *mesh_table["nice"])

    # ===参考点
    bar_e_0 = kwargs["e"]  # 偏心距
    rp_top = ReferencePoint.init_from_datum(
        geo, [0, geo.y_len * bar_e_0, 0], [0, 0, -120, None, 0, 0], "top"
    )
    rp_bottom = ReferencePoint.init_from_datum(
        geo, [0, geo.y_len * bar_e_0, 0], [0, 0, 0, None, 0, 0], "bottom"
    )

    # ===拉杆参数
    roll = RodPattern.init_from_pattern(
        geo,
        kwargs["dia"],
        24,
        RodPattern.get_orthogonal_pattern(2, 5),
        [
            [0.3, 0.4],
            [0.6, 0.2],
        ],
        kwargs["layer_number"],
    )

    # ===元参数
    taskname = f"{fm_time}_" + name + f"_{id}"
    taskpath = Path(r"D:\Casual\T_abaqus") / taskname
    # taskpath = Path(r"D:\ICECASUAL\TABA") / taskname
    taskpath.mkdir(parents=True, exist_ok=True)
    meta = TaskMeta.inti_2(taskname, taskpath)
    meta.submit = kwargs["submit"]
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
        "abaqus_modeling.py",
        "task_generator.py",
        "task_item.py",
        taskjson_name,
    ):
        (taskfolder / "script" / i).parent.mkdir(exist_ok=True, parents=True)
        shutil.copy(i, taskfolder / "script" / i)

    tt.JsonFile.write(comment_data, taskfolder / "script" / "comment_data.json")

    # ===输出信息


#     markdown_table = f"""| 试件编号 | $D\\times B \\times L\\times t $        | $b_s \\times n_s \\times d_s$ | $\\bar e_0$ | 钢管钢材 | 拉杆钢筋 | 混凝土标号 |
# | -------- | ------------------------------------ | --------------------------- | ---------- | -------- | -------- | ---------- |
# |          | $ {geo.len_y} \\times {geo.len_x} \\times {geo.len_z} \\times {geo.tubelar_thickness}$ | ${roll.z_distance} \\times {roll.xy_number} \\times {round(2*math.sqrt(roll.area/math.pi))}$   | ${bar_e_0}$    | ${steel.grade}$ | ${steelbar.grade}$ | ${concrete.grade}$    |"""
#     print(markdown_table)


@logger.catch
def main():
    contbl = "C20 C25 C30 C35 C40 C45 C50 C55 C60 C65 C70 C75 C80".split(" ")
    stltbl = "Q235 Q355 Q390 Q420 Q460".split(" ")

    kwtemplate = {
        "concrete": "C60",
        "steel": "Q390",
        "width": 300,
        "high": 300,
        "e": 0.233,
        "xy": "xy",
        "dia": 14,
        "center_dia": 24,
        "layer_number": 8,
        "submit": False,
    }
    taskuuid = 0

    # ================clean_old===================
    for i in Path("tasks").glob("*.json"):
        os.remove(i)

    tt.JsonFile.write({"start_at": 0, "flag": 0}, "tasks/control.json")
    # ================mater======================
    for i, j in product(contbl, stltbl):
        kwargs = kwtemplate.copy()
        kwargs["concrete"] = i
        kwargs["steel"] = j
        gene(
            taskuuid,
            f"material",
            comment_data=kwargs,
            **kwargs,
        )
        return
        taskuuid += 1

    # ========sec=========
    i_z = 300**4 / 12
    iter_width = [300, 270, 240, 210, 180, 150, 120]
    iter_high = [round(math.pow(12 * i_z / i, 1 / 3), 2) for i in iter_width]
    for i, j in zip(iter_width, iter_high):
        kwargs = kwtemplate.copy()
        kwargs["width"] = i
        kwargs["high"] = j
        gene(
            taskuuid,
            f"section",
            comment_data=kwargs,
            **kwargs,
        )

        taskuuid += 1

    # =========xy=========
    iter1 = (150, 300)
    iter2 = ("x", "y", "xy")
    iter3 = [3, 4, 5, 6, 8, 10, 12, 15, 16, 20]

    for i1, i2, i3 in product(iter1, iter2, iter3):
        kwargs = kwtemplate.copy()
        kwargs["width"] = i1
        kwargs["xy"] = i2
        kwargs["layer_number"] = i3
        gene(
            taskuuid,
            f"xy",
            comment_data=kwargs,
            **kwargs,
        )

        taskuuid += 1

    # =========dia=========

    iter_wid = [150, 300]
    iter_dia = range(8, 22, 2)

    for wid, dia in product(iter_wid, iter_dia):
        kwargs = kwtemplate.copy()
        kwargs["width"] = wid
        kwargs["dia"] = dia
        gene(
            taskuuid,
            f"dia",
            comment_data=kwargs,
            **kwargs,
        )

        taskuuid += 1

    # ========e=========
    iter_wid = [150, 300]
    iter_e = [i / 300 for i in range(0, 100, 10)]

    for wid, e in product(iter_wid, iter_e):
        kwargs = kwtemplate.copy()
        kwargs["width"] = wid
        kwargs["e"] = e
        gene(
            taskuuid,
            f"e",
            comment_data=kwargs,
            **kwargs,
        )

        taskuuid += 1


if __name__ == "__main__":
    main()
