# Infraestructura como Código (IaC)

## Proyecto: HeavyCult Dropshipping — Terraform Configuration

### Archivo: variables.tf

variable "project_name" {
  description = "Nombre del proyecto"
  type        = string
  default     = "heavycult-dropshipping"
}

variable "environment" {
  description = "Entorno de despliegue"
  type        = string
  default     = "production"
}

variable "region_primary" {
  description = "Región primaria AWS"
  type        = string
  default     = "us-east-1"
}

variable "region_secondary" {
  description = "Región secundaria AWS (DR)"
  type        = string
  default     = "us-west-2"
}

variable "mongodb_atlas_project_id" {
  description = "ID del proyecto en MongoDB Atlas"
  type        = string
  default     = ""
}

variable "mongodb_atlas_org_id" {
  description = "ID de la organización en MongoDB Atlas"
  type        = string
  default     = ""
}

variable "mongodb_cluster_tier" {
  description = "Tier del cluster MongoDB Atlas"
  type        = string
  default     = "M10"
}

variable "mongodb_cluster_dr_tier" {
  description = "Tier del cluster DR"
  type        = string
  default     = "M5"
}

variable "db_name" {
  description = "Nombre de la base de datos MongoDB"
  type        = string
  default     = "bd_erp"
}

variable "data_lake_bucket_name" {
  description = "Nombre del bucket S3 para el Data Lake"
  type        = string
  default     = "heavycult-data-lake"
}

variable "enable_cross_region_replication" {
  description = "Habilitar replicación cross-region en S3"
  type        = bool
  default     = true
}

variable "admin_username" {
  description = "Usuario administrador de MongoDB Atlas"
  type        = string
  sensitive   = true
  default     = ""
}

variable "admin_password" {
  description = "Contraseña administrador de MongoDB Atlas"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cidr_block" {
  description = "CIDR block para la VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "tags" {
  description = "Tags comunes para todos los recursos"
  type        = map(string)
  default = {
    Project     = "heavycult-dropshipping"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
