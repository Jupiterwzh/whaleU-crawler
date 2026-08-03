Agent 的一生
One Loop to Read Them All — 一段伪代码看懂 Agent 的全过程
整段代码里,大脑只做一行任务决策,其余全是工程。这就是 Agent = LLM × Harness 最直白的说明:LLM 是 CPU,Harness 是让它可靠工作的操作系统。

Step 1–6 → 看循环如何长出来

The Core Loop
主循环 · 所有概念各就各位
这段主循环可以逐层展开:用顶部 Step 1–6 从最简的「裸 LLM 循环」一步步叠加 harness,绿色高亮本步新增的代码行,配合下方讲解看清每一步多了什么能力(点胶囊或按 ← → 切换)。第 6 步是完整版,仍分三段:① 启动装配(一次性)→ ② while 主循环(每轮一次 LLM 决策)→ ③ 收尾(退出后跑一次)。带颜色的 【概念】 标注可点。

Step 1 / 6
裸循环
# 最简循环:此刻只有大脑在转,还没有任何 harness
function agent_loop(goal):
    context = [goal]                      # 提供给大脑的全部信息,目前只有任务本身
    while True:
        text = LLM(context)               # 大脑唯一的工作:看上下文,决定这一步说什么★ 唯一的「任务决策」LLM 调用
        context += message("assistant", text)   # 把回复追加进历史,下一轮它才记得自己说过什么
        if looks_done(text):              # 粗糙的判停:文本里像是说完了,就停下
            return text

agent 的心脏就是一个 while 循环:把对话历史 context 提供给 LLM,它产出下一句,追加回历史,再进入下一轮。
此刻大脑只会“说”(text),还不能“做”:没有工具、没有记忆、没有治理,纯粹是个会应答的循环。
context 是它唯一的记忆:不把回复写回历史,下一轮它就忘了自己说过什么。

Step 2 / 6
加工具
# 加入“动作”:大脑现在不只是说话,还能调用工具去改变世界
function agent_loop(goal):
    context = [goal]                      # 提供给大脑的全部信息,目前只有任务本身
    tools = register_builtin_tools()      # 【Tool 原语】读写文件 / 跑 bash,agent 能动手的最底层原语
    while True:
        text, action = LLM(context, tools)   # 大脑还要决定“做什么”:返回 (说什么 text, 做什么 action)★ 唯一的「任务决策」LLM 调用
        context += message("assistant", [text, action])
        if action.type == "done":         # 用一个显式动作表示完成,而不是去猜文本
            return text
        if action.type == "call_tool":
            result = run_tool(tools[action.tool], action.args)   # 真正去执行这次工具调用
            context += message("user", result)   # 把结果作为 user 消息回灌,一来(assistant)一回(user)就是 agent 的节拍

LLM 的返回从“只有 text”变成“(text, action)”:既说话,又决定下一步做什么动作。
call_tool 分支真正执行工具,再把结果作为 user 消息回灌,assistant 说/做、user 返回结果,这一来一回就是 agent loop 的基本节拍。
done 也变成一个显式动作,而不是去猜文本说完没。能调工具改变世界、再读回结果,正是 agent 区别于 chatbot 的分水岭。

# ---------- ① 启动装配:跑在 while 之前,一次性 ----------
function build_agent(project):
    system_prompt = vendor_system_prompt()  # 厂商内建、你无法修改的“骨架”那部分上下文:产品级 harness 的核心
    rules     = load_rule_files("CLAUDE.md", "AGENTS.md") # 【规则文件】启动自动加载的声明式约束(你来填的内容物)
    tools     = register_builtin_tools() # 【Tool 原语】读写文件/跑 bash……agent 最底层的动作
    memory    = open_memory()            # 【记忆 (Write)】跨会话长期记忆的读写口
    retriever = open_retriever()         # 【RAG / Select】按需把外部知识检索进上下文
    return Harness(system_prompt, rules, tools, memory, retriever)
 
    return answer

Step 3 / 6
上下文工程
# ---------- ② 主体:整个函数体 = harness;LLM 只占其中一行 ----------
function agent_loop(goal, H):
    # 【CE 上下文工程】组织“提供给大脑的信息”,这是 harness 的另一半工作
    context  = H.system_prompt           # 骨架:厂商内建的系统提示词(范式A 最好的代码级例子,你无法修改)
    context += H.rules                   # 内容物:你在 CLAUDE.md 里填的那部分
    context += H.memory.read(goal)       # 【CE-读记忆】跨会话长期记忆(现代实现里读/写常是模型自己调的工具)
    context += H.retriever.retrieve(goal)# 【CE-Select/RAG】开局先检索一批相关知识(预检索)
    context += goal
 
    done   = False
    answer = None
    steps  = 0
    while not done and steps < MAX_STEPS:   # guard:除最大轮数,真实系统还设超时/费用预算/重复调用检测
        steps += 1
 
        if token_count(context) > LIMIT:
            context = compact(context)  # 【熵管理 / CE-Compress】窗口将满则压缩(这步本身也常是一次 LLM 调用)
 
        menu = H.tools.list()   # 把“可用功能菜单”提供给大脑(此刻只有内建工具)
 
        # ========================================================
        text, action = LLM(context, menu)  # ← LLM 唯一一行做“任务决策”:只负责“想下一步”★ 唯一的「任务决策」LLM 调用
        # 注:多数语言里函数只返回“一个”对象/值,这行返回的其实就是那一个“响应对象”,等号左边把它就地拆成 text(说什么) 和 action(做什么) 两半
        # ========================================================
        context += message("assistant", [text, action])  # 关键:把模型这一整轮(它说的 text + 它发起的 action)打包成一条 assistant 消息写回历史,下一轮它才看得见自己说过/做过什么
 
        if action.type == "done":
            done   = True
            answer = text               # 停下:最终答案就是模型这轮的输出(“无工具调用即停”是另一派等价写法)
            continue
 
        if action.type == "call_tool":
            result = run_tool(H.tools[action.tool], action.args)  # 执行工具(下一步会给它加上沙箱)
            context += message("user", result)   # 工具结果作为一条 user 消息回灌(assistant 说/做 ↔ user 返回结果,一来一回)
 
        elif action.type == "take_note":
            H.memory.write(action.note)                   # 【CE-Write·循环内】大脑主动记笔记(scratchpad)
 
    # ---------- ③ 收尾:循环退出后,跑且只跑一次 ----------
    H.memory.consolidate(context)       # 【CE-Write·会话末】把零散笔记固化成长期记忆

零件变多了,于是把它们抽进 build_agent、打包成一个 harness 对象 H,harness 不是天生的,是这样“长”出来的。
开局认真装配 context:系统提示词 + 规则文件 + 跨会话记忆 + RAG 检索。喂什么给大脑,直接决定任务质量,这是 harness 的另一半工作。
compact 在窗口将满时压缩历史(熵管理 / Compress),take_note 让大脑主动记笔记。注意:这里的“压缩”和第 5 步子 agent 带回的“摘要”是两回事。
while 也加上了 MAX_STEPS 预算上限,别让循环失控。


# ---------- ① 启动装配:跑在 while 之前,一次性 ----------
function build_agent(project):
    system_prompt = vendor_system_prompt()  # 厂商内建、你无法修改的“骨架”那部分上下文:产品级 harness 的核心
    rules     = load_rule_files("CLAUDE.md", "AGENTS.md") # 【规则文件】启动自动加载的声明式约束(你来填的内容物)
    tools     = register_builtin_tools() # 【Tool 原语】读写文件/跑 bash……agent 最底层的动作
    hooks     = register_hooks()         # 【Hooks】绑到生命周期事件上的脚本
    guardrail = register_guardrail()     # 【权限门控/Guardrail】危险动作的策略闸:产品级 harness 最显眼的部件
    sandbox   = create_sandbox(limits)   # 【架构约束/Sandbox】给一切执行加上隔离与资源上限
    tracer    = open_trace()             # 【可观测性】记录每一步,事后可回放
    memory    = open_memory()            # 【记忆 (Write)】跨会话长期记忆的读写口
    retriever = open_retriever()         # 【RAG / Select】按需把外部知识检索进上下文
    return Harness(system_prompt, rules, tools,
                   hooks, guardrail, sandbox, tracer, memory, retriever)
 
Step 4 / 6
治理与安全
# ---------- ② 主体:整个函数体 = harness;LLM 只占其中一行 ----------
function agent_loop(goal, H):
    # 【CE 上下文工程】组织“提供给大脑的信息”,这是 harness 的另一半工作
    context  = H.system_prompt           # 骨架:厂商内建的系统提示词(范式A 最好的代码级例子,你无法修改)
    context += H.rules                   # 内容物:你在 CLAUDE.md 里填的那部分
    context += H.memory.read(goal)       # 【CE-读记忆】跨会话长期记忆(现代实现里读/写常是模型自己调的工具)
    context += H.retriever.retrieve(goal)# 【CE-Select/RAG】开局先检索一批相关知识(预检索)
    context += goal
 
    done   = False
    answer = None
    steps  = 0
    while not done and steps < MAX_STEPS:   # guard:除最大轮数,真实系统还设超时/费用预算/重复调用检测
        steps += 1
 
        if token_count(context) > LIMIT:
            context = compact(context)  # 【熵管理 / CE-Compress】窗口将满则压缩(这步本身也常是一次 LLM 调用)
 
        menu = H.tools.list()   # 把“可用功能菜单”提供给大脑(此刻只有内建工具)
 
        # ========================================================
        text, action = LLM(context, menu)  # ← LLM 唯一一行做“任务决策”:只负责“想下一步”★ 唯一的「任务决策」LLM 调用
        # 注:多数语言里函数只返回“一个”对象/值,这行返回的其实就是那一个“响应对象”,等号左边把它就地拆成 text(说什么) 和 action(做什么) 两半
        # ========================================================
        context += message("assistant", [text, action])  # 关键:把模型这一整轮(它说的 text + 它发起的 action)打包成一条 assistant 消息写回历史,下一轮它才看得见自己说过/做过什么
        H.tracer.record(text, action)   # 【可观测性·循环内】每轮记下整轮(说什么+做什么);真实系统还把下面的观察结果一并记入,凑成(决策,观察)对
 
        if action.type == "done":
            done   = True
            answer = text               # 停下:最终答案就是模型这轮的输出(“无工具调用即停”是另一派等价写法)
            continue
 
        if not H.guardrail.allow(action):                 # 【权限门控/Guardrail】危险动作先拦
            context += message("user", "该动作被策略拦截"); continue   # 高风险时在此停下等人工审批(HITL)
 
        verdict = run_hooks(H.hooks, "PreToolUse", action) # 【Hooks】执行前触发;PreToolUse 也能返回 deny 拦截
        if verdict == "deny":                              #   可见 Guardrail 与 Hooks 实为同一套闸的两种用法
            context += message("user", "被 Hook 拦截"); continue
 
        if action.type == "call_tool":
            result = H.sandbox.run(H.tools[action.tool], action.args)  # 【Tool 原语】内建工具(在沙箱内执行)
            context += message("user", result)   # 工具结果作为一条 user 消息回灌(assistant 说/做 ↔ user 返回结果,一来一回)
 
        elif action.type == "take_note":
            H.memory.write(action.note)                   # 【CE-Write·循环内】大脑主动记笔记(scratchpad)
 
        run_hooks(H.hooks, "PostToolUse", action)         # 【Hooks】执行后触发
 
    # ---------- ③ 收尾:循环退出后,跑且只跑一次 ----------
    # 触发时机 = done==True(任务完成)  或  steps==MAX_STEPS(预算耗尽)
    run_hooks(H.hooks, "SessionEnd", None)  # 【Hooks】会话结束事件:装配时注册,这里才触发
    H.memory.consolidate(context)       # 【CE-Write·会话末】把零散笔记固化成长期记忆
    H.tracer.flush()                    # 【可观测性·会话末】最终落盘
    return answer

guardrail 在动作执行“之前”拦截危险操作(删库 / 转账 / 对外发布),高风险时停下转人工审批(HITL)。
Hooks 绑在生命周期事件上(PreToolUse / PostToolUse / SessionEnd);PreToolUse 也能返回 deny,可见 Guardrail 与 Hooks 是同一套闸的两种用法:一个“拦”,一个“触发”。
sandbox 给每次执行加上隔离与资源上限;tracer 记录每一步,事后可回放、可审计。这一层让 agent 从“能工作”变成“能安全地工作”。


# ---------- ① 启动装配:跑在 while 之前,一次性 ----------
function build_agent(project):
    system_prompt = vendor_system_prompt()  # 厂商内建、你无法修改的“骨架”那部分上下文:产品级 harness 的核心
    rules     = load_rule_files("CLAUDE.md", "AGENTS.md") # 【规则文件】启动自动加载的声明式约束(你来填的内容物)
    skills    = register_skills()        # 【Skill】只登记“名片”(description),不载全文
    tools     = register_builtin_tools() # 【Tool 原语】读写文件/跑 bash……agent 最底层的动作
    mcp       = connect_mcp_servers()    # 【MCP】把外部工具按统一协议接进来(N+M,不为每个工具改代码)
    hooks     = register_hooks()         # 【Hooks】绑到生命周期事件上的脚本
    guardrail = register_guardrail()     # 【权限门控/Guardrail】危险动作的策略闸:产品级 harness 最显眼的部件
    sandbox   = create_sandbox(limits)   # 【架构约束/Sandbox】给一切执行加上隔离与资源上限
    tracer    = open_trace()             # 【可观测性】记录每一步,事后可回放
    memory    = open_memory()            # 【记忆 (Write)】跨会话长期记忆的读写口
    retriever = open_retriever()         # 【RAG / Select】按需把外部知识检索进上下文
    return Harness(system_prompt, rules, skills, tools, mcp,
                   hooks, guardrail, sandbox, tracer, memory, retriever)
 
Step 5 / 6
扩展与协作
# ---------- ② 主体:整个函数体 = harness;LLM 只占其中一行 ----------
function agent_loop(goal, H, depth=0):  # H = 装配好的 harness;depth 给子 agent 防递归过深
    # 【CE 上下文工程】组织“提供给大脑的信息”,这是 harness 的另一半工作
    context  = H.system_prompt           # 骨架:厂商内建的系统提示词(范式A 最好的代码级例子,你无法修改)
    context += H.rules                   # 内容物:你在 CLAUDE.md 里填的那部分
    context += H.memory.read(goal)       # 【CE-读记忆】跨会话长期记忆(现代实现里读/写常是模型自己调的工具)
    context += H.retriever.retrieve(goal)# 【CE-Select/RAG】开局先检索一批相关知识(预检索)
    context += goal
    # 注:除开局预检索,菜单里还放了 search / read_file / memory 等工具,
    #     让模型在循环内按需取数(just-in-time),而非一次性全部放入
 
    done   = False
    answer = None
    steps  = 0
    while not done and steps < MAX_STEPS:   # guard:除最大轮数,真实系统还设超时/费用预算/重复调用检测
        steps += 1
 
        if token_count(context) > LIMIT:
            context = compact(context)  # 【熵管理 / CE-Compress】窗口将满则压缩(这步本身也常是一次 LLM 调用)
 
        # 把“可用功能菜单”提供给大脑:内建工具 + MCP 工具 + Skill 名片(真实系统还含 search/memory 等工具)
        menu = H.tools.list() + H.mcp.list_tools() + H.skills.list_descriptions()
 
        # ========================================================
        text, action = LLM(context, menu)  # ← LLM 唯一一行做“任务决策”:只负责“想下一步”★ 唯一的「任务决策」LLM 调用
        # 注:多数语言里函数只返回“一个”对象/值,这行返回的其实就是那一个“响应对象”,等号左边把它就地拆成 text(说什么) 和 action(做什么) 两半
        # ========================================================
        context += message("assistant", [text, action])  # 关键:把模型这一整轮(它说的 text + 它发起的 action)打包成一条 assistant 消息写回历史,下一轮它才看得见自己说过/做过什么
        H.tracer.record(text, action)   # 【可观测性·循环内】每轮记下整轮(说什么+做什么);真实系统还把下面的观察结果一并记入,凑成(决策,观察)对
 
        if action.type == "done":
            done   = True
            answer = text               # 停下:最终答案就是模型这轮的输出(“无工具调用即停”是另一派等价写法)
            continue
 
        if not H.guardrail.allow(action):                 # 【权限门控/Guardrail】危险动作先拦
            context += message("user", "该动作被策略拦截"); continue   # 高风险时在此停下等人工审批(HITL)
 
        verdict = run_hooks(H.hooks, "PreToolUse", action) # 【Hooks】执行前触发;PreToolUse 也能返回 deny 拦截
        if verdict == "deny":                              #   可见 Guardrail 与 Hooks 实为同一套闸的两种用法
            context += message("user", "被 Hook 拦截"); continue
 
        if action.type == "use_skill":
            instructions = H.skills.load(action.name)     # 【Skill 渐进式披露】命中才把 SKILL.md 全文读进上下文
            context += message("user", instructions)   # 载入的 SKILL.md 全文作为 user 消息进上下文(读入指令文本而非运行;脚本随后走 call_tool)
 
        elif action.type == "call_tool":                  # 区分:工具从哪来
            if action.tool in H.mcp:
                result = H.mcp.call(action.tool, action.args)  # 【MCP】走协议(在外部执行,本地沙箱覆盖不到)
            else:
                result = H.sandbox.run(H.tools[action.tool], action.args)  # 【Tool 原语】内建工具
            context += message("user", result)   # 工具结果作为一条 user 消息回灌(assistant 说/做 ↔ user 返回结果,一来一回)
 
        elif action.type == "spawn_subagent":             # 【子 Agent / CE-Isolate】
            if depth >= MAX_DEPTH:                         #   用上 depth:再嵌一层就太深,直接拒绝,防递归过深 / fork 炸弹
                context += message("user", "子 agent 嵌套已达深度上限,拒绝派发"); continue
            child_H  = H.restrict(action.scope)           #   子 agent 通常拿“受限 harness”:别的提示词 / 工具子集 / 更小模型
            summary  = agent_loop(action.subtask, child_H, depth + 1)  #   开独立上下文递归自己,也可并行 fan-out 多个
            context += message("user", summary)   # 只把“摘要”作为一条 user 消息带回,不污染主上下文
 
        elif action.type == "take_note":
            H.memory.write(action.note)                   # 【CE-Write·循环内】大脑主动记笔记(scratchpad)
 
        run_hooks(H.hooks, "PostToolUse", action)         # 【Hooks】执行后触发
 
    # ---------- ③ 收尾:循环退出后,跑且只跑一次 ----------
    # 触发时机 = done==True(任务完成)  或  steps==MAX_STEPS(预算耗尽)
    run_hooks(H.hooks, "SessionEnd", None)  # 【Hooks】会话结束事件:装配时注册,这里才触发
    H.memory.consolidate(context)       # 【CE-Write·会话末】把零散笔记固化成长期记忆
    H.tracer.flush()                    # 【可观测性·会话末】最终落盘
    return answer

Skill 是给大脑读的“功能包”:平时只占一张名片(description),命中了才把 SKILL.md 全文读进上下文(渐进式披露)。
MCP 把外部工具按统一协议接进来,菜单从“只有内建工具”扩展到“内建 + MCP + Skill 名片”。
spawn_subagent 开一个隔离上下文的子 agent,本质是递归调用 agent_loop 自己,只把摘要带回主流程;MAX_DEPTH 守卫给递归设防,防 fork 炸弹。


# ---------- ① 启动装配:跑在 while 之前,一次性 ----------
function build_agent(project):
    system_prompt = vendor_system_prompt()  # 厂商内建、你无法修改的“骨架”那部分上下文:产品级 harness 的核心
    rules     = load_rule_files("CLAUDE.md", "AGENTS.md") # 【规则文件】启动自动加载的声明式约束(你来填的内容物)
    skills    = register_skills()        # 【Skill】只登记“名片”(description),不载全文
    tools     = register_builtin_tools() # 【Tool 原语】读写文件/跑 bash……agent 最底层的动作
    mcp       = connect_mcp_servers()    # 【MCP】把外部工具按统一协议接进来(N+M,不为每个工具改代码)
    hooks     = register_hooks()         # 【Hooks】绑到生命周期事件上的脚本
    guardrail = register_guardrail()     # 【权限门控/Guardrail】危险动作的策略闸:产品级 harness 最显眼的部件
    sandbox   = create_sandbox(limits)   # 【架构约束/Sandbox】给一切执行加上隔离与资源上限
    tracer    = open_trace()             # 【可观测性】记录每一步,事后可回放
    memory    = open_memory()            # 【记忆 (Write)】跨会话长期记忆的读写口
    retriever = open_retriever()         # 【RAG / Select】按需把外部知识检索进上下文
    return Harness(system_prompt, rules, skills, tools, mcp,
                   hooks, guardrail, sandbox, tracer, memory, retriever)
 
Step 6 / 6
反馈闭环
# ---------- ② 主体:整个函数体 = harness;LLM 只占其中一行 ----------
function agent_loop(goal, H, depth=0):  # H = 装配好的 harness;depth 给子 agent 防递归过深
    # 【CE 上下文工程】组织“提供给大脑的信息”,这是 harness 的另一半工作
    context  = H.system_prompt           # 骨架:厂商内建的系统提示词(范式A 最好的代码级例子,你无法修改)
    context += H.rules                   # 内容物:你在 CLAUDE.md 里填的那部分
    context += H.memory.read(goal)       # 【CE-读记忆】跨会话长期记忆(现代实现里读/写常是模型自己调的工具)
    context += H.retriever.retrieve(goal)# 【CE-Select/RAG】开局先检索一批相关知识(预检索)
    context += goal
    # 注:除开局预检索,菜单里还放了 search / read_file / memory 等工具,
    #     让模型在循环内按需取数(just-in-time),而非一次性全部放入
 
    done   = False
    answer = None
    steps  = 0
    while not done and steps < MAX_STEPS:   # guard:除最大轮数,真实系统还设超时/费用预算/重复调用检测
        steps += 1
 
        if token_count(context) > LIMIT:
            context = compact(context)  # 【熵管理 / CE-Compress】窗口将满则压缩(这步本身也常是一次 LLM 调用)
 
        # 把“可用功能菜单”提供给大脑:内建工具 + MCP 工具 + Skill 名片(真实系统还含 search/memory 等工具)
        menu = H.tools.list() + H.mcp.list_tools() + H.skills.list_descriptions()
 
        # ========================================================
        text, action = LLM(context, menu)  # ← LLM 唯一一行做“任务决策”:只负责“想下一步”★ 唯一的「任务决策」LLM 调用
        # 注:多数语言里函数只返回“一个”对象/值,这行返回的其实就是那一个“响应对象”,等号左边把它就地拆成 text(说什么) 和 action(做什么) 两半
        # ========================================================
        context += message("assistant", [text, action])  # 关键:把模型这一整轮(它说的 text + 它发起的 action)打包成一条 assistant 消息写回历史,下一轮它才看得见自己说过/做过什么
        H.tracer.record(text, action)   # 【可观测性·循环内】每轮记下整轮(说什么+做什么);真实系统还把下面的观察结果一并记入,凑成(决策,观察)对
 
        if action.type == "done":
            done   = True
            answer = text               # 停下:最终答案就是模型这轮的输出(“无工具调用即停”是另一派等价写法)
            continue
 
        if not H.guardrail.allow(action):                 # 【权限门控/Guardrail】危险动作先拦
            context += message("user", "该动作被策略拦截"); continue   # 高风险时在此停下等人工审批(HITL)
 
        verdict = run_hooks(H.hooks, "PreToolUse", action) # 【Hooks】执行前触发;PreToolUse 也能返回 deny 拦截
        if verdict == "deny":                              #   可见 Guardrail 与 Hooks 实为同一套闸的两种用法
            context += message("user", "被 Hook 拦截"); continue
 
        if action.type == "use_skill":
            instructions = H.skills.load(action.name)     # 【Skill 渐进式披露】命中才把 SKILL.md 全文读进上下文
            context += message("user", instructions)   # 载入的 SKILL.md 全文作为 user 消息进上下文(读入指令文本而非运行;脚本随后走 call_tool)
 
        elif action.type == "call_tool":                  # 区分:工具从哪来
            try:
                if action.tool in H.mcp:
                    result = H.mcp.call(action.tool, action.args)  # 【MCP】走协议(在外部执行,本地沙箱覆盖不到)
                else:
                    result = H.sandbox.run(H.tools[action.tool], action.args)  # 【Tool 原语】内建工具
            except ToolError as e:
                result = "工具失败:" + e.message           # 失败也是客观事实:错误回灌,模型据此改换路径重试
            context += message("user", result)   # 工具结果作为一条 user 消息回灌(assistant 说/做 ↔ user 返回结果,一来一回)
 
        elif action.type == "spawn_subagent":             # 【子 Agent / CE-Isolate】
            if depth >= MAX_DEPTH:                         #   用上 depth:再嵌一层就太深,直接拒绝,防递归过深 / fork 炸弹
                context += message("user", "子 agent 嵌套已达深度上限,拒绝派发"); continue
            child_H  = H.restrict(action.scope)           #   子 agent 通常拿“受限 harness”:别的提示词 / 工具子集 / 更小模型
            summary  = agent_loop(action.subtask, child_H, depth + 1)  #   开独立上下文递归自己,也可并行 fan-out 多个
            context += message("user", summary)   # 只把“摘要”作为一条 user 消息带回,不污染主上下文
 
        elif action.type == "take_note":
            H.memory.write(action.note)                   # 【CE-Write·循环内】大脑主动记笔记(scratchpad)
 
        run_hooks(H.hooks, "PostToolUse", action)         # 【Hooks】执行后触发
 
        if action.changed_code:                           # 【反馈循环】HE 的灵魂:让“机器护栏”
            report   = run_sensors(tests, lint, types, CI)#   告诉 agent 它做错没:测试/Lint/类型/CI
            context += message("user", report)   # 失败信息作为一条 user 消息回灌,agent 据此自我修正
 
    # ---------- ③ 收尾:循环退出后,跑且只跑一次 ----------
    # 触发时机 = done==True(任务完成)  或  steps==MAX_STEPS(预算耗尽)
    run_hooks(H.hooks, "SessionEnd", None)  # 【Hooks】会话结束事件:装配时注册,这里才触发
    H.memory.consolidate(context)       # 【CE-Write·会话末】把零散笔记固化成长期记忆
    H.tracer.flush()                    # 【可观测性·会话末】最终落盘
    return answer

工具调用包进 try/except:失败信息也回灌进上下文,失败同样是环境给的客观事实,模型据此换条路重试。
改了代码就自动跑 run_sensors(测试 / Lint / 类型 / CI),把结果回灌、据此自我修正。这是 Harness Engineering 的灵魂:让机器护栏告诉 agent 做错没。
至此完整 harness 成型,LLM 始终只占决策那一行,其余全是工程。这正是本页开头那句话的代码证明。

(名词解释部分省略)

执行流程 · 谁跑一次,谁每轮都跑
同一段代码,有的部分一次性执行,有的每轮循环都执行,有的等循环退出才执行一次。这张时间线把三种节 奏分清。

① 一次性
启动装配  build_agent()
跑在 while 之前,只跑一次。把 harness 的零件登记好:规则文件、Skill 名片、内建工具、MCP 连接、Hooks、Sandbox、Tracer。其中 Skill、MCP、Hooks、命令、子 agent 这类可分发的扩展,可整包来自一个 Plugin。

↓
② 每轮重复
while 主循环  while not done and steps < MAX_STEPS
每一轮 = 一次 LLM 决策 + 一次动作执行。下面这些步骤每轮都重新走一遍:

熵管理·压缩
列出功能菜单
LLM 任务决策(唯一一行)
决策入上下文
权 限守卫
分发:Skill / 工具 / 子Agent
Hooks 前后触发
记轨迹
反馈循环回灌
↓
退出条件 = done==True(任务完成) 或 steps==MAX_STEPS(预算耗尽)
③ 退出后一次
收尾  memory.consolidate() · tracer.flush()
循环退出后,跑且只跑一次:把循环内零散记下的笔记固化成长期记忆,把整条决策链最终落盘,返回答案。注意:这里的「记忆/落盘」各自还有一半发生在循环内 (即时记笔记、每轮记轨迹),收尾只是「会话末的固化」。

尾声 · 循环之上还有循环
本页的 while 循环叫 agent loop,但 2026 年中的热词 Loop Engineering(Addy Osmani 命名)说的不是它,而是循环之上的那一层:到目前为止,goal 仍是人给的,人守在屏幕前等它返回。Loop Engineering 把这最后一环也工程化——谁启动循环、谁验收结果、谁决定下一轮做什么。Claude Code 负责人 Boris Cherny 的表述是:「I don't prompt Claude anymore. I have loops running that prompt Claude and figuring out what to do. My job is to write loops.」一点提醒:这个词 2026 年 6 月才诞生,内涵与边界仍在快速演变,Osmani 本人也明说仍持保留态度——把它当作「正在成形的概念」,而非定论。

outer_loop.pseudo
# ---------- Loop Engineering:人退到循环之上 ----------
while True:
    goal   = find_work(backlog, issues, schedule)   # 系统自己找活:issue 队列 / 定时任务 / CI 事件,不再等人给 goal
    H      = build_agent(project)                   # 每个任务装配一次 harness:即本页 ① 启动装配
    answer = agent_loop(goal, H)                    # 本页讲的全部内容,在这里只占一行★ 整页 = 这一行
    verify_and_record(answer, external_state)       # 客观验收(测试 / CI),写回外部状态,决定下一轮
 
# ⚠ 注意:以上是教学用的极端简化版。真实的外层循环至少还需要:
#   ① 预算与停机守卫(内循环有 MAX_STEPS,外循环同样不能裸奔)   ② verify 连续失败 N 次后 escalate_to_human,升级给人
#   ③ 多 agent 并行时用 worktree 隔离工作区,防文件冲突   ④ goal 与进度写回外部状态(issue / STATE 文件):agent 会忘,repo 不会
Harness × Loop
两层分工,一个公式
Harness Engineering(本页全部内容)回答空间问题:任意一个瞬间,模型周围有什么——工具、沙箱、权限门控、反馈传感器、可观测性。它决定循环体内每一行「能做什么、被什么拦着」。
Loop Engineering(上面六行)回答时间问题:圈与圈之间如何演进——谁触发循环、用什么客观信号验收、何时停机、失败后是重试还是升级给人。它决定这些行「以什么控制流被反复执行」。注意别与本页的 agent loop 混为一谈:agent loop 是循环体本身,loop engineering 是循环之上的编排。
谱系:Prompt Engineering (2023) → Context Engineering (2025) → Harness Engineering (2026.2) → Loop Engineering (2026.6)。公式分两层写更稳:单次 Agent = Model × Harness;长驻 Agentic System = Agent + Outer Loop。本页开头那句「LLM 只占一行」在外层同构地再现:整个 agent_loop 也只占一行——你以为它是主程序,其实它是别人循环体里的一行。
大脑只做一行任务决策,其余全是工程。裸 LLM 是一块发烫的硅;harness 把它变成一台计算机;MCP 与 Plugin 再把这台计算机变成一个生态;而 loop engineering 让这台计算机自己开机干活。