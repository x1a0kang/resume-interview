# MODULAR-RAG-MCP-SERVER：PDF、Chunk、向量与入库源码核查

核查日期：2026-10-14。范围是本地源码与仓库默认配置；没有调用外部模型、下载模型、执行云服务，也没有把 fixture 或 mock 当成真实教材质量验证。本报告不修改参考项目。仓库及其在 `D:/project` 下的父目录未发现适用的 `AGENTS.md`。

## 1. 真实执行链路

```text
scripts/ingest.py --path <PDF或目录> --collection <集合>
→ IngestionPipeline(settings, collection, force)
→ SQLiteIntegrityChecker：计算 PDF 文件 SHA256，已成功文件跳过
→ PdfLoader：MarkItDown.convert(PDF) → Document.text
             PyMuPDF 提取内嵌图片，落盘并追加 [IMAGE: id]
→ DocumentChunker → RecursiveCharacterTextSplitter：字符递归分块
→ ChunkRefiner：规则清洗；可选 LLM 改善文字
→ MetadataEnricher：规则或 LLM 生成标题、摘要、tags
→ ImageCaptioner：Vision LLM 生成引用图片的文字描述，写回 Chunk.text
→ BatchProcessor：DenseEncoder（文本 embedding）+ SparseEncoder（分词、词频）
→ VectorUpserter：Chunk 文字、向量、元数据写 Chroma
→ BM25Indexer：词频建立倒排索引，JSON 落盘
→ ImageStorage：已落盘图片注册到 SQLite 图片索引
→ ingestion_history.db 标记 success
```

源码入口：[文件发现与 PDF 限定](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/scripts/ingest.py:104)、[组件构建](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/pipeline.py:137)、[六阶段 run](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/pipeline.py:229)。CLI 默认集合是 `default`，而 YAML 的 `collection_name` 是 `knowledge_hub`；入库传入 collection 后覆盖向量库集合名，不能把两个默认值视为同一个集合。

这个链路全部是 Python。Java 不在此仓库的实际入库实现中。它没有 ES、VikingDB、Milvus、MySQL、Redis、消息队列或远程对象存储参与这条链路。

## 2. 模型和配置：默认值与真实能力

| 位置 | 仓库默认配置 | 实际用途 | 状态 |
| --- | --- | --- | --- |
| `llm` | `provider=openai`, `gpt-4o`, temperature 0, max_tokens 4096 | Chunk 文本清理、元数据生成 | 默认两个 Transform 的 `use_llm=true`；失败降级 |
| `embedding` | `provider=openai`, `text-embedding-ada-002`, dimensions 1536 | 整理后 Chunk.text 的文本向量 | 真实 API 调用代码存在；凭据是占位符 |
| `vision_llm` | enabled true，`gpt-4o`，图片最长边上限 2048 | 给图生成文字描述 | 真实 vision 请求代码存在；可禁用/失败跳过 |
| splitter | recursive，1000/200 | 按字符递归切分与重叠 | 唯一已注册的内置 splitter |

配置来源：[模型配置](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/settings.yaml:8)、[入库参数](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/settings.yaml:98)。这只是仓库模板，不能表述为作者已在真实环境稳定运行这些模型。

**配置中的 Azure 字段影响实际请求地址。**默认 `provider=openai` 同时保留 `https://YOUR_ENDPOINT.openai.azure.com/`，OpenAI 的实现检测到 `azure_endpoint` 就自动拼 Azure deployment URL 和 `api-key` 鉴权。因此 provider 字符串并不能证明请求发到 OpenAI 公网；要修正/删除对应 Azure 配置或选择匹配的 endpoint。凭据的配置值优先于环境变量，`YOUR_API_KEY_HERE` 不是空值，不会自动被环境变量替换。[Embedding endpoint 选择](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/openai_embedding.py:68)、[文本 LLM endpoint](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/openai_llm.py:80)、[Vision endpoint](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/openai_vision_llm.py:109)。

可选扩展的边界：

- 文本 LLM 实现/注册了 OpenAI、Azure、DeepSeek、Ollama。[注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/__init__.py:22)
- Embedding 实现/注册了 OpenAI、Azure、Ollama；OpenAI 接口支持 `text-embedding-3-*` 的可选 dimensions。ada-002 不发送 dimensions 参数。Ollama 示例的 nomic/mxbai 是可配置模型，并非默认已下载模型。[注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/embedding_factory.py:112)、[dimensions 参数](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/openai_embedding.py:147)、[Ollama 请求](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/ollama_embedding.py:120)
- Vision 内置注册只有 OpenAI、Azure；YAML 注释出现的 Ollama/llava 在 Vision factory 中没有对应内置实现，不能只改 YAML 就获得该能力。[Vision 注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/llm_factory.py:22)
- splitter YAML 注释写 semantic、fixed_length，源码只注册 recursive；它们属于扩展意图。[Splitter 注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/splitter/splitter_factory.py:18)
- 向量库 YAML 注释写 qdrant/pinecone，源码只内置 Chroma；换数据库还要写 adapter 并注册。[Vector Store 注册](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/__init__.py:12)

## 3. PDF 实际怎么处理

`PdfLoader` 初始化普通 `MarkItDown()`，`load()` 直接 `convert(str(path))`，取得 `result.text_content`。项目把这个字段视为 Markdown，但没有读取 PDF 的书签目录、字号层级、段落坐标、页面阅读顺序，也没有建立 Block 或章节树。[初始化与 convert](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:69)

文档元数据实际只有 `source_path`、`doc_type=pdf`、`doc_hash`，加可选 title/images。title 只是查前 20 行的 `# `，找不到就用前 10 行中首个非空行。`Document` 类型注释虽然列出 page_count 等字段，Loader 并没有填充这些字段。[元数据与标题](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:110)

**没有专门 OCR 流程。**源码和依赖未提供扫描页检测、页面渲染、OCR engine 或扫描件分支。不能把其 MarkItDown 接入描述成“成熟扫描教材 OCR”。扫描件中的页面位图若恰好作为内嵌图片被提取，后续 Vision caption 可能读取其中部分文字，但这是图像摘要，不保证完整转录、定位、公式正确性或段落顺序。[PDF 加载入口](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:79)、[图片 caption prompt](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/prompts/image_captioning.txt:3)

**表格与公式没有专门处理器。**它们最终是否可读，取决于 MarkItDown 对该 PDF 输出的文本；项目没有表格单元格结构、跨页表合并、表头补全、LaTeX 公式恢复、公式校验或表格整体分块规则。若表格/公式是位图，可走图片 caption；若几何图由 PDF 矢量线条绘制，`get_images()` 并不等同于整页渲染，代码不会自动把这类图裁出。

PDF 文字解析失败抛 RuntimeError，整个 run 失败。PyMuPDF 不存在或图片提取失败则警告，继续纯文本；单个图片失败也继续下一张。[解析失败](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:102)、[图片降级](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:200)

## 4. 图片是提取的，但当前文字关联很简化

实际流程用 `fitz.open()` → 每页 `page.get_images(full=True)` → `doc.extract_image(xref)`；保存原始提取格式，图片 ID 是 `file_hash[:8]_page_sequence`。图片元数据有页号、宽高、顺序、路径。[图片提取](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:216)

重要实现差异：注释称“追加到当前页面内容末尾”，实际 `insert_position=len(modified_text)` 后 `modified_text += placeholder`，即所有图片占位符最终依次追加到整篇文本末尾。没有把图嵌回原段落、题干或表格附近，position 也只有宽高、页号和图片序号，没有 bbox。因此后续图片 caption 可以单独被召回，但图与正文的教学关联很可能丢失；不适合直接照搬到教材例题入库。[占位符实际位置](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/pdf_loader.py:250)

Chunker 按 Chunk.text 中 `[IMAGE: ...]` 找 image_refs，只给该 Chunk 附这些图片的完整元数据。这条真实联系存在，但依赖前面占位符位置正确。page_num 仅取第一张引用图片的页号，普通文字 Chunk 无可靠页号；start_offset/end_offset 类型字段存在但构造 Chunk 时未填，不能据此恢复精确页面来源。[引用关联](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/chunking/document_chunker.py:210)

## 5. 切分：规则完成边界，LLM 在切完后清理

`RecursiveCharacterTextSplitter` 配置 `length_function=len`、chunk_size=1000、chunk_overlap=200。这里是 **字符数**，不是 token 数。分隔符依次为双换行、换行、英文 `. ! ? ; ,` 加空格、空格、最终单字符；没有专门中文句号/问号分隔符。[分隔符](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/splitter/recursive_splitter.py:42)、[实例参数](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/splitter/recursive_splitter.py:109)

源码注释称 Markdown aware，但它使用普通 RecursiveCharacterTextSplitter 和上面分隔符，没有 MarkdownHeaderTextSplitter、标题识别或代码围栏保护。因此不保证“定义+条件”“例题+图+解法”完整，也不保证表格不被截断。

DocumentChunker 给每个片段生成 `doc_id_index_SHA256(text)[:8]`，继承元数据，附 chunk_index/source_ref。`source_ref` 是回到整份 Document 的来源引用，并非章节层级中父 Chunk 的 ID。本项目没有 ParentDocumentRetriever、parent_splitter/child_splitter、父文本存储或逐级扩展调用。[切分和构造](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/chunking/document_chunker.py:113)、[ID 和 source_ref](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/chunking/document_chunker.py:165)

切完后才执行 ChunkRefiner；它不会重做分块、合并相邻 Chunk 或修复章/节层级。规则清除部分页眉页脚模式、HTML 标签/注释、多余空白并保护代码块；可选 LLM 用每个 Chunk 的全文生成清理后文字，默认最多 5 个线程同时调用。成功文本直接替换 Chunk.text，空输出/异常退回规则文本。[规则清洗](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/chunk_refiner.py:275)、[LLM 调用](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/chunk_refiner.py:346)

Refiner prompt 要求不增添事实、保留 image placeholders、输出纯文本，但代码只验证结果非空，没有程序化检查删字、改公式、丢占位符，也没有单独保留可检索的 `raw_text` 字段。因此教材场景应补原文与清理后文本的双份保存和校验。[Refiner prompt](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/config/prompts/chunk_refinement.txt:3)、[替换策略](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/chunk_refiner.py:114)

## 6. 三种 Transform 的 LLM 成本与检索作用

MetadataEnricher 先做规则标题/前句摘要/关键词，再可选 LLM。LLM 输入最多前 2000 字符，输出格式是 `Title/Summary/Tags`，正则解析，写入 Chunk.metadata；没有把生成摘要或标签拼入 DenseEncoder 的文本。因此这些字段可用于展示/过滤，但不能直接宣称它们提高了文本向量里的主题覆盖。[元数据生成](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/metadata_enricher.py:111)、[LLM 截断](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/metadata_enricher.py:452)

ImageCaptioner 是真实使用：扫描 Chunk 的引用图片 → 每张唯一图调用一次 `chat_with_image(prompt, ImageInput(path))` → 把占位符替换为占位符加 `(Description: caption)`，同时保存 image_captions。线程上限 3。cache 是当前 transform 内存缓存，每次处理新文档会清空，不是跨文档持久缓存。[caption 调用](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/image_captioner.py:91)、[缓存与写回](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/transform/image_captioner.py:163)

Vision 客户端把图片压缩到最长边最多 2048，保留纵横比，用 Base64 传多模态 chat/completions，HTTP timeout 60 秒；图片不在磁盘或 API 失败则该图没有描述，原有 Chunk 继续。[压缩](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/openai_vision_llm.py:270)、[HTTP 调用](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/llm/openai_vision_llm.py:308)

若有 C 个 Chunk、I 张引用且成功读取的唯一图片，默认 Transform 大致需要 `2C + I` 次生成式模型调用：每 Chunk 一次 Refiner、一次 Enricher，每图一次 caption。另有 embedding 批量 API 调用。这是由源码调用粒度推导，实际因禁用、初始化失败、请求失败而变化。教学原文应先考虑规则清理是否已足够，再决定两个文本 Transform 是否必须启用。

## 7. Dense、Sparse 与保存位置

DenseEncoder 只取 `[chunk.text for chunk in chunks]`，因此图像描述会进入文本向量，图像二进制不会进入 embedding。批量大小 100，按序调用 provider 并检查向量数量与本次 encode 内维度一致；没有多模态 embedding 模型，也没有图片向量集合。[DenseEncoder](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/embedding/dense_encoder.py:102)

ada-002 的 1536 是模型的固定维度，Chunk 长度不会改变维度；配置中的 dimensions 在 ada 情况下不发给 API。`get_dimension()` 能读取配置，但 DenseEncoder 主要验证返回向量相互一致，不能把配置注释当成全链路强制维度校验。[请求参数与维度](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/embedding/openai_embedding.py:152)

SparseEncoder 不是另一个神经模型：用 jieba.lcut 中英文分词，去掉纯符号/空白、转小写、保留至少 2 字符的词，用 Counter 统计词频和词数。没有默认停用词表。类头部旧注释称 whitespace tokenization，但实际方法已改为 jieba。[实际 tokenize](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/embedding/sparse_encoder.py:134)

BM25 是项目自写倒排索引和评分，非 ES，也不是稀疏向量数据库：默认 k1=1.5，b=0.75；IDF 为 `log((N-df+0.5)/(df+0.5))`，没有常见的 `+1`，高频词可以负分。每条 posting 存 chunk_id/tf/doc_length，collection 保存总 Chunk 数和平均长度。`add_documents` 重建全索引；小规模演示方便，大规模增量成本会高。[参数](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:71)、[公式](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:436)、[增量合并](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:311)

| 保存内容 | 默认路径/实现 | 说明 |
| --- | --- | --- |
| 向量+清理后 Chunk.text+metadata | `data/db/chroma/`，Chroma PersistentClient | collection 设置 `hnsw:space=cosine`；text 同时在 documents 和 metadata.text |
| BM25 倒排索引 | `data/db/bm25/{collection}/{collection}_bm25.json` | 本地 JSON，无 ES 服务 |
| 原图 | `data/images/{collection}/{完整file_hash}/{image_id}.{原扩展名}` | PdfLoader 直接写文件 |
| 图片路径/页号/collection/doc_hash | `data/db/image_index.db`，SQLite WAL | 图二进制不在向量库 |
| 文件入库状态 | `data/db/ingestion_history.db`，SQLite WAL | 按 PDF SHA256 记录 success/failed |
| 原 PDF | 保留调用方 source_path 引用 | CLI 入库没有复制 PDF 至对象存储或统一归档目录 |

来源：[Pipeline 路径](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/pipeline.py:140)、[Chroma 初始化](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:95)、[Chroma 写入](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:163)、[图片 SQLite schema](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/image_storage.py:96)。Pipeline trace 中曾写 `ImageStorage (JSON index)`，实际是 SQLite，应以实现为准。

复杂 metadata（list/dict）在 Chroma adapter 中被转成逗号拼接字符串/`str()`，不是保留 JSON 类型的结构字段。image_refs 的简单 ID 列表可恢复，但 image_captions/images 这样的嵌套数据不是规范序列化。[metadata sanitize](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:380)

图片命中后如何返回：MCP 的 multimodal assembler 已实现读取原图、Base64 编码为 ImageContent，和 TextContent 一并交给客户端；最终回答模型由外部 MCP 客户端决定。需要模型真正看图时客户端仍须支持视觉输入。此能力来自图片引用回读，不是图像 embedding；默认入库→Chroma→图片回传链路还有下述整合缺口，不能声称端到端已通。[ImageContent 组装](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/multimodal_assembler.py:256)、[查询工具返回](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/query_knowledge_hub.py:451)

**默认图片回传可能丢图。**Chroma 的 `_sanitize_metadata` 把 images/image_captions 的 list[dict] 转为逗号拼接的 Python `str(dict)`，不是规范 JSON；query/get_by_ids 原样返回这些字符串，未见反序列化。Assembler 要求 images 是 list，captions 是 dict，因此前者不会被识别，后者即便存储前还是 list[dict] 也不符合接口。Assembler 可从 `[IMAGE: id]` fallback 取 ID，但 `QueryKnowledgeHubTool` 默认 `ResponseBuilder()` 的 lazy assembler 不注入 ImageStorage，只能按 `data/images/{collection}/{id}.png` 等约定路径找图，而 PdfLoader 实际保存多了 `{doc_hash}` 子目录。应在读取时恢复结构并统一 caption 契约，或者向 assembler 注入 SQLite ImageStorage。图片描述已经写入 Chunk.text，仍可以文本召回，但原图返回不应据此保证。[字符串透传](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/vector_store/chroma_store.py:255)、[Assembler 类型与路径判断](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/multimodal_assembler.py:180)、[默认 builder](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/tools/query_knowledge_hub.py:122)、[默认 assembler](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/core/response/response_builder.py:145)

## 8. 增量、幂等与失败路径：静态源码发现的缺口

以下是源码调用关系推导，未进行真实云模型/全链路运行复现，不能表述为已验证生产故障。

1. **跨 collection 的 SHA256 跳过不隔离。**SQLite primary key 和 should_skip 仅用 file_hash。相同 PDF 先入集合 A，随后入集合 B 可能直接跳过，必须 force 才会处理。[schema](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/file_integrity.py:184)、[skip](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/libs/loader/file_integrity.py:243)
2. **两套 Chunk ID 导致 BM25 重入/删除前缀错配。**Chunker 生成 `doc_<hash>_<index>_<hash>`，VectorUpserter 改用 `SHA256(source_path)[:8]_<index>_<SHA256(final_text)[:8]>`。Pipeline 将 BM25 chunk_id 对齐到 vector_id，却把 `document.id` 当 doc_id 传入 add_documents；后者用 `startswith(doc_id)` 清旧 postings，前缀不匹配。force 重入会合并重复或陈旧 postings；DocumentManager.delete_document 传完整 file_hash 删除 BM25，仍不匹配向量 ID。建议 BM25 存独立 doc_id/source_ref 并按该字段删除。[向量 ID](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/vector_upserter.py:158)、[对齐和 add_documents](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/pipeline.py:441)、[startswith 删除](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:390)、[文档删除](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/document_manager.py:238)
3. **全文变更不自动清旧版本。**file_hash 改变会重新处理；final_text/位置变动产生不同 vector_id，但入库只有 upsert 没有删除原文档旧 IDs。LLM 清理输出即便同 PDF force 重跑也可能不同；旧记录有残留风险。[upsert](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/vector_upserter.py:109)
4. **失败批次并没有完全正确恢复。**BatchProcessor 捕获 batch 异常后继续，只返回成功向量/词频，没有返回与其对应的成功 chunks。Pipeline 仍将原全量 chunks 交给 upserter，其长度检查会失败；Sparse 在 Dense append 后失败还可能造成两路长度不一致。DenseEncoder 类注释写 individual failures 不 crash，但方法本身 re-raise。[batch 执行](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/embedding/batch_processor.py:150)、[长度校验](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/vector_upserter.py:100)
5. **多存储没有事务/回滚。**先写 Chroma，再 BM25，再图片 SQLite，最后标成功；中途失败可能留下部分可查记录。没有 staging collection、版本发布指针、清理补偿或任务队列。[存储顺序](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/pipeline.py:435)
6. **计算哈希之前失败有异常处理问题。**如果 compute_sha256 抛异常，except 中仍直接用尚未定义的 file_hash 调 mark_failed，会掩盖原异常。[run except](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/pipeline.py:542)
7. **BM25 remove_document 平均长度计算重复计数。**遍历每个词的每条 posting 加 doc_length，会对含多个词的同一 Chunk 重复加；之后除 unique Chunk 数得到错误平均长度，影响删除后的 BM25 分数。[统计重算](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/ingestion/storage/bm25_indexer.py:408)

## 9. 与 HP 教材设计的对照

| 前面讨论的能力 | 本项目状态 | 教材应用要补的内容 |
| --- | --- | --- |
| PDF 文字直接读取 | 实现 | 抽样检查阅读顺序/公式/版式 |
| 扫描 PDF OCR | 没有专门实现 | 按页检测文字质量，OCR/版面解析分支 |
| 图片提取与文本描述 | 实现 | bbox、所属例题/段落关联、矢量图裁图、描述质量校验 |
| 表格结构化、公式保真 | 无专门实现 | 单元格/表头/跨页关联、公式转录及校验 |
| 用代码切 Chunk | 实现 | 从通用 1000 字符改为教学单元边界 |
| LLM 切分 | 未采用 | 此处 LLM 是切完后清理，不能混淆 |
| 多层章节/父子 Chunk | 未实现 | 章节树、parent_id、兄弟/父层按需读取 |
| 文本 Dense embedding | 实现 | 接豆包等 provider、同模型同维度并管理版本 |
| 图片多模态 embedding | 未实现 | 先评估实际需求，不把 caption embedding 当图片向量 |
| Chroma 原文+向量一起存 | 实现 | 与 HP MySQL 原文+ES/VikingDB 索引可以用相同 chunk_id 关联 |
| 云端生产入库管理 | 本地 CLI/轻量实现 | 版本发布、幂等、回滚、教材权限和增量一致性 |

本项目值得学习的是接口分层和可替换组件、清晰流水线、文字/图描述共同检索、Dense/BM25 两路准备、图片回传以及 trace。教材解析质量、教学分块、父子上下文和生产数据一致性需要继续设计，不能从“modular”或 README 功能列表推断已覆盖。

## 10. 验证边界与阅读顺序

只做了静态源码追踪；未调用模型或执行云 API。现有 PDF 集成测试使用 simple.pdf 和 with_images.pdf，主要检查 text 非空、hash、metadata 字段；图片测试第 70 行还保留“stub”旧注释且不要求提取到真实图片。这些断言不证明中文教材、扫描件、公式、表格和章节结构质量。[PDF 集成测试](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/tests/integration/test_pdf_loader_integration.py:55)

建议学习顺序：先 pipeline.py 看到总体阶段，再 PdfLoader → DocumentChunker/RecursiveSplitter → 三种 Transform → DenseEncoder/SparseEncoder → VectorUpserter/BM25Indexer/ImageStorage。实际演示前先关闭两个文本 LLM Transform 和 Vision，以容易检查的文本 PDF 验证规则链路；之后再逐个启用，比较内容、调用成本和检索效果。与 HP 方案对照时要始终区分模板默认、可配置组件、真实调用和仅注释中的扩展选项。

启动入口也有区别：根 `main.py` 仅加载配置并输出“Phase E 待实现”，随后退出；`pyproject.toml` 的 `mcp-server = main:main` 指向这个旧入口。真正 stdio 服务在 `src/mcp_server/server.py`，其 `main()` 调 run_stdio_server 并进入 official MCP SDK 的 stdio 生命周期。阅读和启动应以这个模块为准，不能以根 main.py 推断整个仓库未实现 MCP。[旧入口](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/main.py:16)、[真实 stdio 服务](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/src/mcp_server/server.py:82)、[console script](/D:/project/rag-github/MODULAR-RAG-MCP-SERVER/pyproject.toml:49)
