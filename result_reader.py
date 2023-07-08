from .utils import JsonFile
from pathlib import Path
from typing import Union, Iterable, Literal, Sequence, overload, Callable
import numpy as np
import math


class TaskFolder:
    circul_area_to_dia = staticmethod(lambda area: math.sqrt(area * 4 / math.pi))

    def __init__(self, folder_path: Union[str, Path]) -> None:
        self.path_root: Path = Path(folder_path).absolute()
        self.__cache_data = {}

    def __str__(self) -> str:
        return str(self.path_root.name)

    @staticmethod
    def axis_angle2rotation_matrix(axis_vector: np.ndarray, left: bool = False):
        """
        将「轴角」转换为「旋转矩阵」

        Parameters
        ---
        axis_vector : np.ndarray
            代表转动量在x, y, z上的分量, 其模长即为转角(弧度制)
        left : bool, default = False
            是否使用左手系(伸出拇指, 握紧四指时, 拇指为向量方向, 四指为转动方向)

        Note
        ---
        公式来源:
            - [三维旋转：欧拉角、四元数、旋转矩阵、轴角之间的转换](https://zhuanlan.zhihu.com/p/45404840)
            - [机器人正运动学---姿态描述之轴角（旋转向量）](https://blog.csdn.net/hitgavin/article/details/106713290)
        """
        modulus = np.linalg.norm(axis_vector, 2)  # 模长, 即为转动角度
        if modulus == 0:
            return np.eye(3)
        angle = modulus if left else -modulus
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)

        x, y, z = axis_vector / modulus
        return np.array(
            [
                [
                    (1 - cos_a) * x**2 + cos_a,
                    (1 - cos_a) * x * y - z * sin_a,
                    (1 - cos_a) * x * z + y * sin_a,
                ],
                [
                    (1 - cos_a) * x * y + z * sin_a,
                    (1 - cos_a) * y**2 + cos_a,
                    (1 - cos_a) * y * z - x * sin_a,
                ],
                [
                    (1 - cos_a) * x * z - y * sin_a,
                    (1 - cos_a) * y * z + x * sin_a,
                    (1 - cos_a) * z**2 + cos_a,
                ],
            ]
        )

    def get_endpoint_displacement(
        self, x: float = 0.5, y: float = 1, end: Literal["top", "bottom"] = "top"
    ) -> dict:
        """
        在柱端刚性面上, 导出一个点的位移数据

        Parameters
        ---
        x, y : float
            在柱端刚性面上建立局部直角坐标系
                - 以z轴与刚性面的交点为原点
                - 整体坐标系的x, y方向即为局部坐标系的x, y方向
                - 以端面宽, 高作为x, y的单位长度
        end : {"top", "bottom"}
            端面选择

        Returns
        ---
        referpoint_displacement : dict
            拥有("U1", "U2", "U3", "UR1", "UR2", "UR3", "time")作为key
        """
        rp = self.task_params["referpoint"]
        referpoint = np.array(rp[end]["position"])

        end_z = self.z_len * (0 if end == "bottom" else 1)
        target_point = np.array((self.x_len * x, self.y_len * y, end_z))

        referpoint_displacement = (
            self.odb_extract["top_referpoint"]
            if end == "top"
            else self.odb_extract["bottom_referpoint"]
        )

        key_table = ("U1", "U2", "U3", "UR1", "UR2", "UR3")
        target_displacement_data = {i: [] for i in key_table}
        target_displacement_data["time"] = referpoint_displacement["time"]

        to_target = target_point - referpoint

        for u1, u2, u3, ur1, ur2, ur3 in zip(
            *(referpoint_displacement[i] for i in key_table)
        ):
            rotate_matrix = self.axis_angle2rotation_matrix(np.array([ur1, ur2, ur3]))
            displace_to_target = to_target @ rotate_matrix
            target_displacement = [
                *(displace_to_target - to_target + np.array((u1, u2, u3))),
                ur1,
                ur2,
                ur3,
            ]

            for k, v in zip(key_table, target_displacement):
                target_displacement_data[k].append(v)

        return target_displacement_data

    def clean_cache(self, key=None):
        if key is None:
            self.__cache_data.clear()
        else:
            self.__cache_data.pop(key)

    @property
    def path_status(self) -> Path:
        return self.path_root / "task_status.json"

    @property
    def path_taskparams(self) -> Path:
        return self.path_root / "task_params.json"

    @property
    def path_comments(self) -> Path:
        return self.path_root / "comments.json"

    @property
    def path_results(self) -> Path:
        return self.path_root / "results"

    @property
    def path_odb_extract(self) -> Path:
        return self.path_results / "odb_extract.json"

    @property
    def status(self) -> dict:
        key = "status"
        if key not in self.__cache_data:
            self.__cache_data[key] = JsonFile.load(self.path_status)
        return self.__cache_data[key]

    @property
    def raw_task_params(self) -> dict:
        key = "raw_task_params"
        if key not in self.__cache_data:
            self.__cache_data[key] = JsonFile.load(self.path_taskparams)
        return self.__cache_data[key]

    @property
    def task_params(self) -> dict:
        return self.raw_task_params["task_params"]

    @property
    def user_params(self) -> dict:
        return self.raw_task_params["user_params"]

    @property
    def task_params_abstract_1(self) -> dict:
        key = "task_params_abstract_1"
        if key not in self.__cache_data:
            self.__cache_data[key] = {
                "concrete": self.user_params["material_concrete"]["grade"],
                "tubelar": self.user_params["material_tubelar"]["grade"],
                "rod": self.user_params["material_rod"]["grade"],
                "pole": self.user_params["material_pole"]["grade"],
                "width": self.x_len,
                "high": self.y_len,
                "length": self.z_len,
                "tubelar_thickness": self.user_params["geometry"]["tubelar_thickness"],
                "e": (
                    self.user_params["referpoint_top"]["position"][1] / self.y_len
                    - 1 / 2
                ),
                "pattern_rod": self.user_params["rod_pattern"]["pattern_rod"],
                "pattern_pole": self.user_params["rod_pattern"]["pattern_pole"],
                "rod_dia": self.circul_area_to_dia(
                    self.user_params["rod_pattern"]["area_rod"]
                ),
                "rod2_dia": self.circul_area_to_dia(
                    self.user_params["rod_pattern"]["area_rod"] / 2
                ),
                "pole_dia": self.circul_area_to_dia(
                    self.user_params["rod_pattern"]["area_pole"]
                ),
                "layer_spacing": self.user_params["rod_pattern"]["layer_spacing"],
                "name": self.user_params["meta"]["taskname"],
                "comments": self.user_params["comments"],
            }
        return self.__cache_data[key]

    @property
    def x_len(self) -> float:
        return self.task_params["geometry"]["x_len"]

    @property
    def y_len(self) -> float:
        return self.task_params["geometry"]["y_len"]

    @property
    def z_len(self) -> float:
        return self.task_params["geometry"]["z_len"]

    @property
    def comments(self) -> dict:
        if "comments" not in self.__cache_data:
            self.__cache_data["comments"] = JsonFile.load(self.path_comments)
        return self.__cache_data["comments"]

    @property
    def odb_extract(self) -> dict:
        if "odb_extract" not in self.__cache_data:
            self.__cache_data["odb_extract"] = JsonFile.load(self.path_odb_extract)
        return self.__cache_data["odb_extract"]

    @property
    def is_done(self) -> bool:
        if not self.path_status.exists():
            return False
        if not isinstance(self.status["extracted"], (int, float)):
            return False
        return True


class TaskFolderList(list):
    def __init__(self, item: Union[Iterable[TaskFolder], str, Path] = None):
        if isinstance(item, (str, Path)):
            path = Path(item).absolute()

            def istask(path: Path):
                if not path.is_dir():
                    return False
                if not (path / "task_params.json"):
                    return False
                return True

            return super().__init__(TaskFolder(i) for i in path.iterdir() if istask(i))
        elif isinstance(item, Iterable):
            super().__init__(item)
        elif item is None:
            super().__init__()
        else:
            raise TypeError(type(item))

    def __str__(self) -> str:
        return "TaskFolderList(" + ", ".join(str(i) for i in self) + ")"

    @overload
    def __getitem__(self, __i: int) -> TaskFolder:
        ...

    @overload
    def __getitem__(self, __name: str) -> TaskFolder:
        ...

    @overload
    def __getitem__(self, __s: slice) -> Sequence[TaskFolder]:
        ...

    @overload
    def __getitem__(self, __k: Callable[[TaskFolder], bool]):
        ...

    def __getitem__(self, __key: Union[int, slice, str, Callable[[TaskFolder], bool]]):
        if isinstance(__key, int):
            return super().__getitem__(__key)
        elif isinstance(__key, slice):
            return self.__class__(super().__getitem__(__key))
        elif isinstance(__key, str):
            for i in self:
                if i.__str__() == __key:
                    return i
            else:
                raise KeyError(f"{__key} not in {self}")
        elif isinstance(__key, Callable):
            return self.__class__(i for i in self if __key(i))
        else:
            return TypeError(f"unsupported type: {type(__key)}")

    def __setitem__(self, *args, **kwargs):
        return super().__setitem__(*args, **kwargs)

    @property
    def done_tasks(self):
        return self.__class__(i for i in self if i.is_done)
