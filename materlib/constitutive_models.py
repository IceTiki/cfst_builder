import math
from dataclasses import dataclass
from typing import Callable, Union

import numpy as np


@dataclass
class ConcreteConstitutiveModels:
    r"""
    混凝土的本构模型(适用于「带约束拉杆的方形、矩形钢管混凝土柱」有限元分析)
        参考文献: 刘鸿亮, 2013. 带约束拉杆双层钢板内填混凝土组合剪力墙抗震性能研究[D/OL]. 华南理工大学. https://kns.cnki.net/KCMS/detail/detail.aspx?dbcode=CDFD&dbname=CDFD1214&filename=1014153423.nh&v=.

    Parameters
    ---
    core_width : float
        D_c, 柱核心混凝土截面短边边长(mm)
    core_high : float
        B_c, 柱核心混凝土截面长边边长(mm)
    concrete_core_strength : float
        f_c', 核心混凝土圆柱体抗压强度(MPa)
    concrete_axial_strength : float
        f_{ck}, 核心混凝土轴心抗压强度(MPa)
    ---
    tube_area : float
        A_s, 带约束拉杆的方形、矩形钢管混凝土柱截面钢管面积(mm^2)
    tube_yield : float
        f_y, 钢管屈服强度(MPa)
    ---
    pullroll_area : float
        A_b, 单根约束拉杆的面积(mm^2)
    pullroll_yield : float
        f_{yb}, 为约束拉杆 的抗拉强度(MPa)
    pullroll_distance : float
        b_s, 柱纵向约束拉杆的间距(mm)
    pullroll_number : float
        n_s, 柱在b_s范围内约束拉杆的根数
    ---
    sqrt : Callable
        计算property使用的sqrt函数

    Note
    ---
    单位N、mm
        MPa = N/mm^2
    """
    core_width: float
    core_high: float
    concrete_core_strength: float
    concrete_axial_strength: float

    tube_area: float
    tube_yield: float

    pullroll_area: float
    pullroll_yield: float
    pullroll_distance: float
    pullroll_number: float

    sqrt: Callable = math.sqrt
    # sqrt: Callable = np.sqrt

    @property
    def area_concrete(self) -> float:
        r"""A_c, 核心混凝土面积"""
        return self.core_width * self.core_high

    @property
    def xi(self) -> float:
        r"""\xi, 钢管约束系数(紧箍系数)"""
        return (
            self.tube_area
            * self.tube_yield
            / (self.area_concrete * self.concrete_axial_strength)
        )

    @property
    def zeta(self) -> float:
        r"""\zeta, 约束拉杆约束系数"""
        return (self.pullroll_number * self.pullroll_area * self.pullroll_yield) / (
            (self.core_width + self.core_high)
            * self.pullroll_distance
            * self.concrete_axial_strength
        )

    @property
    def epsilon_concrete(self) -> float:
        return (1300 + 12.5 * self.concrete_core_strength) / (10**6)

    @property
    def epsilon_0(self) -> float:
        return self.epsilon_concrete + 800 * self.xi**0.2 * (1 + 48.5 * self.zeta) / (
            10**6
        )

    @property
    def sigma_0(self) -> float:
        return self.concrete_core_strength

    @property
    def beta_0(self) -> float:
        return self.concrete_core_strength ** (0.1) / (
            1.2 * self.sqrt(1 + self.xi) * self.sqrt(1 + 2 * self.zeta)
        )

    @property
    def elasticity_concrete(self) -> float:
        """混凝土弹性模量"""
        return 4730 * self.sqrt(self.concrete_core_strength)

    def eta(self, x) -> Union[float, np.ndarray]:
        return 1.6 + 1.5 / x

    def model(self, epsilon: np.ndarray) -> np.ndarray:
        """
        混凝土的本构模型

        Parameters
        ---
        epsilon : np.ndarray
            应变

        Returns
        ---
        sigma : np.ndarray
            应力
        """
        epsilon = np.array(epsilon)
        x = epsilon / self.epsilon_0
        mask = x <= 1

        func_1 = lambda x: 2 * x - x * x
        func_2 = lambda x: x / (self.beta_0 * (x - 1) ** self.eta(x) + x)
        y = np.piecewise(x, (mask, ~mask), (func_1, func_2))

        sigma = self.sigma_0 * y
        return sigma


@dataclass
class PullrollConstitutiveModels:
    """
    约束拉杆的本构模型(二折线模型)
        参考文献: 刘鸿亮, 2013. 带约束拉杆双层钢板内填混凝土组合剪力墙抗震性能研究[D/OL]. 华南理工大学. https://kns.cnki.net/KCMS/detail/detail.aspx?dbcode=CDFD&dbname=CDFD1214&filename=1014153423.nh&v=.

    Parameters
    ---
    steel_yield : float
        约束拉杆屈服强度(MPa)
    elastic_modulus : float
        约束拉杆弹性模量(MPa)

    Note
    ---
    单位N、mm
        MPa = N/mm^2
    """

    steel_yield: float
    elastic_modulus: float

    @property
    def epsilon_yield(self) -> float:
        """约束拉杆屈服应变"""
        return self.steel_yield / self.elastic_modulus

    def model(self, epsilon: np.ndarray) -> np.ndarray:
        """
        约束拉杆的本构模型

        Parameters
        ---
        epsilon : np.ndarray
            应变

        Returns
        ---
        sigma : np.ndarray
            应力
        """
        sigma = np.zeros(epsilon.shape)
        if np.min(epsilon) < 0:
            raise ValueError("epsilon应是非负数组")

        func_1 = lambda x: self.elastic_modulus * x
        func_2 = (
            lambda x: self.steel_yield
            + self.elastic_modulus * (x - self.epsilon_yield) / 100
        )

        mask = epsilon <= self.epsilon_yield
        sigma = np.piecewise(epsilon, (mask, ~mask), (func_1, func_2))
        return sigma


@dataclass
class SteelTubelarConstitutiveModels:
    r"""
    钢管的本构模型(简化四折线二次流塑模型)
        参考文献: 刘鸿亮, 2013. 带约束拉杆双层钢板内填混凝土组合剪力墙抗震性能研究[D/OL]. 华南理工大学. https://kns.cnki.net/KCMS/detail/detail.aspx?dbcode=CDFD&dbname=CDFD1214&filename=1014153423.nh&v=.

    Parameters
    ---
    steel_yield : float
        f_{y}, 钢材屈服强度(MPa)
    steel_ultimate : float
        f_{u}, 钢材的极限抗拉强度(MPa)
    elastic_modulus : float
        E_a, 钢材的弹性模量(MPa)
    Note
    ---
    单位N、mm
        MPa = N/mm^2
    """
    steel_yield: float
    steel_ultimate: float
    elastic_modulus: float

    @property
    def epsilon_yield(self):
        """epsilon_{y}, 钢材屈服应变"""
        return self.steel_yield / self.elastic_modulus

    def model(self, epsilon: np.ndarray) -> np.ndarray:
        """
        钢管的本构模型

        Parameters
        ---
        epsilon : np.ndarray
            应变

        Returns
        ---
        sigma : np.ndarray
            应力
        """
        if np.min(epsilon) < 0:
            raise ValueError("epsilon应是非负数组")

        func_3 = lambda x: self.steel_yield + (
            self.steel_ultimate - self.steel_yield
        ) * (x - 10 * self.epsilon_yield) / (90 * self.epsilon_yield)

        sigma = np.piecewise(
            epsilon,
            (
                epsilon <= self.epsilon_yield,
                (self.epsilon_yield < epsilon) & (epsilon <= 10 * self.epsilon_yield),
                (10 * self.epsilon_yield < epsilon)
                & (epsilon <= 100 * self.epsilon_yield),
                100 * self.epsilon_yield < epsilon,
            ),
            (
                lambda x: self.elastic_modulus * x,
                self.steel_yield,
                func_3,
                self.steel_ultimate,
            ),
        )
        return sigma
