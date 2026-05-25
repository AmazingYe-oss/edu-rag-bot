terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

# 命名空间
resource "kubernetes_namespace" "edu-rag-app" {
  metadata {
    name = "edu-rag-app"
  }
}

# Deployment 端口修复为 7860
resource "kubernetes_deployment" "edu-rag-deployment" {
  metadata {
    name      = "edu-rag-deploy"
    namespace = kubernetes_namespace.edu-rag-app.metadata[0].name
    labels = {
      app = "edu-rag"
    }
  }

  spec {
    replicas = 2
    selector {
      match_labels = {
        app = "edu-rag"
      }
    }

    template {
      metadata {
        labels = {
          app = "edu-rag"
        }
      }

      spec {
        container {
          image = "amazingye/edu-rag-bot:v4"
          name  = "edu-rag-bot"
          env{
            name="DASHSCOPE_API_KEY"
            value_from {
                secret_key_ref{
                    name = "dashscope-secret"
                    key  = "DASHSCOPE_API_KEY"
                }
            }
          }

          port {
            container_port = 7860
          }
          liveness_probe {
            http_get {
              path = "/"
              port = 7860
            }
            initial_delay_seconds = 60
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 6
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "edu-rag-service" {
  metadata {
    name      = "edu-rag-svc"
    namespace = kubernetes_namespace.edu-rag-app.metadata[0].name
  }

  spec {
    selector = {
      app = kubernetes_deployment.edu-rag-deployment.metadata[0].labels.app
    }

    port {
      port        = 80       
      target_port = 7860    
      node_port   = 30081
    }

    type = "NodePort"
  }
}