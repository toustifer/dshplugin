# 原始 Manim 代码编写指南（`mcp__manim__render`）

当且仅当四个声明式模板（公式、图像、框图、对照）都无法满足高度定制的几何、物理或算法模拟需求时，使用 `mcp__manim__render` 逃生口。

---

## 1. 三步标准开发心流

不要直接调用 `render`！渲染涉及 Python 子进程、LaTeX 与 ffmpeg 编译，耗时通常在 10~25 秒。写原始代码必须遵守：

1. **查骨架**：调用 `mcp__manim__style_guide`，取得当前机器的调色板、可用中文字体名与标准骨架。
2. **做体检**：写好代码后，先调 `mcp__manim__check`。耗时仅 0.1 秒，秒级拦截语法错误、缺少 construct 方法或缺失 import。
3. **真渲染**：体检 100% 通过后再调 `mcp__manim__render`。

---

## 2. 标准代码模板骨架

直接套用以下经过生产验证的代码骨架：

```python
from manim import *

# 1. 配色常量（严禁随意硬编码颜色，保持全站暗色调视觉统一）
config.background_color = "#0E1116"
C_BLUE = "#58C4DD"
C_HIGHLIGHT = "#FFD166"
C_GREEN = "#7BE495"
C_RED = "#FF6B6B"
C_GREY = "#5A6472"
C_EDGE = "#8A94A6"

TITLE_SIZE = 44
BODY_SIZE = 32
NOTE_SIZE = 24

FONT_CJK = "Microsoft YaHei"  # 必须使用 style_guide 返回的本机可用字体

def cn(text, size=BODY_SIZE, color=WHITE, weight=NORMAL):
    """确保中文文本不会渲染成方框或乱码的标准 helper"""
    return Text(text, font=FONT_CJK, font_size=size, color=color, weight=weight)

class ExplainScene(Scene):
    def construct(self):
        # 顶部标题必须预留边距 buff=0.6，防止与图表干涉
        title = cn("核心过程演示", TITLE_SIZE).to_edge(UP, buff=0.6)
        self.play(Write(title), run_time=1.0)
        
        # 业务主体构造...
        # 始终优先使用 VGroup 组织空间关系
        
        # 尾部留白：必须留出 0.5~1.0 秒供用户眼球聚焦最终结论
        self.wait(0.8)
```

---

## 3. 血泪避坑清单（实测致命陷阱）

以下坑点全部在真实运行中被反复踩中，写代码前务必自查：

### 陷阱 1：`VGroup` 中塞入动画对象（致命 TypeError）
- **错误写法**：
  ```python
  # ❌ 崩溃！TypeError: Only values of type VMobject can be added as submobjects of VGroup
  flashes = VGroup(*[ShowPassingFlash(e.copy()) for e in edges])
  self.play(LaggedStart(*flashes))
  ```
- **核心原理**：`ShowPassingFlash`、`FadeIn`、`Indicate` 等是**动画（Animation）**，不是**可视图元（VMobject）**！`VGroup` 只能装图元。
- **正确写法**：直接将动画列表解包传给 `LaggedStart` 或 `self.play`：
  ```python
  # ✅ 正确做法：直接传动画生成器/列表
  flash_anims = [ShowPassingFlash(e.copy().set_color(C_HIGHLIGHT), time_width=0.5) for e in edges]
  self.play(LaggedStart(*flash_anims, lag_ratio=0.05), run_time=1.2)
  ```

### 陷阱 2：中文未显式指定字体变成空心方框
- **错误写法**：`Text("输入层")` 默认使用英文无衬线字体，在 Windows 环境下会导致所有中文字符变成 `[?]` 方框。
- **正确写法**：必须始终包裹 `cn(...)` 或显式传递 `Text("输入层", font=FONT_CJK)`。

### 陷阱 3：公式字符串反斜杠被 Python 转义吃掉
- **错误写法**：`MathTex("\frac{1}{2}")` 会触发不可预测的转义报错。
- **正确写法**：一律使用原始字符串 `MathTex(r"\frac{1}{2}")`。

### 陷阱 4：`.animate` 链式调用时序混乱
- **错误写法**：
  ```python
  # ❌ 错误：不要先把 animate 存入变量再二次调用
  target = dot.animate.shift(UP)
  target.set_color(RED)
  self.play(target)
  ```
- **正确写法**：
  ```python
  # ✅ 单行内连贯声明
  self.play(dot.animate.shift(UP).set_color(RED), run_time=1.0)
  ```

### 陷阱 5：动画时长失控超长
- 单个动作的 `run_time` 建议控制在 `0.6 ~ 1.2` 秒之间。
- 不要堆砌超过 25 秒的复杂故事；**一段动画只解释一个核心关系/过程**。
