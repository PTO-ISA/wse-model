# 0007. WSE 白皮书采用 SuperscalarNPU 核

- **Status**: accepted for whitepaper direction; interface details proposed
- **Date**: 2026-11-05
- **Scope**: 白皮书 v0.2；不改变 Python/ACIR 模型、ISA 编码或 golden vectors

## Context

需求方明确要求将白皮书中的旧核设计替换为本机 SuperScalarModel 所描述的新核，
并确认“SoC 叫 WSE，核叫 SuperscalarNPU”，尽量保留原 WSE 数值作为新核目标配置。
此指令明确授权修改原设计文档，构成此次对通常只读设计源规则的限定例外。

## Decision

1. 核内职责改为 SMT、SPE、VEC、CUBE、TMU、MEM、GPE；TLSU 属于 MEM。
2. 保留 1.4 GHz、FP16/8/4 聚合吞吐、256 B/cycle 向量目标、五项存储预算和
   每核 local DRAM 配置。目标不等于 SSM 默认配置或已测性能，不乘内部 PE 数。
3. 旧 L0/L1/UB 容量保留为预算用途，不把它们强行对应 Local/Shared Tile。
4. 跨核通信保留 Calendar 的路由、时隙与字节守恒结构；旧 MTE/CCE/PIPE 绑定
   由显式标为提案的发送、接收登记、排空和完成语义替代。具体机器编码未定义。
5. WSE 私有 local DRAM 与 SSM 统一 GM/一致性合同的差异必须形成目标 profile，
   不能默认兼容。新增 Q13–Q16 记录内存、通信、启动和核资源的待定项。
6. MEM.TLSU 增加 router 发送/控制接口，Shared memory owner 增加 router 接收写端口；
   TMU 保持代际和发布所有权。先登记并预留资源再对齐；信用流控不能替代时隙服务证明。
7. 外部协同角色泛称“主计算设备”；没有据此选择外部设备的新硬件实现。

## Consequences

白皮书采用真实元素字节数重算理想满利用率 batch 阈值：12/23/23。
旧 6/23/46 及 decision 0006 继续描述现有模型的历史口径；此次不改其测试。

`docs/design/wse-calendar-scheme.md` 保持原文。其旧核接口不能作为 v0.2 的新核
指令证据。代码的迁移、Q13–Q16 的可执行注册与测试、编译器和运行时接入留给后续
实现任务；不能用本次设计源摘要检查宣称模型已符合新白皮书。

本次按用户要求不运行仿真。校验限于文档一致性、来源摘要、严格文档构建与 diff。

## Sources

来源为 SuperScalarModel 的工作区而非完整冻结提交：
[来源路径和 SHA-256 摘要](0007-superscalarnpu-sources.json)。该仓库 HEAD 为
`b45ceca2cf26204574a94e732fda05a329163fff`，相关 NDF 含 draft 条款。
来源摘要用于后续核对，不把工作区内容包装为已验收架构。

修订正文：[WSE 系统架构设计白皮书 v0.2](../design/wse-system-architecture-whitepaper.md)。
