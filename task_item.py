from dataclasses import dataclass, field
import itertools
from pathlib import Path
from typing import Union, Literal, Iterable
import math
import numpy as np

from materlib import materials, constitutive_models
from utils import format_time, JsonFile


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
            "tubelar_thickness": self.tubelar_thickness,
            "concrete_grid_size": self.concrete_grid_size,
            "steel_grid_size": self.steel_grid_size,
            "grid_minsize": 0.1,
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
            固定位移(U1, U2, U3, RU1, RU2, RU3), 设置位移量请使用float类型, 无约束请使用None
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

    rod_ushape_pattern_library = {
        "alpha": [
            [[1 / 2, 0], [1 / 2, 1]],
            [[0, 1 / 2], [1, 1 / 2]],
        ],
        "beta": [
            [[1 / 2, 1 / 3], [1 / 2, 0]],
            [[1 / 2, 1 / 3], [0, 1 / 3]],
            [[1 / 2, 1 / 3], [1, 1 / 3]],
            [[1 / 2, 2 / 3], [1 / 2, 1]],
            [[1 / 2, 2 / 3], [0, 2 / 3]],
            [[1 / 2, 2 / 3], [1, 2 / 3]],
        ],
        "gamma": [
            [[1 / 2, 1 / 4], [1 / 2, 0]],
            [[1 / 2, 1 / 4], [0, 1 / 4]],
            [[1 / 2, 1 / 4], [1, 1 / 4]],
            [[1 / 2, 3 / 4], [1 / 2, 1]],
            [[1 / 2, 3 / 4], [0, 3 / 4]],
            [[1 / 2, 3 / 4], [1, 3 / 4]],
            [[0, 1 / 2], [1, 1 / 2]],
        ],
    }

    pole_ushape_pattern_library = {
        "alpha": [
            [1 / 2, 1 / 2],
        ],
        "beta": [
            [1 / 2, 1 / 3],
            [1 / 2, 2 / 3],
        ],
        "gamma": [
            [1 / 2, 1 / 4],
            [1 / 2, 2 / 4],
            [1 / 2, 3 / 4],
        ],
    }

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
    taskname : str
        job和model的命名, 影响到cae, odb等的文件名

    time_limit : float
        作业最高运行时间(秒)

    gap : float
        选区边缘内缩长度(比如: 框选对象时, 但不包括边界上的对象时, 选区向内缩的长度)

    """

    taskname: str

    time_limit: float = None

    gap: float = 1.0

    @classmethod
    def inti_2(cla, name: str):
        """快速构造类"""
        return cla(name)

    def extract(self):
        return {
            "taskname": str(self.taskname),
            "time_limit": self.time_limit,
            "gap": self.gap,
        }


@dataclass
class AbaqusData:
    """

    Parameters
    ---
    meta : TaskMeta

    geometry : Geometry
    rod_pattern : Pullroll
        约束拉杆分布
    reterpoint_top, referpoint_bottom: ReferencePoint
        上下参考点

    material_concrete : materials.Concrete
    material_tubelar : materials.Steel
    material_rod : materials.SteelBar
        约束拉杆材料
    material_pole: materials.SteelBar
        中心立杆材料
    comment : dict
        备注

    Note
    ---
    单位N、mm
        MPa = N/mm^2
    """

    meta: TaskMeta
    geometry: Geometry
    rod_pattern: RodPattern
    referpoint_top: ReferencePoint
    referpoint_bottom: ReferencePoint
    material_concrete: materials.Concrete
    material_tubelar: materials.Steel
    material_rod: materials.SteelBar
    material_pole: materials.SteelBar
    comment: dict = field(default_factory=dict)

    def name_iter(prefix=f"{format_time()}_ecc_cfst_alpha_", suffix="", start=0):
        num = start
        while 1:
            yield f"{prefix}{num}{suffix}"
            num += 1

    @staticmethod
    def get_ecc_cfst_alpha_template(
        name_iter: Iterable = name_iter,
    ):
        """

        Parameters
        ---
        name_iter : Iterable
            任务名迭代器
        """
        params = {
            "concrete": "C60",
            "tubelar": "Q390",
            "rod": "HRB400",
            "pole": "HRB400",
            "width": 300,
            "high": 300,
            "length": 1200,
            "tubelar_thickness": 6,
            "mesh": ((9, 9, 36), (9, 9, 36)),
            "e": 0.233,
            "pattern_rod": tuple(),
            "pattern_pole": tuple(),
            "rod_dia": 14,
            "pole_dia": 24,
            "layer_number": 8,
            "name": next(name_iter),
            "comment": {},
        }
        return params

    @classmethod
    def init_ecc_cfst_alpha(cla, params):
        """偏压CFST快速建模参数"""

        # ===材料参数
        mater_iter1 = [params[i] for i in ["concrete", "tubelar", "rod", "pole"]]
        mater_iter2 = [
            materials.Concrete,
            materials.Steel,
            materials.SteelBar,
            materials.SteelBar,
        ]
        mater_iter3 = [
            "strength_criterion_pressure",
            "strength_yield",
            "strength_criterion_yield",
            "strength_criterion_yield",
        ]
        mater_iter = [
            j.from_table(i) if isinstance(i, str) else j.from_table_property(k, i)
            for i, j, k in zip(mater_iter1, mater_iter2, mater_iter3)
        ]
        mater_concrete, mater_tubelar, mater_rod, mater_pole = mater_iter

        # ===几何参数
        geo = Geometry(
            params["width"],
            params["high"],
            params["length"],
            params["tubelar_thickness"],
            *params["mesh"],
        )

        # ===参考点
        bar_e_0 = params["e"]  # 偏心距
        rp_top = ReferencePoint.init_from_datum(
            geo, [0, geo.y_len * bar_e_0, 0], [0, 0, -geo.z_len / 10, None, 0, 0], "top"
        )
        rp_bottom = ReferencePoint.init_from_datum(
            geo, [0, geo.y_len * bar_e_0, 0], [0, 0, 0, None, 0, 0], "bottom"
        )

        # ===拉杆参数
        roll = RodPattern.init_from_pattern(
            geo,
            params["rod_dia"],
            params["pole_dia"],
            params["pattern_rod"],
            params["pattern_pole"],
            params["layer_number"],
        )

        # ===元参数
        taskname = params["name"]
        meta = TaskMeta.inti_2(taskname)

        # ===生成json
        return cla(
            meta,
            geo,
            roll,
            rp_top,
            rp_bottom,
            mater_concrete,
            mater_tubelar,
            mater_rod,
            mater_pole,
            params["comment"],
        )

    @property
    def __extract_material_tubelar(self, table_len: int = 10000) -> dict:
        """钢管"""
        steel_model = constitutive_models.SteelTubelarConstitutiveModels(
            self.material_tubelar.strength_yield,
            self.material_tubelar.strength_tensile,
            self.material_tubelar.elastic_modulus,
        )
        sigma_yield = (
            self.material_tubelar.strength_yield / self.material_tubelar.elastic_modulus
        )

        x = np.linspace(sigma_yield, 0.2, table_len)
        y = steel_model.model(x)
        return {
            "sigma": y.tolist(),
            "epsilon": (x - sigma_yield).tolist(),
            "elastic_modulus": self.material_tubelar.elastic_modulus,
            "poissons_ratio": 0.25,
        }

    def __extract_material_steelbar(
        self, steelbar: materials.SteelBar, table_len: int = 10000
    ) -> dict:
        steelbar_model = constitutive_models.PullrollConstitutiveModels(
            steelbar.strength_criterion_yield,
            steelbar.elastic_modulus,
        )
        sigma_yield = steelbar.strength_criterion_yield / steelbar.elastic_modulus

        x = np.linspace(
            sigma_yield,
            0.2,
            table_len,
        )
        y = steelbar_model.model(x)
        return {
            "sigma": y.tolist(),
            "epsilon": (x - sigma_yield).tolist(),
            "elastic_modulus": steelbar.elastic_modulus,
            "poissons_ratio": 0.25,
        }

    @property
    def __extract_material_rod(self, table_len: int = 10000) -> dict:
        """约束拉杆"""
        return self.__extract_material_steelbar(self.material_rod, table_len)

    @property
    def __extract_material_pole(self, table_len: int = 10000) -> dict:
        """中心立杆"""
        return self.__extract_material_steelbar(self.material_pole, table_len)

    @property
    def __extract_material_concrete(self, table_len: int = 10000) -> dict:
        """核心混凝土"""
        concrete_core_strength = (
            self.material_concrete.strength_criterion_pressure * 1.25
        )  # !圆柱体抗压强度约为f_ck的1.25倍(估计值)
        concrete_model = constitutive_models.ConcreteConstitutiveModels(
            self.geometry.x_len,
            self.geometry.y_len,
            concrete_core_strength,
            self.material_concrete.strength_criterion_pressure,
            self.geometry.tube_section_area,
            self.material_tubelar.strength_yield,
            self.rod_pattern.area_rod,
            self.material_rod.strength_criterion_yield,
            self.rod_pattern.layer_spacing,
            self.rod_pattern.number_layer_rods,
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
        concrete_gfi = gfi0 * (self.material_concrete.strength_pressure / 10) ** (0.7)

        return {
            "sigma": y.tolist(),
            "epsilon": x.tolist(),
            "elastic_modulus": elastic_modulus,
            "poissons_ratio": 0.2,
            "strength_fracture": self.material_concrete.strength_tensile,
            "gfi": concrete_gfi,
            "cdp_params": [  # 混凝土塑性损伤模型的参数
                40.0,
                0.1,
                1.16,
                0.6667,
                0.0005,
            ],
        }

    @property
    def __extract_misc(self) -> dict:
        static_step: dict = {
            "max_num_inc": 10000,  # 最大步数
            "initial_inc": 0.01,  # 初始步长
            "min_inc": 1e-07,  # 最小步长
            "nlgeom": "ON",  # 非线性
            "stabilization_method": "DISSIPATED_ENERGY_FRACTION",  # 自动稳定方式
            "continue_damping_factors": True,
            "adaptive_damping_ratio": 0.05,
        }
        #   "stabilization_method": "NONE",  # 自动稳定方式
        #   "continue_damping_factors": False,
        #   "adaptive_damping_ratio": 0,
        performance: dict = {
            "memory": 90,
            "num_cpus": 6,
            "num_gpus": 1,  # 如果不调用GPU填0
        }
        return {
            "static_step": static_step,
            "performance": performance,
            "friction_factor_between_concrete_tubelar": 0.6,  # 钢管-混凝土之间的摩擦系数
            "tubelar_num_int_pts": 9,  # 钢管壳截面的积分数量
        }

    @property
    def members_dict(self) -> dict:
        return {
            k: v.__dict__ if "__dict__" in dir(v) else v
            for k, v in self.__dict__.items()
        }

    def gene_task_folder(self, path_output="tasks", calculate=True):
        (Path(path_output) / self.meta.taskname).mkdir(parents=True, exist_ok=True)
        JsonFile.write(
            self.extract(),
            (Path(path_output) / self.meta.taskname / "task_params.json"),
        )
        JsonFile.write(
            {
                "modelled": "TODO",
                "calculated": "TODO" if calculate else "SKIP",
                "extracted": "TODO" if calculate else "SKIP",
            },
            (Path(path_output) / self.meta.taskname / "task_status.json"),
        )

    def extract(self) -> dict:
        task_params = {
            "materials": {
                "concrete": self.__extract_material_concrete,
                "tubelar": self.__extract_material_tubelar,
                "rod": self.__extract_material_rod,
                "pole": self.__extract_material_pole,
            },
            "geometry": self.geometry.extract(),
            "referpoint": {
                "top": self.referpoint_top.extract(),
                "bottom": self.referpoint_bottom.extract(),
            },
            "rod_pattern": self.rod_pattern.extract(),
            "meta": self.meta.extract(),
            "misc": self.__extract_misc,
            "comment": self.comment,
        }

        return {
            "version": [0, 0, 0, "alpha"],
            "task_params": task_params,
            "user_params": self.members_dict,
        }
