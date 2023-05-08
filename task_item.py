from dataclasses import dataclass
from pathlib import Path
from typing import Union
import math
import numpy as np

from materlib import materials, constitutive_models


@dataclass
class Geometry:
    """
    Parameters
    ---
    len_x : float
        B, 截面短边边长(mm)
    len_y : float
        D, 截面长边边长(mm)
    len_z : float
        H, 柱高度(mm)
    tubelar_thickness : float
        t, 钢管厚度(mm)
    concrete_mesh : float
        混凝土布种数量(x,y,z)方向
    steel_mesh : float
        钢材布种数量(x,y,z)方向
    """

    len_x: float
    len_y: float
    len_z: float
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
    Notice
    ---

    Parameters
    ---
    geo : Geometry
        构件几何信息
    area : float
        A_b, 单根约束拉杆的面积(mm^2), (U型连接件的截面积不需要乘2, 仅算弯折前的截面面积)
    x_number, y_number, z_number: int
        x/y/z方向拉杆个数
    ushape : bool
        是否为U型连接件
    x_exist, y_exist : bool
        是否有x/y方向拉杆
    """

    geo: Geometry
    area: float
    x_number: int = 1
    y_number: int = 1
    z_number: int = 10
    ushape: bool = False
    x_exist: bool = True
    y_exist: bool = True

    @property
    def xy_number(self) -> float:
        """n_s, 柱在b_s范围内约束拉杆的根数"""
        return (self.x_number if self.x_exist else 0) + (
            self.y_number if self.y_exist else 0
        )

    @property
    def x_distance(self) -> float:
        """x方向拉杆的间隔"""
        return self.geo.len_y / (self.x_number + 1 if self.x_exist else 2)

    @property
    def y_distance(self) -> float:
        """y方向拉杆的间隔"""
        return self.geo.len_x / (self.y_number + 1 if self.y_exist else 2)

    @property
    def z_distance(self) -> float:
        """b_s, 柱纵向约束拉杆的间距(mm)"""
        return self.geo.len_z / (self.z_number + 1)

    @property
    def calculation_area(self) -> float:
        r"""混凝土本构的计算截面积, U型连接件的计算截面面积为2倍"""
        return self.area * (2 if self.ushape else 1)

    def __test__(self):
        # z_number = math.ceil(
        #     (self.geometry.length - self.pullroll.z_distance) / self.pullroll.z_distance
        # )
        # z_start = (self.geometry.length - self.pullroll.z_distance * z_number) / 2
        return None


@dataclass
class TaskMeta:
    """

    Parameters
    ---
    jobname : str
        job名
    caename : str
        cae名称
    taskfolder : str
        任务数据保存路径
    modelname : str
        model名

    submit : bool
        是否提交作业
    time_limit : float
        作业最高运行时间(秒)
    """

    jobname: str
    caename: str
    taskfolder: str
    modelname: str

    submit: bool = False
    time_limit: float = None

    @classmethod
    def from2(cla, name: str, path: str):
        """快速构造类"""
        return cla("job_" + name, "cae_" + name, path, "model_" + name)

    @property
    def caepath(self):
        taskfolder = Path(self.taskfolder)
        return str(taskfolder / self.caename)


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
            * (self.geometry.len_y + self.geometry.len_x)
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
        )  # !圆柱体抗压强度约为f_ck的1.25倍
        concrete_model = constitutive_models.ConcreteConstitutiveModels(
            self.geometry.len_x,
            self.geometry.len_y,
            concrete_core_strength,
            self.concrete.strength_pressure,
            self.tube_area,
            self.steel.strength_yield,
            self.pullroll.calculation_area,
            self.steelbar.strength_criterion_yield,
            self.pullroll.z_distance,
            self.pullroll.xy_number,
        )

        concrete_cut = 0.00001

        x = np.linspace(concrete_cut, 0.3, table_len)
        y = concrete_model.model(x)
        x[0] = 0

        # ===混凝土塑性损伤的断裂能

        concrete_gfi = np.interp(concrete_core_strength, [20, 40], [40, 120])
        # print(f"{self.concrete.strength_tensile}MPa <-> {concrete_gfi}N/m")

        return {
            "sigma": y.tolist(),
            "epsilon": x.tolist(),
            "elastic_modulus": self.concrete.elastic_modulus,
            "strength_fracture": concrete_core_strength / 10,
            "gfi": concrete_gfi,
        }

    @property
    def json_geometry(self):
        return {
            "x_len": self.geometry.len_x,
            "y_len": self.geometry.len_y,
            "z_len": self.geometry.len_z,
            "tube_thickness": self.geometry.tubelar_thickness,
            "concrete_seed": tuple(
                j / i
                for i, j in zip(
                    self.geometry.concrete_mesh,
                    (self.geometry.len_x, self.geometry.len_y, self.geometry.len_z),
                )
            ),
            "steel_seed": tuple(
                j / i
                for i, j in zip(
                    self.geometry.steel_mesh,
                    (self.geometry.len_x, self.geometry.len_y, self.geometry.len_z),
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
        return {
            "area": self.pullroll.area,
            "ushape": self.pullroll.ushape,
            # ===z
            "z_number": self.pullroll.z_number,
            "z_distance": self.pullroll.z_distance,
            # ===x
            "x_number": self.pullroll.x_number,
            "x_distance": self.pullroll.x_distance,
            "x_exist": self.pullroll.x_exist,
            # ===y
            "y_number": self.pullroll.y_number,
            "y_distance": self.pullroll.y_distance,
            "y_exist": self.pullroll.y_exist,
        }

    @property
    def json_meta(self):
        return {
            "jobname": str(self.meta.jobname),
            "caepath": str(self.meta.caepath),
            "taskfolder": str(self.meta.taskfolder),
            "modelname": str(self.meta.modelname),
            "submit": self.meta.submit,
            "time_limit": self.meta.time_limit,
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
