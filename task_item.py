from dataclasses import dataclass
import itertools
from pathlib import Path
from typing import Union, Literal
import math
import numpy as np
import json

from materlib import materials, constitutive_models
from tikilib import crypto as tc
from tikilib import text as tt


class Utils:
    def __encrypt(content: str):
        return tc.SimpleAES_StringCrypto("2023_graduation_project").encrypt(content)

    def __decrypt(content: str):
        return tc.SimpleAES_StringCrypto("2023_graduation_project").decrypt(content)

    @classmethod
    def get_encrypt_code(cla):
        # TODO
        repository = Path(__file__).parent
        data = {}
        for i in repository.glob("*.py"):
            k = str(i.name)
            v = i.read_text(encoding="utf-8")
            k, v = map(cla.__encrypt, (k, v))
            data[k] = v

        data = json.dumps(data, ensure_ascii=False)
        return data


@dataclass
class Geometry:
    """
    Parameters
    ---
    x_len : float
        B, 截面短边边长(mm)
    y_len : float
        D, 截面长边边长(mm)
    z_len : float
        H, 柱高度(mm)
    tubelar_thickness : float
        t, 钢管厚度(mm)
    concrete_mesh : float
        混凝土布种数量(x,y,z)方向
    steel_mesh : float
        钢材布种数量(x,y,z)方向
    """

    mesh_table = {
        "best": ((18, 18, 60), (18, 18, 60)),  # 3h
        "excel": ((12, 12, 24), (12, 12, 30)),  # 7min
        "nice": ((9, 9, 16), (7, 7, 20)),  # 2min
        "fast": ((6, 6, 16), (5, 5, 12)),
    }

    x_len: float
    y_len: float
    z_len: float
    tubelar_thickness: float
    concrete_mesh: tuple[int, ...] = (6, 6, 10)
    steel_mesh: tuple[int, ...] = (5, 5, 8)

    @property
    def tube_section_area(self):
        """A_s, 带约束拉杆的方形、矩形钢管混凝土柱截面钢管面积(mm^2)"""
        return 2 * (self.y_len + self.x_len) * self.tubelar_thickness

    @property
    def concrete_grid_size(self):
        return tuple(
            j / i
            for i, j in zip(
                self.concrete_mesh,
                (self.x_len, self.y_len, self.z_len),
            )
        )

    @property
    def steel_grid_size(self):
        return tuple(
            j / i
            for i, j in zip(
                self.steel_mesh,
                (self.x_len, self.y_len, self.z_len),
            )
        )

    @property
    def common_parameters(self):
        datas = {}
        for point in itertools.product(range(3), range(3), range(3)):
            point = tuple(point)
            point_position = tuple(
                i * j / 2 for i, j in zip(point, (self.x_len, self.y_len, self.z_len))
            )
            datas[f"p{''.join(map(str, point))}"] = point_position

        return datas

    def extract(self):
        return {
            "x_len": self.x_len,
            "y_len": self.y_len,
            "z_len": self.z_len,
            "tube_thickness": self.tubelar_thickness,
            "concrete_grid_size": self.concrete_grid_size,
            "steel_grid_size": self.steel_grid_size,
            "common_parameters": self.common_parameters,
        }


@dataclass
class ReferencePoint:
    """
    Parameters
    ---
    position : tuple[float], default=(0,0,0)
        坐标(x,y,z)
    displacement : tuple[float | None], default=(None, )*6
        施加约束(U1, U2, U3, RU1, RU2, RU3), 如果为None会在建模脚本中被转化为abaqus的UNSET
    """

    position: tuple[float] = (0, 0, 0)
    displacement: tuple[Union[float, None]] = (None,) * 6

    @classmethod
    def init_from_datum(
        cla,
        geo: Geometry,
        shift: list[float],
        displacement: list[Union[float, None]],
        face: Literal["top", "bottom"],
    ):
        """
        以构件一个面的中心为基准, 得到偏移后的坐标点。

        Parameters
        ---
        geo : Geometry
            构件几何参数
        shift : list[float]
            偏移量(x,y,z)
        displacement : list[float | None]
            固定位移(U1, U2, U3, RU1, RU2, RU3), 如果为None会转变为abaqus的UNSET(无约束)
        face : {'top', 'bottom'}
            面(顶面/底面)
        """
        if face == "top":
            datum = (geo.x_len / 2, geo.y_len / 2, geo.z_len)
        elif face == "bottom":
            datum = (geo.x_len / 2, geo.y_len / 2, 0)
        else:
            raise ValueError(f"{face} not a supported face")

        position = tuple(i + j for i, j in zip(shift, datum))
        return cla(position, displacement)

    def extract(self):
        return {"position": self.position, "displacement": self.displacement}


@dataclass
class RodPattern:
    """
    Parameters
    ---
    area_rod : float
        A_b, 单根约束拉杆的面积(mm^2)
    area_pole : float
        约束立杆截面面积
    pattern_rod : tuple[Line2d]
        拉杆平面布置
    pattern_pole : tuple[Point2d]
        立杆平面布置
    number_layer_rods : float
        n_b, 柱在b_s范围内约束拉杆的根数
    number_layers : int
        拉杆布置层数
    layer_spacing : float
        b_s, 柱纵向约束拉杆的间距(mm)
    """

    Point2d = tuple[float, float]
    Line2d = tuple[Point2d, Point2d]

    area_rod: float
    area_pole: float
    pattern_rod: tuple[Line2d]
    pattern_pole: tuple[Point2d]
    number_layer_rods: float
    number_layers: int
    layer_spacing: float

    @staticmethod
    def get_division(number: int) -> tuple:
        """
        获取分割区间的位置

        Parameters
        ---
        number : int
            分割区间的位置数

        Examples
        ---
        >>> get_division(1)
        (0.5)

        >>> get_division(4)
        (0.2, 0.4, 0.6, 0.8)
        """
        return tuple((i + 1) / (number + 1) for i in range(number))

    @classmethod
    def get_orthogonal_pattern(cla, x_number=1, y_number=1) -> tuple[Line2d]:
        """
        获取约束拉杆的正交图案
        Parameters
        ---
        x_number : int
            平行x轴方向约束拉杆的数量
        y_number : int
            平行x轴方向约束拉杆的数量
        """
        rod_patten = tuple()

        for i in cla.get_division(x_number):
            p1 = (0, i)
            p2 = (1, i)
            line = (p1, p2)
            rod_patten += (line,)

        for i in cla.get_division(y_number):
            p1 = (i, 0)
            p2 = (i, 1)
            line = (p1, p2)
            rod_patten += (line,)
        return rod_patten

    @classmethod
    def init_from_pattern(
        cla,
        geo: Geometry,
        dia_rod: float,
        dia_pole: float,
        pattern_rod_normal: tuple[Line2d],
        pattern_pole_normal: tuple[Point2d],
        number_layers: int,
    ):
        """
        Parameters
        ---
        geo : Geometry
            构件几何参数
        dia_rod : float
            d_s, 单根约束拉杆的直径(mm)
        dia_pole : float
            约束立杆的直径(mm)
        pattern_rod_normal : tuple[Line2d]
            拉杆平面布置(构件截面坐标系, 构件副对角线坐标分别为(0,0)和(1,1))
        pattern_pole_normal : tuple[Point2d]
            立杆平面布置(构件截面坐标系, 构件副对角线坐标分别为(0,0)和(1,1))
        number_layers : int
            拉杆布置层数
        """
        contact_number = 0
        for line in pattern_rod_normal:
            for point in line:
                if point[0] == 0 or point[0] == 1:
                    contact_number += 1
                elif point[1] == 0 or point[1] == 1:
                    contact_number += 1
        number_rod = contact_number / 2

        converpoint = lambda point: tuple(
            i * j for i, j in zip(point, (geo.x_len, geo.y_len))
        )

        # ===坐标转换
        pattern_rod = tuple(
            tuple(converpoint(point) for point in line) for line in pattern_rod_normal
        )
        pattern_pole = tuple(map(converpoint, pattern_pole_normal))

        layer_spacing = geo.z_len / (number_layers + 1)

        area_rod, area_pole = map(lambda x: math.pi * (x * x) / 4, (dia_rod, dia_pole))

        return cla(
            area_rod,
            area_pole,
            pattern_rod,
            pattern_pole,
            number_rod,
            number_layers,
            layer_spacing,
        )

    def extract(self):
        return {
            "area_rod": self.area_rod,
            "area_pole": self.area_pole,
            "pattern_rod": self.pattern_rod,
            "pattern_pole": self.pattern_pole,
            "number_layer_rods": self.number_layer_rods,
            "number_layers": self.number_layers,
            "layer_spacing": self.layer_spacing,
        }


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

    submit: bool = True
    time_limit: float = None

    @property
    def caepath(self):
        taskfolder = Path(self.taskfolder)
        return str(taskfolder / self.caename)

    @classmethod
    def inti_2(cla, name: str, path: str):
        """快速构造类"""
        return cla(
            "job_" + name,
            "cae_" + name,
            path,
            "model_" + name,
        )

    def extract(self):
        return {
            "jobname": str(self.jobname),
            "caepath": str(self.caepath),
            "taskfolder": str(self.taskfolder),
            "modelname": str(self.modelname),
            "submit": self.submit,
            "time_limit": self.time_limit,
        }


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
    pullroll: RodPattern
    referpoint_top: ReferencePoint
    referpoint_bottom: ReferencePoint

    @property
    def material_tube(self, table_len: int = 10000):
        """钢管"""
        steel_model = constitutive_models.SteelTubelarConstitutiveModels(
            self.steel.strength_yield,
            self.steel.strength_tensile,
            self.steel.elastic_modulus,
        )
        sigma_yield = self.steel.strength_yield / self.steel.elastic_modulus

        x = np.linspace(sigma_yield, 0.2, table_len)
        y = steel_model.model(x)
        return {
            "sigma": y.tolist(),
            "epsilon": (x - sigma_yield).tolist(),
            "elastic_modulus": self.steel.elastic_modulus,
        }

    @property
    def material_rod(self, table_len: int = 10000):
        """约束拉杆"""
        steelbar_model = constitutive_models.PullrollConstitutiveModels(
            self.steelbar.strength_criterion_yield,
            self.steelbar.elastic_modulus,
        )
        sigma_yield = (
            self.steelbar.strength_criterion_yield / self.steelbar.elastic_modulus
        )

        x = np.linspace(
            sigma_yield,
            0.2,
            table_len,
        )
        y = steelbar_model.model(x)
        return {
            "sigma": y.tolist(),
            "epsilon": (x - sigma_yield).tolist(),
            "elastic_modulus": self.steelbar.elastic_modulus,
        }

    @property
    def material_concrte(self, table_len: int = 10000):
        """核心混凝土"""
        concrete_core_strength = (
            self.concrete.strength_criterion_pressure * 1.25
        )  # !圆柱体抗压强度约为f_ck的1.25倍(估计值)
        concrete_model = constitutive_models.ConcreteConstitutiveModels(
            self.geometry.x_len,
            self.geometry.y_len,
            concrete_core_strength,
            self.concrete.strength_criterion_pressure,
            self.geometry.tube_section_area,
            self.steel.strength_yield,
            self.pullroll.area_rod,
            self.steelbar.strength_criterion_yield,
            self.pullroll.layer_spacing,
            self.pullroll.number_layer_rods,
        )

        elastic_x = concrete_model.epsilon_0 / 20
        elastic_y = concrete_model.model(elastic_x)
        elastic_modulus = float(elastic_y / elastic_x)

        x = np.linspace(elastic_x, 0.3, table_len)
        y = concrete_model.model(x)
        x = x - elastic_x

        # ===混凝土塑性损伤的断裂能(COMITE EURO-INTERNATIONAL DU BETON. CEB-FIP MODEL CODE 1990: DESIGN CODE[M/OL]. Thomas Telford Publishing, 1993[2023-05-22]. http://www.icevirtuallibrary.com/doi/book/10.1680/ceb-fipmc1990.35430. DOI:10.1680/ceb-fipmc1990.35430.)
        # G_{f0}取值取决于最大骨料粒径(25N/m-8mm,30N/m-16mm,58N/m-32mm)(取值见CEB-FIP MODEL CODE 1990: DESIGN CODE的Table 2.1.4)
        gfi0 = 58
        concrete_gfi = gfi0 * (self.concrete.strength_pressure / 10) ** (0.7)

        return {
            "sigma": y.tolist(),
            "epsilon": x.tolist(),
            "elastic_modulus": elastic_modulus,
            "strength_fracture": self.concrete.strength_tensile,
            "gfi": concrete_gfi,
        }

    def extract(self) -> dict:
        return {
            "materials": {
                "concrete": self.material_concrte,
                "steel": self.material_tube,
                "steelbar": self.material_rod,
            },
            "geometry": self.geometry.extract(),
            "referpoint": {
                "top": self.referpoint_top.extract(),
                "bottom": self.referpoint_bottom.extract(),
            },
            "pullroll": self.pullroll.extract(),
            "meta": self.meta.extract(),
        }
