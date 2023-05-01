import numpy as np
from matplotlib import pyplot as plt
from dataclasses import dataclass
from typing import Union
import math
import time, datetime
from pathlib import Path

from materlib import materials, constitutive_models
from loguru import logger
from tikilib import plot as tp
from tikilib import binary as tb
from tikilib import text as tt


tp.chinese_font_support()


@dataclass
class Geometry:
    """
    Parameters
    ---
    width : float
        D, 截面短边边长(mm)
    high : float
        B, 截面长边边长(mm)
    deep : float
        H, 柱高度(mm)
    tubelar_thickness : float
        t, 钢管厚度(mm)
    concrete_mesh : float
        混凝土布种数量(x,y,z)方向
    steel_mesh : float
        钢材布种数量(x,y,z)方向
    """

    width: float
    high: float
    deep: float
    tubelar_thickness: float
    concrete_mesh: tuple[int, ...] = (6, 6, 10)
    steel_mesh: tuple[int, ...] = (5, 5, 8)


@dataclass
class ReferencePoint:
    """
    Parameters
    ---
    shift : list[float]
        偏移坐标(x,y,z)
    displacement : list[float | None]
        位移(U1, U2, U3, RU1, RU2, RU3), 如果为None会转变为abaqus的UNSET
    """

    shift: list[float]
    displacement: list[Union[float, None]]


@dataclass
class Pullroll:
    """
    Parameters
    ---
    area : float
        A_b, 单根约束拉杆的面积(mm^2)
    distance : float
        b_s, 柱纵向约束拉杆的间距(mm)
    number : float
        n_s, 柱在b_s范围内约束拉杆的根数
    only_x : bool
        将y方形的拉杆面积设为1(约等于0)
    """

    area: float
    distance: float
    number: float
    only_x: bool = False


@dataclass
class TaskMeta:
    """

    Parameters
    ---
    jobname : str
        job名
    caename : str
        cae名称
    caepath : str
        cae路径
    modelname : str
        model名
    submit : bool
        是否提交作业
    time_limit : float
        作业最高运行时间
    ushape : bool
        是否为U型连接件
    """

    jobname: str
    caename: str
    caepath: str
    modelname: str

    submit: bool = False
    time_limit: float = 3600

    ushape: bool = True


@dataclass
class AbaqusData:
    """

    Parameters
    ---
    meta : TaskMeta
    ---
    concrete : materials.Concrete
    steel : materials.Steel
    steelbar : materials.SteelBar
        约束拉杆材料
    ---
    geometry : Geometry
    pullroll : Pullroll
        约束拉杆分布
    reterpoint_top, referpoint_bottom: ReferencePoint
        上下参考点

    Note
    ---
    单位N、mm
        MPa = N/mm^2
    """

    meta: TaskMeta
    concrete: materials.Concrete
    steel: materials.Steel
    steelbar: materials.SteelBar
    geometry: Geometry
    pullroll: Pullroll
    reterpoint_top: ReferencePoint
    referpoint_bottom: ReferencePoint

    @property
    def tube_area(self):
        """A_s, 带约束拉杆的方形、矩形钢管混凝土柱截面钢管面积(mm^2)"""
        return (
            2
            * (self.geometry.high + self.geometry.width)
            * self.geometry.tubelar_thickness
        )

    @property
    def json_tube(self, table_len: int = 10000):
        """钢管"""
        steel_model = constitutive_models.SteelTubelarConstitutiveModels(
            self.steel.strength_yield,
            self.steel.strength_tensile,
            self.steel.elastic_modulus,
        )

        x = np.linspace(
            self.steel.strength_yield / self.steel.elastic_modulus, 0.2, table_len
        )
        y = steel_model.model(x)
        # plt.scatter(x, y, s=1)
        return {
            "sigma": y.tolist(),
            "epsilon": (
                x - self.steel.strength_yield / self.steel.elastic_modulus
            ).tolist(),
            "elastic_modulus": self.steel.elastic_modulus,
        }

    @property
    def json_steelbar(self, table_len: int = 10000):
        """约束拉杆"""
        steelbar_model = constitutive_models.PullrollConstitutiveModels(
            self.steelbar.strength_criterion_yield,
            self.steelbar.elastic_modulus,
        )
        x = np.linspace(
            self.steelbar.strength_criterion_yield / self.steelbar.elastic_modulus,
            0.2,
            table_len,
        )
        y = steelbar_model.model(x)
        # plt.scatter(x, y, s=1)
        return {
            "sigma": y.tolist(),
            "epsilon": (
                x
                - self.steelbar.strength_criterion_yield / self.steelbar.elastic_modulus
            ).tolist(),
            "elastic_modulus": self.steelbar.elastic_modulus,
        }

    @property
    def json_core_concrete(self, table_len: int = 10000):
        """核心混凝土"""
        concrete_core_strength = (
            self.concrete.strength_pressure * 1.25
        )  # !圆柱体抗压强度暂取f_ck的1.25倍
        concrete_model = constitutive_models.ConcreteConstitutiveModels(
            self.geometry.width,
            self.geometry.high,
            concrete_core_strength,
            self.concrete.strength_pressure,
            self.tube_area,
            self.steel.strength_yield,
            self.pullroll.area,
            self.steelbar.strength_criterion_yield,
            self.pullroll.distance,
            self.pullroll.number,
        )

        x = np.linspace(0, 0.03, table_len)
        y = concrete_model.model(x)
        for i, j in zip(x, y):
            if j >= self.concrete.strength_pressure:
                concrete_cut = i
                break
        else:
            raise Exception("??????")
        concrete_cut = 0.0001

        x = np.linspace(concrete_cut, 0.03, table_len) + (0.03 - 0) / table_len
        y = concrete_model.model(x)
        # plt.scatter(x, y, s=1)

        x = x - concrete_cut
        x[0] = 0

        # ===混凝土塑性损伤的断裂能

        concrete_gfi = np.interp(concrete_core_strength, [20, 40], [40, 120])
        print(f"{self.concrete.strength_tensile}MPa <-> {concrete_gfi}N/m")

        return {
            "sigma": y.tolist(),
            "epsilon": x.tolist(),
            "elastic_modulus": self.concrete.elastic_modulus,
            "strength_tensile": self.concrete.strength_tensile,
            "gfi": concrete_gfi,
        }

    @property
    def json_geometry(self):
        return {
            "width": self.geometry.width,
            "high": self.geometry.high,
            "length": self.geometry.deep,
            "tube_thickness": self.geometry.tubelar_thickness,
            "concrete_seed": tuple(
                j / i
                for i, j in zip(
                    self.geometry.concrete_mesh,
                    (self.geometry.width, self.geometry.high, self.geometry.deep),
                )
            ),
            "steel_seed": tuple(
                j / i
                for i, j in zip(
                    self.geometry.steel_mesh,
                    (self.geometry.width, self.geometry.high, self.geometry.deep),
                )
            ),
        }

    @property
    def json_referpoint(self):
        return {
            "top": {
                "shift": self.reterpoint_top.shift,
                "displacement": self.reterpoint_top.displacement,
            },
            "bottom": {
                "shift": self.referpoint_bottom.shift,
                "displacement": self.referpoint_bottom.displacement,
            },
        }

    @property
    def json_pullroll(self):
        number_z = math.ceil(
            (self.geometry.deep - self.pullroll.distance) / self.pullroll.distance
        )
        start_shift = (self.geometry.deep - self.pullroll.distance * number_z) / 2
        return {
            "area": self.pullroll.area,
            "distance": self.pullroll.distance,
            "number_xy": self.pullroll.number,
            "number_z": number_z,
            "start_shift": start_shift,
            "only_x": self.pullroll.only_x,
        }

    @property
    def json_meta(self):
        taskfolder = Path(self.meta.caepath)
        taskfolder.mkdir(exist_ok=True, parents=True)
        caepath = str(taskfolder / self.meta.caename)
        return {
            "jobname": self.meta.jobname,
            "caepath": caepath,
            "taskfolder": str(taskfolder),
            "modelname": self.meta.modelname,
            "submit": self.meta.submit,
            "time_limit": self.meta.time_limit,
            "ushape": self.meta.ushape,
        }

    @property
    def json_task(self):
        return {
            "materials": {
                "concrete": self.json_core_concrete,
                "steel": self.json_tube,
                "steelbar": self.json_steelbar,
            },
            "geometry": self.json_geometry,
            "referpoint": self.json_referpoint,
            "pullroll": self.json_pullroll,
            "meta": self.json_meta,
        }


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
        False,
        3600,
        True,
    )

    geo = Geometry(300, 300, 1200, 6, (6, 6, 12), (5, 5, 10))
    roll = Pullroll(math.pi * (14 / 2) ** 2, 150, 1, False)
    e = 0.2  # 偏心距
    rp_top = ReferencePoint([0, geo.high * e, 0], [0, 0, -200, None, 0, 0])
    rp_bottom = ReferencePoint([0, geo.high * e, 0], [0, 0, 0, None, 0, 0])

    abadata = AbaqusData(meta, concrete, steel, steelbar, geo, roll, rp_top, rp_bottom)
    tt.JsonFile.write(
        abadata.json_task,
        "abatmp.json",
    )


if __name__ == "__main__":
    main()
    # m = materials.Concrete.from_table("C30")
    # tmp = 5.80107
