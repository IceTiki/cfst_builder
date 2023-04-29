import numpy as np
from matplotlib import pyplot as plt
from dataclasses import dataclass
from typing import Union
import math

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
    """

    width: float
    high: float
    deep: float
    tubelar_thickness: float


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
    """

    area: float
    distance: float
    number: float


@dataclass
class AbaqusData:
    """

    Parameters
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
    def json_tube(self, table_len: int = 50):
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
    def json_steelbar(self, table_len: int = 50):
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
    def json_core_concrete(self, table_len: int = 50):
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
        }


@logger.catch
def main():
    concrete = materials.Concrete.from_table("C60")
    steel = materials.Steel.from_table("Q390")
    steelbar = materials.SteelBar.from_table("HRB400")
    geo = Geometry(300, 300, 1500, 6)
    roll = Pullroll(math.pi * (14 / 2) ** 2, 150, 1)
    e = 0.133  # 偏心距
    rp_top = ReferencePoint([0, geo.high * e, 0], [0, 0, -45, None, None, None])
    rp_bottom = ReferencePoint([0, geo.high * e, 0], [0, 0, 0, None, None, None])
    # steel.strength_yield = 344.45
    # steelbar.strength_criterion_yield = 387.98
    # concrete.strength_criterion_pressure = 39.82

    abadata = AbaqusData(concrete, steel, steelbar, geo, roll, rp_top, rp_bottom)
    tt.JsonFile.write(
        abadata.json_task,
        "abatmp.json",
    )
    # plt.xscale("log")
    # plt.yscale("log")
    # plt.xlabel(r"$\varepsilon$ 伸长率 (1)")
    # plt.ylabel(r"$\sigma$ 应力 (MPa)")
    # plt.savefig("tmp.png", dpi=600)
    # plt.show()


if __name__ == "__main__":
    main()
    # m = materials.Concrete.from_table("C30")
    # tmp = 5.80107
