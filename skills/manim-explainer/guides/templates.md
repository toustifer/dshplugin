# 声明式模板实战手册

优先使用声明式模板：它们直接由 MCP 引擎将结构化参数编译成经过排版约束的 Manim 场景，比手写原始代码快 10 倍，且绝不会出现语法错误或图层穿模。

四个模板对应四种常见解释场景：

| 场景 | 工具名称 | 核心职责 |
|---|---|---|
| 公式变形推导 | `mcp__manim__equation` | 3b1b 风格逐步变形展示代数/几何推导 |
| 函数曲线与几何 | `mcp__manim__graph` | 坐标系函数图像、切线、积分面积、参数滑动 |
| 流程/架构/时序 | `mcp__manim__diagram` | 节点拓扑、状态转换、依赖网络 |
| 方案/概念对比 | `mcp__manim__compare` | 左右并列对照，突出异同点 |

---

## 1. 公式推导：`mcp__manim__equation`

### 适用场景
- 勾股定理、欧拉公式、贝叶斯定理推导
- 算法复杂度递推式化简
- 矩阵乘法、注意力权重计算步骤展开

### 参数规范
- `steps`: `list[str]`（必填，2~6 个 LaTeX 字符串）。
  - **切记**：每个字符串代表公式的一个瞬时完整状态！Manim 会自动通过 `TransformMatchingTex` 追踪公共子项平滑位移。
  - LaTeX 中反斜杠必须规范转义（如 `\\frac{a}{b}` 或在 JSON 中传入合法转义字符串）。
- `title`: `str | None`（可选，顶部标题，支持中文）。
- `highlight`: `list[str] | None`（可选，与 `steps` 等长）。
  - 每一步中想要黄色高亮标记的核心子串（必须在当前步的公式中**字面完全一致地出现**，否则静默不高亮）。
- `quality`: `"draft"`（默认）或 `"final"`。

### 示例调用
```json
{
  "title": "欧拉恒等式变形",
  "steps": [
    "e^{ix} = \\cos(x) + i\\sin(x)",
    "e^{i\\pi} = \\cos(\\pi) + i\\sin(\\pi)",
    "e^{i\\pi} = -1 + i(0)",
    "e^{i\\pi} + 1 = 0"
  ],
  "highlight": [
    "e^{ix}",
    "x = \\pi",
    "-1",
    "+ 1 = 0"
  ]
}
```

### 避坑点
1. **不要一次传超过 6 步**：画面会拥挤且动画节奏过赶，超过 6 步应拆分为两个核心阶段。
2. **符号一致性**：若前后两步符号完全不同（如前一步写 `x`，后一步突然换成 `y`），平滑变形会退化为淡出淡入；保留公共符号能激活最佳的 3b1b 变形质感。

---

## 2. 函数图像：`mcp__manim__graph`

### 适用场景
- 损失函数行为（MSE vs CrossEntropy）
- 激活函数形态（Sigmoid, ReLU, GELU）
- 梯度下降收敛过程（切线移动）
- 概率密度函数与积分面积

### 参数规范
- `expressions`: `list[str]`（必填，1~3 个以 `x` 为变量的 Python 表达式，可使用 `np.*`，如 `"np.sin(x)"`、`"x**2 - 2*x + 1"`）。
- `title`: `str | None`（可选）。
- `x_range`: `[min, max, step]`（可选，默认 `[-4, 4, 1]`）。
- `y_range`: `[min, max, step]`（可选，默认 `[-3, 3, 1]`）。
- `highlight`: `dict | None`（可选）。
  - `{"x": 1.5, "tangent": true, "area": [0, 2]}`
  - `tangent: true` 会在指定 `x` 处动态生成切线并滑动。
  - `area: [a, b]` 会在指定区间渲染积分阴影区。
- `parameter`: `dict | None`（可选，`{"symbol": "a", "from": 1.0, "to": 3.0}`，配合表达式中的变量符号演示动态滑动）。

### 示例调用
```json
{
  "title": "ReLU 与 Sigmoid 激活函数对比",
  "expressions": [
    "np.maximum(0, x)",
    "1 / (1 + np.exp(-x))"
  ],
  "x_range": [-4, 4, 1],
  "y_range": [-1, 3, 1],
  "highlight": {
    "x": 0.0,
    "tangent": false
  }
}
```

---

## 3. 架构与流程：`mcp__manim__diagram`

### 适用场景
- 神经网络各层连接流程
- 编译管道、RAG 处理链路、分布式通信
- 状态机迁移与决策分支

### 参数规范
- `nodes`: `list[dict]`（必填，1~8 个节点）。
  - `id`: `str`（唯一标识，如 `"input"`, `"encoder"`）。
  - `label`: `str`（显示文字，支持中文）。
  - `kind`: `"process"` (默认蓝色) / `"decision"` (黄色菱形) / `"terminal"` (绿色圆角) / `"data"` (灰色数据源)。
- `edges`: `list[dict]`（必填）。
  - `from`: 起始节点 `id`。
  - `to`: 目标节点 `id`。
  - `label`: `str | None`（连线上的流转说明）。
- `layout`: `"vertical"`（默认自上而下）或 `"horizontal"`（自左向右）。

### 示例调用
```json
{
  "title": "大模型 RAG 检索生成流程",
  "layout": "horizontal",
  "nodes": [
    {"id": "q", "label": "用户 Query", "kind": "terminal"},
    {"id": "emb", "label": "向量化 Embedding", "kind": "process"},
    {"id": "db", "label": "向量知识库检索", "kind": "data"},
    {"id": "llm", "label": "LLM 综合生成", "kind": "process"},
    {"id": "ans", "label": "最终回答", "kind": "terminal"}
  ],
  "edges": [
    {"from": "q", "to": "emb"},
    {"from": "emb", "to": "db", "label": "相似度匹配"},
    {"from": "db", "to": "llm", "label": "Top-K 上下文"},
    {"from": "llm", "to": "ans"}
  ]
}
```

---

## 4. 左右对照：`mcp__manim__compare`

### 适用场景
- 正确做法 vs 错误做法
- 传统方案 vs 新架构优化（如 RNN vs Transformer）
- 浅拷贝 vs 深拷贝、同步 vs 异步

### 参数规范
- `left`: `{"title": str, "items": list[str]}`（必填，items 1~5 条）。
- `right`: `{"title": str, "items": list[str]}`（必填，items 1~5 条）。
- `title`: `str | None`（可选）。
- `left_color`: `"red"`（默认） / `"blue"` / `"green"` / `"highlight"` / `"grey"`。
- `right_color`: `"green"`（默认） / `"red"` / `"blue"` / `"highlight"` / `"grey"`。

### 示例调用
```json
{
  "title": "RNN 与 Transformer 架构特性对比",
  "left": {
    "title": "传统 RNN 序列模型",
    "items": [
      "单向时序递推，无法真正并行计算",
      "长程依赖易产生梯度消失或遗忘",
      "计算时间复杂度随序列长度线性堆积"
    ]
  },
  "left_color": "red",
  "right": {
    "title": "Transformer 自注意力机制",
    "items": [
      "全局注意力矩阵，矩阵乘法天然支持高度并行",
      "任意两个 Token 间连接距离恒为 O(1)",
      "位置编码（Positional Encoding）保留序列顺序"
    ]
  },
  "right_color": "green"
}
```
