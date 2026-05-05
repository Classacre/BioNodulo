# Guidance for Future AI Coding Agents

- Preserve the Python-first architecture.
- Keep the MVP simple.
- Do not introduce Rust unless there is a very specific need.
- Do not build a full workflow DSL.
- Do not copy ComfyUI code directly.
- Keep node APIs stable.
- Add tests for schema and execution changes.
- Preserve mock mode.
- Prefer explicit, readable code over clever abstractions.
- Treat bioinformatics reproducibility as a core feature.
- Do not add AI image generation concepts such as diffusion models, checkpoints, CLIP, VAE, LoRA, samplers, schedulers, or prompt weighting.
- Real runs should record workflow JSON, commands, logs, inputs, outputs, executable paths where available, environment metadata, node statuses, and cache keys.
