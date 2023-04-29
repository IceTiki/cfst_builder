import numpy as np
from matplotlib import pyplot as plt
from dataclasses import dataclass

from materlib import materials, constitutive_models
from loguru import logger
from tikilib import plot as tp
from tikilib import binary as tb
from tikilib import text as tt


tp.chinese_font_support()


@dataclass
class AbaqusData:
    """

    Parameters
    ---
    concrete : materials.Concrete
    steel : materials.Steel
    steelbar : materials.SteelBar
    ---
    core_width : float
        D_c, 柱核心混凝土截面短边边长(mm)
    core_high : float
        B_c, 柱核心混凝土截面长边边长(mm)
    column_length : float
        H, 柱高度(mm)
    tube_thickness : float
        t, 钢管厚度(mm)
    ---
    pullroll_area : float
        A_b, 单根约束拉杆的面积(mm^2)
    pullroll_distance : float
        b_s, 柱纵向约束拉杆的间距(mm)
    pullroll_number : float
        n_s, 柱在b_s范围内约束拉杆的根数

    Note
    ---
    单位N、mm
        MPa = N/mm^2
    """

    concrete: materials.Concrete
    steel: materials.Steel
    steelbar: materials.SteelBar

    core_width: float
    core_high: float
    column_length: float
    tube_thickness: float

    pullroll_area: float
    pullroll_distance: float
    pullroll_number: float

    @property
    def tube_area(self):
        """A_s, 带约束拉杆的方形、矩形钢管混凝土柱截面钢管面积(mm^2)"""
        return 2 * (self.core_high + self.core_width) * self.tube_thickness

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
    def json_pullroll(self, table_len: int = 50):
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
        concrete_model = constitutive_models.ConcreteConstitutiveModels(
            self.core_width,
            self.core_high,
            self.concrete.strength_pressure * 1.25,  # !圆柱体抗压强度暂取f_ck的1.25倍
            self.concrete.strength_pressure,
            self.tube_area,
            self.steel.strength_yield,
            self.pullroll_area,
            self.steelbar.strength_criterion_yield,
            self.pullroll_distance,
            self.pullroll_number,
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

        concrete_gfi = np.interp(
            self.concrete.strength_pressure * 1.25, [20, 40], [40, 120]
        )
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
            "width": self.core_width,
            "high": self.core_high,
            "length": self.column_length,
            "tube_thickness": self.tube_thickness,
        }

    @property
    def json_task(self):
        return {
            "materials": {
                "concrete": self.json_core_concrete,
                "steel": self.json_tube,
                "steelbar": self.json_pullroll,
            },
            "geometry": self.json_geometry,
        }


@logger.catch
def main():
    concrete = materials.Concrete.from_table("C40")
    steel = materials.Steel.from_table("Q345GJ")
    steelbar = materials.SteelBar.from_table("HRB335")

    # steel.strength_yield = 344.45
    # steelbar.strength_criterion_yield = 387.98
    # concrete.strength_criterion_pressure = 39.82
    e = 0.133  # todo
    print("偏心距", e * 300)

    abadata = AbaqusData(
        concrete, steel, steelbar, 300, 300, 1500, 6, np.pi * (14 / 2) ** 2, 150, 1
    )
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
