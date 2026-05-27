# RAG-Cloud-Native-Practice (大模型 RAG 云原生高阶架构实践)

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Microservice-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![Kubernetes](https://img.shields.io/badge/Kubernetes-Ready-blue?logo=kubernetes)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Database-orange)
![Prometheus](https://img.shields.io/badge/Prometheus-Observability-e6522c?logo=prometheus)
![Grafana](https://img.shields.io/badge/Grafana-Dashboard-F46800?logo=grafana)
![Terraform](https://img.shields.io/badge/Terraform-IaC-purple?logo=terraform)
![GitOps](https://img.shields.io/badge/GitOps-ArgoCD-orange?logo=argo)
![CI/CD](https://img.shields.io/badge/CI-GitHub_Actions-green?logo=github-actions)

## 项目简介 (Overview)

本项目是一个面向生产级交付标准的大模型 RAG（Retrieval-Augmented Generation，检索增强生成）云原生工程化实践项目。

项目从一个本地运行的 RAG 脚本起步，逐步完成容器化、微服务拆分、CI/CD 自动化、GitOps 持续交付、Ingress 七层流量治理、Prometheus + Grafana 可观测性建设，以及 ChromaDB 向量数据库持久化改造，最终构建出一个基于 Kubernetes 的企业级 AI 应用交付体系。

> 核心设计理念：跨越 AI Demo 与生产级 AI 应用之间的工程鸿沟，重点解决 AI 应用在云原生环境中的交付、伸缩、观测、持久化和自动化运维问题。

---

## 系统拓扑架构 (Architecture Topology)

本项目在 Kubernetes 中实现了计算与存储分离、前后端解耦、七层流量接入以及全链路可观测。

```mermaid
flowchart LR
    Client["User Browser"]
    Ingress["Nginx Ingress Controller"]
    UI["Frontend Pod - Gradio UI"]
    API["Backend Pod - FastAPI API"]
    ChromaDB["ChromaDB Vector Database"]
    PVC["PersistentVolumeClaim"]
    LLM["Aliyun DashScope LLM"]
    Prometheus["Prometheus ServiceMonitor"]
    Grafana["Grafana Dashboard"]

    Client --> Ingress
    Ingress --> UI
    UI --> API
    API --> ChromaDB
    ChromaDB --> PVC
    API --> LLM
    Prometheus --> API
    Grafana --> Prometheus
```

---

## 云原生交付链路 (Cloud Native Delivery Workflow)

项目采用双仓 GitOps 架构，将业务代码仓与 Kubernetes 配置仓彻底解耦。

```mermaid
flowchart LR
    Dev["Developer Push Code"]
    CI["GitHub Actions"]
    Scan["Trivy Security Scan"]
    ACR["Aliyun ACR"]
    GitOps["GitOps Config Repo"]
    ArgoCD["ArgoCD"]
    K8s["Kubernetes Cluster"]
    Pod["RAG Service Pods"]

    Dev --> CI
    CI --> Scan
    Scan --> ACR
    CI --> GitOps
    GitOps --> ArgoCD
    ArgoCD --> K8s
    K8s --> Pod
```

交付流程如下：

1. 开发者向业务代码仓库 Push 代码。
2. GitHub Actions 自动触发 CI 流水线。
3. CI 执行 Docker 镜像构建。
4. Trivy 对镜像进行安全扫描，实现安全左移。
5. 扫描通过后，将镜像推送至阿里云 ACR。
6. CI 自动修改 GitOps 配置仓库中的镜像 Tag。
7. ArgoCD 监听 GitOps 仓库变更。
8. ArgoCD 将期望状态同步到 Kubernetes 集群。
9. Kubernetes 执行滚动更新，完成服务发布。

---

## 核心工程化演进 (Key Engineering Highlights)

本项目经历了三次重大架构演进，实现了从本地 AI Demo 到云原生 AI 应用的完整升级。

### V1.0: 基础设施即代码 (IaC) 与 CI/CD 飞轮

- **Terraform 自动化编排**：抛弃手工点击控制台，使用 `main.tf` 声明式管理底层云资源。
- **Docker 容器化改造**：将本地 RAG 应用封装为标准容器镜像，实现环境一致性和可移植交付。
- **GitHub Actions 自动化流水线**：代码 Push 后自动完成构建、扫描、推送和配置更新。
- **Trivy 安全左移扫描**：在镜像推送前执行漏洞扫描，对 `CRITICAL` 和 `HIGH` 级别漏洞进行阻断。
- **双仓 GitOps 模式**：业务代码仓与 Kubernetes Manifests 配置仓分离，职责边界清晰。
- **ArgoCD Pull-based Delivery**：通过 ArgoCD 拉取 GitOps 仓库状态并同步到集群，避免 CI 系统直接持有集群高权限凭证。

### V2.0: 微服务拆分与全链路可观测性 (Observability)

- **前后端解耦**：将单体 `app.py` 拆分为前端 `ui.py` 与后端 `api.py`。
- **FastAPI 后端算力层**：后端服务专注于 RAG 检索、向量查询和大模型调用。
- **Gradio 前端展示层**：前端服务专注于用户交互和问答展示。
- **独立横向扩缩容**：前后端可根据访问压力和算力压力分别扩容。
- **Nginx Ingress 七层路由**：通过 Ingress 统一接管外部访问入口，替代简单 NodePort 暴露方式。
- **Prometheus + Grafana 可观测体系**：通过业务指标埋点和 ServiceMonitor 实现接口 QPS、请求延迟、错误率等指标采集。
- **SRE 监控闭环**：通过 Grafana Dashboard 实现服务运行状态可视化，为后续容量规划和故障排查打基础。

### V3.0: 状态剥离与持久化大脑 (Stateful Persistence)

- **计算与存储分离**：将向量索引从本地文件系统剥离，迁移到 ChromaDB 向量数据库。
- **ChromaDB 向量数据库**：用于存储 RAG 知识库 Embedding 数据，支撑语义检索能力。
- **StatefulSet 部署有状态服务**：使用 Kubernetes StatefulSet 管理 ChromaDB，保证服务身份稳定。
- **PVC 持久化存储**：通过 PersistentVolumeClaim 挂载持久化存储，避免 Pod 重建导致知识库数据丢失。
- **知识库快速恢复**：服务重启后可直接加载已有向量数据，减少重复 Embedding 成本。

---

## 技术栈 (Tech Stack)

### AI 应用层

- Python 3.11
- LlamaIndex
- FastAPI
- Gradio
- DashScope API

### 容器化与编排

- Docker
- Docker Compose
- Kubernetes
- Kustomize
- Nginx Ingress Controller

### 有状态存储

- ChromaDB
- StatefulSet
- PersistentVolumeClaim

### CI/CD 与 GitOps

- GitHub Actions
- 阿里云 ACR
- ArgoCD
- GitOps 双仓模式

### 可观测性与 SRE

- Prometheus
- Grafana
- kube-prometheus-stack
- ServiceMonitor
- prometheus-fastapi-instrumentator

### 基础设施即代码

- Terraform
- HCL

---

## 核心代码目录结构 (Repository Structure)

```text
├── .github/workflows/       # GitHub Actions CI 自动化流水线
├── data/                    # RAG 知识库初始文档
├── src/                     # RAG 核心逻辑实现
├── api.py                   # FastAPI 后端微服务算力层
├── ui.py                    # Gradio 前端展示层
├── Dockerfile               # 微服务统一镜像构建文件
├── requirements.txt         # Python 核心依赖
└── main.tf                  # Terraform IaC 基础设施代码
```

> 注：Kubernetes 集群的 GitOps 声明式配置，如 Deployment、Service、Ingress、StatefulSet、ServiceMonitor、Kustomization 等，维护在独立的 GitOps 配置仓库中。

---

## 项目亮点 (Project Highlights)

- 从本地 RAG 脚本演进为 Kubernetes 上的云原生 AI 应用。
- 使用 GitHub Actions、阿里云 ACR、ArgoCD 打通端到端自动化发布链路。
- 引入 Trivy 安全扫描，在 CI 阶段实现容器镜像安全左移。
- 使用双仓 GitOps 模式，实现业务代码与基础设施配置解耦。
- 通过 Nginx Ingress 实现七层流量入口治理。
- 通过 Prometheus + Grafana 构建基础 SRE 可观测能力。
- 通过 ChromaDB + StatefulSet + PVC 实现知识库向量数据持久化。
- 覆盖 AI 工程化、DevOps、SRE、Kubernetes、GitOps、IaC 等多个生产级技术域。

---

## 适用场景 (Use Cases)

本项目适用于以下场景：

- 企业内部知识库问答系统
- 云原生 AI 应用工程化实践
- Kubernetes 上的 RAG 服务部署
- AI 应用 CI/CD 与 GitOps 交付演示
- 云计算、DevOps、SRE、解决方案架构师岗位作品集项目

---

## 作者 (Author)

**朱玮烨 (AmazingYe)**

- 2027届 数据科学与大数据技术
- AWS Certified Solutions Architect - Professional
- 阿里云大模型 ACP 认证
- 寻求云计算 / 云原生 / DevOps / SRE / AI 工程化相关实习机会，欢迎联系交流！
