# 历史短视频音频生产流水线（history-voice-pipeline）

> 按《执行方案 v1.0》施工并深化实现：「史料 → 事件卡 → 风格选定 → 大纲 → 旁白成稿 → 画本 → IndexTTS2 配音 → 成品音频」的人机协同流水线。
> 核心原则贯穿始终：**每个 AI 节点产出物都必须经过人工闸门（查看/修改/打回）才放行下一节点。**

---

## 一、相对执行方案的深化点

| 深化项 | 说明 |
| ------ | ---- |
| **节点命名含义化** | 全部节点以职责命名（见下表），无 N1-N8 这类代号进入代码 |
| **每节点一个 deepagents 实例** | 六个内容节点各自是独立的 deep agent（`app/agents/factory.py` 按节点装配）：独立模型档案 + 独立 skills 目录（复制进节点工作区 `data/agent_workspaces/<节点>/skills/`，deepagents 渐进加载）+ 可选 MCP 工具；外层 LangGraph 主图负责编排与人工闸门 |
| **技能/MCP 前端可配** | 设置页可逐节点勾选挂载哪些 skills、哪些 MCP 服务器；默认按执行方案 §5.1 挂载表播种；MCP 服务器支持 http/sse/stdio/websocket 四种 transport，可在线测试连接列出工具 |
| **闸门架构修订** | 每个 AI 环节拆成「产出节点 → 闸门节点」两个图节点：interrupt 只放闸门里，resume 时闸门重跑零成本——**避免 resume 重复调 LLM 烧 token** |
| **Prompt 集中管理** | 全部节点 prompt 收在 `app/prompts.py` 一个文件：人格 L1 常驻前缀在此统一注入，每个 builder 返回 (system, user) 作为该节点 deep agent 的 system_prompt + 任务消息；system 首行带 `<!-- NODE:节点id -->` 标记（MockLLM 路由 + 日志审计两用）；技能不再全文塞进 prompt，改为「挂载清单」引导 agent 用 read_file 渐进读取 |
| **六份文档转 skill** | 六份方法论原样转 `skills/*/SKILL.md`（只加 frontmatter 不改正文），另按 §4.1/§4.6 新建 `historical-event-cards`、`narration-auditor` 两个技能 |
| **零依赖降级通道** | `mock_tts`（正弦音合成）+ mock 模型档案（LangChain 路由式假模型）：不配任何 Key、不装 IndexTTS2 也能全链路演示与测试 |

## 二、节点命名一览（命名即含义）

```
产出节点                            闸门节点（人工）
n1_event_card_mining      史料选矿   gate_n1_event_cards      事件卡闸门
n2_style_robe_selection   外衣选定   gate_n2_style_card       风格拍板（必选动作）
n3_outline_blueprinting   大纲蓝图   gate_g1_theme_veto       ⛔主题否决关（强制）
n4_narration_construction 旁白施工   gate_n4_script           成稿闸门
n5_draft_three_gate_audit 三道门禁   gate_n5_audit_verdict    审核裁决（可打回N4）
n6_storyboard_translation 画本翻译   gate_n6_storyboard       画本闸门
n7_unit_voice_synthesis   分段合成   gate_n7_unit_listening   单元试听（勾选重生）
n7_failed_unit_regeneration 塌段定点重生（只重生选中单元）
n8_audio_mastering        质检后期   gate_g2_final_listening  ⛔审听签发（可标塌段回N7）
finalize_episode_archive  归档（打回教训沉淀 + 读音词典入库）
```

打回路由：闸门 reject → 回本环节产出节点重跑（feedback 注入 prompt，「按条目改不重写」）；
N5 reject → 跨节点回 N4（打回条目自动组装注入）；G2 标塌段 → 回 N7 定点重生。

## 三、快速开始

```bash
pip install -r requirements.txt
cp .env.example .env          # 默认 HVP_TTS_BACKEND=mock，零依赖可跑
python run.py                 # http://127.0.0.1:8600
```

1. **模型设置页**：建模型档案（演示选 provider=`mock` 恒可用；生产填 OpenAI 兼容的 base_url/api_key/model），绑定六个内容节点；
2. **节点 Agent 挂载**（同页）：逐节点勾选 skills / MCP 工具——默认已是 §5.1 挂载表；下方可登记 MCP 服务器（http/sse/stdio/websocket）并「测试连接」列出其工具；
3. **项目列表页**：粘贴史料 → 选类型（人物/朝代/事件）→ 创建并启动；
4. **工作台**：流程条实时刷新（SSE），每个闸门看产物 → 放行 / 编辑后放行 / 打回（填意见）；
5. 音频节点逐单元试听、勾选重生；成品页整轨审听、标塌段回退；
6. 归档后 `data/memory/lessons.md` 自动沉淀本任务打回教训，读音词典入库——**下一个任务自动继承**。

## 四、接真实 LLM 与 IndexTTS2

- LLM：任何 OpenAI 兼容服务（DeepSeek/Kimi/Qwen/Ollama）均可，设置页逐项配；建议 N4 用最强模型、N5 用不同家模型（交叉防盲区）。
- IndexTTS2：`.env` 设 `HVP_TTS_BACKEND=indextts2` + `INDEXTTS2_BASE_URL`；参数签名差异只改 `app/tts/indextts2_client.py` 一处（开工先 `IndexTTS2Client().smoke_test()`）。
- 音色库页上传 narrator 基准音色 + 情感参考音频。

## 五、测试

```bash
python -m pytest tests/ -q     # 37 passed
```

| 测试 | 覆盖 |
| ---- | ---- |
| test_scans.py | 禁词/套话/零信息量扫描、字数分级容差 |
| test_prompts.py | 人格 L1 常驻注入、节点标记、技能挂载清单（渐进加载）、挂载覆盖、打回注入、记忆审计 |
| test_agent_factory.py | deepagents 工厂：§5.1 默认播种、工作区技能副本、mock 全栈调用、配置校验、MCP 错误可读 |
| test_audio.py | mock 合成、停顿/章间拼接、FFmpeg 后期（-16 LUFS）、字幕时间轴 |
| test_pipeline_e2e.py | 全流程：打回重跑+版本递增、编辑放行、定点重生、G2 塌段回退、归档沉淀 |
| test_api.py | HTTP 建任务→启动→闸门快照→放行/打回、第二集强制衔接段 |
| test_retry_and_delete.py | JSON 加固、节点内部重试、error 后原地重试、项目级联删除、节点记录/日志端点 |

## 六、目录结构

```
app/
├── main.py              FastAPI 入口（API + static + /media）
├── prompts.py           ★ 全部节点 prompt 集中管理
├── state.py             PipelineState 全局状态契约
├── models.py / db.py    SQLModel 表（含 mcp_servers / node_agent_configs）
├── llm.py               模型档案解析 + extract_json 加固
├── agents/
│   ├── node_registry.py 内容节点清单 + §5.1 默认技能挂载表（单一真源）
│   ├── lc_models.py     模型档案 → LangChain ChatModel（mock 路由/OpenAI 兼容/init_chat_model）
│   └── factory.py       ★ deepagents 实例工厂：按节点装配 模型+skills目录+MCP工具
├── skills_loader.py     技能加载（原文+frontmatter 元数据+目录清单）
├── memory_store.py      人格 L2 系列记忆（lessons/voice_samples）
├── graph/pipeline.py    LangGraph 主图（编排各 deep agent 节点+闸门+回退边）
├── graph/nodes.py       全部节点实现（内容节点经 factory 调 deep agent）
├── services/scans.py    确定性扫描（不进 LLM）
├── services/artifacts.py 产物版本管理（重跑不覆盖）
├── services/runner.py   后台线程调度 + checkpoint
└── tts/                 mock_tts / indextts2_client / postprocess(FFmpeg)
skills/                  8 个技能目录（6 份原文 + 2 份新建，节点的默认技能库）
static/                  index / run / settings / voices 四页（无构建）
data/                    运行时生成：pipeline.db、agent_workspaces/、projects/{id}/、memory/、refs/
tests/                   7 个测试文件，37 条用例
```

## 七、人格三层落实情况（§5.3）

- **L1 常驻**：`prompts.persona_prefix()` 把 persona-writer 全文注入每个内容节点 system 首段，测试强制断言；
- **L2 系列记忆**：归档时打回教训 → `lessons.md`；闸门放行时语气示例 → `voice_samples.md`；N6/N7 专名 → `pronunciation_dict` 表；后续任务开工自动读取，`memories_loaded` 可审计；
- **L3 单集记忆**：声口样句、情绪坐标、伏笔登记表随 state/产物文件在各节点间共享。

## 八、deepagents 架构要点（v1.2 重构）

- **每个内容节点 = 一个 deepagents 实例**（执行方案 §3/§4）：`create_deep_agent(model, system_prompt, skills, tools, backend)`——模型来自该节点绑定的模型档案；`system_prompt` 来自 prompts.py（L1 人格 + 挂载清单 + L2 记忆）；`backend=FilesystemBackend(节点工作区)`；挂载技能复制到工作区 `skills/` 下，走 deepagents 原生渐进加载（清单 → read_file 手册正文 → 随附资源）。
- **MCP**：设置页登记服务器（http/sse/stdio/websocket），逐节点勾选挂载；构建 agent 时经 `langchain-mcp-adapters` 的 `MultiServerMCPClient` 拉取工具注入 `tools=`；连接失败报带节点名/服务器名的错误，进 node_runs 可重试。
- **LangGraph 仍是编排层**：主图不变（产出节点→人工闸门→回退边），deep agent 在产出节点内部被调用。已知坑已修：节点函数内调 agent 必须显式传**全新 thread_id 的 config**，否则内层图继承外层 checkpoint 上下文，resume/重试时 LangGraph 会确定性重放旧结果、模型不被重调（有最小复现测试守护——test_retry_and_delete.py）。
- **配置即缓存失效**：agent 缓存键含 技能文件 mtime + 节点配置/MCP 表更新时间戳，前端改挂载后下次构建自动生效。

## 九、运维能力（v1.1 增补）

| 能力 | 实现 |
| ---- | ---- |
| **项目删除** | `DELETE /api/projects/{id}`——连运行记录、产物版本、checkpoint、产物文件一起清；项目列表页每张卡片有删除按钮（带确认） |
| **出错重试** | 节点失败后 run 进入 `error`；工作台错误面板点「重试失败节点」→ `POST /api/runs/{id}/retry` → LangGraph `invoke(None)` **从 checkpoint 原地重跑失败节点**，不从头再来。另：LLM 输出 JSON 解析失败时节点内部已自动重试 1 次（附「只输出 JSON」强约束） |
| **节点查看** | `GET /api/runs/{id}/node-runs`——每次节点执行的状态/耗时/错误；工作台底部「节点运行记录」折叠区实时可查 |
| **后台日志** | `data/logs/pipeline.log`（RotatingFileHandler 5MB×3）：驱动开始/节点开始完成/LLM 返回字数/失败 traceback 全记录；`GET /api/logs/tail?lines=200` 在线查看 |
| **JSON 加固** | `extract_json` 剥离推理模型 `<think>` 块、容忍代码块包裹与前后散文、空返回报清晰错误——修掉线上「Expecting value: line 1 column 1」事故 |

## 十、已知边界（本期范围外，按 §1.2）

- 不做视频剪辑/地图动画（字幕时间轴 JSON 留给地图 pipeline 对轴）
- 不做 BGM 生成与混音（后期链已预留 sidechain 参数位）
- 一次一集；选题与分集界定是人工动作
