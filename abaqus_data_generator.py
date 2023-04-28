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
    ---
    tube_area : float
        A_s, 带约束拉杆的方形、矩形钢管混凝土柱截面钢管面积(mm^2)
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

    tube_area: float

    pullroll_area: float
    pullroll_distance: float
    pullroll_number: float

    @property
    def json_tube(self, table_len: int = 50):
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
    def data_pullroll(self, table_len: int = 50):
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
        concrete_model = constitutive_models.ConcreteConstitutiveModels(
            self.core_width,
            self.core_high,
            self.concrete.strength_pressure / 0.8,
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

        x = np.linspace(concrete_cut, 0.03, table_len) + (0.03 - 0) / table_len
        y = concrete_model.model(x)
        # plt.scatter(x, y, s=1)

        x = x - concrete_cut
        x[0] = 0
        return {
            "sigma": y.tolist(),
            "epsilon": x.tolist(),
            "elastic_modulus": self.concrete.elastic_modulus,
        }


@logger.catch
def main():
    concrete = materials.Concrete.from_table("C50")
    steel = materials.Steel.from_table("Q355")
    steelbar = materials.SteelBar.from_table("HRB400")
    abadata = AbaqusData(concrete, steel, steelbar, 500, 500, 5 * 500 * 4, 1, 1, 0)

    json_data = {
        "materials": {
            "concrete": abadata.json_core_concrete,
            "steel": abadata.json_tube,
            "steelbar": abadata.data_pullroll,
        }
    }
    tt.JsonFile.write(
        json_data,
        "abatmp.json",
    )
    # plt.xscale("log")
    # plt.yscale("log")
    # plt.xlabel(r"$\varepsilon$ 伸长率 (1)")
    # plt.ylabel(r"$\sigma$ 应力 (MPa)")
    # plt.savefig("tmp.png", dpi=600)
    # plt.show()

    # ===混凝土塑性损伤的断裂能
    print(
        f"{abadata.concrete.strength_tensile}MPa <-> {np.interp(abadata.concrete.strength_pressure / 0.8, [20, 40], [40, 120])}N/mm"
    )


if __name__ == "__main__":
    main()
    # m = materials.Concrete.from_table("C30")
    # tmp = 5.80107
