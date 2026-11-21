# 深度登记 晶圆图谱复判台

- 规模为中型。
- 本台供封测厂良率工程师从来源探针图复核到标准晶圆图，按物理掩模、复测号、分档和四邻域生成证据。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 图档采信 | 逐档核查编码、重复档头与坏栏 | `GET /api/runs/{run_id}/intake` | `app/modules/intake/reader.py` `app/modules/intake/catalog.py` | `tests/test_intake.py` |
| M2 坐标对表 | 比较原点位和统一南缺口点位，按机台试算 | `GET /api/runs/{run_id}/coordinates/probe` | `app/modules/coordinates/transform.py` | `tests/test_coordinates.py` |
| M3 有效芯粒 | 从圆片阵列查看有效位、边缘及缺口 | `GET /api/runs/{run_id}/mask/{wafer}` | `app/modules/mask/geometry.py` `app/modules/mask/view.py` | `tests/test_mask.py` |
| M4 复测裁决 | 筛选裁决与测次冲突，定位原始证据 | `GET /api/runs/{run_id}/retest/{wafer}` | `app/modules/retest/measurements.py` `app/modules/retest/arbitrate.py` | `tests/test_retest.py` |
| M5 缺陷簇 | 检查四邻域成员、分档和原行 | `GET /api/runs/{run_id}/clusters/{wafer}` | `app/modules/clusters/components.py` | `tests/test_clusters.py` |
| M6 良率勾稽 | 核对坐标集合、实收和交接差值 | `GET /api/runs/{run_id}/yield` | `app/modules/yield_audit/compare.py` | `tests/test_yield.py` |
| M7 图批复盘 | 原子运行、按归档重算、核验后导出 | `POST /api/runs` `POST /api/runs/{run_id}/rerun` `GET /api/runs/{run_id}/export` | `app/modules/runs/pipeline.py` `app/modules/runs/service.py` `app/modules/runs/bundle.py` `app/store.py` | `tests/test_runs.py` |

## 陷阱登记

| TRAP | 现象与样例 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | `probe-b.csv` 为 GB18030 | 中文栏名乱码 | 回退解码保留中文值 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_gb_source_decodes_chinese_values` |
| TRAP-02 | `probe-a.csv` 含 UTF-8 BOM | 首列不可查 | 去 BOM 后比较档头 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_bom_source_preserves_wafer_column` |
| TRAP-03 | `probe-a.csv` 混用 CRLF/LF 且备注跨行 | 一条记录拆成两条 | 按 CSV 逻辑行解析并记物理范围 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_multiline_evidence_has_physical_span` |
| TRAP-04 | `probe-a.csv` 和 `probe-b.csv` 重复档头 | 把档头计为芯粒 | 档头独立记账并增加段数 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_segment_headers_advance_reordered_contract` |
| TRAP-05 | `probe-a.csv` 末行多一栏 | 静默丢栏 | 全行隔离并保留多栏 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_width_mismatch_retains_all_raw_fields` |
| TRAP-06 | `probe-b.csv` 测次和档位为全角数字 | 剔除真实复测 | NFKC 后读取整数 | `app/modules/retest/measurements.py` | `tests/test_retest.py::test_valid_second_measurement_overrides_failure_and_normalizes_width` |
| TRAP-07 | `probe-b.csv` 末次记 `N/A` | 用空值抹去旧判定 | 隔离空值，使用已取得的测次 | `app/modules/retest/measurements.py` | `tests/test_retest.py::test_missing_later_value_does_not_override_prior_failure` |
| TRAP-14 | `(3,3)` 同次反向判定 | 后写覆盖或回退旧通过 | 双方隔离，新测次记冲突 | `app/modules/retest/arbitrate.py` | `tests/test_retest.py::test_same_attempt_conflict_does_not_fall_back_to_earlier_pass` |
| TRAP-16 | `truncated.json` 第二档末尾被截去完整逻辑行 | 错把半批当全批 | 实收和声明不符拒绝发布 | `app/modules/intake/reader.py` `app/modules/runs/service.py` | `tests/test_intake.py::test_complete_looking_truncation_fails_manifest_count` `tests/test_runs.py::test_truncated_second_source_leaves_previous_snapshot_untouched` |
| TRAP-17 | `probe-b.csv` 中文栏名且第二段换序 | 错对 X/Y 或分档 | 映射别名并按段绑定字段 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_segment_headers_advance_reordered_contract` |
| TRAP-18 | 空文件、空行与仅档头的构造输入 | 产生零行成功批次 | 三态分别返回错误码 | `app/modules/intake/reader.py` | `tests/test_intake.py::test_empty_header_and_blank_are_separate` |
| TRAP-19 | `(0,1)` 多测次，2 号在 10 号之后到达 | 误选最后行或字典序最大值 | 取最大有效测次号 | `app/modules/retest/arbitrate.py` | `tests/test_retest.py::test_numeric_attempt_precedence_ignores_arrival_order` |

补充反例包括经过 X 反射后重新推导缺口转角、圆形边缘等式包含、对角缺陷分簇、恢复点断开原失效带、平移阵列漏位以及同键并发只提交一次。

## 对账不变量

- 有效位集合与裁决键集合相等，有效数守恒到四类最终状态。
- 实收行按五类互斥归档，声明的逻辑数据量可独立回推。
- 对外提供一份证据包，同一规则版本下输入相同时运行号与结果摘要一致。
