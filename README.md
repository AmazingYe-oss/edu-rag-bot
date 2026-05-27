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

本项目是一个面向大厂生产标准的云原生工程化高阶实践项目。
项目从一个本地运行的大语言模型 RAG（检索增强生成）脚本起步，经历了从单体到微服务、从无状态到有状态、从黑盒到全链路可观测的完整架构演进，最终构建出一个基于 Kubernetes 的企业级 AI 应用。

> 核心设计理念：跨越 AI 算法开发与生产交付的鸿沟，聚焦 AI 应用在高可用、可观测性、持久化存储、纯正 GitOps 自动化发布等云原生架构领域的顶级工程实践。

---

## 系统拓扑架构 (Architecture Topology)

本项目在 Kubernetes 中实现了彻底的计算与存储分离、前后端解耦及流量精细化管控：

~~~mermaid
graph TD
    Client([用户浏览器]) -->|rag.amazingye.local| Ingress[Nginx Ingress Controller 七层网关]
    Ingress --> UI[Frontend Pod / UI 微服务]
    UI -->|HTTP| API[Backend Pod / FastAPI 核心算力]
    
    API -.->|1. 读取持久化知识| ChromaDB[(ChromaDB Vector Database\nStatefulSet + PVC)]
    API -.->|2. 发起对话| LLM((Aliyun DashScope LLM))
    
    Prometheus[Prometheus ServiceMonitor] ==定时抓取==> API
    Grafana[Grafana SRE 大盘] -.-> Prometheus
~~~

---

## 核心工程化演进 (Key Engineering Highlights)

本项目经历了三次重大架构演进，实现了真正的微服务化：

### V1.0: 基础设施即代码 (IaC) 与 CI/CD 飞轮
* **Terraform 自动化编排**：抛弃手工点击控制台，使用 main.tf 声明式管理底层资源。
* **双仓 GitOps 模式**：业务代码仓与 K8s 配置仓（Manifests）彻底分离。
* **GitHub Actions + ArgoCD**：代码 Push 触发 CI 自动构建推送阿里云 ACR，随后 ArgoCD 自动捕获 Kustomize 变更，发起集群状态 Sync 滚动更新，实现拉模式（Pull-based）无缝交付。

### V2.0: 微服务拆分与全链路可观测性 (Observability)
* **前后端解耦 (Microservices)**：将单体 app.py 劈裂为纯粹的前端 UI (ui.py) 与高性能算力后端 (api.py / FastAPI)，支持独立横向扩缩容。
* **Nginx Ingress 七层路由**：摒弃简陋的 NodePort，配置本地企业级泛域名解析与流量接管。
* **上帝之眼 (Prometheus + Grafana)**：引入 kube-prometheus-stack，通过植入探针并编写 K8s ServiceMonitor 打通自定义业务指标暴露，构建实时监控大盘（QPS、延迟等）。

### V3.0: 状态剥离与持久化大脑 (Stateful Persistence)
* **计算与存储分离**：摒弃极其脆弱的本地文件系统向量索引，正式接入 ChromaDB 向量数据库。
* **StatefulSet + PVC**：在 K8s 中使用 StatefulSet 部署 ChromaDB，并动态挂载网络云盘（PersistentVolumeClaim），实现 Pod 意外销毁重启后数据零丢失，知识库秒级恢复，极大节省大模型 Embedding 开销。

---

## 技术栈 (Tech Stack)

* **AI 应用层**：Python 3.11, LlamaIndex, FastAPI, Gradio, DashScope API
* **存储与有状态服务**：ChromaDB (Vector DB)
* **容器化与编排**：Docker, Kubernetes (K8s)
* **可观测性 (SRE)**：Prometheus, Grafana, prometheus-fastapi-instrumentator
* **基础设施编排 (IaC)**：Terraform (HCL)
* **持续交付 (CI/CD)**：GitHub Actions, 阿里云 ACR, ArgoCD, Kustomize

---

## 核心代码目录结构 (Repository Structure)

~~~text
├── .github/workflows/       # GitHub Actions CI 自动化流水线
├── data/                    # RAG 知识库初始文档
├── src/                     # RAG 核心逻辑实现
├── api.py                   # (V2.0新增) FastAPI 后端微服务算力层
├── ui.py                    # (V2.0新增) Gradio 前端展示层
├── Dockerfile               # 微服务统一胖镜像构建文件，结合 K8s Command 动态启动
├── requirements.txt         # 核心依赖 (包含 chromadb, prometheus探针等)
└── main.tf                  # Terraform IaC 基础设施代码
~~~
*(注：Kubernetes 集群的 GitOps 声明式配置，如 StatefulSet, ServiceMonitor, Ingress, Kustomization 等维护在独立的配置仓库中。)*

---

## 作者 (Author)

**朱玮烨 (AmazingYe)**
* 2027届 数据科学与大数据技术
* AWS Certified Solutions Architect - Professional
* 阿里云大模型 ACP 认证
* **寻求 云计算 / 云原生 / DevOps / SRE / AI工程化 相关实习机会，欢迎联系交流！**
