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

```mermaid
graph TD
    Client([用户浏览器]) -->|rag.amazingye.local| Ingress[Nginx Ingress Controller 七层网关]
    Ingress --> UI[Frontend Pod / UI 微服务]
    UI -->|HTTP| API[Backend Pod / FastAPI 核心算力]
    
    API -.->|1. 读取持久化知识| ChromaDB[(ChromaDB Vector Database\nStatefulSet + PVC)]
    API -.->|2. 发起对话| LLM((Aliyun DashScope LLM))
    
    Prometheus[Prometheus ServiceMonitor] ==定时抓取==> API
    Grafana[Grafana SRE 大盘] -.-> Prometheus
