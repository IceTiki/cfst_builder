from pathlib import Path
from .utils import JsonFile
from typing import Literal, Callable, Union
from dataclasses import dataclass

__TABLE_FOLDER = Path(__file__).parent / "table"
__materials_table: dict[str:dict] = {}


def get_materials_table(
    material_name: Literal["concrete", "steel_bar", "steel"]
) -> dict:
    """获取材料表"""
    if material_name not in __materials_table:
        __materials_table[material_name] = JsonFile.load(
            __TABLE_FOLDER / f"{material_name}.json"
        )
    return __materials_table[material_name]


class MaterialOperation:
    """实现各材料的二元运算符"""

    def __binary_operator_same(
        self,
        other,
        oper_str: Callable = lambda x, y: f"({x}+{y})",
        oper_number: Callable = lambda x, y: x + y,
    ):
        """二元运算符魔术方法实现"""
        params = {}
        self_data = self.__dict__
        if isinstance(other, self.__class__):
            other_data = other.__dict__
            for k in self_data.keys():
                if isinstance(self_data[k], str):
                    params[k] = oper_str(self_data[k], other_data[k])
                elif isinstance(self_data[k], (int, float)):
                    params[k] = oper_number(self_data[k], other_data[k])
        elif isinstance(other, (int, float)):
            for k in self_data.keys():
                if isinstance(self_data[k], str):
                    params[k] = oper_str(self_data[k], other)
                elif isinstance(self_data[k], (int, float)):
                    params[k] = oper_number(self_data[k], other)
        else:
            raise TypeError(
                f"unsupported operand type(s): '{self.__class__}' and '{type(other)}'"
            )

        return self.__class__(**params)

    def from_table_property(cla, property_name: str, target_value: Union[int, float]):
        """
        根据所需属性, 线性内插得到合适的材料

        Parameters
        ---
        cla
            实现了'+'(能和同类型相加),'*'(能与浮点数相乘)二元运算符。
            并且有grade_table静态属性和from_table静态函数。
        property_name : str
            属性名
        target_value : int | float
            目标值
        """
        mater_table = [cla.from_table(i) for i in cla.grade_table]
        mater_table.sort(key=lambda x: getattr(x, property_name))
        table_min = getattr(mater_table[0], property_name)
        table_max = getattr(mater_table[-1], property_name)
        if target_value < table_min or target_value > table_max:
            raise ValueError(
                f"target_value({target_value}) not in range [{table_min}, {table_max}]"
            )

        # ===二分查找
        start = 0
        end = len(mater_table) - 1
        while start <= end:
            mid = (start + end) // 2
            mid_value = getattr(mater_table[mid], property_name)
            if mid_value == target_value:
                return mater_table[mid]
            elif mid_value < target_value:
                start = mid + 1
            else:
                end = mid - 1

        # 如果没有匹配到区间端点, 那么会以start = end + 1结束
        # 二分查找中的最后一个循环必然是在start = end = mid时
        # 若mid > target, 那么区间应在(mid-1, mid)
        # 若mid < target, 那么区间应在(mid, mid+1)
        smaller = mater_table[end]
        bigger = mater_table[start]
        smaller_property_value = getattr(smaller, property_name)
        bigger_property_value = getattr(bigger, property_name)

        # ===线性内插
        alpha = (target_value - smaller_property_value) / (
            bigger_property_value - smaller_property_value
        )
        # return smaller + (bigger - smaller) * alpha  # 两种线性内插的写法
        return smaller * (1 - alpha) + bigger * alpha  # 两种线性内插的写法

    def __add__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({x}+{y})",
            lambda x, y: x + y,
        )

    def __sub__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({x}-{y})",
            lambda x, y: x - y,
        )

    def __mul__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({x}*{y})",
            lambda x, y: x * y,
        )

    def __truediv__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({x}/{y})",
            lambda x, y: x / y,
        )

    def __radd__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({y}+{x})",
            lambda x, y: y + x,
        )

    def __rsub__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({y}-{x})",
            lambda x, y: y - x,
        )

    def __rmul__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({y}*{x})",
            lambda x, y: y * x,
        )

    def __rtruediv__(self, other):
        return self.__binary_operator_same(
            other,
            lambda x, y: f"({y}/{x})",
            lambda x, y: y / x,
        )


@dataclass
class Steel(MaterialOperation):
    """
    钢材性质

    Parameters
    ---
    grade : str
        牌号
    type : str
        类型
    strength : float
        f, 抗拉、抗压、抗弯设计值(MPa)
    strength_shearing : float
        f_v, 抗剪强度设计值(MPa)
    strength_ce : float
        f_ce, 端面承压(刨平压紧)(MPa)
    strength_yield : float
        f_y, 屈服强度设计值(MPa)
    strength_tensile : float
        f_u, 抗拉强度设计值(MPa)
    elastic_modulus : float
        E, 弹性模量(MPa)
    shear_modulus : float
        G, 剪变模量(MPa)
    coefficient_of_linear_expansion : float
        线膨胀系数(以每°C计)
    density : float
        质量密度(kg/m^3)
    """

    grade_table = ["Q235", "Q345GJ", "Q355", "Q390", "Q420", "Q460"]
    grade_table_literal = Literal["Q235", "Q345GJ", "Q355", "Q390", "Q420", "Q460"]

    grade: str
    type: str
    strength: float
    strength_shearing: float
    strength_ce: float
    strength_yield: float
    strength_tensile: float
    elastic_modulus: float
    shear_modulus: float
    coefficient_of_linear_expansion: float
    density: float

    @classmethod
    def from_table(
        cla,
        grade: grade_table_literal,
        thickness: float = 100,
    ):
        """
        从材料表文件中获取参数并实例化

        Parameters
        ---
        grade : str
            钢材牌号
        thickness : float
            钢材厚度或直径(mm)
        """
        sheet_data = get_materials_table("steel")
        key_word = {
            "grade": "牌号",
            "type": "类型",
            "strength": "抗拉、抗压、抗弯设计值",
            "strength_shearing": "抗剪强度设计值",
            "strength_ce": "端面承压",
            "strength_yield": "屈服强度",
            "strength_tensile": "抗拉强度",
            "elastic_modulus": "弹性模量",
            "shear_modulus": "剪变模量",
            "coefficient_of_linear_expansion": "线膨胀系数",
            "density": "质量密度",
        }
        key_word_index = {}
        for param_name, param_keyword in key_word.items():
            for column_index, column_head in enumerate(sheet_data["index"]):
                if param_keyword in column_head:
                    key_word_index[param_name] = column_index
                    break

        steel_data_ = []
        for row_data in sheet_data["values"]:
            if grade == row_data[0] and row_data[2] < thickness <= row_data[3]:
                steel_data_ = row_data
                break
        else:
            raise ValueError("未在表中找到符合牌号和厚度的钢材")

        params = {k: steel_data_[v] for k, v in key_word_index.items()}
        return cla(**params)

    @classmethod
    def from_table_property(cla, property_name: str, target_value: Union[int, float]):
        """
        指定材料的属性值, 根据表格中的材料通过线性内插生成对应材料。

        Parameters
        ---
        property_name : str
            属性名
        target_value : int | float
            目标值
        """
        return super().from_table_property(cla, property_name, target_value)


@dataclass
class SteelBar(MaterialOperation):
    """
    钢筋性质

    Parameters
    ---
    grade : str
        牌号
    diameter_range : str
        公称直径(d/mm)("最小~最大")
    strength_criterion_yield : float
        f_yk, 屈服强度标准值(MPa)
    strength_criterion_ultimate : float
        f_stk, 极限强度标准值(MPa)
    strength_tensile : float
        f_y, 抗拉强度设计值(MPa)
    strength_pressure : float
        f_y', 抗压强度设计值(MPa)
    elastic_modulus : float
        E_s, 弹性模量(MPa)
    elongation_ultimate : float
        delta_gt, 最大力下总伸长率限值(%)
    density : float
        质量密度(kg/m^3)
    """

    grade_table = [
        "HPB300",
        "HRB335",
        "HRB400",
        "HRBF400",
        "RRB400",
        "HRB500",
        "HRBF500",
    ]
    grade_table_literal = Literal[
        "HPB300", "HRB335", "HRB400", "HRBF400", "RRB400", "HRB500", "HRBF500"
    ]

    grade: str
    diameter_range: str
    strength_criterion_yield: float
    strength_criterion_ultimate: float
    strength_tensile: float
    strength_pressure: float
    elastic_modulus: float
    elongation_ultimate: float
    density: float

    @classmethod
    def from_table(
        cla,
        grade: grade_table_literal,
    ):
        """
        从材料表文件中获取参数并实例化

        Parameters
        ---
        grade : str
            钢筋牌号
        """
        sheet_data = get_materials_table("steel_bar")
        key_word = {
            "grade": "牌号",
            "diameter_range": "公称直径",
            "strength_criterion_yield": "屈服强度标准值",
            "strength_criterion_ultimate": "极限强度标准值",
            "strength_tensile": "抗拉强度设计值",
            "strength_pressure": "抗压强度设计值",
            "elastic_modulus": "弹性模量",
            "elongation_ultimate": "总伸长率限值",
            "density": "质量密度",
        }
        key_word_index = {}
        for param_name, param_keyword in key_word.items():
            for column_index, column_head in enumerate(sheet_data["index"]):
                if param_keyword in column_head:
                    key_word_index[param_name] = column_index
                    break

        steelbar_data = []
        for row_data in sheet_data["values"]:
            if grade == row_data[0]:
                steelbar_data = row_data
                break
        else:
            raise ValueError("未在表中找到符合牌号的钢筋")

        params = {k: steelbar_data[v] for k, v in key_word_index.items()}
        return cla(**params)

    @classmethod
    def from_table_property(cla, property_name: str, target_value: Union[int, float]):
        """
        指定材料的属性值, 根据表格中的材料通过线性内插生成对应材料。

        Parameters
        ---
        property_name : str
            属性名
        target_value : int | float
            目标值
        """
        return super().from_table_property(cla, property_name, target_value)


@dataclass
class Concrete(MaterialOperation):
    """
    混凝土特性

    Parameters
    ---
    grade : str
        混凝土标号
    strength_criterion_pressure : float
        f_ck, 抗压标准值(MPa)
    strength_criterion_tensile : float
        f_tk, 抗拉标准值(MPa)
    strength_pressure : float
        f_c, 抗压设计值(MPa)
    strength_tensile : float
        f_t, 抗拉设计值(MPa)
    elastic_modulus : float
        E, 弹性模量(MPa)
    density : float
        质量密度(kg/m^3)
    """

    grade_table = [
        "C15",
        "C20",
        "C25",
        "C30",
        "C35",
        "C40",
        "C45",
        "C50",
        "C55",
        "C60",
        "C65",
        "C70",
        "C75",
        "C80",
    ]
    grade_table_literal = Literal[
        "C15",
        "C20",
        "C25",
        "C30",
        "C35",
        "C40",
        "C45",
        "C50",
        "C55",
        "C60",
        "C65",
        "C70",
        "C75",
        "C80",
    ]

    grade: str
    strength_criterion_pressure: float
    strength_criterion_tensile: float
    strength_pressure: float
    strength_tensile: float
    elastic_modulus: float
    density: float

    @classmethod
    def from_table(
        cla,
        grade: grade_table_literal,
    ):
        """
        从材料表文件中获取参数并实例化

        Parameters
        ---
        grade : str
            混凝土标号
        """
        sheet_data = get_materials_table("concrete")
        key_word = {
            "grade": "混凝土标号",
            "strength_criterion_pressure": "抗压标准值",
            "strength_criterion_tensile": "抗拉标准值",
            "strength_pressure": "抗压设计值",
            "strength_tensile": "抗拉设计值",
            "elastic_modulus": "弹性模量",
            "density": "质量密度",
        }
        key_word_index = {}
        for param_name, param_keyword in key_word.items():
            for column_index, column_head in enumerate(sheet_data["index"]):
                if param_keyword in column_head:
                    key_word_index[param_name] = column_index
                    break

        concrete_data = []
        for row_data in sheet_data["values"]:
            if grade == row_data[0]:
                concrete_data = row_data
                break
        else:
            raise ValueError("未在表中找到符合标号的混凝土")

        params = {k: concrete_data[v] for k, v in key_word_index.items()}
        return cla(**params)

    @classmethod
    def from_table_property(cla, property_name: str, target_value: Union[int, float]):
        """
        指定材料的属性值, 根据表格中的材料通过线性内插生成对应材料。

        Parameters
        ---
        property_name : str
            属性名
        target_value : int | float
            目标值
        """
        return super().from_table_property(cla, property_name, target_value)
