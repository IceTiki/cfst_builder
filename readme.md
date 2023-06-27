# 用户手册

## 文档

* **[建模参数](docs/建模参数.md)**
* **[开发文档](docs/开发文档.md)**

# PLAN&TODO

## PLAN

- [ ] 网络获取任务

## TODO

- [ ] 轴心核心抗压和圆柱体抗压的值怎么选取
- [ ] 网格、方向、密度
- [ ] 弹性阶段的参数会影响塑性阶段吗
- [ ] 断裂能 真的是N/m吗


# 参考

## 重要

* BiliBili
  * [钢管混凝土建模教程](https://www.bilibili.com/video/BV1Qg411q72r)
  * [方钢管混凝土短柱轴压-零基础ABAQUS保姆级教学](https://www.bilibili.com/video/BV1Qg411q72r/)
  * [ABAQUS调用NVIDIA显卡CUDA加速](https://www.bilibili.com/video/BV1vT4y1z74H/)
* ABAQUS手册
  * [Abaqus Scripting Reference Guide (6.14)](http://130.149.89.49:2080/v6.14/books/ker/default.htm?startat=pt01ch07pyo04.html)`abaqus-python开发手册`
  * [ABAQUS Scripting User's Manual (v6.6)](https://classes.engineering.wustl.edu/2009/spring/mase5513/abaqus/docs/v6.6/books/cmd/default.htm?startat=pt02ch06s01.html)`abaqus cae使用手册`
  * [Element integration point variables](https://abaqus-docs.mit.edu/2017/English/SIMACAEOUTRefMap/simaout-c-std-elementintegrationpointvariables.htm)`输出变量含义说明`
  * [CAE User's Manual PDF](http://dsk-016-1.fsid.cvut.cz:2080/v6.12/pdf_books/CAE.pdf)
  * [Scripting User's Manual PDF](http://dsk-016-1.fsid.cvut.cz:2080/v6.12/pdf_books/SCRIPT_USER.pdf)
* 其他
  * [如何使用Nvidia显卡对abaqus进行加速](https://blog.csdn.net/kaede0v0/article/details/121474168)

## 杂项

* `abaqus cae noGUI=**.py`
* CAE（COMPLETE SOLUTION FOR ABAQUS FINITE ELEMENT MODELING, VISUALIZATION, AND PROCESS AUTOMATION）
* `seaborn`中`sns.regplot()`的默认置信区间为95%（也就是回归直线下面的色带）
* 现在C15、Q345GJ已被弃用

## 其他

* BiliBili
  * [【狂小华】Abaqus实例（一）钢筋混凝土简支梁结构工程实例建模全过程教学讲解（土木工程）](https://www.bilibili.com/video/BV1CR4y1F7wx/)
  * [ABAQUS非线性收敛问题的六个建议 - 哔哩哔哩](https://www.bilibili.com/read/cv7204780)
  * [abaqus tie约束与merge布尔操作的区别？_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1QW4y167ok/)
* 知乎
  * [四大强度理论概述](https://zhuanlan.zhihu.com/p/540529157)
  * [有限元软件中应力应变参数意义、von mises屈服准则](https://www.zhihu.com/tardis/zm/art/578255942)
  * [【Abaqus】结构工程常用国际单位表 - 知乎](https://zhuanlan.zhihu.com/p/376250217)
  * [Abaqus安装教程 - 知乎](https://zhuanlan.zhihu.com/p/408159623)
* 其他
  * [使用python进行ABAQUS的二次开发的简要说明（by Young 2017.06.27）_abaqus二次开发难度_young2203的博客-CSDN博客](https://blog.csdn.net/young2203/article/details/81937268)

## 未阅

* [Abaqus应用实例丨 钢筋混凝土简支梁数值模拟](https://zhuanlan.zhihu.com/p/143692725)
* [【干货分享】你还在手动提取数据吗？用Python提取Abaqus中的输出结果数据。提升科研工作效率](https://www.bilibili.com/video/BV1Jd4y1D7kQ/)
* [滞回曲线捏缩讲解]( https://www.bilibili.com/video/BV1sq4y1D7MN/1)
* [python处理Abaqus ODB文件（10分钟学会）](https://www.bilibili.com/video/BV1tX4y1Z7YL/)
* [【新手向】Python对ABAQUS的二次开发-简单案例](https://www.bilibili.com/video/BV1CP4y1e753/)
* [ABAQUS方钢管混凝土轴压试验验证]( https://www.bilibili.com/video/BV19R4y147gb/)
* [利用Python提取ABAQUS的计算结果（ODB） - 知乎](https://zhuanlan.zhihu.com/p/333879415)
* [ABAQUS收敛控制经验谈（一）——漫谈不收敛的原因,abaqus分析培训、Abaqus培训、abaqus技术教程、abaqus岩土分析、钢筋混凝土仿真、abaqus分析理论、abaqus软件下载、abaqus umat用户子程序编程、Abaqus代做、Abaqus基础知识](http://www.1cae.com/a/abaqus/45/abaqus-3755.htm)
* [Abaqus-python脚本到底应该怎么写？一文带你入门 - 知乎](https://zhuanlan.zhihu.com/p/338230059?utm_id=0)
* [(PDF) ABAQUS Python二次开发攻略](https://www.researchgate.net/publication/311946787_ABAQUS_Pythonercikaifagonge)
* [科研仿真之Abaqus入门篇 - 知乎](https://zhuanlan.zhihu.com/p/147353423)