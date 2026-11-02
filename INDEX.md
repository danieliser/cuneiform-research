# Cuneiform research workbench

Research specification requested by Daniel, 2026-11-02. Separate from the adjacent ancient-ai satire project.

- [SPEC-v0.2.md](SPEC-v0.2.md): authoritative integrated specification after review; preserves the symbol graph, multimodal and MCP roadmap with corrected linguistic layers and phased validation. No corpus ingested or performance result claimed.
- [Independent Claude Opus 5.5 high review](reviews/opus-5.5-high-review.md) and [parent disposition](reviews/disposition-v0.2.md).
- [SPEC-v0.1.md](SPEC-v0.1.md): frozen predecessor.
- [MULTIMODAL-MCP-ADDENDUM-v0.1.md](MULTIMODAL-MCP-ADDENDUM-v0.1.md): frozen user-directed extension, incorporated into v0.2.

Task clarification: the intended graph connects individual symbol occurrences, document positions, patterns, fragments, readings and translations. Historical people/events can be a later extension. Frequent sequence queries and traversable interpretation dependencies are central. This is task-specific scope, so no universal skill rule or memory update is justified.

## Implementation checkpoint — 2026-11-02

- [README](README.md): runnable in-memory CLI, exact commands, implemented and unverified capabilities.
- [Source ingestion design and rights ledger](docs/INGESTION-DESIGN.md): actual small eBL/CDLI samples; ORACC unresolved contract; no image work.
- [CHECKPOINT](CHECKPOINT.md): executed verification, blocked disk-backed checks and parent handoff.
- [Typed graph schema](cuneiform/schema.sql), [CLI](cuneiform/cli.py), and [tests](tests/): narrow Python/DuckDB foundation. Persistent Parquet/snapshot path implemented but not yet runtime-verified because the 3 GiB reserve is unavailable. Full SPEC-v0.2 research/MCP scope remains future work.
