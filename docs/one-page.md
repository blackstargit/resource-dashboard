# AI Resource Monitoring Dashboard

*Your machine's vitals, live, in one screen.*

---

## What It Is

A real-time dashboard that watches your computer's health — CPU, RAM, disk, and GPU — and shows it to you the instant it changes. No refreshing, no digging through terminal commands, no guessing why your machine feels slow. Just open the page and watch it breathe.

![Dashboard screenshot](./docs/screenshot.png)

---

## Why It's Cool

- **It's alive.** Stats stream to your browser in real time — the graphs move as your system works, not on a 30-second delay.
- **Sees everything.** CPU (overall and per-core), memory pressure, disk space, GPU load, VRAM, and temperature — one screen, zero blind spots.
- **Not just watching, acting.** Sort the process list by CPU, memory, or GPU usage, spot the runaway one, and kill it right from the dashboard — no terminal needed.
- **Knows what's using the GPU.** Every process's video memory usage is tied back to the process itself, so "what's eating my VRAM" is a glance, not a mystery.
- **Watches itself too.** The dashboard reports its own CPU and memory footprint, plus system uptime and battery — so it's honest about the cost of watching.
- **Built for AI workloads.** GPU tracking makes it a natural fit for watching training runs and inference jobs chew through hardware.
- **Runs anywhere.** One Docker command and it's up — Linux or Windows, with or without an NVIDIA GPU.
- **Lightweight by design.** A single, self-contained service: no separate frontend server, no complicated setup, no bloat.

---

## How It Works (Plain English)

A small Python service constantly checks in on the machine's vital signs and pushes updates straight to a clean, modern web dashboard — the same technology news sites use to push live scores without you hitting refresh. Point it at any machine, and it becomes a live health monitor for that computer.

---

## Under the Hood *(for the curious)*

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · Server-Sent Events |
| Frontend | React |
| Metrics | CPU (+per-core), RAM, Disk, GPU (load/VRAM/temp), Processes |
| Controls | Sort, filter, and kill processes from the UI |
| Deployment | Docker, single container, one port |

---

*One dashboard. Every resource. Zero guesswork.*
