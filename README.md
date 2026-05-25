# 🚀 RAG-Cloud-Native-Practice (大模型 RAG 云原生工程化实践)

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-blue?logo=kubernetes)
![Terraform](https://img.shields.io/badge/Terraform-IaC-purple?logo=terraform)
![GitOps](https://img.shields.io/badge/GitOps-ArgoCD-orange?logo=argo)
![CI/CD](https://img.shields.io/badge/CI-GitHub_Actions-green?logo=github-actions)

## 📖 项目简介 (Overview)

本项目是一个面向云原生交付架构的工程化实践项目。
项目将基于本地运行的**大语言模型 RAG（检索增强生成）问答应用**，进行完整的微服务重构、容器化封装，并最终通过 **Terraform、GitHub Actions 与 ArgoCD** 实现基础设施即代码 (IaC) 与纯正的 **GitOps (拉模式) 自动化部署链路**。

> **💡 核心设计理念**：不局限于 AI 算法本身的开发，而是聚焦于 AI 应用从“本地脚本”到“生产级云原生应用”的完整工程化交付闭环。

---

## 🏗️ 架构设计与 GitOps 工作流 (Architecture & Workflow)

本项目严格遵循 GitOps 最佳实践，实现了从代码提交到集群状态同步的全自动化闭环。

```mermaid
sequenceDiagram
    participant Dev as 👨‍💻 开发者
    participant CodeRepo as 🐙 GitHub 源码仓库
    participant CI as ⚙️ GitHub Actions (CI)
    participant ACR as 📦 阿里云 ACR 镜像仓
    participant K8s as ☸️ Kubernetes 集群
    participant ArgoCD as 🐙 ArgoCD (CD)

    Dev->>CodeRepo: 1. Push App Code (app.py)
    CodeRepo->>CI: 2. 触发 CI 流水线
    CI->>ACR: 3. 构建 Docker 镜像并 Push
    CI->>CodeRepo: 4. 修改 K8s 部署清单中的 Image Tag
    ArgoCD-->>CodeRepo: 5. 监听配置状态漂移 (Watch)
    ArgoCD->>K8s: 6. 自动拉取新镜像并滚动更新 (Sync)
    K8s-->>Dev: 7. RAG 服务更新完成 🎉
