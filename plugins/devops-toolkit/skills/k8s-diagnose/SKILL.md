---
name: k8s-diagnose
description: Deep health check of Kubernetes pods, events, restarts, and resource saturation.
---

# Kubernetes Cluster Diagnostics

Diagnostic inspection routine for failing pods and saturated nodes.

## Instructions
1. Check OOMKilled pods and recent CrashLoopBackOff restarts.
2. Query cluster events for scheduling warnings.
3. Validate node memory/CPU pressure.
