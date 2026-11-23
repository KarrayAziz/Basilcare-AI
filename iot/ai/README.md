# AI components

- [model](model/README.md): training, export and evaluation of the on-device leaf model.
- [service](service/README.md): cited CLI assistant, local Ollama adapter and initial
  traces/evaluation; API/PWA and MCP integrations are pending.

These components are grouped under IoT. Training still runs on a laptop or training
machine; only inference runs on the Raspberry Pi. Moving the files does not add a
deployed AI service. The assistant currently runs separately through explicit CLI commands.
