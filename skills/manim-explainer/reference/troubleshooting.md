# 渲染排错与自愈协议

当调用 `mcp__manim__render` 或声明式模板失败时，MCP 引擎会截获底层子进程的 stderr，并将堆栈格式化为结构化诊断包返回。绝不要无头苍蝇式地重试，必须根据诊断精准修复。

---

## 1. 结构化错误响应解剖

典型失败返回结构如下：

```json
{
  "ok": false,
  "runId": "20260915-124116-15af1bcc",
  "stage": "manim",
  "error": {
    "stage": "manim",
    "message": "manim 退出码 1",
    "stderrTail": "TypeError: Only values of type VMobject can be added as submobjects of VGroup..."
  },
  "hint": "检查第 86 行附近的对象类型...",
  "codePath": "<render_root>\\...\\scene.py"
}
```

### 必看核心字段
- `error.stderrTail`：底层 Python/LaTeX/Manim 报错的最底层真实原因。
- `hint`：MCP 引擎启发式正则给出的针对性修复建议（命中率极高）。
- `codePath`：真实保存在磁盘上的完整代码，可用代码阅读工具查阅。

---

## 2. 常见报错模式与直达疗法

| 错误特征（stderr 片段） | 根本原因 | 标准修复动作 |
|---|---|---|
| `TypeError: Only values of type VMobject...` | 把动画对象（`ShowPassingFlash`/`FadeIn`）塞进了 `VGroup` | 将其改为普通 Python 列表，解包传给 `LaggedStart` 或 `self.play` |
| `latex error converting to dvi` / `LaTeX Error: ...` | 公式中有不合法的 LaTeX 语法，或缺少特定数学宏包 | 简化公式表达式，确认 `r"..."` 原始字符串，去掉不支持的冷门宏 |
| `NameError: name 'null' is not defined` | 在 Python 代码中手写了 JSON 字面量 `null` 或 `false` | 替换为 Python 原生 `None` 或 `False` |
| `AttributeError: ... has no attribute 'animate'` | 对非 Mobject 对象调用了 `.animate` | 检查变量是否为图元对象，不要链式缓存 animate 变量 |
| `FileNotFoundError: latex` | 本机未安装 MiKTeX/TeXLive 或未在 PATH 上 | 降级为纯文本 `cn(...)` 展示，不使用 LaTeX 公式 |

---

## 3. 自愈铁律（两折止损）

1. **最多重试 2 次**：
   - 第一次失败：仔细阅读 `stderrTail` 与报错行号，**只修改诱发崩溃的那一处逻辑**，严禁推倒重来。
   - 第二次若仍然失败：**立刻停止尝试渲染**！
2. **拒绝静默吞错，优雅降级**：
   - 不允许对用户假装什么都没发生，也不允许仅抛出一句冷冰冰的“渲染失败”。
   - 必须在回答正文中：
     1. 正常用文字把核心原理推导阐明；
     2. 诚实告知由于 Manim 渲染异常未能生成动态视频；
     3. 附带给出 `scene.py` 路径供开发者排查。

---

## 4. 用户反馈「没看到动画 / 你没发出来」怎么办？（血泪防呆）

当用户发出这种疑问时，**99% 的概率不是底层渲染坏了，而是模型犯了糊涂，把行为规则执行砸了**！请立即按以下顺序自查：

1. **第一排查点：自己是不是把 `previewMarkdown` 漏贴了？！**
   - 回看上一轮输出：文本里到底有没有 `![anim](/myprogram/...)` 这一行？
   - 很多模型会犯一个典型毛病：调用完工具后只顾着用嘴吹“如上方动画所示”、“请看视频”，实际上文本里根本漏贴了图片语法！
   - **立即补救动作**：在当前回答里把工具返回的 `![anim](...)` 原样贴出来！
2. **第二排查点：是不是误以为调了 `publish_file` 就不用贴 Markdown 了？！**
   - `publish_file` 是为了提供高清 MP4 播放器和附件卡片，它**绝不能代替正文动图**。正文动图必须同时贴出。
3. **严禁的三大自作聪明行为（违者必究）**：
   - ❌ **严禁去弹外部程序**：严禁通过 PowerShell / Bash 执行 `Start-Process` 打开本地播放器，严禁手写 HTML 去唤起 Chrome 弹窗！这严重破坏聊天体验。
   - ❌ **严禁甩锅通道**：严禁谎称“由于聊天界面的媒体渲染通道限制”。
   - ❌ **严禁乱抽帧**：不要自作主张用 ffmpeg 提取第 3 秒、第 5 秒截图或另起炉灶切 GIF，原动图完全可播。
